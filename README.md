# Movie-Agent

面向 ModelScope「AI + 影视流」创作的电影 Agent：从一句原创科幻创意出发，协同完成项目设定、剧本、视觉规范、可渲染分镜和成片交付。

面向 ModelScope「AI + 影视流」比赛的电影 Agent MVP。输入一句原创科幻创意，应用会生成项目设定、短剧本、按镜头拆分的台词本/字幕轨、视觉设定和可供 ComfyUI 执行的结构化分镜。

默认是 **mock 制作模式**：不会调用 ComfyUI 或下载模型，但会完整模拟“规划 → 镜头生成 → 质检 → AI Edit 粗剪 → 最终批准”的状态流，并保存每个镜头的任务状态。Spark 上将 `VIDEO_GENERATION_MODE=comfyui` 后，页面会逐镜提交已验证的 MiniMax-H3 工作流；所有镜头通过质检后先进入 `6/6 SHOTS READY`，由用户启动 AI Edit Rough Cut，再选择字幕模式并批准最终 FFmpeg 成片。

## 工作流

`MovieOrchestrator` 负责共享状态和任务顺序；导演、编剧、分镜、视觉设定、生成、质检和剪辑均为独立 Agent。流程支持实时事件推送、项目断点保存和单镜头重试：

`创意输入 → 导演定调 → 编剧成稿 + 台词本/字幕轨 → 分镜拆解 → 视觉设定 → 逐镜生成 → 关键帧质检 → 6/6 SHOTS READY → AI Edit Rough Cut → 预览/重剪 → 批准交付`

编剧 Agent 会在剧本完成时同步生成按镜头拆分的 `dialogue_book` 与 `subtitle_track`。用户可在“剧本与旁白”页逐镜编辑并锁定；锁定前不会启动 AI Edit，后续配音、字幕和剪辑只读取这版内容。字幕默认开启，项目可导出 SRT/VTT，并在最终批准时选择无字幕、软字幕（MP4 可选字幕轨 + SRT/VTT）或烧录字幕。

## 启用魔搭文本 API

默认 `MODEL_PROVIDER=mock`，不调用外部服务。要启用导演、编剧、分镜和视觉设定的真实文本生成，在 Spark 或魔搭创空间的 `.env` / Secrets 中配置：

```text
MODEL_PROVIDER=modelscope
MODELSCOPE_API_KEY=你的魔搭访问令牌
MODELSCOPE_MODEL=Qwen/Qwen3-30B-A3B-Instruct-2507
```

此阶段会由 ModelScope API 生成文字创作资产；API 客户端只依赖 Python 标准库。真实视频模式要求 Spark 本机 ComfyUI、MiniMax-H3 权重、FFmpeg 与 `workflows/minimax_h3_t2v_api.json` 均已验证。

当前 Spark 已验证的 MiniMax-H3 工作流是 **T2V**。系统在真实渲染模式会只接受 T2V 分镜；I2V / R2V 要等对应工作流接入后再开放，避免把不受支持的镜头提交给错误的节点图。

## 视频质检与原创性审核

规划阶段先执行结构检查、固定 IP 关键词过滤，并在启用 ModelScope 文本创作模式时进行语义版权复核：高风险提案会在渲染前被阻断，中风险会记录明确的改写建议。

真实生成的每一个 MP4 都会按镜头时长抽取 1–5 张关键帧，归档到 `outputs/<project_id>/quality/shot-XX/`。如需把关键帧送入视觉模型，额外配置支持图片输入的 ModelScope 模型：

```text
MODELSCOPE_VISION_MODEL=你的视觉模型标识
VISION_KEYFRAMES_PER_SHOT=3
```

启用后，质检会比较角色、场景与视觉规范，将结论写入同目录的 `review.json`；角色/场景分数低于 70、模型判定失败或发现高版权风险时，该镜头会触发已有的重试机制。未配置视觉模型时，系统不会伪称已完成视觉理解，只会保存关键帧并标注为待人工复核。

## 当前能力

- 导演、编剧、视觉设定、分镜四个独立 Agent；真实 ModelScope 文本模式或离线 mock 模式均可运行。
- 6–10 个结构化分镜：镜头号、时长、景别、画面、动作、声音、生成方式和最终提示词。
- 质量门：检查镜头数、时长、提示词、视觉卡、固定 IP 风险与可选的语义版权风险。
- 视频质检：抽取可追溯关键帧；可选视觉模型复核角色、场景一致性与版权风险。
- 项目自动保存、历史恢复、单镜头重新规划、JSON / Markdown 导出。
- 真实视频模式逐镜同步运行，支持已完成镜头跳过和失败镜头重试；长项目建议先用 mock 模式验证规划结果。
- AI Edit 工作流：自动生成镜头排序、Trim、转场、旁白、BGM、SFX、字幕和 FFmpeg Rough Cut；用户预览粗剪后再批准最终成片。
- 字幕工作流：编剧阶段审阅/编辑/锁定 Dialogue Book 与 Subtitle Track；支持默认烧录字幕、软字幕和无字幕交付，以及 SRT/VTT 导出。

## 本地启动

### AI 片场前端（推荐，完整体验）

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python server.py
```

访问 `http://127.0.0.1:9071`。这是「黑场放映室」风格的三幕式界面：第一幕输入创意并开机，第二幕实时观看七位 Agent 剧组成员集结交付，第三幕在分镜墙审阅每个镜头、在制作手册编辑并锁定台词、在监视器看到 `SHOTS READY` 后启动 AI Edit，并在放映室预览 Rough Cut、选择字幕模式、批准最终成片和导出档案。创作、渲染和粗剪过程通过 SSE 流式推送，进度与镜头状态实时刷新。

### Gradio 简版（创空间保底）

```bash
python app.py
```

创空间部署仍以 `app.py` 为入口（见 docs/DEPLOYMENT.md）；Gradio 保底页也提供台词本编辑/锁定、Rough Cut、字幕模式与 SRT/VTT 导出控制。本地演示、录屏与 Spark 真实生成建议使用 `python server.py`，后者提供完整的 SSE 片场交互。两者共享同一套 orchestrator、项目存档与导出逻辑。

Windows 上启动后访问 `http://127.0.0.1:9071`。其他系统请按其终端语法激活 `.venv`。

## 部署与参赛

完整的魔搭创空间部署步骤、验收清单和创作说明模板见 [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) 与 [docs/CREATION_NOTES.md](docs/CREATION_NOTES.md)。

访问令牌只能放在 `.env` 或创空间密文环境变量中，绝不能提交到 Git。模型通过 OpenAI 兼容的 `https://api-inference.modelscope.cn/v1` 接口调用。

已包含一个安全的 `ComfyUIClient`：它只会提交从 Spark ComfyUI 页面验证并导出的 API 工作流模板，且只能改写配置清单中明确声明的提示词、种子与时长节点。

## 配置速查

| 场景 | 关键配置 |
| --- | --- |
| 离线演示 | `MODEL_PROVIDER=mock`、`VIDEO_GENERATION_MODE=mock` |
| ModelScope 文本创作 | `MODEL_PROVIDER=modelscope`、`MODELSCOPE_API_KEY`、`MODELSCOPE_MODEL` |
| Spark 真实生成 | `VIDEO_GENERATION_MODE=comfyui`、`COMFY_BASE_URL`、已验证的 H3 工作流 |
| 视觉质检 | `MODELSCOPE_VISION_MODEL`、`VISION_KEYFRAMES_PER_SHOT` |

令牌只能放在 `.env` 或平台密文中，不能提交到 Git。默认服务端口是 `9071`，默认 ComfyUI 地址是 `http://127.0.0.1:8188`。

## 项目结构

- `server.py`：AI 片场前端服务（FastAPI + SSE + 静态托管）。
- `static/`：三幕式前端（零构建的 HTML/CSS/JS）。
- `app.py`：创空间 Gradio 保底入口。
- `movie_agent/agents`：导演、编剧、分镜、视觉设定、生成、质检和剪辑 Agent。
- `movie_agent/services`：ModelScope、ComfyUI、字幕导出、FFmpeg、项目质量门等外部能力适配层。
- `workflows/`：存放已验证的 ComfyUI API 工作流 JSON 模板；见其中 README。
- `projects/`：运行时项目数据，不纳入 Git。

## 合规

仅使用原创或获授权的素材；不得使用现有影视 IP、角色、台词、片名、真人肖像或未经授权的声音。不要将密码、Token、API Key 或服务器信息提交到仓库。

## English Documentation

Movie-Agent is a multi-agent film production workspace for the ModelScope “AI + Film/TV” competition. It turns one original science-fiction idea into a production brief, short script, locked dialogue/subtitle assets, visual bible, structured storyboard, generated shots, quality reports, a reviewable Rough Cut, and an approved final delivery.

### Workflow

`Idea → Director → Writer + Dialogue Book → Storyboard → Visual Bible → Shot Generation → Keyframe QA → SHOTS READY → AI Edit Rough Cut → Review/Re-cut → Approve Delivery`

`MovieOrchestrator` coordinates shared project state and event delivery. Director, writer, storyboard, visual bible, generation, reviewer, and editor are independent modules. Projects are persisted as JSON and can resume from completed shots.

### Modes

- **Mock mode** runs the planning, subtitle, shot, and AI Edit state flow without downloading models or calling ComfyUI. It stops at Rough Cut until the user explicitly approves delivery.
- **ModelScope text mode** uses the OpenAI-compatible ModelScope endpoint for creative planning agents.
- **Spark ComfyUI mode** submits the verified MiniMax-H3 T2V workflow one shot at a time. When every shot passes QA, AI Edit creates a Rough Cut; final FFmpeg assembly happens only after approval.

The writer emits one editable `dialogue_book` and timed `subtitle_track` cue per shot. Users can revise and lock these assets in the screenplay tab. Voiceover, subtitle exports, and AI Edit read the locked revision only. Subtitles are enabled by default, with `none`, `soft` (selectable MP4 track plus SRT/VTT sidecars), and `burned` delivery modes.

The currently verified Spark workflow is T2V. I2V and R2V remain disabled until their corresponding workflows are verified.

### Video Quality and Originality Review

Before rendering, the planning quality gate checks structure, duration, prompt completeness, visual cards, and known IP references. When a ModelScope text model is enabled, a semantic copyright reviewer evaluates substantial similarity to existing films, characters, titles, dialogue, and signature settings. High-risk proposals are blocked; medium-risk proposals receive rewrite guidance.

After each real MP4 is generated, the reviewer extracts 1–5 interior keyframes and stores them under `outputs/<project_id>/quality/shot-XX/`. To enable optional multimodal review, configure `MODELSCOPE_VISION_MODEL` and `VISION_KEYFRAMES_PER_SHOT`. The vision reviewer compares character and scene consistency against the visual bible and writes `review.json`. A failed verdict, a score below 70, or high copyright risk triggers the existing shot retry flow. Without a vision model, keyframes are still archived and the result is explicitly marked for human review.

### Quick Start

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# Linux/macOS: source .venv/bin/activate
python -m pip install -r requirements.txt
copy .env.example .env  # Windows; use cp on Linux/macOS
python server.py
```

Open `http://127.0.0.1:9071`. The FastAPI interface provides the cinematic three-act workspace, SSE progress updates, shot timeline, monitor, screenplay lock/editor, prominent `SHOTS READY → AI Edit` entry point, Rough Cut preview, subtitle mode selection, premiere flow, and project exports. The Gradio `app.py` fallback also exposes dialogue/subtitle editing and locking, Rough Cut, approval, subtitle mode, and SRT/VTT delivery controls for a Space deployment.

### Configuration and Compliance

For Spark rendering, set `VIDEO_GENERATION_MODE=comfyui` only after ComfyUI, MiniMax-H3 weights, FFmpeg, and the verified workflow have been validated. Store tokens only in `.env` or platform secrets; never commit passwords, tokens, API keys, server credentials, model weights, caches, or media outputs. Use only original or licensed material.
