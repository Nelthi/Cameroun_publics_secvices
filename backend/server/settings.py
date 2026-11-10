from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]


def data_root() -> Path:
    return Path(os.getenv("DATA_ROOT", BASE_DIR / "data"))


def admin_token():
    return os.getenv("ADMIN_TOKEN") or None
