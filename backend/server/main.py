"""Application FastAPI de démonstration : interfaces utilisateur et administrateur.

    python -m backend.server                  # LLM lu dans LLM_* (voir llm.env.example)
    python -m backend.server --demo-llm       # sans LLM : réponse extraite du passage le plus proche
"""
from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.pipeline.phase3 import IMPLS

for _name, _spec in IMPLS.items():  # branche les VRAIES tâches T1, T2, T3 derrière T4 (jamais les faux)
    os.environ.setdefault(_name, _spec)

from . import routes_admin, routes_chat, services  # noqa: E402

app = FastAPI(title="Cameroun Public Service AI — API de démonstration", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(routes_admin.router)
app.include_router(routes_chat.router)


@app.get("/api/health")
def health():
    from backend.ai import groq
    from backend.pipeline.serve import llm_mode

    return {"status": "ok", "admin_protected": bool(os.getenv("ADMIN_TOKEN")), "llm": llm_mode(),
            "groq_configured": groq.is_configured(), "tasks": {k: os.environ[k] for k in IMPLS}}
