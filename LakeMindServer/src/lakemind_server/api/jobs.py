from __future__ import annotations
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

router = APIRouter()


def _eng(request: Request):
    return request.app.state.engines.distributed


class SubmitBody(BaseModel):
    func: str
    args: dict = {}


@router.post("/")
async def submit_job(body: SubmitBody, request: Request):
    job_id = _eng(request).submit(body.func, body.args)
    return {"job_id": job_id, "status": "submitted"}


@router.get("/{job_id}")
async def job_status(job_id: str, request: Request):
    return _eng(request).status(job_id)


@router.get("/{job_id}/result")
async def job_result(job_id: str, request: Request):
    return {"result": _eng(request).result(job_id)}
