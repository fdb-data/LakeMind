"""FastAPI BFF：/api/* 只读端点 + 静态资源 + /metrics。"""
from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from prometheus_client import generate_latest

from .config import Config, load_config
from .chat import chat
from .metrics import LATENCY, MCP_READS, REQUESTS
from .mcp_client import McpReadClient

_log = logging.getLogger("lakemind.monitor")
__all__ = ["create_app"]


def create_app(config: Config | None = None) -> FastAPI:
    config = config or load_config()
    mcp = McpReadClient(config)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            await mcp.connect()
            _log.info("connected to MCP %s", config.mcp.url)
        except Exception as e:
            _log.warning("MCP connect failed on startup (will retry on demand): %s", e)
        yield
        await mcp.close()

    app = FastAPI(title="LakeMindMonitor BFF", lifespan=lifespan)

    async def _ensure_mcp():
        if not mcp.connected:
            await mcp.connect()

    async def _read(uri: str):
        await _ensure_mcp()
        MCP_READS.labels(resource=uri).inc()
        return await mcp.read_resource(uri)

    def _wrap(ep: str):
        def deco(fn):
            import functools

            @functools.wraps(fn)
            async def wrapper(*a, **kw):
                t0 = time.time()
                try:
                    data = await fn(*a, **kw)
                    REQUESTS.labels(endpoint=ep, status="ok").inc()
                    return data
                except Exception as e:
                    REQUESTS.labels(endpoint=ep, status="error").inc()
                    raise HTTPException(status_code=503, detail=str(e))
                finally:
                    LATENCY.labels(endpoint=ep).observe(time.time() - t0)
            return wrapper
        return deco

    @app.get("/api/health")
    @_wrap("health")
    async def api_health():
        return {"monitor": "ok", "mcp_connected": mcp.connected}

    @app.get("/api/system-health")
    @_wrap("system-health")
    async def api_system_health():
        return await _read("lake://system/health")

    @app.get("/api/capabilities")
    @_wrap("capabilities")
    async def api_capabilities():
        return await _read("lake://capabilities")

    @app.get("/api/workspace")
    @_wrap("workspace")
    async def api_workspace():
        return await _read("lake://workspace")

    @app.get("/api/data")
    @_wrap("data")
    async def api_data():
        return await _read("lake://data")

    @app.get("/api/data/{name}")
    @_wrap("data-detail")
    async def api_data_detail(name: str):
        return await _read(f"lake://data/{name}")

    @app.get("/api/knowledge")
    @_wrap("knowledge")
    async def api_knowledge():
        return await _read("lake://knowledge")

    @app.get("/api/skills")
    @_wrap("skills")
    async def api_skills():
        return await _read("lake://skills")

    @app.get("/api/memory")
    @_wrap("memory")
    async def api_memory():
        return await _read("lake://memory")

    @app.get("/api/experience")
    @_wrap("experience")
    async def api_experience():
        return await _read("lake://experience")

    @app.post("/api/chat")
    @_wrap("chat")
    async def api_chat(message: str):
        return await chat(message, config, mcp)

    @app.get("/metrics")
    async def metrics():
        return PlainTextResponse(generate_latest(), media_type="text/plain")

    static_dir = Path(__file__).resolve().parent.parent / "static"
    if static_dir.exists():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

    return app
