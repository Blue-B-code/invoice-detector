"""
Routes pour le webhook WhatsApp Business.

Deux endpoints :
  GET  /webhook — Vérification initiale de l'abonnement (challenge/response)
  POST /webhook — Réception des messages entrants
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.services.invoice_service import InvoiceService

logger = logging.getLogger(__name__)
router = APIRouter()


# ─── GET /webhook — Vérification du webhook ──────────────────────────────────

@router.get("/webhook", summary="Vérification du webhook WhatsApp")
async def verify_webhook(
    hub_mode: str = Query(alias="hub.mode", default=""),
    hub_verify_token: str = Query(alias="hub.verify_token", default=""),
    hub_challenge: str = Query(alias="hub.challenge", default=""),
):
    """
    Endpoint de vérification utilisé par Meta lors de l'abonnement au webhook.

    WhatsApp envoie une requête GET avec :
      - hub.mode         = "subscribe"
      - hub.verify_token = token défini dans WHATSAPP_VERIFY_TOKEN
      - hub.challenge    = challenge à renvoyer

    Returns:
        Le challenge en texte brut si le token est valide.

    Raises:
        HTTPException 403 si le token est invalide.
    """
    if hub_mode == "subscribe" and hub_verify_token == settings.WHATSAPP_VERIFY_TOKEN:
        logger.info("✅ Webhook WhatsApp vérifié avec succès.")
        return int(hub_challenge)

    logger.warning(
        f"⚠️  Échec de la vérification du webhook — "
        f"mode='{hub_mode}' token='{hub_verify_token}'"
    )
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token invalide.")


# ─── POST /webhook — Réception des messages ──────────────────────────────────

@router.post("/webhook", summary="Réception des messages WhatsApp", status_code=status.HTTP_200_OK)
async def receive_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Reçoit et traite les événements WhatsApp Business.

    WhatsApp s'attend à recevoir une réponse 200 rapidement.
    Le traitement lourd (download, parsing, DB) se fait de manière synchrone
    mais peut être déporté en tâche de fond (Celery/ARQ) pour la production.

    Returns:
        {"status": "ok"} dans tous les cas pour éviter les renvois de webhooks.
    """
    try:
        payload: dict[str, Any] = await request.json()
    except Exception:
        logger.error("Payload webhook non parsable.")
        return {"status": "ok"}  # Toujours 200 pour WhatsApp

    logger.debug(f"Payload reçu : {payload}")

    # ── Extraction du message document depuis le payload ──────────────────
    media_message = _extract_document_message(payload)
    if media_message is None:
        # Pas un message document — ignorer silencieusement
        return {"status": "ok"}

    media_id = media_message["media_id"]
    sender_phone = media_message["from_phone"]
    mime_type = media_message.get("mime_type", "")

    # ── Vérification du type MIME ─────────────────────────────────────────
    if mime_type and "pdf" not in mime_type.lower():
        logger.info(f"Type de fichier non supporté : {mime_type}. Ignoré.")
        from app.utils.whatsapp_client import send_whatsapp_message
        send_whatsapp_message(
            sender_phone,
            "⚠️ Seuls les fichiers PDF sont acceptés. Veuillez renvoyer votre facture au format PDF.",
        )
        return {"status": "ok"}

    # ── Traitement de la facture ──────────────────────────────────────────
    service = InvoiceService(db)
    result = service.process_invoice(media_id=media_id, sender_phone=sender_phone)
    logger.info(f"Traitement terminé — statut : {result.status}")

    return {"status": "ok"}


# ─── Helpers privés ───────────────────────────────────────────────────────────

def _extract_document_message(payload: dict[str, Any]) -> dict | None:
    """
    Navigue dans la structure du payload WhatsApp pour extraire
    les informations du premier message de type 'document'.

    Structure attendue :
    {
      "entry": [{
        "changes": [{
          "value": {
            "messages": [{
              "from": "33612345678",
              "type": "document",
              "document": {
                "id": "...",
                "filename": "...",
                "mime_type": "application/pdf"
              }
            }]
          }
        }]
      }]
    }

    Args:
        payload: Le payload JSON brut du webhook.

    Returns:
        Un dict avec media_id, from_phone, mime_type, filename ou None.
    """
    try:
        entries = payload.get("entry", [])
        for entry in entries:
            for change in entry.get("changes", []):
                value = change.get("value", {})
                messages = value.get("messages", [])
                for msg in messages:
                    if msg.get("type") == "document":
                        doc = msg.get("document", {})
                        return {
                            "media_id": doc["id"],
                            "from_phone": msg["from"],
                            "mime_type": doc.get("mime_type", ""),
                            "filename": doc.get("filename", ""),
                        }
    except (KeyError, TypeError) as e:
        logger.warning(f"Erreur lors de l'extraction du message document : {e}")

    return None
