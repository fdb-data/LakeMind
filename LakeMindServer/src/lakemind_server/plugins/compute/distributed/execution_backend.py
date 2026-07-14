from __future__ import annotations
from typing import Protocol, runtime_checkable


@runtime_checkable
class ExecutionBackend(Protocol):
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
    ) -> str: ...

    def cancel(self, backend_job_id: str) -> None: ...

    def get_status(self, backend_job_id: str) -> str: ...

    def get_logs(self, backend_job_id: str) -> str: ...

    def get_result(self, backend_job_id: str) -> dict: ...
