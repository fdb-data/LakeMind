"""Request context."""
from __future__ import annotations
import contextvars
from dataclasses import dataclass
from .config import TokenIdentity

@dataclass(frozen=True)
class Identity:
    agent_id: str
    tenant_id: str
    scopes: tuple[str, ...]
    @classmethod
    def from_token(cls, t: TokenIdentity) -> "Identity":
        return cls(t.agent_id, t.tenant_id, tuple(t.scopes))
    def has_scope(self, scope: str) -> bool:
        return scope in self.scopes

current_identity: contextvars.ContextVar[Identity] = contextvars.ContextVar("current_identity")

def get_identity() -> Identity:
    return current_identity.get()
