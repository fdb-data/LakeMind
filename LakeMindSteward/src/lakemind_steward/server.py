"""Steward HTTP server."""
from __future__ import annotations
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from .config import Config, load_config
from .mcp_client import McpClient
from .agent import chat, inspect

config = load_config()
mcp = McpClient(config.mcp)

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await mcp.close()

app = FastAPI(title="LakeMindSteward", lifespan=lifespan)

class ChatRequest(BaseModel):
    message: str

@app.post("/chat")
async def chat_endpoint(req: ChatRequest):
    result = await chat(req.message, mcp)
    return JSONResponse(result)

@app.post("/inspect")
async def inspect_endpoint():
    result = await inspect(mcp)
    return JSONResponse(result)

@app.get("/health")
async def health():
    return {"status": "ok", "service": "lakemind-steward"}
