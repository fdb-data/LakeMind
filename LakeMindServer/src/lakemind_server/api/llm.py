from __future__ import annotations
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

router = APIRouter()


def _eng(request: Request):
    eng = request.app.state.engines.llm
    if eng is None:
        raise HTTPException(status_code=503, detail="LLM engine not configured")
    return eng


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatBody(BaseModel):
    messages: list[ChatMessage]
    model: str = "auto"
    temperature: float = 0.7
    max_tokens: int = 0


class EmbedBody(BaseModel):
    texts: list[str]
    model: str = "auto"


@router.post("/chat")
async def chat(body: ChatBody, request: Request):
    eng = _eng(request)
    messages = [{"role": m.role, "content": m.content} for m in body.messages]
    try:
        result = eng.chat(messages, model=body.model,
                          temperature=body.temperature, max_tokens=body.max_tokens)
        return result
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/embed")
async def embed(body: EmbedBody, request: Request):
    eng = _eng(request)
    try:
        vectors = eng.embed(body.texts, model=body.model)
        dim = len(vectors[0]) if vectors else 0
        return {"vectors": vectors, "dim": dim, "count": len(vectors)}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/models")
async def list_models(request: Request):
    eng = _eng(request)
    return {"models": eng.list_models()}


@router.get("/health")
async def llm_health(request: Request):
    eng = _eng(request)
    return {"healthy": eng.health()}
