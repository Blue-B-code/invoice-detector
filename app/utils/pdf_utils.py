"""
Utilitaires pour le traitement des fichiers PDF :
  - calcul du hash SHA-256
  - extraction du texte
  - parsing des données de facture
"""

import hashlib
import logging
import re
from datetime import date
from typing import Optional

import pdfplumber

from app.schemas import InvoiceData

logger = logging.getLogger(__name__)


def compute_sha256(content: bytes) -> str:
    """
    Calcule le hash SHA-256 d'un contenu binaire.

    Args:
        content: Le contenu brut du fichier PDF.

    Returns:
        La représentation hexadécimale du hash SHA-256.
    """
    return hashlib.sha256(content).hexdigest()


def extract_text_from_pdf(content: bytes) -> str:
    """
    Extrait le texte brut de toutes les pages d'un PDF.

    Args:
        content: Le contenu binaire du PDF.

    Returns:
        Le texte extrait, ou une chaîne vide si l'extraction échoue.
    """
    try:
        import io
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            pages_text = []
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    pages_text.append(text)
            full_text = "\n".join(pages_text)
            logger.debug(f"Texte extrait ({len(full_text)} caractères).")
            return full_text
    except Exception as e:
        logger.error(f"❌ Échec de l'extraction du texte PDF : {e}", exc_info=True)
        return ""


def _parse_amount(text: str) -> Optional[float]:
    """
    Extrait le montant depuis le texte de la facture.

    Stratégies tentées dans l'ordre :
      1. Motif "Total : 1 234,56" ou "Total: 1234.56"
      2. Motif "Montant : ..." ou "Amount : ..."

    Args:
        text: Le texte brut extrait du PDF.

    Returns:
        Le montant en float ou None si non trouvé.
    """
    patterns = [
        r"(?:total|montant total|amount due|net à payer)\s*[:\-]?\s*([\d\s,.]+)",
        r"(?:montant|amount|total HT|total TTC)\s*[:\-]?\s*([\d\s,.]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            raw = match.group(1).strip()
            # Normalise les séparateurs (espaces, virgules, points)
            normalized = re.sub(r"\s", "", raw)
            normalized = normalized.replace(",", ".")
            # Supprime les points milliers si le dernier séparateur est une virgule
            if normalized.count(".") > 1:
                parts = normalized.rsplit(".", 1)
                normalized = parts[0].replace(".", "") + "." + parts[1]
            try:
                return float(normalized)
            except ValueError:
                continue
    return None


def _parse_date(text: str) -> Optional[date]:
    """
    Extrait la date depuis le texte de la facture.

    Formats supportés :
      - DD/MM/YYYY  ou  DD-MM-YYYY
      - YYYY-MM-DD
      - DD Month YYYY  (ex: 15 janvier 2024)

    Args:
        text: Le texte brut extrait du PDF.

    Returns:
        Un objet date ou None si non trouvé.
    """
    from datetime import datetime

    # Format numérique standard
    numeric_patterns = [
        (r"\b(\d{2})[\/\-](\d{2})[\/\-](\d{4})\b", "%d/%m/%Y"),
        (r"\b(\d{4})[\/\-](\d{2})[\/\-](\d{2})\b", "%Y/%m/%d"),
    ]
    for pattern, fmt in numeric_patterns:
        match = re.search(pattern, text)
        if match:
            raw = match.group(0).replace("-", "/")
            try:
                return datetime.strptime(raw, fmt).date()
            except ValueError:
                continue

    # Format littéral (fr / en)
    months_fr = {
        "janvier": "01", "février": "02", "mars": "03", "avril": "04",
        "mai": "05", "juin": "06", "juillet": "07", "août": "08",
        "septembre": "09", "octobre": "10", "novembre": "11", "décembre": "12",
    }
    months_en = {
        "january": "01", "february": "02", "march": "03", "april": "04",
        "may": "05", "june": "06", "july": "07", "august": "08",
        "september": "09", "october": "10", "november": "11", "december": "12",
    }
    all_months = {**months_fr, **months_en}
    month_pattern = "|".join(all_months.keys())
    match = re.search(
        rf"\b(\d{{1,2}})\s+({month_pattern})\s+(\d{{4}})\b", text, re.IGNORECASE
    )
    if match:
        day, month_name, year = match.groups()
        month = all_months[month_name.lower()]
        try:
            return datetime.strptime(f"{day}/{month}/{year}", "%d/%m/%Y").date()
        except ValueError:
            pass

    return None


def _parse_invoice_id(text: str) -> Optional[str]:
    """
    Extrait l'identifiant de facture depuis le texte.

    Motifs reconnus :
      - "Facture N° : INV-2024-001"
      - "Invoice #: 12345"
      - "N° facture : FAC-001"

    Args:
        text: Le texte brut extrait du PDF.

    Returns:
        L'identifiant en chaîne ou None si non trouvé.
    """
    patterns = [
        r"(?:facture\s*n[°o]?|invoice\s*(?:no|n°|#|number|num)?)\s*[:\-]?\s*([A-Z0-9\-_/]+)",
        r"(?:n[°o]\s*facture|ref(?:erence)?)\s*[:\-]?\s*([A-Z0-9\-_/]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def parse_invoice_data(text: str) -> Optional[InvoiceData]:
    """
    Parse le texte extrait d'un PDF pour en extraire les données de facture.

    Args:
        text: Le texte brut du PDF.

    Returns:
        Un objet InvoiceData si toutes les données sont trouvées, None sinon.
    """
    if not text.strip():
        logger.warning("Texte PDF vide — impossible d'extraire les données.")
        return None

    invoice_id = _parse_invoice_id(text)
    amount = _parse_amount(text)
    invoice_date = _parse_date(text)

    missing = []
    if not invoice_id:
        missing.append("invoice_id")
    if amount is None:
        missing.append("amount")
    if invoice_date is None:
        missing.append("invoice_date")

    if missing:
        logger.warning(f"Champs manquants dans le PDF : {missing}")
        return None

    logger.info(
        f"📄 Données extraites — id='{invoice_id}' montant={amount} date={invoice_date}"
    )
    return InvoiceData(invoice_id=invoice_id, amount=amount, invoice_date=invoice_date)
