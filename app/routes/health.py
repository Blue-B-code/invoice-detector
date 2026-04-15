"""
Routes utilitaires : health check et consultation des factures.
"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.repositories.invoice_repository import InvoiceRepository
from app.schemas import InvoiceResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health", summary="Health check")
async def health_check():
    """Vérifie que l'API est opérationnelle."""
    return {"status": "healthy", "service": "invoice-duplicate-detector"}


@router.get("/invoices", response_model=list[InvoiceResponse], summary="Liste des factures")
async def list_invoices(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """
    Retourne la liste paginée des factures enregistrées.

    Args:
        limit:  Nombre maximum de résultats (défaut 50).
        offset: Décalage pour la pagination.

    Returns:
        Liste de factures triées par date d'insertion décroissante.
    """
    repo = InvoiceRepository(db)
    invoices = repo.get_all(limit=limit, offset=offset)
    return invoices