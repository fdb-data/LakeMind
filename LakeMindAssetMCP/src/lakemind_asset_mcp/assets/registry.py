"""Asset type registry with declarative YAML support."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

__all__ = ["AssetDefinition", "Registry", "registry"]


@dataclass
class AssetDefinition:
    type: str
    description: str
    resource_root: str
    capabilities: list[str]
    storage: dict = field(default_factory=dict)
    operations: dict = field(default_factory=dict)
    raw: dict = field(default_factory=dict)

    @classmethod
    def from_yaml(cls, path: Path) -> "AssetDefinition":
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        return cls(
            type=raw["type"],
            description=raw.get("description", ""),
            resource_root=raw.get("resource_root", ""),
            capabilities=raw.get("capabilities", []),
            storage=raw.get("storage", {}),
            operations=raw.get("operations", {}),
            raw=raw,
        )


@dataclass
class Registry:
    types: dict[str, AssetDefinition] = field(default_factory=dict)

    def register(self, defn: AssetDefinition) -> None:
        self.types[defn.type] = defn

    def unregister(self, type: str) -> None:
        self.types.pop(type, None)

    def capability_graph(self) -> dict[str, Any]:
        return {
            t.type: {
                "description": t.description,
                "resource_root": t.resource_root,
                "capabilities": t.capabilities,
            }
            for t in self.types.values()
        }

    def load_native(self, native_dir: Path) -> None:
        for yml in sorted(native_dir.glob("*.yaml")):
            self.register(AssetDefinition.from_yaml(yml))


registry = Registry()
