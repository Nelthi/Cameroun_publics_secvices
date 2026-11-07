"""Chaîne complète : T1 -> T2 -> T3, avec audit TOUJOURS écrit."""
import json
import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from datetime import datetime

from pydantic import ValidationError

from . import audit, stages
from .config import CLARIFICATION_MESSAGE, ERROR_MESSAGE, REFUSAL_MESSAGE, get_timeout
from .schemas import AgentOut, RoutingOut, ValidationOut

log = logging.getLogger("t4.pipeline")
_EXECUTOR = ThreadPoolExecutor(max_workers=4)


class StageError(Exception):
    """Une étape (T1, T2 ou T3) a échoué ou a renvoyé un JSON non conforme."""


def new_request_id() -> str:
    return f"REQ-{datetime.now():%Y%m%d}-{uuid.uuid4().hex[:6].upper()}"


def _dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)


def _run_stage(record, column, label, fn, model, *args):
    """Appelle une étape avec délai maximum, garde sa sortie brute pour l'audit,
    puis la valide contre le contrat."""
    timeout = get_timeout()
    try:
        raw = _EXECUTOR.submit(fn, *args).result(timeout=timeout)
    except FutureTimeout:
        raise StageError(f"{label} : délai dépassé ({timeout} s)")
    except Exception as exc:
        raise StageError(f"{label} : {type(exc).__name__}: {exc}") from exc
    record[column] = _dumps(raw)  # sortie brute conservée même si invalide
    try:
        return model.model_validate(raw)
    except ValidationError as exc:
        details = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())
        raise StageError(f"{label} : sortie non conforme au contrat ({details})") from exc


def _unique_sources(citations):
    seen, sources = set(), []
    for c in citations:
        key = (c.document_id, c.source_page)
        if key not in seen:
            seen.add(key)
            sources.append({"document_id": c.document_id, "source_page": c.source_page})
    return sources


def run(question: str) -> dict:
    """Traite une question de bout en bout et renvoie la réponse de l'API."""
    started = time.perf_counter()
    request_id, timestamp = new_request_id(), datetime.now().isoformat(timespec="seconds")
    record = {"request_id": request_id, "timestamp": timestamp,
              "question": audit.mask_sensitive(question),
              "routing_json": None, "agent_outputs_json": None, "validation_json": None,
              "status": "error", "final_answer": None, "duration_ms": None, "error": None}
    gaps, answer, sources = [], ERROR_MESSAGE, []

    try:
        payload = {"request_id": request_id, "question": question,
                   "language": "fr", "timestamp": timestamp}
        routing = _run_stage(record, "routing_json", "T1 (routage)",
                             stages.route_question, RoutingOut, payload)
        if routing.needs_clarification:
            record["status"], answer = "needs_clarification", CLARIFICATION_MESSAGE
        else:
            draft = _run_stage(record, "agent_outputs_json", "T2 (agents)",
                               stages.run_agents, AgentOut, routing.model_dump(), question)
            valid = _run_stage(record, "validation_json", "T3 (guardrails)",
                               stages.validate_answer, ValidationOut, draft.model_dump(), question)
            record["status"] = valid.status
            answer = valid.final_answer or (REFUSAL_MESSAGE if valid.status == "refused" else "")
            sources = [] if valid.status == "refused" else _unique_sources(valid.citations)
            gaps = [g.model_dump() for g in valid.gaps]
    except StageError as exc:
        record["status"], record["error"] = "error", str(exc)
        log.error("%s : %s", request_id, exc)
    except Exception as exc:  # filet de sécurité : le serveur ne doit jamais planter
        record["status"], record["error"] = "error", f"{type(exc).__name__}: {exc}"
        log.exception("%s : erreur inattendue", request_id)
    finally:
        record["final_answer"] = answer
        record["duration_ms"] = int((time.perf_counter() - started) * 1000)
        try:
            audit.write_audit(record, gaps)
        except Exception:
            log.exception("%s : ÉCHEC d'écriture de l'audit", request_id)

    return {"request_id": request_id, "status": record["status"], "answer": answer,
            "sources": sources, "timestamp": timestamp}
