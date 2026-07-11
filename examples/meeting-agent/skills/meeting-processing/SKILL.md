# 会议录音实时知识化

实时录音 → ASR 转写 → 会议纪要 → 知识萃取 → 知识库入库。

## Jobs

- **asr**: 音频 chunk → 转写文本（调用 ModelServing FunASR）
- **summarize**: 转写文本 → 结构化纪要（调用 ModelServing LLM）
- **extract**: 纪要 → 知识点 + 入库（调用 ModelServing LLM + REST API）

## 模型服务

所有 LLM 和 ASR 调用通过 LakeMindModelServing (:10824)：
- ASR: FunASR (SenseVoice-Small) → /v1/audio/transcriptions
- LLM: litellm (deepseek-v4-flash) → /v1/chat/completions
