"""
Tests unitaires pour le système de détection de doublons de factures.

Couvre :
  - Utilitaires PDF (hash, parsing)
  - Repository (création, détection de doublons)
  - Service (workflow complet avec mocks)
  - Routes webhook (vérification, réception)
"""

import io
from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models.invoice import Invoice
from app.repositories.invoice_repository import InvoiceRepository
from app.schemas import InvoiceCreate, InvoiceData
from app.utils.pdf_utils import compute_sha256, parse_invoice_data


# ─── Configuration de la DB de test (SQLite en mémoire) ──────────────────────

TEST_DATABASE_URL = "sqlite:///./test_invoices.db"

engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def setup_db():
    """Crée et détruit les tables pour chaque test."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db_session():
    """Fournit une session DB de test."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_session):
    """Client de test FastAPI avec injection de la DB de test."""
    # Crée les tables dans la session de test avant chaque requête
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


# ─── Tests : utilitaires PDF ──────────────────────────────────────────────────

class TestPdfUtils:

    def test_compute_sha256_retourne_64_chars(self):
        content = b"Contenu de test"
        result = compute_sha256(content)
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_compute_sha256_deterministe(self):
        content = b"Meme contenu"
        assert compute_sha256(content) == compute_sha256(content)

    def test_compute_sha256_differents_contenus(self):
        assert compute_sha256(b"A") != compute_sha256(b"B")

    def test_parse_invoice_data_texte_vide(self):
        result = parse_invoice_data("")
        assert result is None

    def test_parse_invoice_data_texte_complet(self):
        text = """
        FACTURE N° : INV-2024-001
        Date : 15/01/2024
        Total : 1 250,00 EUR
        """
        result = parse_invoice_data(text)
        assert result is not None
        assert result.invoice_id == "INV-2024-001"
        assert result.amount == 1250.00
        assert result.invoice_date == date(2024, 1, 15)

    def test_parse_invoice_data_manque_montant(self):
        text = "Facture N° : FAC-001\nDate : 01/01/2024\n"
        result = parse_invoice_data(text)
        assert result is None

    def test_parse_invoice_data_manque_date(self):
        text = "Facture N° : FAC-001\nMontant : 500\n"
        result = parse_invoice_data(text)
        assert result is None


# ─── Tests : Repository ───────────────────────────────────────────────────────

class TestInvoiceRepository:

    def _make_invoice_data(self, suffix="001") -> InvoiceCreate:
        return InvoiceCreate(
            invoice_id=f"INV-{suffix}",
            amount=1000.00,
            invoice_date=date(2024, 1, 15),
            pdf_hash="a" * 64,
            sender_phone="33612345678",
        )

    def test_create_nouvelle_facture(self, db_session):
        repo = InvoiceRepository(db_session)
        data = self._make_invoice_data()
        invoice, is_new = repo.create(data)
        assert is_new is True
        assert invoice.invoice_id == "INV-001"
        assert invoice.status == "valid"

    def test_create_doublon_invoice_id(self, db_session):
        repo = InvoiceRepository(db_session)
        data = self._make_invoice_data()
        repo.create(data)

        # Même invoice_id, hash différent
        data2 = InvoiceCreate(
            invoice_id="INV-001",
            amount=500.00,
            invoice_date=date(2024, 2, 1),
            pdf_hash="b" * 64,
        )
        _, is_new = repo.create(data2)
        assert is_new is False

    def test_create_doublon_hash(self, db_session):
        repo = InvoiceRepository(db_session)
        data = self._make_invoice_data()
        repo.create(data)

        # Même hash, invoice_id différent
        data2 = InvoiceCreate(
            invoice_id="INV-002",
            amount=500.00,
            invoice_date=date(2024, 2, 1),
            pdf_hash="a" * 64,  # même hash
        )
        _, is_new = repo.create(data2)
        assert is_new is False

    def test_find_by_invoice_id(self, db_session):
        repo = InvoiceRepository(db_session)
        repo.create(self._make_invoice_data())
        found = repo.find_by_invoice_id("INV-001")
        assert found is not None
        assert found.invoice_id == "INV-001"

    def test_find_by_invoice_id_inexistant(self, db_session):
        repo = InvoiceRepository(db_session)
        assert repo.find_by_invoice_id("INEXISTANT") is None

    def test_get_all(self, db_session):
        repo = InvoiceRepository(db_session)
        for i in range(3):
            repo.create(InvoiceCreate(
                invoice_id=f"INV-{i:03d}",
                amount=100.0,
                invoice_date=date(2024, 1, 1),
                pdf_hash=str(i) * 64,
            ))
        all_invoices = repo.get_all()
        assert len(all_invoices) == 3


# ─── Tests : Routes Webhook ───────────────────────────────────────────────────

class TestWebhookRoutes:

    def test_verify_webhook_valide(self, client):
        response = client.get(
            "/webhook",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "invoice_detector_verify_token",
                "hub.challenge": "12345",
            },
        )
        assert response.status_code == 200
        assert response.text == "12345"

    def test_verify_webhook_token_invalide(self, client):
        response = client.get(
            "/webhook",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "mauvais_token",
                "hub.challenge": "12345",
            },
        )
        assert response.status_code == 403

    def test_receive_webhook_non_document(self, client):
        """Un message texte ordinaire doit être ignoré silencieusement."""
        payload = {
            "entry": [{
                "changes": [{
                    "value": {
                        "messages": [{
                            "from": "33612345678",
                            "type": "text",
                            "text": {"body": "Bonjour"}
                        }]
                    }
                }]
            }]
        }
        response = client.post("/webhook", json=payload)
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    @patch("app.routes.webhook.InvoiceService")
    def test_receive_webhook_document_pdf(self, mock_service_class, client):
        """Un message document PDF doit déclencher le service."""
        mock_service = MagicMock()
        mock_service.process_invoice.return_value = MagicMock(status="valid")
        mock_service_class.return_value = mock_service

        payload = {
            "entry": [{
                "changes": [{
                    "value": {
                        "messages": [{
                            "from": "33612345678",
                            "type": "document",
                            "document": {
                                "id": "media_123",
                                "filename": "facture.pdf",
                                "mime_type": "application/pdf",
                            }
                        }]
                    }
                }]
            }]
        }
        response = client.post("/webhook", json=payload)
        assert response.status_code == 200
        mock_service.process_invoice.assert_called_once_with(
            media_id="media_123",
            sender_phone="33612345678",
        )


# ─── Tests : Health Check ─────────────────────────────────────────────────────

class TestHealthRoutes:

    def test_health_check(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_list_invoices_vide(self, client):
        response = client.get("/invoices")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        assert len(response.json()) == 0
