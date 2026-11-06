"""Application FastAPI — Cameroun Public Service AI (Phase 2 / T1)."""

from __future__ import annotations

from pathlib import Path
from typing import Union

from fastapi import FastAPI

from .routes_documents import router as documents_router


def create_app(data_root: Union[str, Path] = "data") -> FastAPI:
    """Factory de l'API (utile pour les tests avec un data_root isolé)."""
    application = FastAPI(
        title="Cameroun Public Service AI",
        version="0.1.0",
        description=(
            "API de la Knowledge Base — projet ITU AI for Good 2026 (équipe HEMLE).\n\n"
            "## Phase 2 — T1 Ingestion and Storage\n\n"
            "Importe et enregistre des documents administratifs (PDF, DOCX, TXT) "
            "sans extraction de texte.\n\n"
            "Documentation interactive : `/docs` (Swagger UI) et `/redoc`."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        contact={"name": "Équipe HEMLE"},
    )
    application.state.data_root = Path(data_root)
    application.include_router(documents_router)

    @application.get(
        "/health",
        tags=["Système"],
        summary="Vérifier que l'API répond",
    )
    def health() -> dict[str, str]:
        return {"status": "ok", "module": "T1"}

    return application


app = create_app()
