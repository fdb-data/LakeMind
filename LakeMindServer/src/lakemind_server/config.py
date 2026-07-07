from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
import yaml
import os


@dataclass
class EngineConfig:
    plugin: str
    config: dict[str, Any] = field(default_factory=dict)


@dataclass
class EnginesConfig:
    object_storage: EngineConfig = None
    tabular: EngineConfig = None
    vector: EngineConfig = None
    kv: EngineConfig = None
    graph: EngineConfig = None
    metadata: EngineConfig = None
    sql: EngineConfig = None
    distributed: EngineConfig = None
    embedding: EngineConfig = None
    memory: EngineConfig = None
    llm: EngineConfig = None


@dataclass
class ServerConfig:
    host: str = "0.0.0.0"
    port: int = 10823
    api_key: str = "lakemind-internal-api-key"
    master_key: str = ""
    engines: EnginesConfig = None


def _resolve_env(value: Any) -> Any:
    if isinstance(value, str):
        if value.startswith("${") and value.endswith("}"):
            env_key = value[2:-1]
            return os.environ.get(env_key, value)
        return value
    if isinstance(value, dict):
        return {k: _resolve_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_env(v) for v in value]
    return value


def _resolve_dict(d: dict) -> dict:
    return {k: _resolve_env(v) for k, v in d.items()}


def load_config(path: str | None = None) -> ServerConfig:
    if path is None:
        path = os.environ.get("LAKE_CONFIG", "config/engines.yaml")
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    server_cfg = raw.get("server", {})
    api_key = os.environ.get("API_KEY", server_cfg.get("api_key", "lakemind-internal-api-key"))
    master_key = os.environ.get("LAKEMIND_MASTER_KEY", server_cfg.get("master_key", ""))

    storage = raw.get("storage", {})
    compute = raw.get("compute", {})
    cognitive = raw.get("cognitive", {})

    def ec(d):
        if not d:
            return None
        return EngineConfig(plugin=d.get("plugin", ""), config=_resolve_dict(d.get("config", {})))

    engines = EnginesConfig(
        object_storage=ec(storage.get("object")),
        tabular=ec(storage.get("tabular")),
        vector=ec(storage.get("vector")),
        kv=ec(storage.get("kv")),
        graph=ec(storage.get("graph")),
        metadata=ec(storage.get("metadata")),
        sql=ec(compute.get("sql")),
        distributed=ec(compute.get("distributed")),
        embedding=ec(cognitive.get("embedding")),
        memory=ec(cognitive.get("memory")),
        llm=ec(cognitive.get("llm")),
    )

    return ServerConfig(
        host=server_cfg.get("host", "0.0.0.0"),
        port=int(server_cfg.get("port", 10823)),
        api_key=api_key,
        master_key=master_key,
        engines=engines,
    )
