"""Lance l'API de T4 branchée sur les VRAIES tâches T1, T2 et T3 (et non sur les faux de app/mocks.py).

    python -m backend.pipeline.serve                    # LLM lu dans LLM_* (voir llm.env.example)
    python -m backend.pipeline.serve --demo-llm         # sans LLM : réponse extraite du passage le plus proche
    python -m backend.pipeline.serve --host 0.0.0.0 --port 8000

Les variables T1_IMPL / T2_IMPL / T3_IMPL déjà définies dans le terminal sont respectées.
"""
from __future__ import annotations

import argparse
import os

from .phase3 import IMPLS


def llm_mode() -> str:
    if os.getenv("PHASE3_LLM", "").strip().lower() == "demo" and not os.getenv("LLM_PROVIDER"):
        return "DÉMO sans LLM (extraction du passage le plus proche, pas de génération)"
    if os.getenv("LLM_PROVIDER"):
        return f"{os.getenv('LLM_PROVIDER')} / {os.getenv('LLM_MODEL', '?')}"
    return "NON CONFIGURÉ : les agents ne pourront pas répondre (voir llm.env.example ou --demo-llm)"


def main(argv=None):
    ap = argparse.ArgumentParser(description="API Phase 3 branchée sur T1, T2 et T3")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--demo-llm", action="store_true", help="mode démonstration sans LLM")
    args = ap.parse_args(argv)
    if args.demo_llm:
        os.environ["PHASE3_LLM"] = "demo"
    for name, spec in IMPLS.items():
        os.environ.setdefault(name, spec)
    print("T1 :", os.environ["T1_IMPL"], "\nT2 :", os.environ["T2_IMPL"],
          "\nT3 :", os.environ["T3_IMPL"], "\nLLM :", llm_mode(), flush=True)
    import uvicorn

    uvicorn.run("app.main:app", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
