"""
Repository pour l'accès aux données de la table `invoices`.
Toute interaction avec la DB passe par cette couche.
"""

import logging
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.invoice import Invoice
from app.schemas import InvoiceCreate

logger = logging.getLogger(__name__)


class InvoiceRepository:
    """
    Couche d'accès aux données pour les factures.
    Encapsule toutes les requêtes SQL liées aux factures.
    """

    def __init__(self, db: Session):
        self.db = db

    def find_by_invoice_id(self, invoice_id: str) -> Optional[Invoice]:
        """
        Recherche une facture par son identifiant métier.

        Args:
            invoice_id: L'identifiant de la facture à rechercher.

        Returns:
            L'instance Invoice si trouvée, None sinon.
        """
        return self.db.query(Invoice).filter(Invoice.invoice_id == invoice_id).first()

    def find_by_hash(self, pdf_hash: str) -> Optional[Invoice]:
        """
        Recherche une facture par le hash SHA-256 de son PDF.

        Args:
            pdf_hash: Le hash SHA-256 du PDF.

        Returns:
            L'instance Invoice si trouvée, None sinon.
        """
        return self.db.query(Invoice).filter(Invoice.pdf_hash == pdf_hash).first()

    def create(self, data: InvoiceCreate) -> tuple[Invoice, bool]:
        """
        Insère une nouvelle facture en base de données.

        Utilise la contrainte UNIQUE de la base pour détecter les doublons
        de manière atomique (evite les race conditions).

        Args:
            data: Les données validées de la facture à créer.

        Returns:
            Un tuple (invoice, is_new) où is_new indique si c'est une nouvelle
            entrée (True) ou un doublon existant (False).

        Raises:
            Exception: En cas d'erreur inattendue de la base de données.
        """
        invoice = Invoice(
            invoice_id=data.invoice_id,
            amount=data.amount,
            invoice_date=data.invoice_date,
            pdf_hash=data.pdf_hash,
            status="valid",
            sender_phone=data.sender_phone,
        )

        try:
            self.db.add(invoice)
            self.db.commit()
            self.db.refresh(invoice)
            logger.info(f"✅ Facture '{data.invoice_id}' enregistrée (id={invoice.id}).")
            return invoice, True

        except IntegrityError as e:
            self.db.rollback()
            logger.warning(
                f"⚠️  Violation de contrainte UNIQUE pour invoice_id='{data.invoice_id}' "
                f"ou hash='{data.pdf_hash}'. Détail : {e.orig}"
            )
            # Récupérer l'entrée existante pour la retourner
            existing = self.find_by_invoice_id(data.invoice_id) or self.find_by_hash(data.pdf_hash)
            return existing, False

        except Exception as e:
            self.db.rollback()
            logger.error(f"❌ Erreur inattendue lors de l'insertion : {e}", exc_info=True)
            raise

    def get_all(self, limit: int = 100, offset: int = 0) -> list[Invoice]:
        """
        Retourne la liste paginée de toutes les factures.

        Args:
            limit:  Nombre maximum de résultats.
            offset: Nombre de résultats à sauter.

        Returns:
            Liste d'instances Invoice.
        """
        return (
            self.db.query(Invoice)
            .order_by(Invoice.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
