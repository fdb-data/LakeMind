"""审计日志：工具调用记录（脱敏 JSON）。"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog

from ..context import get_identity

__all__ = ["audit_log", "configure_logging"]

_log = structlog.get_logger("lakemind.audit")


def configure_logging(level: str = "info") -> None:
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            {"debug": 10, "info": 20, "warning": 30, "error": 40}.get(level, 20)
        ),
    )


def _redact(args: dict[str, Any], keys: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in args.items():
        out[k] = "***" if k.lower() in keys else v
    return out


def audit_log(tool: str, arguments: dict[str, Any], redact_keys: list[str]) -> None:
    try:
        ident = get_identity()
        agent_id, tenant_id = ident.agent_id, ident.tenant_id
    except LookupError:
        agent_id, tenant_id = "unknown", "unknown"
    _log.info(
        "tool_call",
        ts=datetime.now(timezone.utc).isoformat(),
        agent_id=agent_id,
        tenant_id=tenant_id,
        tool=tool,
        arguments=_redact(arguments, [k.lower() for k in redact_keys]),
    )
