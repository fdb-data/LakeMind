from __future__ import annotations
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

router = APIRouter()


def _eng(request: Request):
    return request.app.state.engines.kv


class SetBody(BaseModel):
    value: str
    ttl: int | None = None


@router.put("/{key}")
async def set_kv(key: str, body: SetBody, request: Request, db: int = 0):
    _eng(request).set(db, key, body.value, body.ttl)
    return {"status": "ok", "key": key}


@router.get("/{key}")
async def get_kv(key: str, request: Request, db: int = 0):
    val = _eng(request).get(db, key)
    if val is None:
        raise HTTPException(status_code=404, detail="Key not found")
    return {"key": key, "value": val}


@router.delete("/{key}")
async def delete_kv(key: str, request: Request, db: int = 0):
    deleted = _eng(request).delete(db, key)
    return {"status": "ok" if deleted else "not_found", "key": key}


@router.get("/")
async def scan_kv(request: Request, pattern: str = "*", limit: int = 1000, db: int = 0):
    keys = _eng(request).scan(db, pattern, limit)
    return {"keys": keys, "count": len(keys)}
