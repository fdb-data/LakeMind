from __future__ import annotations
import os
from typing import Any

_RAY_AVAILABLE = False
try:
    from ray.job_submission import JobSubmissionClient
    _RAY_AVAILABLE = True
except ImportError:
    pass


_RAY_DASHBOARD = os.environ.get("LAKEMIND_RAY_DASHBOARD", "http://ray-head:8265")

_STATUS_MAP = {
    "PENDING": "QUEUED",
    "RUNNING": "RUNNING",
    "SUCCEEDED": "SUCCEEDED",
    "FAILED": "FAILED",
    "STOPPED": "CANCELLED",
}


class RayExecutionBackend:

    def __init__(self, dashboard_url: str | None = None) -> None:
        self._dashboard = dashboard_url or _RAY_DASHBOARD
        self._client = None
        if _RAY_AVAILABLE:
            try:
                self._client = JobSubmissionClient(self._dashboard)
            except Exception:
                self._client = None

    def submit(
        self,
        job_id: str,
        skill_package_uri: str,
        entry_point: str,
        inputs: dict,
        params: dict,
        resources: dict,
        secrets: dict,
        model_binding: dict | None,
    ) -> str:
        if self._client is None:
            raise RuntimeError("Ray not available")

        env = {f"LAKEMIND_SECRET_{k}": v for k, v in secrets.items()}
        env["LAKEMIND_JOB_ID"] = job_id
        if model_binding:
            env["LAKEMIND_MODEL_BINDING"] = str(model_binding)

        runtime_env = {
            "env_vars": env,
            "pip": ["pylance", "lancedb"],
        }

        ray_job_id = self._client.submit_job(
            entrypoint=f"python {entry_point}",
            runtime_env=runtime_env,
            metadata={"lakemind_job_id": job_id},
            resources={
                "CPU": resources.get("cpu", 1),
                "memory": resources.get("memory_gb", 1) * 1024 * 1024 * 1024,
            },
        )
        return ray_job_id

    def cancel(self, backend_job_id: str) -> None:
        if self._client is None:
            return
        self._client.stop_job(backend_job_id)

    def get_status(self, backend_job_id: str) -> str:
        if self._client is None:
            return "LOST"
        status = self._client.get_job_status(backend_job_id)
        return _STATUS_MAP.get(str(status), "RUNNING")

    def get_logs(self, backend_job_id: str) -> str:
        if self._client is None:
            return ""
        return self._client.get_job_logs(backend_job_id)

    def get_result(self, backend_job_id: str) -> dict:
        if self._client is None:
            return {}
        logs = self.get_logs(backend_job_id)
        return {"logs": logs, "ray_job_id": backend_job_id}
