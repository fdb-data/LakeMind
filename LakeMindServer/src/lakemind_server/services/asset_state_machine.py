from __future__ import annotations

VALID_TRANSITIONS = {
    "DRAFT": {"CREATING", "DELETING"},
    "CREATING": {"PROCESSING", "FAILED", "DELETING"},
    "PROCESSING": {"READY", "DEGRADED", "FAILED", "DELETING"},
    "READY": {"DEPRECATED", "DELETING"},
    "DEGRADED": {"PROCESSING", "DELETING"},
    "FAILED": {"DELETING"},
    "DEPRECATED": {"DELETING"},
    "DELETING": {"DELETED"},
    "DELETED": set(),
}


def can_transition(current: str, target: str) -> bool:
    return target in VALID_TRANSITIONS.get(current, set())


def transition(current: str, target: str) -> str:
    if not can_transition(current, target):
        raise ValueError(f"Invalid state transition: {current} -> {target}")
    return target


def check_ready(bindings: list[dict]) -> bool:
    required = [b for b in bindings if b.get("is_required", True)]
    return all(b["status"] == "READY" for b in required)


def check_degraded(bindings: list[dict]) -> bool:
    required = [b for b in bindings if b.get("is_required", True)]
    optional = [b for b in bindings if not b.get("is_required", True)]
    return all(b["status"] == "READY" for b in required) and any(b["status"] == "FAILED" for b in optional)
