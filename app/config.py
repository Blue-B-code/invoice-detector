"""
Configuration centralisée de l'application via variables d'environnement.
"""

import os
from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Paramètres de l'application chargés depuis les variables d'environnement."""

    # ── Application ────────────────────────────────────────────────────────
    APP_ENV: str = "development"
    LOG_TO_FILE: bool = False

    # ── Base de données ────────────────────────────────────────────────────
    DATABASE_URL: str = "sqlite:///./invoices.db"

    # ── WhatsApp Business API ──────────────────────────────────────────────
    WHATSAPP_API_URL: str = "https://graph.facebook.com/v18.0"
    WHATSAPP_PHONE_NUMBER_ID: str = ""
    WHATSAPP_ACCESS_TOKEN: str = ""
    WHATSAPP_VERIFY_TOKEN: str = "invoice_detector_verify_token"

    # ── Traitement PDF ─────────────────────────────────────────────────────
    MAX_PDF_SIZE_MB: int = 10
    DOWNLOAD_TIMEOUT_SECONDS: int = 30

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Retourne l'instance unique des paramètres (singleton via cache)."""
    return Settings()


settings = get_settings()