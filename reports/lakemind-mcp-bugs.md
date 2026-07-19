# LakeMind 系统Bug清单 — Meeting Agent v0.2.0 走 MCP 时发现

> 发现时间：2026-07-18
> 发现场景：Meeting Agent v0.2.0 按 AGENTS.md 架构纪律走 MCP（AssetMCP + DataMCP），暴露以下系统级 bug

---

## Bug-1: DataMCP `s3_put` 不支持二进制数据

**严重度**: P0 — 阻断音频上传

**现象**: DataMCP 的 `s3_put(uri: str, body: str)` 参数类型是 `str`，内部做 `body.encode()` 转成 UTF-8 bytes。二进制音频数据（webm/wav）无法直接作为字符串传递，base64 编码后存入的是 base64 文本而非原始二进制。

**根因**: `LakeMindMCP/LakeMindDataMCP/src/lakemind_data_mcp/tools/data.py:126`
```python
async def s3_put(uri: str, body: str) -> dict:
    await server.object_put(bucket, key, body.encode())  # str → UTF-8 bytes
```

**修复方案**: `s3_put` 增加 `body_b64: str | None = None` 参数，当传入 base64 编码的二进制数据时，`base64.b64decode(body_b64)` 还原为原始 bytes 再存储。`s3_get` 对应返回 base64 编码的二进制数据。

---

## Bug-2: DataMCP `s3_get` 不支持二进制数据

**严重度**: P0 — 阻断音频下载

**现象**: `s3_get` 内部做 `data.decode("utf-8")`，二进制数据会抛 `UnicodeDecodeError` 或返回乱码。

**根因**: `LakeMindMCP/LakeMindDataMCP/src/lakemind_data_mcp/tools/data.py:115`
```python
async def s3_get(uri: str) -> dict:
    data = await server.object_get(bucket, key)
    content = data.decode("utf-8") if isinstance(data, bytes) else str(data)  # 二进制会失败
    return {"uri": uri, "content": content, "size": len(data)}
```

**修复方案**: `s3_get` 返回 `content_b64` 字段（base64 编码），调用方按需解码。

---

## Bug-3: DataMCP `ray_submit_job` 未将 env_overrides 注入 Ray Worker

**严重度**: P0 — 阻断 ASR Job 执行

**现象**: `ray_submit_job` 接受 `env_overrides` 参数，但 Ray Worker 运行时 `SERVER_API_KEY` 等环境变量为空，导致 `Illegal header value b'Bearer '` 错误。

**根因**: `LakeMindServer/src/lakemind_server/api/jobs.py` 提交 Ray Job 时未将 `env_overrides` 传入 `ray.job_submission` 的 `runtime_env`。

**修复方案**: 在提交 Ray Job 时将 `env_overrides` 合并到 `runtime_env["env_vars"]`。

---

## Bug-4: DataMCP 无 v0.2.0 JobService 工具

**严重度**: P1 — 功能缺失

**现象**: DataMCP 的 `ray_submit_job` 调用 v0.1.0 compute API (`/api/v1/compute/jobs/submit`)，不支持 v0.2.0 JobService (`/api/v1/jobs`) 的 `skill_ref`/`model_profile`/`idempotency_key` 参数。

**根因**: `LakeMindMCP/LakeMindDataMCP/src/lakemind_data_mcp/server_client.py:183` 调用的是旧 API。

**修复方案**: DataMCP 新增 `submit_job`/`get_job`/`get_job_result` 工具，对接 v0.2.0 JobService。

---

## Bug-5: ModelServing ASR 缺少 ffmpeg，无法解码 WebM/Opus

**严重度**: P0 — 阻断浏览器录音转写

**现象**: 浏览器 MediaRecorder 产出 `audio/webm`（Opus 编码），ModelServing 的 faster-whisper 后端依赖 ffmpeg 解码非 WAV 格式，但容器内未安装 ffmpeg，报 `[Errno 1094995529] Invalid data found when processing input`。

**根因**: `LakeMindModelServing/Dockerfile` 未安装 ffmpeg。

**修复方案**: Dockerfile 添加 `RUN apt-get update && apt-get install -y ffmpeg`。

---

## 修复计划

| Bug | 修改范围 | 预估工作量 | 优先级 |
|-----|---------|-----------|--------|
| Bug-1 | DataMCP `s3_put` 增加 `body_b64` 参数 | 0.5h | P0 |
| Bug-2 | DataMCP `s3_get` 返回 `content_b64` | 0.5h | P0 |
| Bug-3 | Server `jobs.py` 注入 env_overrides 到 Ray runtime_env | 1h | P0 |
| Bug-5 | ModelServing Dockerfile 安装 ffmpeg | 0.5h | P0 |
| Bug-4 | DataMCP 新增 v0.2.0 JobService 工具 | 2h | P1 |

**修复顺序**: Bug-5 → Bug-3 → Bug-1+Bug-2 → Bug-4

**验证方式**: 修复后重新运行 Meeting Agent v0.2.0 E2E 测试（录音 → 上传 → ASR → 纪要 → 知识），确认全链路走 MCP 且无错误。
