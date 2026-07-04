"""MCP 客户端测试辅助。"""
import json


def tool_json(res):
    """FastMCP 把 dict 返回值序列化为单个 TextContent；取其 JSON。"""
    return json.loads(res.content[0].text)


def res_json(res):
    """读取 MCP 资源内容为 JSON。"""
    return json.loads(res.contents[0].text)
