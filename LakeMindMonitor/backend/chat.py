"""对话：Steward 代理 + 只读直连降级。"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from .config import Config
from .mcp_client import McpReadClient

_log = logging.getLogger("lakemind.monitor")

INTENTS: list[tuple[list[str], str, str]] = [
    (["健康", "状态", "health"], "lake://system/health", "组件健康"),
    (["数据", "表", "data", "dataset"], "lake://data", "数据集列表"),
    (["知识", "knowledge"], "lake://knowledge", "知识库列表"),
    (["技能", "skill"], "lake://skills", "Skill 列表"),
    (["记忆", "memory"], "lake://memory", "记忆概况"),
    (["经验", "experience"], "lake://experience", "经验记录"),
    (["能力", "capability"], "lake://capabilities", "能力图"),
    (["工作区", "workspace"], "lake://workspace", "工作区"),
]


async def chat(message: str, config: Config, mcp: McpReadClient) -> dict[str, Any]:
    if config.steward.url:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    config.steward.url,
                    headers={"Authorization": f"Bearer {config.steward.token}"} if config.steward.token else {},
                    json={"message": message},
                )
                resp.raise_for_status()
                return {"reply": resp.json(), "mode": "steward"}
        except Exception as e:
            _log.warning("steward proxy failed, degrade to readonly: %s", e)
    return await _readonly_direct(message, mcp)


async def _readonly_direct(message: str, mcp: McpReadClient) -> dict[str, Any]:
    msg = message.lower()
    for keys, uri, label in INTENTS:
        if any(k in msg or k in message for k in keys):
            try:
                data = await mcp.read_resource(uri)
                return {"reply": {label: data}, "mode": "readonly-direct"}
            except Exception as e:
                return {"reply": f"读取 {uri} 失败: {e}", "mode": "readonly-direct"}
    hints = "、".join(label for _, _, label in INTENTS)
    return {
        "reply": f"只读直连模式（Steward 未就绪）。当前仅支持只读查询，可问：{hints}。",
        "mode": "readonly-direct",
    }
