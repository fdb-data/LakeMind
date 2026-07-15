# ASR 模型安装经验总结

> 2026-07-15 · LakeMind v0.2.0 · faster-whisper-small 部署全记录

---

## 一、最终架构

```
Systran/faster-whisper-small (MIT, ~461MB, CTranslate2 格式)
  │
  ├─ 预下载: hf_hub_download(repo_id, revision, filename, local_dir)
  │  └─ 固定 commit: 536b0662742c02347bc0e980a01041f333bce120
  │  └─ SHA-256: 3e305921506d8872816023e4c273e75d2419fb89b24da97b4fe7bce14170d671
  │
  ├─ 存储: Docker volume `asr-models` → /models/asr/faster-whisper-small/
  │  ├─ model.bin (461MB)
  │  ├─ config.json
  │  ├─ tokenizer.json
  │  ├─ vocabulary.txt
  │  └─ model-manifest.json
  │
  ├─ 运行时: faster-whisper 1.2.1 + CTranslate2 4.8.1
  │  ├─ device=cpu, compute_type=int8
  │  ├─ cpu_threads=4, num_workers=1
  │  ├─ HF_HUB_OFFLINE=1 (禁止运行时下载)
  │  └─ 无 torch, 无 CUDA, 无 ffmpeg
  │
  └─ 服务: model-serving 容器
     ├─ startup: asyncio.to_thread(asr_service.load)
     ├─ /health/components/asr → 503 if not ready, 200 if ready
     └─ ASR 失败不拖垮 ModelServing (required: false)
```

---

## 二、踩坑全记录（6 次失败 → 1 次成功）

| 轮次 | 模型 | 失败原因 | 根因分类 | 耗时 |
|------|------|----------|----------|------|
| 1 | FunASR/SenseVoiceSmall | torch 未安装 | **依赖管理** | 2h |
| 2 | FunASR/SenseVoiceSmall | ModelScope DNS 解析失败 | **网络** | 0.5h |
| 3 | FunASR/SenseVoiceSmall | vad_model/punc_model 不接受本地路径 | **API 误解** | 1h |
| 4 | FunASR/SenseVoiceSmall | 许可证非 Apache 2.0（自定义 FunASR License） | **合规** | — |
| 5 | faster-whisper-large-v3-turbo | HF 401 Unauthorized（gated repo） | **仓库权限** | 0.5h |
| 6 | faster-whisper-large-v3 | 下载 ~3GB 太重；误选非 turbo 模型 | **模型选型** | 1h |
| 7 | faster-whisper-small (WhisperModel download_root) | model.bin 下载到 HF 缓存子目录，不在目标目录 | **API 误解** | 0.5h |
| 8 | faster-whisper-small (snapshot_download local_dir) | Docker Desktop 下载中途崩溃 | **环境稳定性** | 1h |
| 9 | faster-whisper-small (hf_hub_download) | **成功** | — | 0.2h |

---

## 三、每个坑的详细根因和正确做法

### 坑 1：torch 未安装

**现象**：`import torch` 失败，FunASR 依赖 torch 但 pyproject.toml 未声明。

**根因**：FunASR 隐式依赖 torch + torchaudio + numba + llvmlite，共 ~2GB CUDA 包。

**正确做法**：faster-whisper 不依赖 torch，使用 CTranslate2 后端。直接声明 `faster-whisper` 即可，不要引入 torch。

**教训**：选 ASR 引擎时，**先查依赖树**。依赖 torch 的引擎在 CPU-only 环境中极重。

---

### 坑 2：ModelScope DNS 解析失败

**现象**：`modelscope.cn` DNS 解析失败，模型无法下载。

**根因**：FunASR 通过 ModelScope 下载模型，ModelScope 是阿里云服务，DNS 可能被 Docker 网络配置影响。

**正确做法**：faster-whisper 通过 HuggingFace 下载，HF 在国内可用（虽然慢）。

**教训**：**优先选择 HuggingFace 作为模型源**，避免国内平台 DNS/网络问题。

---

### 坑 3：vad_model/punc_model 不接受本地路径

**现象**：FunASR 的 `AutoModel(vad_model="fsmn-vad")` 只接受 ModelScope 模型 ID，不接受本地路径。

**根因**：FunASR API 设计耦合 ModelScope，辅助模型必须从 ModelScope 下载。

**正确做法**：faster-whisper 内置 Silero VAD（`vad_filter=True`），无需单独的 VAD 模型。Whisper 自带标点，无需 punc_model。

**教训**：**避免需要多个辅助模型的引擎**。单模型 + 内置 VAD 是最优解。

---

### 坑 4：许可证问题

**现象**：SenseVoiceSmall 模型许可证是自定义 FunASR License，非 Apache 2.0/MIT。

**正确做法**：faster-whisper（MIT）+ Whisper 模型（MIT）= 全链路 MIT。

**教训**：**选模型前先查许可证**。企业部署需要许可证清晰的开源模型。

---

### 坑 5：HuggingFace gated repo

**现象**：`Systran/faster-whisper-large-v3-turbo` 返回 401 Unauthorized。

**根因**：该仓库是 gated repo，需要 HF 账号 + 接受条款才能下载。

**正确做法**：使用公开仓库 `Systran/faster-whisper-small`。

**教训**：**先确认目标仓库是否 public**。`hf download --dry-run` 可以快速验证。

---

### 坑 6：模型选型错误（太大）

**现象**：`Systran/faster-whisper-large-v3` 的 model.bin ~3GB，下载耗时 40+ 分钟。

**根因**：large-v3（非 turbo）的 float16 模型约 3GB，不适合作为默认轻量模型。

**正确做法**：`Systran/faster-whisper-small` 约 461MB，适合作为默认。large-v3-turbo（~1.6GB）作为可选高精度 Profile。

**教训**：**默认模型选轻量级**（<500MB）。大模型作为可选 Profile，不作为默认下载项。

| 模型 | 体积 | 定位 |
|------|------|------|
| faster-whisper-small | ~461MB | **默认** |
| faster-whisper-medium | ~1.5GB | 不推荐（体积接近 turbo 但精度更低） |
| faster-whisper-large-v3-turbo | ~1.6GB | 可选高精度 |
| faster-whisper-large-v3 | ~3GB | 不推荐（太重） |

---

### 坑 7：download_root 下载到错误目录

**现象**：`WhisperModel(model_id, download_root=MODEL_DIR)` 下载完成后，`model.bin` 不在 `MODEL_DIR` 根目录，而在 HF 缓存子目录中。

**根因**：`download_root` 参数传给 `huggingface_hub.snapshot_download` 的 `cache_dir`，文件存储在 `cache_dir/models--Systran--faster-whisper-small/snapshots/<hash>/` 子目录中。

**正确做法**：使用 `huggingface_hub.hf_hub_download(repo_id, filename, local_dir=MODEL_DIR)` 或 `snapshot_download(repo_id, local_dir=MODEL_DIR)`，`local_dir` 会将文件直接放在目标目录。

**教训**：**不要用 WhisperModel 的 download_root 参数**。用 `hf_hub_download` + `local_dir` 预下载，然后用 `WhisperModel(local_path)` 加载。

---

### 坑 8：Docker Desktop 下载中途崩溃

**现象**：Docker Desktop 在长时间下载（>30分钟）时崩溃，WSL 需要重启。

**根因**：Docker Desktop 在 Windows 上的稳定性问题，长时间网络 IO 可能触发崩溃。

**正确做法**：用 `hf_hub_download` 单独下载 `model.bin`（最大的文件），其他小文件已在之前的 partial download 中存在。整个下载在容器中完成，但只下载一个文件，耗时 <10 分钟。

**教训**：
- **长下载不要在 Docker 容器中做**，优先在 WSL 宿主机下载
- 如果必须在容器中下载，**分文件下载**，先下小文件再下大文件
- 使用 **staging 目录 + 原子重命名**，避免半成品被误认为可用

---

### 坑 9（额外）：Ray submit_job 参数错误

**现象**：`JobSubmissionClient.submit_job() got an unexpected keyword argument 'resources'`

**根因**：`ray_compute.py` 用 `submit_kwargs["resources"]` 传给 Ray，但 Ray 2.41.0 的 `submit_job()` 不接受 `resources` 参数。

**正确做法**：使用 `entrypoint_num_cpus` 代替 `resources`。

**教训**：**Ray API 版本兼容性要查文档**。`resources` 是 Ray Core 的概念，不是 Job Submission Client 的参数。

---

## 四、下次部署不同模型的 Checklist

### 选型阶段

- [ ] 确认模型许可证（MIT / Apache 2.0）
- [ ] 确认 HuggingFace 仓库是 public（非 gated）
- [ ] 确认模型体积 <500MB（作为默认模型）
- [ ] 确认运行时依赖不包含 torch/CUDA
- [ ] 确认模型支持本地路径加载（`local_files_only=True`）
- [ ] 确认无需辅助模型（VAD/punc 内置或不需要）

### 预下载阶段

- [ ] 固定模型 commit hash（不跟随 main）
- [ ] 查询 model.bin 的 SHA-256（HF 网页或 `hf_hub_download` 后计算）
- [ ] 用 `hf_hub_download(repo_id, revision, filename, local_dir)` 下载
- [ ] **不要用** `WhisperModel(download_root=...)` 下载
- [ ] **不要用** `snapshot_download` 下载全部文件（用 `allow_patterns` 过滤）
- [ ] 下载完成后验证全部必需文件存在
- [ ] 计算 SHA-256 并与预期值比对
- [ ] 写 `model-manifest.json`（含 model_id, revision, sha256, verified）

### 集成阶段

- [ ] `language="auto"` 在代码中映射为 `None`
- [ ] `segments` 生成器用 `list()` 完整消费
- [ ] `condition_on_previous_text=False`（避免重复循环）
- [ ] ASR 失败不 crash ModelServing（`required: false`）
- [ ] `/health/components/asr` 独立健康检查
- [ ] `HF_HUB_OFFLINE=1` 在运行时容器中设置
- [ ] `ASR_CONCURRENCY=1`（CPU 单并发）
- [ ] docker-compose 不强制 `depends_on: asr-model-init`

### 验证阶段（按顺序）

1. 宿主机检查文件存在 + SHA-256
2. 容器内离线加载 `WhisperModel(path, local_files_only=True)`
3. 真实音频转写测试
4. `/health/components/asr` → 200
5. meeting-agent 端到端 → `[OK] ASR chunk N: text_len=...`
6. 故障注入：删除 tokenizer.json → 503 + 错误信息

---

## 五、关键文件索引

| 文件 | 职责 |
|------|------|
| `LakeMindModelServing/src/.../services/asr.py` | ASRService：状态机 + load + transcribe |
| `LakeMindModelServing/src/.../tools/prefetch_asr.py` | 预下载：staging + SHA-256 + 原子安装 |
| `LakeMindModelServing/src/.../config.py` | ASRBuiltInConfig dataclass |
| `LakeMindModelServing/config/models.yaml` | ASR 配置段 |
| `LakeMindModelServing/src/.../app.py` | startup preload（非致命） |
| `LakeMindModelServing/src/.../api/audio.py` | /v1/audio/transcriptions 端点 |
| `LakeMindModelServing/src/.../api/health.py` | /health/live + /health/ready + /health/components/asr |
| `LakeMindModelServing/pyproject.toml` | faster-whisper 依赖（无 torch） |
| `LakeMindModelServing/Dockerfile` | python:3.12-slim + libgomp1 |
| `docker-compose.yml` | asr-model-init (profile: model-download) + model-serving |
| `LakeMindServer/src/.../ray_compute.py` | entrypoint_num_cpus（不是 resources） |

---

## 六、一句话总结

> **选 MIT 许可的轻量模型，用 hf_hub_download + local_dir 预下载，固定 commit + SHA-256 校验，HF_HUB_OFFLINE=1 离线加载，ASR 失败不拖垮服务。**
