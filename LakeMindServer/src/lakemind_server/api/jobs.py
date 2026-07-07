from __future__ import annotations
import os
import uuid
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

router = APIRouter()


def _eng(request: Request):
    return request.app.state.engines.distributed


def _meta(request: Request):
    return request.app.state.engines.metadata


def _obj(request: Request):
    return request.app.state.engines.object_storage


def _ctx(request: Request):
    return {
        "tenant_id": request.headers.get("X-Tenant-Id", "default"),
        "agent_id": request.headers.get("X-Agent-Id", "unknown"),
    }


class SubmitBody(BaseModel):
    func: str
    args: dict = {}


class SubmitSkillBody(BaseModel):
    skill_uri: str
    job_name: str
    params: dict = {}
    task_id: str = ""
    env_overrides: dict = {}
    resources: dict = {}


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


@router.post("/submit")
async def submit_skill_job(body: SubmitSkillBody, request: Request):
    ctx = _ctx(request)
    meta = _meta(request)
    dist = _eng(request)
    obj = _obj(request)

    bucket = "lakemind-filesets"
    parts = body.skill_uri.replace("s3://", "").split("/", 1)
    if len(parts) == 2:
        sk_bucket, sk_key = parts[0], parts[1]
    else:
        tenant_id = ctx["tenant_id"]
        name_ver = body.skill_uri.replace("lake://skills/", "")
        if "@" in name_ver:
            name, ver = name_ver.split("@", 1)
        else:
            name, ver = name_ver, ""
        sk_key = f"{tenant_id}/skills/{name}.zip"

    try:
        skill_zip = obj.get(sk_bucket or bucket, sk_key)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"skill package not found: {e}")

    if isinstance(skill_zip, str):
        skill_zip = skill_zip.encode()

    tenant_secrets = meta.get_secret_values(ctx["tenant_id"])
    env_vars: dict[str, str] = {}
    for k, v in os.environ.items():
        env_vars[k] = v
    env_vars.update(tenant_secrets)
    env_vars.update(body.env_overrides)

    job_id = f"job_{uuid.uuid4().hex[:8]}"

    from ..utils.ray_yaml import parse_ray_yaml
    ray_cfg = parse_ray_yaml(skill_zip, body.job_name)

    meta.create_ray_job(
        job_id=job_id,
        tenant_id=ctx["tenant_id"],
        agent_id=ctx["agent_id"],
        skill_uri=body.skill_uri,
        job_name=body.job_name,
        entrypoint=ray_cfg["entrypoint"],
        params=body.params,
        task_id=body.task_id,
    )

    for key_name in tenant_secrets:
        meta.log_secret_access(
            ctx["tenant_id"], key_name, ctx["agent_id"],
            body.task_id, job_id,
        )

    try:
        ray_job_id = dist.submit_skill_job(
            skill_zip=skill_zip,
            job_name=body.job_name,
            env_vars=env_vars,
            resources_override=body.resources,
            job_id=job_id,
        )
        meta.update_ray_job_status(job_id, "running", ray_job_id=ray_job_id)
    except Exception as e:
        meta.update_ray_job_status(job_id, "failed")
        raise HTTPException(status_code=500, detail=f"ray submit failed: {e}")

    return {"job_id": job_id, "status": "submitted", "ray_job_id": ray_job_id}


@router.post("/{job_id}/cancel")
async def cancel_job(job_id: str, request: Request):
    meta = _meta(request)
    dist = _eng(request)
    job = meta.get_ray_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"job '{job_id}' not found")
    ray_job_id = job.get("ray_job_id", "")
    if ray_job_id:
        result = dist.cancel_job(ray_job_id)
    else:
        result = {"job_id": job_id, "status": "cancelled"}
    meta.update_ray_job_status(job_id, "cancelled")
    return result


@router.get("")
async def list_jobs(request: Request, status: str = ""):
    ctx = _ctx(request)
    return _meta(request).list_ray_jobs(ctx["tenant_id"], status)
