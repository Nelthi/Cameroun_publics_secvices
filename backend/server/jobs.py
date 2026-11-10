"""Tâches longues (extraction, découpage, vectorisation) exécutées en arrière-plan, une à la fois."""
from __future__ import annotations

import threading
import traceback
import uuid
from datetime import datetime
from typing import Callable

_JOBS: dict = {}
_ORDER: list = []
_RUN_LOCK = threading.Lock()  # une seule tâche lourde à la fois (modèle d'embedding, quotas Groq)
_LOCK = threading.Lock()


class Job:
    def __init__(self, kind: str, params: dict):
        self.data = {"id": uuid.uuid4().hex[:10], "kind": kind, "params": params, "status": "queued",
                     "progress": 0.0, "log": [], "result": None, "error": None,
                     "created_at": datetime.now().isoformat(timespec="seconds"),
                     "finished_at": None}

    def log(self, message: str):
        self.data["log"].append(f"{datetime.now():%H:%M:%S}  {message}")

    def progress(self, value: float):
        self.data["progress"] = round(min(max(value, 0.0), 1.0), 3)


def start(kind: str, params: dict, fn: Callable[[Job], dict], *, wait: bool = False) -> dict:
    job = Job(kind, params)
    with _LOCK:
        _JOBS[job.data["id"]] = job
        _ORDER.append(job.data["id"])

    def runner():
        with _RUN_LOCK:
            job.data["status"] = "running"
            try:
                job.data["result"] = fn(job)
                job.data["status"] = "done" if not (job.data["result"] or {}).get("errors") else "error"
            except Exception as exc:  # noqa: BLE001
                job.data["status"] = "error"
                job.data["error"] = f"{type(exc).__name__}: {exc}"
                job.log("ERREUR : " + job.data["error"])
                job.data["trace"] = traceback.format_exc(limit=3)
            finally:
                job.progress(1.0)
                job.data["finished_at"] = datetime.now().isoformat(timespec="seconds")

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    if wait:
        thread.join()
    return job.data


def get(job_id: str):
    return _JOBS.get(job_id)


def recent(limit: int = 15):
    with _LOCK:
        ids = _ORDER[-limit:][::-1]
    return [_JOBS[i].data for i in ids]
