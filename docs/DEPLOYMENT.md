# 魔搭创空间部署清单

## 0. Stage 5B production release contract

The accepted production target is the private Docker Studio
`LuckyPan/Movie-Agent`. Keep the Studio private during acceptance and do not
expose it publicly until a separate authentication review approves every
mutation route. The target must run the `master` branch on the free
`platform/2v-cpu-16g-mem` resource, listen on `0.0.0.0:7860`, and use
`/mnt/workspace` for durable state.

The competition Option B runtime uses real ModelScope text planning and Mock-only
media:

```text
MODEL_PROVIDER=modelscope
MODELSCOPE_MODEL=Qwen/Qwen3-30B-A3B-Instruct-2507
MODELSCOPE_MAX_TOKENS=8192
IMAGE_GENERATION_MODE=mock
VIDEO_GENERATION_MODE=mock
PUBLIC_DEMO_MODE=true
# Set APP_ACCESS_TOKEN only in the Studio secret configuration; never commit it.
APP_ACCESS_TOKEN=<deployment secret>
MAX_ACTIVE_JOBS=2
MAX_UPLOAD_MB=10
PUBLIC_MAX_PROJECTS=20
PUBLIC_MAX_UPLOAD_MB=10
PROJECTS_DIR=/mnt/workspace/projects
OUTPUTS_DIR=/mnt/workspace/outputs
COMFY_OUTPUT_DIR=/mnt/workspace/comfy-output
PORT=7860
```

`MODELSCOPE_API_KEY` and `APP_ACCESS_TOKEN` belong only in Studio Secrets.
The Public Demo may call the real ModelScope text LLM for dynamic planning, but
image generation, video generation, ComfyUI, Wan/DashScope, and TTS remain
disabled and Mock/none respectively. Do not submit a real media-provider
generation request. The real media adapters remain available for controlled
private deployments.

## 1. 推送代码

将仓库推送到 GitHub。不要提交 `.env`、`models/`、`outputs/` 或 `projects/`。

## 2. 创建创空间

主部署使用 Docker Studio，运行 FastAPI `server.py`；Gradio `app.py` 仅作为 fallback / compatibility 入口。Docker 启动命令为（先做固定、无网络的运行时自检）：

```bash
python scripts/stage5a_runtime_check.py && uvicorn server:app --host 0.0.0.0 --port ${PORT:-7860} --workers 1
```

依赖文件仍为 `requirements.txt`。

### 单实例 Job Ledger

比赛部署保持单进程账本策略，不启用 Redis / Celery。使用 FastAPI 入口时必须保持一个 Uvicorn worker：

```bash
uvicorn server:app --host 0.0.0.0 --port ${PORT:-7860} --workers 1
```

`JobLedger` 的跨请求保护依赖同一进程内的锁；多 worker 会让不同进程看到不一致的 process-local lock。产品化部署再评估 SQLite lease、file lock 或外部队列。

## 3. 添加 Variables / Secrets

公开竞赛 Demo 使用真实 ModelScope 文本规划和 Mock-only media；建议设置：

```text
MODEL_PROVIDER=modelscope
IMAGE_GENERATION_MODE=mock
VIDEO_GENERATION_MODE=mock
TTS_PROVIDER=none
PUBLIC_DEMO_MODE=true
APP_ACCESS_TOKEN=<仅在创空间后台填写>
MODELSCOPE_API_KEY=<仅在创空间后台填写>
PROJECTS_DIR=/mnt/workspace/projects
OUTPUTS_DIR=/mnt/workspace/outputs
PORT=7860

# 真实文本模型配置；不要提交真实值。
# MODELSCOPE_API_BASE=https://api-inference.modelscope.cn/v1
# MODELSCOPE_MODEL=Qwen/Qwen3-30B-A3B-Instruct-2507

# 需要真实 Wan 视频时再配置；不要提交真实值。公开模式禁止启用。
# VIDEO_GENERATION_MODE=remote
# REMOTE_VIDEO_API_BASE=<Beijing workspace API base>
# REMOTE_VIDEO_MODEL=wan2.7-t2v
# REMOTE_VIDEO_API_KEY=<仅在创空间后台填写>
```

不要把 Key 填进 Git、README、网页日志或项目导出文件。

## 4. 验收

- Studio 保持 private；匿名访问被平台拒绝是预期的安全边界，不作为失败。
- `GET /health`、`GET /api/health` 和 `GET /api/health/ready` 在目标容器内返回健康/ready；外部探针按平台认证边界配置。
- 输入原创科幻创意后，页面出现项目设定、剧本、按镜头拆分的 Dialogue Book / Subtitle Track、视觉卡、6–10 个分镜和任务日志。
- 能在编剧阶段编辑并锁定台词本；未锁定前不得进入配音、字幕和 AI Edit。
- 全部镜头通过质检后显示 `SHOTS READY`，先生成可预览的 Rough Cut，再明确批准最终成片。
- Deliver / 放映室按“未剪辑 → AI 剪辑中 → 最终成片完成”显示状态；最终成片存在时显示真实播放器、技术元数据和可跳转 Shot Timeline，不存在时明确显示 `FINAL CUT NOT GENERATED`。
- 最终成片完成后，Deliver 播放器右侧出现 `FINAL LOOK / COLOR FINISH`。六种预设、强度、颗粒、暗角和高光柔化都只作用于整部影片；点击预设即时预览，点击“应用 Final Look”后才保存。真实视频由 FFmpeg 生成带版本号的润色母版，mock 模式只保存润色与导出方案，不伪造媒体文件。
- `导出成片` 提供 MP4/MOV/WebM、720P/1080P、16:9/9:16/1:1 与烧录/软字幕/无字幕选项，默认 MP4 + H.264 + 1080P；JSON、制作手册 Markdown、SRT/VTT 位于 `更多导出`。
- 默认启用字幕，并可在交付时选择烧录、软字幕或无字幕；SRT/VTT 可单独导出。
- AI Edit 必须按 `Picture Cut → Voice → Music → SFX → Subtitles → Mix → Final Encode` 展示进度；声音设计区应显示 Music Brief、Emotional Arc、四轨状态和 Smart Ducking。
- 配乐支持 AI 自动配乐、素材库音乐和用户上传音乐三种模式；Deliver 放映室提供音乐强度、四轨开关、试听、重规划和 Smart Ducking 控制。没有真实音频生成器时也要保留可审阅的声音设计计划，不能伪称已有音频媒体。
- 能打开已保存项目，且可导出 JSON 与 Markdown。
- 无 API Key 时仍可切换为 mock 模式演示。
- 视频能力未就绪时，页面明确标注为 mock 视频流程，不能将占位路径宣传为真实成片。

### 持久化、重启与恢复

- `/mnt/workspace/projects`：项目 JSON、`project.json.bak`、`job.json` 和恢复所需的 Job Ledger。
- `/mnt/workspace/outputs`：用户上传音频、Source、Proxy、Screening Preview、Final Master 及导出产物；可重建的派生媒体仍保留版本元数据。
- `/mnt/workspace/comfy-output`：仅在后续启用 Spark/ComfyUI 时使用的 Provider 输出目录。
- `/tmp` 与容器工作目录：临时上传文件、锁和缓存，重启后不得视为可靠数据。

容器启动时 `scripts/stage5a_runtime_check.py` 会固定检查 FFmpeg、FFprobe、应用路由、静态资源和 `/mnt/workspace` 写读能力，并维护重启 marker。看到
`persistence_marker_previous=PRESENT` 与 `persistence_survived_restart=PASS`
后，才可把恢复链路视为通过。任务中断后先读取
`GET /api/projects/<project_id>/job?after=0&limit=40`，确认
`RECOVERABLE_FAILED / RESUME AVAILABLE`，再由操作者显式重试；不要通过删除
`project.json` 或 `job.json` 来“恢复”。

### 发布后最小检查

1. 确认 `master` 已部署、启动日志包含 `Application startup complete`。
2. 确认 Stage 5A 自检的所有 `PASS` 项，以及 `/mnt/workspace` marker 已跨重启保留。
3. 在 Mock 模式创建一个测试项目，读取项目、诊断、Job Ledger、导出 JSON/Markdown；不调用真实 Provider。
4. 确认无 Key 时文本/图片/视频能力仍为 Mock 或明确 `PROVIDER REQUIRED`，而不是伪造媒体。
5. 记录构建 SHA、目标 URL 的认证结果、健康结果和测试项目清理决定。

### P4 运行诊断与交付预检

部署后可用下面两个只读接口检查一个项目是否能安全继续：

```text
GET /api/projects/<project_id>/diagnostics
GET /api/projects/<project_id>/delivery-preflight?resolution=1080p&aspect=16:9&subtitle_mode=burned
```

`diagnostics` 返回规范化阶段、镜头通过/失败/过期计数、最近日志、脱敏错误和下一步恢复动作；不会返回媒体路径、Token 或主机信息。刷新项目时普通 `GET /api/projects/<project_id>` 也会携带同一份快照。

`delivery-preflight` 会在导出前检查 Final Cut 是否批准、当前 Final Master 是否存在且未过期、台词本是否锁定、镜头是否全部通过质检、目标分辨率是否满足以及 FFmpeg 是否可用。导出接口会重复执行这份检查，失败时返回 `409 DELIVERY_NOT_READY` 和可读的 `blocking_reasons`，避免把 Proxy、Screening Preview 或低清素材误当成交付母版。

### P5 断线恢复与重复任务保护

创作、Spark 渲染和 AI Edit 启动后，服务会在每个项目目录写入被 `.gitignore` 忽略的 `job.json`。它只记录任务阶段、状态、进度、游标和脱敏后的最近事件，不保存 Prompt、媒体路径或凭据。SSE 连接断开不会停止后台任务，客户端可用下面的接口补读事件：

```text
GET /api/projects/<project_id>/job?after=0&limit=40
```

同一项目已有 `running` 任务时，重复提交会返回 `409 JOB_ALREADY_RUNNING` 以及当前任务摘要。每项任务还持久化 `operation_id`、幂等键、项目版本、输入指纹、心跳和 lease。服务重启或 lease 过期后，未正常收尾的任务会显示为 `recoverable_failed` / `RECOVERABLE_FAILED`，页面将提示 `RESUME AVAILABLE`；重新提交时仍会经过项目锁和既有状态/QC检查。部署必须保持 `--workers 1`，避免多个进程拥有互不知情的进程内执行锁。

## 5. Spark 视频模式

将验证过的 ComfyUI 服务限定为 `127.0.0.1:8188`，由 Movie-Agent 后端调用。前端创空间不直接暴露 Spark 的 ComfyUI 端口或任何凭据。

在 Spark 应用目录的 `.env` 中设置：

```ini
VIDEO_GENERATION_MODE=comfyui
COMFY_BASE_URL=http://127.0.0.1:8188
COMFY_WORKFLOW_TEMPLATE=minimax_h3_t2v_api.json
COMFY_OUTPUT_DIR=/path/to/ComfyUI/output
OUTPUTS_DIR=/path/to/Movie-Agent/outputs
COMFY_MAX_RETRIES=2
VIDEO_GENERATION_MAX_RETRIES=2
PROJECT_MASTER_FPS=24
```

点击页面的“Spark 真实生成”后，应用会逐镜调用固定 API 工作流；每个镜头完成即保存 `project.json`，全部通过质检后显示 `SHOTS READY` 并推进到 `DELIVER`。点击 AI Edit 后按 Picture Cut、Voice、Music、SFX、Subtitles、Mix、Final Encode 顺序生成可预览的 `rough-cut.mp4`，用户确认字幕与声音设计后批准才输出 `final-cut.mp4`。放映室可重新剪辑已批准项目，并通过导出配置接口生成不同容器、分辨率、画幅与字幕模式的交付文件。已通过质检的镜头会在再次点击后跳过；单镜生成或媒体完整性质检失败时，会按 `VIDEO_GENERATION_MAX_RETRIES` 自动重试。远程视频任务使用独立的 request/task timeout，并在首次获得 task_id 后持久化；进程重启时 resume 已提交任务，不会因为轮询失败重新 POST。
