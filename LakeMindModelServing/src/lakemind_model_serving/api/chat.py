from __future__ import annotations

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from ..auth import check_auth

router = APIRouter()


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = "auto"
    messages: list[ChatMessage]
    temperature: float = 0.7
    max_tokens: int = 0
    stream: bool = False


@router.post("/v1/chat/completions")
async def chat_completions(body: ChatCompletionRequest, request: Request):
    check_auth(request)
    gateway = request.app.state.gateway
    messages = [{"role": m.role, "content": m.content} for m in body.messages]
    try:
        result = gateway.chat(
            messages=messages,
            model=body.model,
            temperature=body.temperature,
            max_tokens=body.max_tokens,
            stream=body.stream,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
