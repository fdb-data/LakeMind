from __future__ import annotations
import asyncio
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
import pyarrow as pa

router = APIRouter()


def _eng(request: Request):
    return request.app.state.engines.vector


class CreateTableBody(BaseModel):
    name: str
    data: list[dict]
    mode: str = "overwrite"


class AddBody(BaseModel):
    data: list[dict]


class SearchBody(BaseModel):
    query_vec: list[float]
    top_k: int = 5
    filter: str | None = None


@router.post("/{db}")
async def create_vector_table(db: str, body: CreateTableBody, request: Request):
    data = pa.Table.from_pylist(body.data)
    await asyncio.to_thread(_eng(request).create_table, db, body.name, data, body.mode)
    return {"status": "ok", "db": db, "name": body.name}


@router.get("/{db}")
async def list_vector_tables(db: str, request: Request):
    tables = await asyncio.to_thread(_eng(request).list_tables, db)
    return {"db": db, "tables": tables}


@router.get("/{db}/{name}")
async def describe_vector_table(db: str, name: str, request: Request):
    return await asyncio.to_thread(_eng(request).describe, db, name)


@router.get("/{db}/{name}/scan")
async def scan_vector_table(db: str, name: str, request: Request, limit: int = 100, offset: int = 0):
    rows = await asyncio.to_thread(_eng(request).scan, db, name, limit, offset)
    return {"results": rows, "count": len(rows)}


@router.post("/{db}/{name}/add")
async def add_vectors(db: str, name: str, body: AddBody, request: Request):
    data = pa.Table.from_pylist(body.data)
    n = await asyncio.to_thread(_eng(request).add, db, name, data)
    return {"status": "ok", "rows_added": n}


@router.post("/{db}/{name}/search")
async def search_vectors(db: str, name: str, body: SearchBody, request: Request):
    results = await asyncio.to_thread(_eng(request).search, db, name, body.query_vec, body.top_k, body.filter)
    return {"results": results, "count": len(results)}


@router.post("/{db}/{name}/add_arrow")
async def add_vectors_arrow(db: str, name: str, request: Request):
    if request.headers.get("content-type", "").lower() != "application/x-arrow":
        raise HTTPException(415, "Unsupported media type, expected application/x-arrow")
    cl = int(request.headers.get("content-length", 0))
    if cl > 100 * 1024 * 1024:
        raise HTTPException(413, "Payload too large, split into batches < 100MB")
    body = await request.body()
    reader = pa.ipc.open_stream(body)
    data = reader.read_all()
    if data.num_rows > 20000:
        raise HTTPException(400, "Max 20000 vectors per request")
    vec_field = data.schema.field("vector")
    if hasattr(vec_field.type, 'list_size') and vec_field.type.list_size > 0:
        if vec_field.type.list_size != 768:
            raise HTTPException(400, f"Expected vector dim=768, got {vec_field.type.list_size}")
    n = await asyncio.to_thread(_eng(request).add, db, name, data)
    return {"status": "ok", "rows_added": n}
