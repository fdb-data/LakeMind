"""Config."""
from __future__ import annotations
import os, re
from pathlib import Path
from typing import Any
import yaml
from pydantic import BaseModel, Field

class ServerCfg(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8500

class McpEndpoint(BaseModel):
    url: str
    token: str

class McpCfg(BaseModel):
    asset: McpEndpoint
    data: McpEndpoint
    admin: McpEndpoint

class LlmCfg(BaseModel):
    provider: str = "simple"
    base_url: str = ""
    api_key: str = ""
    model: str = ""

class Config(BaseModel):
    server: ServerCfg = Field(default_factory=ServerCfg)
    mcp: McpCfg
    llm: LlmCfg = Field(default_factory=LlmCfg)

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
