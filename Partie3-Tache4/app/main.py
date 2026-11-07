"""API FastAPI de T4.   Lancement :  uvicorn app.main:app --reload"""
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from . import audit, pipeline
from .config import MAX_QUESTION_CHARS
from .schemas import AskOut

app = FastAPI(title="Cameroun Public Service AI - API", version="1.0")


class AskIn(BaseModel):
    question: str = Field(max_length=MAX_QUESTION_CHARS)

    @field_validator("question")
    @classmethod
    def not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("La question ne peut pas être vide")
        return value


@app.post("/ask", response_model=AskOut)
def ask(body: AskIn):
    result = pipeline.run(body.question)
    if result["status"] == "error":  # vrai problème technique : HTTP 503
        return JSONResponse(status_code=503, content=result)
    return result  # approved / partial / refused / needs_clarification : HTTP 200


@app.get("/audit/{request_id}")
def get_audit(request_id: str):
    row = audit.get_audit(request_id)
    if row is None:
        raise HTTPException(status_code=404, detail="request_id inconnu")
    return row


@app.get("/gaps")
def get_gaps():
    return audit.list_gaps()


@app.get("/health")
def health():
    return {"status": "ok"}
