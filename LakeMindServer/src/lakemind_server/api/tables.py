from __future__ import annotations
import asyncio
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
import pyarrow as pa

router = APIRouter()

_TYPE_MAP = {
    "string": pa.string(), "str": pa.string(),
    "int64": pa.int64(), "long": pa.int64(),
    "int32": pa.int32(), "int": pa.int32(),
    "float64": pa.float64(), "double": pa.float64(),
    "float32": pa.float32(), "float": pa.float32(),
    "bool": pa.bool_(), "boolean": pa.bool_(),
    "timestamp": pa.timestamp("us"),
    "binary": pa.binary(),
}


def _eng(request: Request):
    return request.app.state.engines.tabular


class CreateTableBody(BaseModel):
    namespace: str
    table: str
    schema: dict[str, str]
    location: str | None = None


class WriteBody(BaseModel):
    rows: list[dict]


@router.post("/")
async def create_table(body: CreateTableBody, request: Request):
    fields = [pa.field(name, _TYPE_MAP.get(t, pa.string())) for name, t in body.schema.items()]
    schema = pa.schema(fields)
    loc = await asyncio.to_thread(_eng(request).create_table, body.namespace, body.table, schema, body.location)
    return {"status": "ok", "namespace": body.namespace, "table": body.table, "location": loc}


@router.get("/{namespace}")
async def list_tables(namespace: str, request: Request):
    tables = await asyncio.to_thread(_eng(request).list_tables, namespace)
    return {"namespace": namespace, "tables": tables}


@router.get("/{namespace}/{table}")
async def describe_table(namespace: str, table: str, request: Request):
    return await asyncio.to_thread(_eng(request).describe, namespace, table)


@router.delete("/{namespace}/{table}")
async def drop_table(namespace: str, table: str, request: Request):
    await asyncio.to_thread(_eng(request).drop_table, namespace, table)
    return {"status": "ok"}


@router.post("/{namespace}/{table}/append")
async def append_data(namespace: str, table: str, body: WriteBody, request: Request):
    data = pa.Table.from_pylist(body.rows)
    n = await asyncio.to_thread(_eng(request).append, namespace, table, data)
    return {"status": "ok", "rows_written": n}


@router.post("/{namespace}/{table}/overwrite")
async def overwrite_data(namespace: str, table: str, body: WriteBody, request: Request):
    data = pa.Table.from_pylist(body.rows)
    n = await asyncio.to_thread(_eng(request).overwrite, namespace, table, data)
    return {"status": "ok", "rows_written": n}


@router.get("/{namespace}/{table}/scan")
async def scan_table(namespace: str, table: str, request: Request,
                     columns: str | None = None, filter: str | None = None, limit: int | None = None):
    cols = columns.split(",") if columns else None
    result = await asyncio.to_thread(_eng(request).scan, namespace, table, cols, filter, limit)
    return {"rows": result.to_pylist(), "count": result.num_rows}
