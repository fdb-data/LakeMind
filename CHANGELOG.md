# Changelog

> 完整变更日志见 [docs/changelog.md](docs/changelog.md)。

## v0.1.0 (2026-07-12)

### 核心
- Initial release: 13 containers, 10 engines, 58 MCP tools
- LakeMindModelServing: litellm + fastembed + FunASR (:10824)
- Steward LLM dialog via ModelServing
- 3 compose 组：lakemind-server / lakemind-mcp / lakemind-runtime

### Fixes — Ray jobs（一等公民）
- Ray dashboard `--dashboard-host=0.0.0.0`：dashboard 默认绑定 127.0.0.1，JobSubmissionClient 跨容器不可達
- `ray_compute.py`：JobSubmissionClient 使用 dashboard 地址（`http://lakemind-ray-head:8265`）而非 Ray client 地址
- `ray_compute.py`：`from ray.job_submission import JobSubmissionClient` 显式导入（`ray.job_submission` 属性不可用）
- `ray_compute.py`：`working_dir` 替代 `py_modules`（Ray 不接受 .zip 作为 py_modules）
- `ray_compute.py`：新增 `get_job_status(ray_job_id)` 方法，支持 skill job 状态轮询
- `ray_compute.py`：temp file 清理（finally block）
- `ray_compute.py`：移除死代码 `_remote_eval`
- `jobs.py`：`job_status`/`job_result` 端点支持 skill job（查 PG + 轮询 Ray）
- `jobs.py`：`lake://` URI 解析修复（原先 `lake://` 被误当 `s3://` 格式解析）
- `protocols.py`：`DistributedComputePlugin` 新增 `get_job_status` 方法
- `embedded.py`：新增 `get_job_status` stub
- `engines.yaml`：新增 `dashboard_address` 配置项

### Fixes — Embedding & Memory
- AssetMCP/DataMCP `embed()` → ModelServing `/v1/embeddings` (was 404 on Server)
- Memory search: L2 → cosine metric (score was always 0 with L2)
- `verify_full.py`: adapted for ModelServing architecture (286/286 L0-L8 PASS)

### Added — Examples
- `examples/meeting-agent/` — browser real-time meeting agent demo (17min live test, 145 chunks, 100+ Ray jobs, 100% success)
- `examples/lakemind-connector/` — opencode Skill for LakeMind cognitive backend (v0.1.0: Ray jobs + ASR + S3 URI API)
- `README_agent.md` — agent-facing onboarding guide (§4 Ray jobs development guide, §9 gotchas)

### Verification
- verify_full.py: 286/286 L0-L8 PASS
- Ray built-in func: sum/parallel_map/pi_monte_carlo/sleep_test/matrix_multiply 全 PASS
- Skill-based Ray job: submit → status(SUCCEEDED) → result(completed) → cancel(STOPPED) 全 PASS
- DataMCP → Server → Ray 完整链路 PASS
- Ray cluster: 3 nodes, 12 CPU, 11/12 verify_ray.py PASS (1 FAIL: 容器内无 docker 命令)
- See [docs/release-notes-v0.1.0.md](docs/release-notes-v0.1.0.md) for full notes
