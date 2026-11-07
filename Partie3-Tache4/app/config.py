"""Réglages de T4. Les valeurs variables se lisent dans l'environnement."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
MAX_QUESTION_CHARS = 500

ERROR_MESSAGE = "Service momentanément indisponible. Veuillez réessayer plus tard."
REFUSAL_MESSAGE = "Je n'ai pas trouvé cette information dans les documents officiels disponibles."
CLARIFICATION_MESSAGE = "Pouvez-vous préciser votre question ?"


def get_db_path() -> Path:
    """Chemin de la base d'audit (variable AUDIT_DB, sinon data/audit.db)."""
    return Path(os.getenv("AUDIT_DB", BASE_DIR / "data" / "audit.db"))


def get_timeout() -> float:
    """Délai maximum (secondes) accordé à CHAQUE étape T1/T2/T3."""
    return float(os.getenv("STAGE_TIMEOUT", "60"))
