from __future__ import annotations
import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from steward_service import StewardService

app = FastAPI(title="LakeMind Steward", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_steward = StewardService()


@app.get("/health")
async def health():
    return {"status": "ok", "service": "steward"}


@app.get("/inspection")
async def get_inspection():
    return await _steward.inspect()


@app.get("/inspection/last")
async def get_last_inspection():
    return _steward.get_last_inspection() or {"message": "no_inspection_yet"}


@app.post("/suggest")
async def suggest_action(request: Request):
    body = await request.json()
    return await _steward.suggest_action(body)


@app.post("/chat")
async def chat(request: Request):
    body = await request.json()
    message = body.get("message", "")

    inspection = _steward.get_last_inspection()
    if not inspection:
        inspection = await _steward.inspect()

    summary = inspection.get("summary", {})
    response_text = (
        f"Steward 巡检完成：发现 {summary.get('total', 0)} 个问题"
        f"（{summary.get('critical', 0)} 严重，{summary.get('warning', 0)} 警告）。"
    )

    if "巡检" in message or "inspect" in message.lower():
        return {"response": response_text, "inspection": inspection}

    return {"response": response_text}
