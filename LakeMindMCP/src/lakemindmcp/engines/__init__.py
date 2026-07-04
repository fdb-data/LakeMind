"""引擎适配层。

封装各引擎客户端，按资产类型适配。上层（assets/tools/resources）只与
Asset 抽象交互，不出现 ``LanceDB`` / ``Redis`` / ``PyIceberg`` 等具体实现名。
"""
from __future__ import annotations

from dataclasses import dataclass

from ..config import Config
from .dragonfly import DragonflyClient
from .embedding import EmbeddingProvider, build_embedding
from .gravitino import GravitinoClient
from .iceberg import IcebergClient
from .lancedb import LanceDBClient
from .s3 import S3Client

__all__ = ["Engines", "build_engines"]


@dataclass
class Engines:
    s3: S3Client
    iceberg: IcebergClient
    gravitino: GravitinoClient
    lancedb: LanceDBClient
    dragonfly: DragonflyClient
    embedding: EmbeddingProvider


def build_engines(config: Config) -> Engines:
    s3 = S3Client(config.engines.s3)
    s3.ensure_bucket("lakemind-iceberg")
    s3.ensure_bucket("lakemind-filesets")
    return Engines(
        s3=s3,
        iceberg=IcebergClient(config.engines.iceberg, config.engines.s3),
        gravitino=GravitinoClient(config.engines.gravitino),
        lancedb=LanceDBClient(config.engines.lance),
        dragonfly=DragonflyClient(config.engines.dragonfly),
        embedding=build_embedding(config.embedding),
    )
