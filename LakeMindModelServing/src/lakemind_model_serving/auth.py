from __future__ import annotations

from fastapi import Request, HTTPException


def check_auth(request: Request) -> None:
    api_key = getattr(request.app.state, "api_key", "lakemind-modelserving-key")
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = auth[len("Bearer "):]
    if token != api_key:
        raise HTTPException(status_code=403, detail="Invalid API key")
