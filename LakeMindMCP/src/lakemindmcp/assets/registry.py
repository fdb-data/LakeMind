"""资产类型注册表与能力图。P3 实现。"""
from __future__ import annotations

from dataclasses import dataclass, field

__all__ = ["AssetType", "Registry", "registry"]


@dataclass
class AssetType:
    type: str
    description: str
    schema: dict
    resource_root: str
    capabilities: list[str]
    lifecycle: list[str] | None = None


@dataclass
class Registry:
    types: dict[str, AssetType] = field(default_factory=dict)

    def register(self, at: AssetType) -> None:
        self.types[at.type] = at

    def capability_graph(self) -> dict[str, list[str]]:
        return {t.type: t.capabilities for t in self.types.values()}


registry = Registry()
