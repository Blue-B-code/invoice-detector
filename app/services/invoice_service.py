"""
Service principal de traitement des factures.
Orchestre l'extraction PDF, la détection de doublons et la réponse WhatsApp.
"""

import logging

from sqlalchemy.orm import Session

from app.repositories.invoice_repository import InvoiceRepository
from app.schemas import InvoiceCreate, ProcessingResult
from app.utils.pdf_utils import compute_sha256, extract_text_from_pdf, parse_invoice_data
from app.utils.whatsapp_client import (
    download_media,
    get_media_url,
    send_whatsapp_message,
)

logger = logging.getLogger(__name__)


class InvoiceService:
    """
    Orchestre le traitement complet d'une facture reçue via WhatsApp.

    Workflow :
      1. Télécharger le PDF depuis WhatsApp
      2. Calculer le hash SHA-256
      3. Extraire les données (invoice_id, montant, date)
      4. Vérifier les doublons et persister
      5. Notifier l'expéditeur via WhatsApp
    """

    # Messages de réponse envoyés à l'utilisateur
    MSG_VALID = (
        "✅ *Facture valide*\n\n"
        "Votre facture *{invoice_id}* d'un montant de *{amount}* a été enregistrée avec succès.\n"
        "Date : {date}"
    )
    MSG_DUPLICATE = (
        "❌ *Facture déjà utilisée*\n\n"
        "La facture *{invoice_id}* a déjà été soumise et est enregistrée dans notre système.\n"
        "Si vous pensez qu'il s'agit d'une erreur, contactez notre support."
    )
    MSG_INVALID_PDF = (
        "⚠️ *Fichier invalide*\n\n"
        "Impossible de lire votre fichier PDF ou d'en extraire les données nécessaires.\n"
        "Assurez-vous que le PDF contient bien :\n"
        "• Un numéro de facture\n"
        "• Un montant\n"
        "• Une date"
    )
    MSG_ERROR = (
        "🚨 *Erreur système*\n\n"
        "Une erreur inattendue s'est produite lors du traitement de votre facture.\n"
        "Veuillez réessayer dans quelques instants."
    )

    def __init__(self, db: Session):
        self.repo = InvoiceRepository(db)

    def process_invoice(
        self,
        media_id: str,
        sender_phone: str,
    ) -> ProcessingResult:
        """
        Traite une facture PDF reçue via WhatsApp de bout en bout.

        Args:
            media_id:     Identifiant du média WhatsApp à télécharger.
            sender_phone: Numéro de téléphone de l'expéditeur.

        Returns:
            Un ProcessingResult décrivant le résultat du traitement.
        """
        logger.info(
            f"📨 Traitement d'une facture — media_id={media_id}, phone={sender_phone}"
        )

        # ── Étape 1 : Téléchargement du PDF ──────────────────────────────
        pdf_content = self._download_pdf(media_id)
        if pdf_content is None:
            self._notify(sender_phone, self.MSG_ERROR)
            return ProcessingResult(
                status="error",
                message="Échec du téléchargement du PDF depuis WhatsApp.",
            )

        # ── Étape 2 : Hash SHA-256 ────────────────────────────────────────
        pdf_hash = compute_sha256(pdf_content)
        logger.info(f"🔑 Hash SHA-256 : {pdf_hash}")

        # ── Étape 3 : Extraction du texte et parsing ──────────────────────
        text = extract_text_from_pdf(pdf_content)
        invoice_data = parse_invoice_data(text)

        if invoice_data is None:
            logger.warning("Données de facture introuvables dans le PDF.")
            self._notify(sender_phone, self.MSG_INVALID_PDF)
            return ProcessingResult(
                status="error",
                message="Impossible d'extraire les données de la facture depuis le PDF.",
            )

        # ── Étape 4 : Persistance et détection de doublon ─────────────────
        create_data = InvoiceCreate(
            invoice_id=invoice_data.invoice_id,
            amount=invoice_data.amount,
            invoice_date=invoice_data.invoice_date,
            pdf_hash=pdf_hash,
            sender_phone=sender_phone,
        )

        invoice, is_new = self.repo.create(create_data)

        # ── Étape 5 : Notification WhatsApp ───────────────────────────────
        if is_new:
            message = self.MSG_VALID.format(
                invoice_id=invoice.invoice_id,
                amount=f"{invoice.amount:,.2f}",
                date=invoice.invoice_date.strftime("%d/%m/%Y"),
            )
            result_status = "valid"
            result_message = f"Facture '{invoice.invoice_id}' enregistrée avec succès."
        else:
            message = self.MSG_DUPLICATE.format(invoice_id=invoice.invoice_id)
            result_status = "duplicate"
            result_message = f"Facture '{invoice.invoice_id}' détectée comme doublon."

        self._notify(sender_phone, message)
        logger.info(f"📊 Résultat : {result_status} — {result_message}")

        from app.schemas import InvoiceResponse
        return ProcessingResult(
            status=result_status,
            message=result_message,
            invoice=InvoiceResponse.model_validate(invoice),
        )

    # ─── Méthodes privées ─────────────────────────────────────────────────────

    def _download_pdf(self, media_id: str) -> bytes | None:
        """
        Récupère l'URL du média puis télécharge son contenu.

        Args:
            media_id: Identifiant du média WhatsApp.

        Returns:
            Le contenu binaire du PDF ou None en cas d'échec.
        """
        media_url = get_media_url(media_id)
        if not media_url:
            logger.error(f"URL introuvable pour media_id={media_id}.")
            return None

        try:
            return download_media(media_url)
        except ValueError as e:
            logger.error(f"Fichier rejeté : {e}")
            return None

    def _notify(self, phone: str, message: str) -> None:
        """
        Envoie un message WhatsApp à l'expéditeur.

        Args:
            phone:   Numéro destinataire.
            message: Texte du message.
        """
        success = send_whatsapp_message(phone, message)
        if not success:
            logger.error(f"Échec de l'envoi WhatsApp vers {phone}.")
