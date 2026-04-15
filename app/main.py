"""
Point d'entrée principal de l'application FastAPI.
"""

import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.routes import webhook, health


# ─── Configuration du logging ───────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/app.log") if settings.LOG_TO_FILE else logging.NullHandler(),
    ],
)

logger = logging.getLogger(__name__)


# ─── Lifespan (startup / shutdown) ──────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise les ressources au démarrage, les libère à l'arrêt."""
    logger.info("🚀 Démarrage de Invoice Detector API...")
    init_db()
    logger.info("✅ Base de données initialisée.")
    yield
    logger.info("🛑 Arrêt de Invoice Detector API.")


# ─── Application ────────────────────────────────────────────────────────────

app = FastAPI(
    title="Invoice Duplicate Detector",
    description="Détection de doublons de factures via WhatsApp Business API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, tags=["Health"])
app.include_router(webhook.router, tags=["WhatsApp Webhook"])
