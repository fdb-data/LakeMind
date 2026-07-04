"""引擎适配层。

封装各引擎客户端，按资产类型适配。上层（assets/tools/resources）只与
Asset 抽象交互，不出现 ``LanceDB`` / ``Redis`` / ``PyIceberg`` 等具体实现名。
"""
from __future__ import annotations

from dataclasses import dataclass

from ..config import Config
from .dragonfly import DragonflyClient
from .duckdb import query_arrow
from .embedding import EmbeddingProvider, build_embedding
from .graph import GraphClient
from .iceberg import IcebergClient
from .lancedb import LanceDBClient
from .s3 import S3Client

__all__ = ["Engines", "build_engines"]


@dataclass
class Engines:
    s3: S3Client
    iceberg: IcebergClient
    dragonfly: DragonflyClient
    lance: LanceDBClient
    lancedb: LanceDBClient
    duckdb: object
    embedding: EmbeddingProvider
    graph: GraphClient


def build_engines(config: Config) -> Engines:
    s3 = S3Client(config.engines.s3)
    s3.ensure_bucket("lakemind-iceberg")
    s3.ensure_bucket("lakemind-filesets")
    return Engines(
        s3=s3,
        iceberg=IcebergClient(config.engines.iceberg, config.engines.s3),
        dragonfly=DragonflyClient(config.engines.dragonfly),
        lance=LanceDBClient(config.engines.lance),
        lancedb=LanceDBClient(config.engines.lance),
        duckdb=query_arrow,
        embedding=build_embedding(config.embedding),
        graph=GraphClient(config.engines.postgres),
    )
