from __future__ import annotations
from fastapi import APIRouter, Request, HTTPException
from ..security.middleware import get_security_context
from ..security.actions import Action
from ..services.job_service import JobService

router = APIRouter()
_job_service = JobService()


def _check_perm(ctx, action: str) -> None:
    if not ctx.has_scope(action):
        raise HTTPException(status_code=403, detail="PERMISSION_DENIED")


@router.post("")
async def submit_job(request: Request):
    ctx = get_security_context(request)
    _check_perm(ctx, Action.JOB_SUBMIT.value)
    body = await request.json()
    return _job_service.submit(ctx, **body)


@router.get("")
async def list_jobs(request: Request):
    ctx = get_security_context(request)
    params = request.query_params
    return _job_service.list_jobs(
        ctx,
        status=params.get("status"),
        page=int(params.get("page", "1")),
        page_size=int(params.get("page_size", "50")),
    )


@router.get("/{job_id}")
async def get_job(job_id: str, request: Request):
    ctx = get_security_context(request)
    return _job_service.get_job(ctx, job_id)


@router.post("/{job_id}/cancel")
async def cancel_job(job_id: str, request: Request):
    ctx = get_security_context(request)
    _check_perm(ctx, Action.JOB_CANCEL.value)
    return _job_service.cancel(ctx, job_id)


@router.post("/{job_id}/retry")
async def retry_job(job_id: str, request: Request):
    ctx = get_security_context(request)
    _check_perm(ctx, Action.JOB_SUBMIT.value)
    return _job_service.retry(ctx, job_id)


@router.get("/{job_id}/result")
async def get_result(job_id: str, request: Request):
    ctx = get_security_context(request)
    return _job_service.get_result(ctx, job_id)


@router.get("/{job_id}/attempts")
async def get_attempts(job_id: str, request: Request):
    ctx = get_security_context(request)
    return _job_service.get_attempts(ctx, job_id)
