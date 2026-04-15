"""
Client pour l'API WhatsApp Business.
Gère le téléchargement des médias et l'envoi de messages.
"""

import logging
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# ─── Constantes ──────────────────────────────────────────────────────────────

MAX_SIZE_BYTES = settings.MAX_PDF_SIZE_MB * 1024 * 1024
TIMEOUT = settings.DOWNLOAD_TIMEOUT_SECONDS


# ─── Fonctions publiques ─────────────────────────────────────────────────────

def get_media_url(media_id: str) -> Optional[str]:
    """
    Récupère l'URL de téléchargement d'un média WhatsApp à partir de son ID.

    Args:
        media_id: L'identifiant du média renvoyé par le webhook.

    Returns:
        L'URL de téléchargement ou None en cas d'erreur.
    """
    url = f"{settings.WHATSAPP_API_URL}/{media_id}"
    headers = {"Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}"}

    try:
        response = httpx.get(url, headers=headers, timeout=TIMEOUT)
        response.raise_for_status()
        data = response.json()
        media_url = data.get("url")
        logger.info(f"URL média obtenue pour media_id={media_id}.")
        return media_url
    except httpx.HTTPStatusError as e:
        logger.error(f"❌ Erreur HTTP lors de la récupération de l'URL média : {e}")
        return None
    except Exception as e:
        logger.error(f"❌ Erreur inattendue (get_media_url) : {e}", exc_info=True)
        return None


def download_media(media_url: str) -> Optional[bytes]:
    """
    Télécharge le contenu binaire d'un média WhatsApp.

    Args:
        media_url: L'URL de téléchargement du média.

    Returns:
        Le contenu binaire du fichier ou None en cas d'erreur.

    Raises:
        ValueError: Si le fichier dépasse la taille maximale autorisée.
    """
    headers = {"Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}"}

    try:
        with httpx.stream("GET", media_url, headers=headers, timeout=TIMEOUT) as response:
            response.raise_for_status()

            content_length = int(response.headers.get("content-length", 0))
            if content_length > MAX_SIZE_BYTES:
                raise ValueError(
                    f"Fichier trop volumineux : {content_length / 1024 / 1024:.1f} MB "
                    f"(max {settings.MAX_PDF_SIZE_MB} MB)"
                )

            chunks = []
            total = 0
            for chunk in response.iter_bytes(chunk_size=8192):
                total += len(chunk)
                if total > MAX_SIZE_BYTES:
                    raise ValueError(
                        f"Fichier trop volumineux (>{settings.MAX_PDF_SIZE_MB} MB)"
                    )
                chunks.append(chunk)

        content = b"".join(chunks)
        logger.info(f"✅ Média téléchargé ({len(content) / 1024:.1f} KB).")
        return content

    except ValueError:
        raise
    except httpx.HTTPStatusError as e:
        logger.error(f"❌ Erreur HTTP lors du téléchargement du média : {e}")
        return None
    except Exception as e:
        logger.error(f"❌ Erreur inattendue (download_media) : {e}", exc_info=True)
        return None


def send_whatsapp_message(to_phone: str, message: str) -> bool:
    """
    Envoie un message texte via l'API WhatsApp Business.

    Args:
        to_phone: Le numéro de téléphone destinataire (format international, sans +).
        message:  Le texte du message à envoyer.

    Returns:
        True si l'envoi a réussi, False sinon.
    """
    if not settings.WHATSAPP_PHONE_NUMBER_ID or not settings.WHATSAPP_ACCESS_TOKEN:
        logger.warning(
            "⚠️  Variables WhatsApp non configurées — message simulé (mode développement).\n"
            f"   → Destinataire : {to_phone}\n"
            f"   → Message      : {message}"
        )
        return True  # Retourne True pour ne pas bloquer le flux en dev

    url = f"{settings.WHATSAPP_API_URL}/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "text",
        "text": {"body": message},
    }

    try:
        response = httpx.post(url, json=payload, headers=headers, timeout=TIMEOUT)
        response.raise_for_status()
        logger.info(f"✅ Message WhatsApp envoyé à {to_phone}.")
        return True
    except httpx.HTTPStatusError as e:
        logger.error(f"❌ Erreur HTTP lors de l'envoi WhatsApp : {e} — {e.response.text}")
        return False
    except Exception as e:
        logger.error(f"❌ Erreur inattendue (send_whatsapp_message) : {e}", exc_info=True)
        return False
