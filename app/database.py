"""
Configuration et initialisation de la base de données SQLAlchemy.
"""

import logging
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session, DeclarativeBase

from app.config import settings

logger = logging.getLogger(__name__)

# ─── Moteur SQLAlchemy ───────────────────────────────────────────────────────

connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    # SQLite nécessite check_same_thread=False pour les usages multi-threadés
    connect_args["check_same_thread"] = False

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=(settings.APP_ENV == "development"),
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ─── Base déclarative ────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    """Classe de base pour tous les modèles SQLAlchemy."""
    pass


# ─── Fonctions utilitaires ───────────────────────────────────────────────────

def init_db() -> None:
    """Crée toutes les tables si elles n'existent pas encore."""
    from app.models import invoice  # noqa: F401 — import requis pour la découverte
    Base.metadata.create_all(bind=engine)
    logger.info("Tables créées / vérifiées avec succès.")


def get_db() -> Generator[Session, None, None]:
    """
    Dépendance FastAPI qui fournit une session DB par requête.
    Garantit la fermeture de la session en fin de requête.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()