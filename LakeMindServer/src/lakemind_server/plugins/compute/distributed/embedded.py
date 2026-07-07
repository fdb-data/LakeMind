from __future__ import annotations
from typing import Any
import uuid


class EmbeddedCompute:
    def __init__(self, **kwargs):
        self._jobs: dict[str, dict] = {}

    def submit(self, func: str, args: dict) -> str:
        job_id = f"job_{uuid.uuid4().hex[:8]}"
        self._jobs[job_id] = {"func": func, "args": args, "status": "completed", "result": None}
        return job_id

    def status(self, job_id: str) -> dict:
        job = self._jobs.get(job_id)
        if not job:
            return {"job_id": job_id, "status": "not_found"}
        return {"job_id": job_id, "status": job["status"]}

    def result(self, job_id: str) -> Any:
        job = self._jobs.get(job_id)
        if not job:
            return None
        return job["result"]

    def health(self) -> bool:
        return True

    def submit_skill_job(self, skill_zip: bytes, job_name: str,
                         env_vars: dict[str, str], resources_override: dict,
                         job_id: str) -> str:
        raise NotImplementedError("submit_skill_job requires Ray compute engine")

    def cancel_job(self, job_id: str) -> dict:
        return {"job_id": job_id, "status": "cancelled"}
