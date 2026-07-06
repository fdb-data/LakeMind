"""Steward agent — LangGraph inspection workflow + conversational management."""
from __future__ import annotations
import json
from typing import Any
from langgraph.graph import StateGraph, END
from .mcp_client import McpClient

INTENTS = [
    (["健康", "health", "status"], "admin", "get_platform_health", {}),
    (["用户", "user"], "admin", "list_users", {}),
    (["租户", "tenant"], "admin", "list_tenants", {}),
    (["token", "令牌"], "admin", "list_tokens", {}),
    (["资产", "asset", "能力", "capability"], "asset", "__read_capabilities__", {}),
    (["数据", "data", "表", "table"], "data", "list_tables", {}),
    (["知识", "knowledge"], "asset", "__read_knowledge__", {}),
    (["技能", "skill"], "asset", "__read_skills__", {}),
    (["记忆", "memory"], "asset", "__read_memory__", {}),
    (["本体", "ontology"], "asset", "__read_ontology__", {}),
]


def _match_intent(message: str) -> tuple[str, str, dict] | None:
    msg = message.lower()
    for keys, face, tool, args in INTENTS:
        if any(k in msg or k in message for k in keys):
            return face, tool, args
    return None


async def chat(message: str, mcp: McpClient) -> dict[str, Any]:
    match = _match_intent(message)
    if match is None:
        return {"reply": "我可以帮您管理平台：健康检查、用户/租户/Token管理、资产查看、数据查询等。请告诉我您想做什么。", "mode": "steward"}

    face, tool, args = match
    try:
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
                text = r["result"]["contents"][0]["text"] if r["result"]["contents"] else "{}"
                return {"reply": text, "mode": "steward", "face": face}
            return {"reply": f"读取失败: {r.get('error', {})}", "mode": "steward"}
        else:
            r = await mcp.call(face, tool, args)
            if "result" in r:
                text = r["result"]["content"][0]["text"] if r["result"].get("content") else str(r["result"])
                return {"reply": text, "mode": "steward", "face": face, "tool": tool}
            return {"reply": f"调用失败: {r.get('error', {})}", "mode": "steward"}
    except Exception as e:
        return {"reply": f"错误: {e}", "mode": "steward"}


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
    return {"health": result.get("health"), "issues": result.get("issues"), "report": result.get("report")}
