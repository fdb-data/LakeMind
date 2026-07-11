"""Steward agent — LangGraph inspection workflow + LLM-backed conversation."""
from __future__ import annotations
import json
import logging
from typing import Any
import httpx
from langgraph.graph import StateGraph, END
from .mcp_client import McpClient
from .config import LlmCfg

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是 LakeMind 认知资产存取平台的管理运维助手 Steward。

你的职责：
- 监控平台健康状态（引擎、容器）
- 管理用户、租户、Token
- 查看知识库、技能、记忆、本体等认知资产
- 查询数据表、向量库、S3 存储、图数据

当用户询问平台相关信息时，你可以通过以下关键词触发具体的数据查询：
- "健康"/"health"/"状态" → 平台健康检查
- "用户"/"user" → 用户列表
- "租户"/"tenant" → 租户列表
- "token"/"令牌" → Token 列表
- "知识"/"knowledge" → 知识库浏览
- "技能"/"skill" → 技能浏览
- "记忆"/"memory" → 记忆浏览
- "本体"/"ontology" → 本体浏览
- "数据"/"data"/"table" → 数据表列表
- "资产"/"asset"/"能力"/"capability" → 平台能力总览

如果用户的问题不涉及上述具体操作，请根据你的知识自然回答。
回答请使用中文，简洁明了。"""

FORMAT_PROMPT = """你是 LakeMind 平台管理助手。用户提出了一个问题，你已获取到相关数据。
请将数据用简洁的中文格式化后回答用户。如果数据是 JSON，请提取关键信息用表格或列表展示，不要直接输出原始 JSON。"""

INTENTS = [
    (["健康", "health", "status"], "admin", "get_platform_health", {}),
    (["用户", "user"], "admin", "list_users", {}),
    (["租户", "tenant"], "admin", "list_tenants", {}),
    (["token", "令牌"], "admin", "list_tokens", {}),
    (["资产", "asset", "能力", "capability"], "asset", "__read_capabilities__", {}),
    (["知识", "knowledge"], "asset", "__read_knowledge__", {}),
    (["技能", "skill"], "asset", "__read_skills__", {}),
    (["记忆", "memory"], "asset", "__read_memory__", {}),
    (["本体", "ontology"], "asset", "__read_ontology__", {}),
    (["数据", "data", "table"], "data", "list_tables", {}),
]


def _match_intent(message: str) -> tuple[str, str, dict] | None:
    msg = message.lower()
    for keys, face, tool, args in INTENTS:
        if any(k in msg or k in message for k in keys):
            return face, tool, args
    return None


async def _call_llm(llm: LlmCfg, messages: list[dict]) -> str:
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{llm.base_url}/v1/chat/completions",
            headers={"Authorization": f"Bearer {llm.api_key}"},
            json={
                "model": llm.model,
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 0,
                "stream": False,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


async def _call_mcp_tool(mcp: McpClient, face: str, tool: str, args: dict) -> str:
    if tool.startswith("__read_"):
        uri_map = {
            "__read_capabilities__": "lake://capabilities",
            "__read_knowledge__": "lake://knowledge",
            "__read_skills__": "lake://skills",
            "__read_memory__": "lake://memory",
            "__read_ontology__": "lake://ontology",
        }
        r = await mcp.read(face, uri_map[tool])
        if "result" in r:
            return r["result"]["contents"][0]["text"] if r["result"]["contents"] else "{}"
        return json.dumps(r.get("error", {}), ensure_ascii=False)
    else:
        r = await mcp.call(face, tool, args)
        if "result" in r:
            return r["result"]["content"][0]["text"] if r["result"].get("content") else str(r["result"])
        return json.dumps(r.get("error", {}), ensure_ascii=False)


async def chat(message: str, mcp: McpClient, llm: LlmCfg) -> dict[str, Any]:
    use_llm = llm.provider != "simple" and llm.base_url
    match = _match_intent(message)

    if match:
        face, tool, args = match
        try:
            raw = await _call_mcp_tool(mcp, face, tool, args)
            if use_llm:
                try:
                    reply = await _call_llm(llm, [
                        {"role": "system", "content": FORMAT_PROMPT},
                        {"role": "user", "content": f"用户问：{message}\n\n查询到的数据：\n{raw}"},
                    ])
                    return {"reply": reply, "mode": "steward", "face": face, "tool": tool}
                except Exception as e:
                    logger.warning("LLM format failed, returning raw: %s", e)
            return {"reply": raw, "mode": "steward", "face": face, "tool": tool}
        except Exception as e:
            return {"reply": f"错误: {e}", "mode": "steward"}

    if use_llm:
        try:
            reply = await _call_llm(llm, [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": message},
            ])
            return {"reply": reply, "mode": "steward"}
        except Exception as e:
            logger.error("LLM call failed: %s", e)
            return {"reply": f"LLM 调用失败: {e}", "mode": "steward"}

    return {"reply": "我可以帮您管理平台：健康检查、用户/租户/Token管理、资产查看、数据查询等。请告诉我您想做什么。", "mode": "steward"}


async def inspect(mcp: McpClient) -> dict[str, Any]:
    """Autonomous inspection workflow: check health → collect status."""
    workflow = StateGraph(dict)

    async def check_health(state: dict) -> dict:
        r = await mcp.call("admin", "get_platform_health", {})
        if "result" in r:
            text = r["result"]["content"][0]["text"] if r["result"].get("content") else "{}"
            state["health"] = json.loads(text) if isinstance(text, str) else text
        else:
            state["health"] = {"error": str(r.get("error"))}
        return state

    async def analyze(state: dict) -> dict:
        health = state.get("health", {})
        issues = [k for k, v in health.items() if v is not True and v != "ok"]
        state["issues"] = issues
        state["healthy"] = len(issues) == 0
        return state

    async def report(state: dict) -> dict:
        if state.get("healthy"):
            state["report"] = "All systems healthy."
        else:
            state["report"] = f"Issues found: {state.get('issues', [])}"
        return state

    workflow.add_node("check_health", check_health)
    workflow.add_node("analyze", analyze)
    workflow.add_node("report", report)
    workflow.add_edge("check_health", "analyze")
    workflow.add_edge("analyze", "report")
    workflow.add_edge("report", END)
    workflow.set_entry_point("check_health")

    app = workflow.compile()
    result = await app.ainvoke({})
    issues = result.get("issues", [])
    return {"health": result.get("health"), "issues": issues, "healthy": len(issues) == 0, "report": result.get("report")}
