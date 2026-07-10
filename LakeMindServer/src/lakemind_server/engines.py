from __future__ import annotations
from typing import Any
from .config import ServerConfig
from .plugins.registry import build_engine


class Engines:
    def __init__(self, cfg: ServerConfig):
        e = cfg.engines
        meta_cfg = e.metadata
        meta_config = dict(meta_cfg.config)
        if cfg.master_key:
            meta_config["master_key"] = cfg.master_key
        self.object_storage = build_engine("storage.object", e.object_storage.plugin, e.object_storage.config)
        self.tabular = build_engine("storage.tabular", e.tabular.plugin, e.tabular.config)
        self.vector = build_engine("storage.vector", e.vector.plugin, e.vector.config)
        self.kv = build_engine("storage.kv", e.kv.plugin, e.kv.config)
        self.graph = build_engine("storage.graph", e.graph.plugin, e.graph.config)
        self.metadata = build_engine("storage.metadata", meta_cfg.plugin, meta_config)
        self.sql = build_engine("compute.sql", e.sql.plugin, e.sql.config)
        self.distributed = build_engine("compute.distributed", e.distributed.plugin, e.distributed.config)
        self.embedding = build_engine("cognitive.embedding", e.embedding.plugin, e.embedding.config) if e.embedding else None
        memory_config = dict(e.memory.config)
        memory_config["model_serving_url"] = e.model_serving_url
        self.memory = build_engine("cognitive.memory", e.memory.plugin, memory_config)
        self.llm = build_engine("cognitive.llm", e.llm.plugin, e.llm.config) if e.llm else None
        if self.llm and hasattr(self.memory, "set_llm"):
            self.memory.set_llm(self.llm)

    def all_health(self) -> dict[str, bool]:
        return {
            "object_storage": self.object_storage.health(),
            "tabular": self.tabular.health(),
            "vector": self.vector.health(),
            "kv": self.kv.health(),
            "graph": self.graph.health(),
            "metadata": self.metadata.health(),
            "sql": self.sql.health(),
            "distributed": self.distributed.health(),
            "embedding": self.embedding.health() if self.embedding else False,
            "memory": self.memory.health(),
            "llm": self.llm.health() if self.llm else False,
        }
