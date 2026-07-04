"""系统级资源：lake://ontology（预留，返回暂未启用）。"""
from __future__ import annotations


def register(mcp) -> None:
    @mcp.resource("lake://ontology")
    def ontology() -> dict:
        """本体资产（预留）。"""
        return {"status": "disabled", "message": "Ontology 资产类型暂未启用"}
