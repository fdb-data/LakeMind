from __future__ import annotations
import hashlib
import ulid
from ..db import execute, execute_one
from ..security.context import SecurityContext
from .audit_service import AuditService
from .asset_service import AssetService


def _ulid(prefix: str) -> str:
    return f"{prefix}_{str(ulid.new())}"


class JobArtifactService:

    @staticmethod
    def create_artifact(
        job_id: str,
        attempt_id: str,
        artifact_type: str,
        uri: str,
        checksum: str | None = None,
        size_bytes: int | None = None,
        can_assetize: bool = False,
    ) -> dict:
        artifact_id = _ulid("art")
        execute(
            """
            INSERT INTO job_artifacts
                (artifact_id, job_id, attempt_id, artifact_type, uri, checksum, size_bytes, can_assetize)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (artifact_id, job_id, attempt_id, artifact_type, uri, checksum, size_bytes, can_assetize),
        )
        return execute_one("SELECT * FROM job_artifacts WHERE artifact_id = %s", (artifact_id,))

    @staticmethod
    def list_artifacts(job_id: str) -> list[dict]:
        return execute(
            "SELECT * FROM job_artifacts WHERE job_id = %s ORDER BY created_at DESC",
            (job_id,),
        )

    @staticmethod
    def assetize(ctx: SecurityContext, artifact_id: str, asset_type: str = "knowledge") -> dict:
        artifact = execute_one("SELECT * FROM job_artifacts WHERE artifact_id = %s", (artifact_id,))
        if not artifact:
            raise ValueError("ARTIFACT_NOT_FOUND")
        if not artifact["can_assetize"]:
            raise ValueError("ARTIFACT_NOT_ASSETIZABLE")

        asset = AssetService.create_asset(
            ctx,
            asset_type=asset_type,
            name=f"artifact_{artifact_id}",
            source_uri=artifact["uri"],
            metadata={"origin": "job_artifact", "job_id": artifact["job_id"]},
        )

        execute(
            "UPDATE job_artifacts SET asset_id = %s WHERE artifact_id = %s",
            (asset["asset_id"], artifact_id),
        )

        AssetService.record_lineage(
            asset["asset_id"],
            source_asset_id=None,
            relation="derived_from_job",
            details={"job_id": artifact["job_id"], "artifact_id": artifact_id},
        )

        AuditService.record(
            ctx, action="job.artifact_assetize",
            resource_type="job_artifact", resource_id=artifact_id,
            details={"asset_id": asset["asset_id"]},
        )
        return {"artifact_id": artifact_id, "asset_id": asset["asset_id"]}

    @staticmethod
    def compute_checksum(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()
