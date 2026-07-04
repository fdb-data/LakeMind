from __future__ import annotations
from fastapi import APIRouter, Request, HTTPException, Response
from pydantic import BaseModel

router = APIRouter()


def _eng(request: Request):
    return request.app.state.engines.object_storage


@router.put("/{bucket}/{key:path}")
async def put_object(bucket: str, key: str, request: Request):
    body = await request.body()
    _eng(request).put(bucket, key, body)
    return {"status": "ok", "bucket": bucket, "key": key, "size": len(body)}


@router.get("/{bucket}/{key:path}")
async def get_object(bucket: str, key: str, request: Request):
    data = _eng(request).get(bucket, key)
    return Response(content=data, media_type="application/octet-stream")


@router.head("/{bucket}/{key:path}")
async def exists_object(bucket: str, key: str, request: Request):
    if _eng(request).exists(bucket, key):
        return Response(status_code=200)
    raise HTTPException(status_code=404, detail="Not found")


@router.delete("/{bucket}/{key:path}")
async def delete_object(bucket: str, key: str, request: Request):
    _eng(request).delete(bucket, key)
    return {"status": "ok"}


@router.get("/{bucket}")
async def list_objects(bucket: str, request: Request, prefix: str = "", limit: int = 1000):
    keys = _eng(request).list(bucket, prefix, limit)
    return {"bucket": bucket, "keys": keys, "count": len(keys)}
