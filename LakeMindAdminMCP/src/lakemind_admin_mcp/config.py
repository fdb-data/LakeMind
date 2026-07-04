"""Config for AdminMCP."""
from __future__ import annotations
import os, re
from pathlib import Path
from typing import Any
import yaml
from pydantic import BaseModel, Field

class ServerCfg(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8403
    mcp_path: str = "/mcp"
    stateless: bool = True

class PostgresCfg(BaseModel):
    host: str
    port: int = 5432
    db: str = "lakemind"
    user: str = "lakemind"
    password: str = "lakemind_pass"

class TokenIdentity(BaseModel):
    token: str
    agent_id: str
    tenant_id: str
    scopes: list[str] = Field(default_factory=list)

class AuditCfg(BaseModel):
    level: str = "info"
    redact_keys: list[str] = Field(default_factory=lambda: ["token", "password", "secret"])

class Config(BaseModel):
    server: ServerCfg = Field(default_factory=ServerCfg)
    postgres: PostgresCfg
    tokens: list[TokenIdentity]
    audit: AuditCfg = Field(default_factory=AuditCfg)

    def token_map(self) -> dict[str, TokenIdentity]:
        return {t.token: t for t in self.tokens}

_ENV_RE = re.compile(r"\$\{([A-Z0-9_]+)\}")

def _interpolate(value: Any) -> Any:
    if isinstance(value, str):
        return _ENV_RE.sub(lambda m: os.environ.get(m.group(1), ""), value)
    if isinstance(value, dict):
        return {k: _interpolate(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_interpolate(v) for v in value]
    return value

def load_config(path: str | Path | None = None) -> Config:
    p = Path(path or os.environ.get("LAKE_CONFIG", "config/config.yaml"))
    raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    return Config.model_validate(_interpolate(raw))
