from __future__ import annotations
import os
import time
import httpx
from fastapi import FastAPI, Request, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

app = FastAPI(title="LakeMind Control Center BFF", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_CONTROL_PLANE = os.environ.get("LAKEMIND_CONTROL_PLANE", "http://lakemind-server:10823")
_BFF_TOKEN = os.environ.get("LAKEMIND_BFF_TOKEN", "")

_sessions: dict[str, dict] = {}


class LoginRequest(BaseModel):
    username: str
    password: str


async def _cp_get(path: str, params: dict | None = None, tenant_id: str | None = None) -> dict:
    headers = {"Authorization": f"Bearer {_BFF_TOKEN}"}
    if tenant_id:
        headers["X-Tenant-Id"] = tenant_id
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{_CONTROL_PLANE}{path}",
            params=params,
            headers=headers,
            timeout=10.0,
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        return resp.json()


async def _cp_post(path: str, body: dict | None = None, tenant_id: str | None = None) -> dict:
    headers = {"Authorization": f"Bearer {_BFF_TOKEN}"}
    if tenant_id:
        headers["X-Tenant-Id"] = tenant_id
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{_CONTROL_PLANE}{path}",
            json=body,
            headers=headers,
            timeout=10.0,
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        return resp.json()


@app.post("/auth/login")
async def login(req: LoginRequest):
    import hashlib
    password_hash = hashlib.sha256(req.password.encode()).hexdigest()
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{_CONTROL_PLANE}/api/v1/security/auth/login",
            json={"username": req.username, "password_hash": password_hash},
            timeout=10.0,
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=401, detail="INVALID_CREDENTIALS")
        data = resp.json()

    session_id = f"sess_{int(time.time())}_{req.username}"
    _sessions[session_id] = {
        "username": req.username,
        "token": data.get("token", ""),
        "role": data.get("role", "tenant_admin"),
        "tenant_id": data.get("tenant_id"),
    }
    response = JSONResponse({"session_id": session_id, "role": _sessions[session_id]["role"]})
    response.set_cookie("session_id", session_id, httponly=True, max_age=3600, samesite="lax")
    return response


@app.post("/auth/logout")
async def logout(request: Request):
    session_id = request.cookies.get("session_id")
    if session_id and session_id in _sessions:
        del _sessions[session_id]
    response = JSONResponse({"ok": True})
    response.delete_cookie("session_id")
    return response


def _get_session(request: Request) -> dict:
    session_id = request.cookies.get("session_id")
    if not session_id or session_id not in _sessions:
        raise HTTPException(status_code=401, detail="NOT_AUTHENTICATED")
    return _sessions[session_id]


def _refresh_session_cookie(response: JSONResponse, request: Request) -> JSONResponse:
    session_id = request.cookies.get("session_id")
    if session_id:
        response.set_cookie("session_id", session_id, httponly=True, max_age=3600, samesite="lax")
    return response


@app.get("/overview")
async def overview(request: Request):
    session = _get_session(request)
    import asyncio
    results = await asyncio.gather(
        _cp_get("/api/v1/instances"),
        _cp_get("/api/v1/assets", {"page_size": "1"}),
        _cp_get("/api/v1/jobs", {"page_size": "1"}, tenant_id=session.get("tenant_id")),
        _cp_get("/api/v1/audit", {"page_size": "5"}),
        return_exceptions=True,
    )
    resp = JSONResponse({
        "instances": results[0] if not isinstance(results[0], Exception) else {"items": []},
        "assets_total": results[1].get("total", 0) if not isinstance(results[1], Exception) else 0,
        "jobs_total": results[2].get("total", 0) if not isinstance(results[2], Exception) else 0,
        "recent_audit": results[3].get("items", []) if not isinstance(results[3], Exception) else [],
    })
    return _refresh_session_cookie(resp, request)


@app.get("/assets")
async def list_assets(request: Request):
    _get_session(request)
    params = dict(request.query_params)
    return await _cp_get("/api/v1/assets", params)


@app.get("/assets/{asset_id}")
async def get_asset(asset_id: str, request: Request):
    _get_session(request)
    return await _cp_get(f"/api/v1/assets/{asset_id}")


@app.get("/assets/{asset_id}/bindings")
async def get_bindings(asset_id: str, request: Request):
    _get_session(request)
    return await _cp_get(f"/api/v1/assets/{asset_id}/bindings")


@app.get("/assets/{asset_id}/lineage")
async def get_lineage(asset_id: str, request: Request):
    _get_session(request)
    return await _cp_get(f"/api/v1/assets/{asset_id}/lineage")


@app.get("/jobs")
async def list_jobs(request: Request):
    session = _get_session(request)
    params = dict(request.query_params)
    return await _cp_get("/api/v1/jobs", params, tenant_id=session.get("tenant_id"))


@app.get("/jobs/{job_id}")
async def get_job(job_id: str, request: Request):
    session = _get_session(request)
    return await _cp_get(f"/api/v1/jobs/{job_id}", tenant_id=session.get("tenant_id"))


@app.post("/jobs/{job_id}/retry")
async def retry_job(job_id: str, request: Request):
    session = _get_session(request)
    return await _cp_post(f"/api/v1/jobs/{job_id}/retry", tenant_id=session.get("tenant_id"))


@app.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str, request: Request):
    session = _get_session(request)
    return await _cp_post(f"/api/v1/jobs/{job_id}/cancel", tenant_id=session.get("tenant_id"))


@app.get("/models")
async def list_models(request: Request):
    _get_session(request)
    return await _cp_get("/api/v1/models/definitions")


@app.post("/models/definitions")
async def create_model(request: Request):
    _get_session(request)
    body = await request.json()
    return await _cp_post("/api/v1/models/definitions", body)


@app.get("/models/deployments")
async def list_deployments(request: Request):
    _get_session(request)
    return await _cp_get("/api/v1/models/deployments")


@app.post("/models/deployments")
async def create_deployment(request: Request):
    _get_session(request)
    body = await request.json()
    return await _cp_post("/api/v1/models/deployments", body)


@app.post("/models/deployments/{deployment_id}/enable")
async def enable_deployment(deployment_id: str, request: Request):
    _get_session(request)
    return await _cp_post(f"/api/v1/models/deployments/{deployment_id}/enable")


@app.post("/models/deployments/{deployment_id}/disable")
async def disable_deployment(deployment_id: str, request: Request):
    _get_session(request)
    return await _cp_post(f"/api/v1/models/deployments/{deployment_id}/disable")


@app.get("/models/profiles")
async def list_profiles(request: Request):
    _get_session(request)
    return await _cp_get("/api/v1/models/profiles")


@app.post("/models/profiles")
async def create_profile(request: Request):
    _get_session(request)
    body = await request.json()
    return await _cp_post("/api/v1/models/profiles", body)


@app.post("/models/profiles/resolve")
async def resolve_profile(request: Request):
    _get_session(request)
    body = await request.json()
    return await _cp_post("/api/v1/models/profiles/resolve", body)


@app.get("/instances")
async def list_instances(request: Request):
    _get_session(request)
    return await _cp_get("/api/v1/instances")


@app.get("/configuration")
async def get_config(request: Request):
    _get_session(request)
    return await _cp_get("/api/v1/configuration")


@app.get("/security/principals")
async def list_principals(request: Request):
    _get_session(request)
    return await _cp_get("/api/v1/security/principals")


@app.get("/operations")
async def list_operations(request: Request):
    _get_session(request)
    params = dict(request.query_params)
    return await _cp_get("/api/v1/operations", params)


@app.post("/operations/{op_id}/approve")
async def approve_operation(op_id: str, request: Request):
    _get_session(request)
    return await _cp_post(f"/api/v1/operations/{op_id}/approve")


@app.get("/audit")
async def list_audit(request: Request):
    _get_session(request)
    params = dict(request.query_params)
    return await _cp_get("/api/v1/audit", params)


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            data = await ws.receive_text()
            await ws.send_json({"type": "pong", "data": data})
    except WebSocketDisconnect:
        pass


@app.get("/health")
async def health():
    return {"status": "ok", "service": "control-center-bff"}
