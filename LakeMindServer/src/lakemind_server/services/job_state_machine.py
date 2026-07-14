from __future__ import annotations

VALID_TRANSITIONS: dict[str, set[str]] = {
    "SUBMITTED": {"QUEUED", "CANCELLED"},
    "QUEUED": {"RUNNING", "FAILED", "CANCELLED", "TIMED_OUT"},
    "RUNNING": {"SUCCEEDED", "FAILED", "TIMED_OUT", "CANCELLING", "LOST"},
    "CANCELLING": {"CANCELLED", "FAILED"},
    "SUCCEEDED": set(),
    "FAILED": set(),
    "TIMED_OUT": set(),
    "CANCELLED": set(),
    "LOST": set(),
}

TERMINAL_STATES = {"SUCCEEDED", "FAILED", "TIMED_OUT", "CANCELLED", "LOST"}


def can_transition(from_state: str, to_state: str) -> bool:
    return to_state in VALID_TRANSITIONS.get(from_state, set())


def transition(from_state: str, to_state: str) -> str:
    if not can_transition(from_state, to_state):
        raise ValueError(f"INVALID_TRANSITION: {from_state} -> {to_state}")
    return to_state


def is_terminal(state: str) -> bool:
    return state in TERMINAL_STATES
