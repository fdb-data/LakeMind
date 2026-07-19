import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lakemind_utils import llm_chat, upload_to_s3

DEFAULT_PROMPT = """你是会议纪要助手。根据转写文本生成结构化会议纪要（Markdown）。
格式：
## 会议摘要
（一句话概括）

## 关键决策
1. ...

## 行动项
- [ ] 负责人：任务

## 讨论要点
- ...

只输出纪要内容，不要加额外说明。"""


def main():
    params = json.loads(os.environ["RAY_JOB_PARAMS"])
    transcript = params.get("transcript", "")
    meeting_title = params.get("meeting_title", "会议")
    template = params.get("template_snapshot", {})
    custom_instructions = template.get("minutes", {}).get("custom_instructions", "")

    prompt = DEFAULT_PROMPT
    if custom_instructions:
        prompt += f"\n\n额外要求：{custom_instructions}"

    minutes = llm_chat(prompt, f"会议标题：{meeting_title}\n\n转写文本：\n{transcript}")

    output = {"minutes": minutes}
    result_uri = params.get("result_uri")
    if result_uri:
        upload_to_s3(result_uri, json.dumps(output, ensure_ascii=False))
    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
