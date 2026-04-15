"""
Modèle SQLAlchemy pour la table `invoices`.
"""

from datetime import datetime, date

from sqlalchemy import String, Numeric, Date, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Invoice(Base):
    """
    Représente une facture stockée dans la base de données.

    Attributs:
        id          : Clé primaire auto-incrémentée.
        invoice_id  : Identifiant métier de la facture (UNIQUE).
        amount      : Montant de la facture.
        invoice_date: Date de la facture.
        pdf_hash    : Hash SHA-256 du fichier PDF (UNIQUE).
        status      : Statut — 'valid' ou 'duplicate'.
        sender_phone: Numéro WhatsApp de l'expéditeur.
        created_at  : Horodatage d'insertion.
    """

    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    invoice_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False)
    pdf_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="valid")
    sender_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<Invoice id={self.id} invoice_id='{self.invoice_id}' "
            f"amount={self.amount} status='{self.status}'>"
        )
