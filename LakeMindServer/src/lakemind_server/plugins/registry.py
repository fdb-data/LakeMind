from __future__ import annotations
from typing import Any

from .storage.object.seaweedfs import SeaweedFSStorage
from .storage.tabular.iceberg import IcebergTabularStorage
from .storage.vector.lancedb import LanceVectorStorage
from .storage.kv.dragonfly import DragonflyKVStorage
from .storage.graph.postgres_graph import PostgresGraphStorage
from .storage.metadata.postgres import PostgresMetadataStore
from .compute.sql.duckdb import DuckDBSQLCompute
from .compute.distributed.embedded import EmbeddedCompute
from .cognitive.embedding.fastembed import FastEmbedPlugin
from .cognitive.memory.basic import BasicMemory

PLUGIN_REGISTRY: dict[str, dict[str, type]] = {
    "storage.object": {
        "seaweedfs": SeaweedFSStorage,
    },
    "storage.tabular": {
        "iceberg": IcebergTabularStorage,
    },
    "storage.vector": {
        "lancedb": LanceVectorStorage,
    },
    "storage.kv": {
        "dragonfly": DragonflyKVStorage,
    },
    "storage.graph": {
        "postgres_graph": PostgresGraphStorage,
    },
    "storage.metadata": {
        "postgres": PostgresMetadataStore,
    },
    "compute.sql": {
        "duckdb": DuckDBSQLCompute,
    },
    "compute.distributed": {
        "embedded": EmbeddedCompute,
    },
    "cognitive.embedding": {
        "fastembed": FastEmbedPlugin,
    },
    "cognitive.memory": {
        "basic": BasicMemory,
    },
}


def build_engine(category: str, plugin_name: str, config: dict) -> Any:
    cls = PLUGIN_REGISTRY[category][plugin_name]
    return cls(**config)
