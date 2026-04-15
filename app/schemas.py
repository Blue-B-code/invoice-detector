"""
Schémas Pydantic pour la validation des données et la sérialisation.
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


# ─── Schémas de facture ──────────────────────────────────────────────────────

class InvoiceData(BaseModel):
    """Données extraites d'un fichier PDF de facture."""

    invoice_id: str = Field(..., description="Identifiant unique de la facture")
    amount: float = Field(..., gt=0, description="Montant de la facture")
    invoice_date: date = Field(..., description="Date de la facture")


class InvoiceCreate(InvoiceData):
    """Données nécessaires pour créer une nouvelle entrée en base."""

    pdf_hash: str = Field(..., description="Hash SHA-256 du fichier PDF")
    sender_phone: str | None = Field(None, description="Numéro de téléphone de l'expéditeur")


class InvoiceResponse(BaseModel):
    """Réponse retournée par l'API après traitement d'une facture."""

    id: int
    invoice_id: str
    amount: float
    invoice_date: date
    pdf_hash: str
    status: Literal["valid", "duplicate"]
    sender_phone: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Schémas de résultat de traitement ──────────────────────────────────────

class ProcessingResult(BaseModel):
    """Résultat complet du traitement d'une facture."""

    status: Literal["valid", "duplicate", "error"]
    message: str
    invoice: InvoiceResponse | None = None


# ─── Schémas du webhook WhatsApp ─────────────────────────────────────────────

class WhatsAppMediaMessage(BaseModel):
    """Structure simplifiée d'un message WhatsApp contenant un document."""

    message_id: str
    from_phone: str
    media_id: str
    filename: str | None = None
    mime_type: str | None = None