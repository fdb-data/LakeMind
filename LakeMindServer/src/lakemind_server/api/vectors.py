from __future__ import annotations
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
    _eng(request).create_table(db, body.name, data, body.mode)
    return {"status": "ok", "db": db, "name": body.name}


@router.get("/{db}")
async def list_vector_tables(db: str, request: Request):
    tables = _eng(request).list_tables(db)
    return {"db": db, "tables": tables}


@router.get("/{db}/{name}")
async def describe_vector_table(db: str, name: str, request: Request):
    return _eng(request).describe(db, name)


@router.get("/{db}/{name}/scan")
async def scan_vector_table(db: str, name: str, request: Request, limit: int = 100, offset: int = 0):
    rows = _eng(request).scan(db, name, limit, offset)
    return {"results": rows, "count": len(rows)}


@router.post("/{db}/{name}/add")
async def add_vectors(db: str, name: str, body: AddBody, request: Request):
    data = pa.Table.from_pylist(body.data)
    n = _eng(request).add(db, name, data)
    return {"status": "ok", "rows_added": n}


@router.post("/{db}/{name}/search")
async def search_vectors(db: str, name: str, body: SearchBody, request: Request):
    results = _eng(request).search(db, name, body.query_vec, body.top_k, body.filter)
    return {"results": results, "count": len(results)}
