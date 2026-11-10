from __future__ import annotations

import argparse
import os


def main(argv=None):
    ap = argparse.ArgumentParser(description="API de démonstration (utilisateur + administrateur)")
    ap.add_argument("--host", default="0.0.0.0", help="0.0.0.0 pour que le téléphone puisse joindre l'API")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--demo-llm", action="store_true", help="réponse extraite du passage (sans LLM)")
    args = ap.parse_args(argv)
    if args.demo_llm:
        os.environ["PHASE3_LLM"] = "demo"
    from backend.pipeline.serve import llm_mode

    print("LLM :", llm_mode())
    print("Groq (découpage IA, métadonnées) :", "configuré" if os.getenv("GROQ_API_KEY") else "GROQ_API_KEY absente")
    print("Protection admin :", "oui (X-Admin-Token)" if os.getenv("ADMIN_TOKEN") else "non (démo)", flush=True)
    import uvicorn

    uvicorn.run("backend.server.main:app", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
