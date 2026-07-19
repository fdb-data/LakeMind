import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lakemind_utils import llm_chat, upload_to_s3

DEFAULT_PROMPT = """你是知识萃取助手。从会议纪要和转写中提取知识点，输出 JSON。
每个知识点格式：
{"type": "decision|action_item|risk|requirement|lesson|fact", "title": "...", "body": "...", "tags": ["..."], "confidence": 0.8, "evidence": {"quote": "原文引用", "start_ms": null, "end_ms": null}}

只输出 JSON 数组，不要加 markdown 代码块标记。"""


def main():
    params = json.loads(os.environ["RAY_JOB_PARAMS"])
    transcript = params.get("transcript", "")
    minutes = params.get("minutes", "")
    template = params.get("template_snapshot", {})

    enabled_types = template.get("knowledge", {}).get("enabled_types", ["fact"])
    prompt = DEFAULT_PROMPT + f"\n\n只提取以下类型的知识：{', '.join(enabled_types)}"

    user_content = f"会议纪要：\n{minutes}\n\n转写文本：\n{transcript}"
    raw = llm_chat(prompt, user_content)
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()

    items = json.loads(raw)
    for item in items:
        item.setdefault("type", "fact")
        item.setdefault("tags", [])
        item.setdefault("confidence", 0.8)
        item.setdefault("evidence", {})

    output = {"items": items}
    result_uri = params.get("result_uri")
    if result_uri:
        upload_to_s3(result_uri, json.dumps(output, ensure_ascii=False))
    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
