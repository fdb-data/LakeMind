"""配置模型。"""
from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

__all__ = ["Config", "load_config"]


class ServerCfg(BaseModel):
    host: str = "0.0.0.0"
    port: int = 3000


class McpCfg(BaseModel):
    url: str
    read_token: str


class StewardCfg(BaseModel):
    url: str = ""
    token: str = ""


class RefreshCfg(BaseModel):
    health_interval_sec: int = 10


class Config(BaseModel):
    server: ServerCfg = Field(default_factory=ServerCfg)
    mcp: McpCfg
    steward: StewardCfg = Field(default_factory=StewardCfg)
    refresh: RefreshCfg = Field(default_factory=RefreshCfg)


def load_config(path: str | Path | None = None) -> Config:
    p = Path(path or os.environ.get("LAKE_CONFIG", "config/config.yaml"))
    raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    return Config.model_validate(raw)
