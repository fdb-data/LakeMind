from __future__ import annotations
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import JSONResponse
from .config import load_config, ServerConfig
from .engines import Engines
from .auth import verify_api_key, get_tenant_context
from .api import objects, tables, vectors, kv, graph, sql, jobs, embedding, memory, metadata, system, llm, secrets

cfg = load_config()
engines = Engines(cfg)

app = FastAPI(title="LakeMind Server", version="1.0.0")

app.state.cfg = cfg
app.state.engines = engines


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    if request.url.path in ("/docs", "/openapi.json", "/redoc") or request.url.path == "/api/v1/system/health":
        return await call_next(request)
    if not request.url.path.startswith("/api/v1/"):
        return await call_next(request)
    try:
        await verify_api_key(request, cfg)
    except HTTPException as exc:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    return await call_next(request)


app.include_router(objects.router, prefix="/api/v1/storage/objects", tags=["storage-objects"])
app.include_router(tables.router, prefix="/api/v1/storage/tables", tags=["storage-tables"])
app.include_router(vectors.router, prefix="/api/v1/storage/vectors", tags=["storage-vectors"])
app.include_router(kv.router, prefix="/api/v1/storage/kv", tags=["storage-kv"])
app.include_router(graph.router, prefix="/api/v1/storage/graph", tags=["storage-graph"])
app.include_router(sql.router, prefix="/api/v1/compute/sql", tags=["compute-sql"])
app.include_router(jobs.router, prefix="/api/v1/compute/jobs", tags=["compute-jobs"])
app.include_router(embedding.router, prefix="/api/v1/cognitive/embedding", tags=["cognitive-embedding"])
app.include_router(memory.router, prefix="/api/v1/cognitive/memory", tags=["cognitive-memory"])
app.include_router(llm.router, prefix="/api/v1/cognitive/llm", tags=["cognitive-llm"])
app.include_router(metadata.router, prefix="/api/v1/metadata", tags=["metadata"])
app.include_router(secrets.router, prefix="/api/v1/metadata/secrets", tags=["metadata-secrets"])
app.include_router(system.router, prefix="/api/v1/system", tags=["system"])
