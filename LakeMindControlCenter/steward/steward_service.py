from __future__ import annotations
import os
import time
import logging
import httpx
from typing import Any

logger = logging.getLogger(__name__)

_CONTROL_PLANE = os.environ.get("LAKEMIND_CONTROL_PLANE", "http://lakemind-server:10823")
_STEWARD_TOKEN = os.environ.get("LAKEMIND_STEWARD_TOKEN", "")
_MODEL_SERVING = os.environ.get("LAKEMIND_MODEL_SERVING", "http://lakemind-model-serving:10824")

_AUTO_ACTIONS = {
    "retry_embedding": "low",
    "rebuild_index": "low",
    "sync_ray_status": "low",
    "run_reconciler": "low",
    "cleanup_temp": "low",
    "execute_approved_reload": "low",
}

_HIGH_RISK_ACTIONS = {
    "delete_asset", "revoke_token", "modify_security_policy",
    "disable_model", "stop_service", "cancel_critical_job",
    "delete_skill", "data_migration", "rotate_platform_secret",
}


class StewardService:

    def __init__(self) -> None:
        self._last_inspection: dict | None = None

    async def inspect(self) -> dict:
        findings: list[dict] = []

        findings.extend(await self._check_service_health())
        findings.extend(await self._check_degraded_assets())
        findings.extend(await self._check_lost_jobs())
        findings.extend(await self._check_outbox_backlog())
        findings.extend(await self._check_binding_drift())
        findings.extend(await self._check_config_drift())

        report = {
            "timestamp": time.time(),
            "findings": findings,
            "summary": {
                "total": len(findings),
                "critical": len([f for f in findings if f["severity"] == "critical"]),
                "warning": len([f for f in findings if f["severity"] == "warning"]),
                "info": len([f for f in findings if f["severity"] == "info"]),
            },
        }
        self._last_inspection = report
        return report

    async def suggest_action(self, finding: dict) -> dict:
        action_type = finding.get("suggested_action")
        if not action_type:
            return {"action": "none", "reason": "no_suggested_action"}

        if action_type in _AUTO_ACTIONS:
            return await self._execute_auto_action(action_type, finding)
        elif action_type in _HIGH_RISK_ACTIONS:
            return await self._create_high_risk_operation(action_type, finding)
        else:
            return {"action": "manual", "reason": "unknown_action_type"}

    async def _execute_auto_action(self, action_type: str, finding: dict) -> dict:
        auto_level = await self._get_auto_level()
        if auto_level == "observe":
            return {"action": "observe", "reason": "auto_action_disabled", "finding": finding}

        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(
                    f"{_CONTROL_PLANE}/api/v1/operations",
                    json={
                        "action": action_type,
                        "risk_level": "low",
                        "details": finding,
                    },
                    headers={"Authorization": f"Bearer {_STEWARD_TOKEN}"},
                    timeout=10.0,
                )
                if resp.status_code == 200:
                    return {"action": "auto_executed", "operation": resp.json()}
                else:
                    return {"action": "failed", "error": resp.text}
            except Exception as e:
                return {"action": "failed", "error": str(e)}

    async def _create_high_risk_operation(self, action_type: str, finding: dict) -> dict:
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(
                    f"{_CONTROL_PLANE}/api/v1/operations",
                    json={
                        "action": action_type,
                        "risk_level": "high",
                        "details": finding,
                    },
                    headers={"Authorization": f"Bearer {_STEWARD_TOKEN}"},
                    timeout=10.0,
                )
                if resp.status_code == 200:
                    return {"action": "approval_required", "operation": resp.json()}
                else:
                    return {"action": "failed", "error": resp.text}
            except Exception as e:
                return {"action": "failed", "error": str(e)}

    async def _get_auto_level(self) -> str:
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(
                    f"{_CONTROL_PLANE}/api/v1/configuration/effective/steward.auto_action_level",
                    headers={"Authorization": f"Bearer {_STEWARD_TOKEN}"},
                    timeout=5.0,
                )
                if resp.status_code == 200:
                    return resp.json().get("value", "observe")
            except Exception:
                pass
        return "observe"

    async def _check_service_health(self) -> list[dict]:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{_CONTROL_PLANE}/api/v1/instances",
                    headers={"Authorization": f"Bearer {_STEWARD_TOKEN}"},
                    timeout=5.0,
                )
                if resp.status_code == 200:
                    instances = resp.json().get("items", [])
                    return [
                        {
                            "category": "service_health",
                            "severity": "critical",
                            "message": f"Instance {i['instance_id']} unhealthy",
                            "suggested_action": "stop_service" if i.get("health_status") == "down" else None,
                        }
                        for i in instances
                        if i.get("health_status") not in ("healthy",)
                    ]
        except Exception:
            pass
        return []

    async def _check_degraded_assets(self) -> list[dict]:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{_CONTROL_PLANE}/api/v1/assets",
                    params={"status": "DEGRADED"},
                    headers={"Authorization": f"Bearer {_STEWARD_TOKEN}"},
                    timeout=5.0,
                )
                if resp.status_code == 200:
                    items = resp.json().get("items", [])
                    return [
                        {
                            "category": "degraded_asset",
                            "severity": "warning",
                            "message": f"Asset {a['asset_id']} is DEGRADED",
                            "suggested_action": "rebuild_index",
                        }
                        for a in items
                    ]
        except Exception:
            pass
        return []

    async def _check_lost_jobs(self) -> list[dict]:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{_CONTROL_PLANE}/api/v1/jobs",
                    params={"status": "LOST"},
                    headers={"Authorization": f"Bearer {_STEWARD_TOKEN}"},
                    timeout=5.0,
                )
                if resp.status_code == 200:
                    items = resp.json().get("items", [])
                    return [
                        {
                            "category": "lost_job",
                            "severity": "warning",
                            "message": f"Job {j['job_id']} is LOST",
                            "suggested_action": "sync_ray_status",
                        }
                        for j in items
                    ]
        except Exception:
            pass
        return []

    async def _check_outbox_backlog(self) -> list[dict]:
        return []

    async def _check_binding_drift(self) -> list[dict]:
        return []

    async def _check_config_drift(self) -> list[dict]:
        return []

    def get_last_inspection(self) -> dict | None:
        return self._last_inspection
