import os
import json
import httpx
from lakemind_utils import download_from_s3, upload_to_s3, llm_chat, SERVER_URL, SERVER_KEY

EXTRACT_PROMPT = """你是知识萃取助手。从会议纪要中提取知识点，输出 JSON 数组。
每个知识点格式：{"title": "...", "body": "...", "type": "meeting_decision|meeting_action|meeting_fact", "tags": ["..."]}
只输出 JSON 数组，不要加 markdown 代码块标记或其他说明。"""


def main():
    params = json.loads(os.environ["RAY_JOB_PARAMS"])
    minutes_uri = params["minutes_uri"]
    meeting_id = params["meeting_id"]
    meeting_title = params.get("meeting_title", "会议")
    result_uri = params["result_uri"]

    minutes = download_from_s3(minutes_uri).decode()

    raw = llm_chat(EXTRACT_PROMPT, minutes)
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()
    concepts = json.loads(raw)

    for concept in concepts:
        concept.setdefault("type", "meeting_fact")
        concept.setdefault("tags", [])
        concept["frontmatter"] = {
            "type": concept["type"],
            "title": concept["title"],
            "tags": concept["tags"],
            "meeting_id": meeting_id,
            "meeting_title": meeting_title,
        }

    try:
        httpx.post(
            f"{SERVER_URL}/api/v1/cognitive/knowledge/ingest",
            headers={"Authorization": f"Bearer {SERVER_KEY}", "Content-Type": "application/json"},
            json={"kb_name": "meetings", "concepts": concepts},
            timeout=60,
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"knowledge ingest warning: {e}")

    output = {"concepts": concepts}
    upload_to_s3(result_uri, json.dumps(output, ensure_ascii=False))
    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
