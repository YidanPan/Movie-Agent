# Movie-Agent

面向 ModelScope「AI + 影视流」创作的电影 Agent：从一句原创科幻创意出发，协同完成项目设定、剧本、视觉规范、可渲染分镜和成片交付。

面向 ModelScope「AI + 影视流」比赛的电影 Agent MVP。输入一句原创科幻创意，应用会生成项目设定、短剧本、按镜头拆分的台词本/字幕轨、视觉设定和可供 ComfyUI 执行的结构化分镜。

默认是 **mock 制作模式**：不会调用 ComfyUI 或下载模型，但会完整模拟“规划 → 镜头生成 → 质检 → AI Edit 粗剪 → 最终批准”的状态流，并保存每个镜头的任务状态。Spark 上将 `VIDEO_GENERATION_MODE=comfyui` 后，页面会逐镜提交已验证的 MiniMax-H3 工作流；所有镜头通过质检后先进入 `6/6 SHOTS READY`，由用户启动 AI Edit Rough Cut，再选择字幕模式并批准最终 FFmpeg 成片。

## 工作流

`MovieOrchestrator` 负责共享状态和任务顺序；导演、编剧、分镜、视觉设定、生成、质检和剪辑均为独立 Agent。流程支持实时事件推送、项目断点保存和单镜头重试：

`创意输入 → 导演定调 → Scene Beats → English Screenplay + Dialogue/Narration Lock → Visual Bible / Continuity Lock → Storyboard → 逐镜生成 → Continuity QC → 6/6 SHOTS READY → Picture Cut → Continuous Voice → Music → SFX → Subtitles → Mix → Final Encode`

编剧 Agent 会在剧本完成时同步生成按镜头拆分的 `dialogue_book` 与 `subtitle_track`。用户可在“剧本与旁白”页逐镜编辑并锁定；锁定前不会启动 AI Edit，后续配音、字幕和剪辑只读取这版内容。字幕默认开启，项目可导出 SRT/VTT，并在最终批准时选择无字幕、软字幕（MP4 可选字幕轨 + SRT/VTT）或烧录字幕。

整片语言由 `FILM_LANGUAGE` 控制，默认值为 `en`。影片中的对白、旁白、字幕、片名卡、片尾、屏幕文字和所有生成 Prompt 均以 English 为准；界面仍可保持中文/双语。Storyboard 先生成 Scene Beats，每个镜头保存 `Narrative Purpose / Starting State / Main Action / Character Reaction / Ending State / Transition Hook`，并只提交相对上一镜的 `Shot Delta`。Visual Bible 会生成可复用的 `Character Lock / Scene Lock / Cinematography Lock / reference_seed`，Continuity QC 会标记 `STYLE_DRIFT / CHARACTER_DRIFT / SCENE_DRIFT`，明显失控的镜头不会进入 Final Cut。

时间线编辑不会覆盖原始生成长度：每个 Shot 同时保存 `source_duration_seconds` 与当前 `desired_duration`，支持 `TRIM / EXTEND / HOLD LAST FRAME / SLOW MOTION / REGENERATE`。编辑后的字幕和 Music Emotional Arc 会重新按时间线对齐；真实 FFmpeg 合成会在拼接前执行对应的时长操作。

Deliver 页是 Final Cut Screening Room：项目未剪辑时显示项目摘要与 `N/N SHOTS READY`，AI Edit 进行时展示镜头合成、旁白、字幕、BGM、SFX 和 FFmpeg 编码进度；批准真实成片后才显示播放器、时长/分辨率/画幅/编码/音频元数据与可跳转 Shot Timeline。播放器右侧的 `FINAL LOOK / COLOR FINISH` 是导出前的全片最终润色台：提供原片、胶片叙事、冷灰未来、梦境超现实、纪实去饱和、赛博夜色六种预设，支持强度、颗粒、暗角和高光柔化，点击预设即可在播放器中即时试听；默认锁定 `WHOLE FILM`，点击应用后才写入交付配置。`导出成片` 支持 MP4/MOV/WebM、720P/1080P、16:9/9:16/1:1 和三种字幕模式，默认 MP4 + H.264 + 1080P + 16:9；JSON、制作手册 Markdown 和 SRT/VTT 收纳在 `更多导出`。

视频质量按三层资产管理：`Source` 是模型原始镜头，`Working Proxy` 只服务分镜浏览和编辑响应，`Screening Preview` 用于 Deliver 放映室并优先选择 720P 或 1080P，`Final Master` 是唯一允许进入最终导出的来源。播放器不会通过 CSS scale、blur 或低质量 canvas 二次放大；如果源文件低于目标分辨率，界面会明确显示 `LOW RES SOURCE`。真实镜头进入 Rough Cut 前会自动执行 `Resolution / FPS / SAR / Pixel Format / 48kHz` 标准化（mock 或无法探测的媒体会明确 DEFERRED），保留原始 Source 记录，最终导出仍只读取 Master，不会把 Proxy 当成母版。

### P2 管线可靠性

上游内容现在通过 `movie_agent/services/revisions.py` 做显式依赖失效传播。修改 Shot 的 Prompt、动作、景别或叙事字段会创建新的 Shot revision、计算 `prompt_hash`，并将旧的 Source/QC/Cut/Final Look/Export 指针标记为 `STALE`；旧文件和元数据进入历史记录，不会被直接删除。仅修改时间线时保留原始 Source，重新计算字幕、旁白、情绪曲线和剪辑衍生物。Shot 与 Asset 记录包含 revision、provider、model、seed、created_at、qc_status、source_resolution、source_fps、source_duration 和 stale，便于追溯“哪一次生成导致了变化”。Project JSON 同时记录 `schema_version`、`created_at`、`updated_at` 与失效事件。

服务端渲染和媒体写入使用按项目隔离的锁：同一项目串行，不同项目可并行，不需要额外队列服务。`movie_agent/pipeline/` 提供 planning / rendering / editing / state 的渐进式边界；旧的 `MovieOrchestrator` 与 API 保持兼容。零构建前端继续由 `static/app.js` 提供入口，同时加载 `static/js/` ES Module registry 与 `static/css/` 语义模块，方便后续逐步抽离而不破坏 Spark 直接托管。Crew Radio 只从后端日志和 SSE 事件构造 Agent 名称、时间与状态，不再注入与当前项目无关的固定剧情文案。

### P3 生产可靠性

长任务失败现在会写入结构化的 `error_code`、`error_message`、`stage`、`retry_count`、`recoverable` 和时间戳；SSE 会发送同一份安全错误对象，并尽可能带回失败后的项目快照。错误消息会过滤常见 Token/密码字段，不会把凭据回显到浏览器或日志。Generation、Quality、AI Edit 等阶段可据此区分输入错误、媒体缺失、ComfyUI/Provider 暂时不可用和质检失败，支持有依据地重试。

项目 JSON 仍采用临时文件替换，并在每次成功写入前保留 `project.json.bak`。主快照损坏时 `ProjectStore` 会自动读取最近一次有效备份；主文件和备份均损坏则明确返回恢复错误，不会静默创建空项目。新增 `/api/health` 能力检查（存储、FFmpeg、FFprobe、ModelScope 密钥存在性和 ComfyUI 工作流），`/api/health/ready` 作为部署 readiness probe；检查只返回能力状态，不返回密钥、服务器凭据或内部地址。

媒体交付也遵循 fail-closed：Final Cut 播放器只解析当前、未过期的 `Final Master`，Shot 播放器拒绝 stale revision，Rough Cut 只在真实 Rough Cut 状态下提供。导出接口不再把 Rough Cut、Screening Preview 或 Working Proxy 提升为母版；没有有效 Final Master 时明确拒绝导出，避免低清或旧版本素材被误交付。

### P4 可恢复性与交付预检

`movie_agent/pipeline/diagnostics.py` 提供统一的项目诊断快照：它以持久化项目状态为准，汇总镜头通过/失败/过期数量、台词锁定版本、Source/Proxy/Screening/Final Master 可用性、最近片场日志、脱敏错误和下一步动作。快照不包含媒体路径或凭据，可通过 `GET /api/projects/<project_id>/diagnostics` 查询；普通项目读取也会在 `diagnostics` 字段中携带同一份信息，因此刷新页面后仍能恢复现场，而不是回到空白等待态。

导出前可调用 `GET /api/projects/<project_id>/delivery-preflight`（支持 `resolution`、`aspect`、`subtitle_mode` 查询参数）查看阻塞项和警告。视频导出接口会在编码前执行同一预检：只有已批准的 Final Cut、当前 Final Master、锁定台词本、通过质检的镜头和足够的目标分辨率才能进入编码；Proxy、Screening Preview、过期资产或低清母版不会被悄悄提升为交付源。前端会把失败原因和可恢复动作显示在 Crew Assembly 状态行中。

### P5 断线可恢复任务

渲染、AI Edit 和创作流现在都有持久化 `Job Ledger`。SSE 只是实时视图，任务事件会以脱敏后的游标记录到项目目录；浏览器刷新、SSH 隧道短暂断开或重新打开项目时，可通过 `GET /api/projects/<project_id>/job?after=<cursor>` 读取最近进度。相同项目的重复提交会返回 `409 JOB_ALREADY_RUNNING`，不会并行启动两个互相覆盖的任务。

任务完成或失败后仍保留最近事件、阶段、进度、错误码和恢复状态；服务重启后如果发现旧任务停在 `running`，会标记为 `orphaned / RESUME AVAILABLE`，允许用户按当前项目状态重新提交。Job Ledger 只保存类型、Agent、镜头号、计数和短描述，不保存 Prompt、媒体路径、Token 或项目完整内容。

### 双主题工作状态

顶栏的 `SCREENING / DESK` 切换对应两种制作状态，并不是简单的黑白反转：

- `Screening Room`：暖黑、琥珀金、局部聚光与监视器材质，用于沉浸式制作和审片。
- `Production Desk`：暖白、羊皮纸、深棕黑正文与细线分隔，用于清晰阅读剧本、制作手册和项目档案。

主题由 CSS design tokens 统一管理，切换使用约 520ms 的灯光过渡。首次访问跟随浏览器 `prefers-color-scheme`；用户手动选择后写入 `localStorage` 的 `movie-agent-theme`，刷新或重新打开页面仍会保持选择。

本轮 audit-first 视觉审计、字体角色、材质收敛、动效拨杆和回归清单记录在 [docs/DESIGN_AUDIT.md](docs/DESIGN_AUDIT.md)。

前端动效按生产阶段各自承担一个清晰的电影语义：首页使用 Fresnel 聚光灯开场，并以鼠标距离驱动“剧本文字 → 线稿 → 光影 → 色彩 → 电影帧”的暗房显影；Crew Assembly 用相邻节点的 proximity 受光和交接光点表达 Agent 数据流，分镜墙使用可拖拽、带轻惯性与 scroll-snap 的 Film Strip，并让镜头卡从未曝光线稿逐步显影为 keyframe，镜头媒体以冲印/曝光过渡显影，制作手册使用 editorial reveal，Deliver 使用 Final Look 前后分割与声音时间线。动效默认尊重 `prefers-reduced-motion`，低性能设备会关闭环境光、颗粒和持续动画；交互保留浏览器原生光标，通过卡片、节点和时间线本身提供上下文反馈，避免自定义光标遮挡内容。首页显影底片使用 `static/assets/cinematic-darkroom-frame.webp`，可替换为团队自有的授权视觉素材。

AI Edit 的声音部门是正式的后期模块：导演设定、剧本情绪、视觉风格、镜头节奏和总时长会生成可审阅的 `Music Brief` 与 `Emotional Arc`。配乐支持 `AI 自动配乐`、`素材库音乐`、`用户上传音乐` 三种来源；Deliver 放映室可调整音乐强度并立即保存，用户上传文件会保存到项目输出目录。混音明确拆分为 `Voice / Music / SFX / Ambience` 四轨，每轨均可试听、开关或重新规划；Smart Ducking 会在 Dialogue Book 的语音区间自动降低 Music 并平滑恢复。锁定台词后，AI Edit 会优先用同一 Voice ID/Accent/Rate 一次生成 `outputs/<project>/audio/voice.wav`，以实测音频时长按比例对齐 Dialogue Book 与 SRT/VTT；未配置 `edge-tts` 或其他 provider 时会明确显示 `PROVIDER REQUIRED`，不会伪造音频文件。真实混音使用 48kHz、180ms dropout/crossfade 语义、Smart Ducking、`loudnorm`（-14 LUFS）与 limiter（-1 dBTP），并区分 TARGET 与 MEASURED。

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
- AI Edit 工作流：按 `Picture Cut → Voice → Music → SFX → Subtitles → Mix → Final Encode` 顺序生成可审阅 Rough Cut；用户预览粗剪后再批准最终成片。已交付项目可从放映室重新剪辑并重新生成 Rough Cut。
- 声音设计工作流：生成 Music Brief、BPM/乐器/进入与高潮位置/淡出位置、逐镜情绪曲线；提供 AI、素材库、用户上传三种配乐模式，以及 Voice / Music / SFX / Ambience 四轨、试听、开关、重规划和 Smart Ducking 状态。
- 字幕工作流：编剧阶段审阅/编辑/锁定 Dialogue Book 与 Subtitle Track；支持默认烧录字幕、软字幕和无字幕交付，以及 SRT/VTT 导出。
- Final Look 工作流：仅在 Deliver / Final Cut Screening Room 开放；对真实成片提供六种整片色彩预设、强度与颗粒/暗角/高光柔化控制。浏览器预览不会改变原文件，确认“应用 Final Look”后，真实模式由 FFmpeg 渲染带版本号的润色母版，mock 模式只保存可复现的交付方案，不伪造视频媒体。

## 本地启动

### AI 片场前端（推荐，完整体验）

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python server.py
```

访问 `http://127.0.0.1:9071`。这是「黑场放映室」风格的三幕式界面：第一幕输入创意并开机，第二幕实时观看七位 Agent 剧组成员集结交付，第三幕在分镜墙审阅每个镜头、在制作手册编辑并锁定台词、在监视器看到 `SHOTS READY` 后启动 AI Edit，并在 Final Cut Screening Room 预览 Rough Cut、审片、跳转镜头、选择字幕模式、批准最终成片和导出档案。创作、渲染和粗剪过程通过 SSE 流式推送，进度与镜头状态实时刷新。

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
- `movie_agent/services`：ModelScope、ComfyUI、字幕导出、声音设计、Final Look、FFmpeg、项目质量门等外部能力适配层。
- `workflows/`：存放已验证的 ComfyUI API 工作流 JSON 模板；见其中 README。
- `projects/`：运行时项目数据，不纳入 Git。

## 合规

仅使用原创或获授权的素材；不得使用现有影视 IP、角色、台词、片名、真人肖像或未经授权的声音。不要将密码、Token、API Key 或服务器信息提交到仓库。

## English Documentation

Movie-Agent is a multi-agent film production workspace for the ModelScope “AI + Film/TV” competition. It turns one original science-fiction idea into a production brief, short script, locked dialogue/subtitle assets, visual bible, structured storyboard, generated shots, quality reports, a reviewable Rough Cut, and an approved final delivery.

### Workflow

`Idea → Director → Scene Beats → English Screenplay → Dialogue/Narration Lock → Visual Bible / Continuity Lock → Storyboard → Shot Generation → Continuity QC → SHOTS READY → Picture Cut → Continuous Voice → Music → SFX → Subtitles → Mix → Final Encode`

`MovieOrchestrator` coordinates shared project state and event delivery. Director, writer, storyboard, visual bible, generation, reviewer, and editor are independent modules. Projects are persisted as JSON and can resume from completed shots.

### Modes

- **Mock mode** runs the planning, subtitle, shot, and AI Edit state flow without downloading models or calling ComfyUI. It stops at Rough Cut until the user explicitly approves delivery.
- **ModelScope text mode** uses the OpenAI-compatible ModelScope endpoint for creative planning agents.
- **Spark ComfyUI mode** submits the verified MiniMax-H3 T2V workflow one shot at a time. When every shot passes QA, AI Edit creates a Rough Cut; final FFmpeg assembly happens only after approval.

The writer emits one editable `dialogue_book` and timed `subtitle_track` cue per shot. Users can revise and lock these assets in the screenplay tab. Voiceover, subtitle exports, and AI Edit read the locked revision only. Subtitles are enabled by default, with `none`, `soft` (selectable MP4 track plus SRT/VTT sidecars), and `burned` delivery modes.

`FILM_LANGUAGE` defaults to `en`: all in-film dialogue, narration, subtitles, title cards, credits, monitor text, and generation prompts are English while the UI may remain bilingual. Story Beats are created before the storyboard; every shot carries narrative purpose, start/end state, main action, character reaction, and a transition hook. The Visual Bible becomes a reusable `Character Lock / Scene Lock / Cinematography Lock / reference_seed` contract, and Continuity QC reports `STYLE_DRIFT`, `CHARACTER_DRIFT`, or `SCENE_DRIFT` before a shot can enter Final Cut.

Continuous voice uses `TTS_PROVIDER=edge_tts` and `TTS_VOICE=en-US-GuyNeural` by default. Install the requirements on Spark, then lock the Dialogue Book and start AI Edit (or call `POST /api/projects/<project_id>/audio/tracks/voice/generate`) to render `outputs/<project_id>/audio/voice.wav`. The provider is optional: `TTS_PROVIDER=none` keeps an explicit `PROVIDER REQUIRED` state and never creates placeholder audio.

Editorial timing is separate from native generation timing. Each shot stores `source_duration_seconds` plus the current `desired_duration`, with `TRIM`, `EXTEND`, `HOLD LAST FRAME`, `SLOW MOTION`, and `REGENERATE` operations. FFmpeg applies the timing operation before concatenation, then subtitle cues and the Music Emotional Arc are realigned to the edited timeline. Voice is rendered as one continuous English track with a locked voice profile instead of unrelated per-shot TTS clips; the measured WAV duration is stored with the alignment contract.

Deliver also includes a dedicated `FINAL LOOK / COLOR FINISH` inspector after Final Cut preview and before export. It offers six whole-film presets — Original, Film Narrative, Cool Gray Future, Dream Surreal, Documentary Desat, and Cyber Night — plus intensity, grain, vignette, and highlight-softening controls. Clicking a preset immediately auditions a browser preview; only an explicit Apply action persists the look. Real media is rendered by FFmpeg into a revisioned master, while mock mode stores the reproducible export plan without inventing a video file. Whole-film scope is the default; current-shot/current-scene scope is reserved for a future advanced mode.

Video media follows explicit `Source → Working Proxy → Screening Preview → Final Master` tiers. Working Proxy is disposable and optimized for storyboard/edit responsiveness. Screening Preview is the Deliver viewer copy and prefers 720p or 1080p without silently upscaling a smaller source. Final Master is the only source accepted by the export endpoint, so a proxy can never become a delivery master. The player avoids CSS scaling, blur, and low-quality canvas resizing. Real shot media is normalized to the project resolution, fps, SAR, pixel format, and 48 kHz audio before Rough Cut; when the source is below target, Deliver shows `LOW RES SOURCE` and keeps the original path alongside the normalized master. Final export always reads the master contract.

The editorial encode path keeps the original source untouched, writes an edit mezzanine as ProRes 422 LT when the local FFmpeg build supports it, and falls back to H.264 CRF 13 only for incompatible builds. Timing, picture assembly, audio mix, and Final Look preserve that mezzanine instead of repeatedly generating H.264 CRF 18 intermediates. Working Proxy uses CRF 30, Screening Preview uses CRF 22, and the selected delivery container receives the single final delivery encode.

Visual QC references are persisted in `outputs/<project>/references/reference-bank.json` and copied into the same project-owned reference directory. The reviewer can use approved character/scene references, the previous approved shot's late keyframe, and current-shot keyframes; process memory is not the source of truth. Without a Vision Model, media integrity only moves a shot to `AWAITING_VISUAL_REVIEW`; the shot becomes `APPROVED` only after the `APPROVE SHOT` action, which also promotes that shot's review keyframes into the bank.

### P2 Pipeline Reliability

Upstream edits now pass through `movie_agent/services/revisions.py`. Changing a
shot prompt, action, framing, or narrative field creates a new Shot revision
and `prompt_hash`, marks the old Source/QC/Cut/Final Look/Export pointers as
`STALE`, and keeps their files in history for rollback or comparison. A timing
only edit preserves the source render while recalculating subtitle, voice,
emotional-arc, and editorial derivatives. Shot and asset records expose
revision, provider, model, seed, created_at, qc_status, source_resolution,
source_fps, source_duration, and stale metadata. Project JSON records
`schema_version`, `created_at`, `updated_at`, and invalidation events.

Media mutations use one process-local lock per project: tasks for the same film
remain serialized while unrelated projects can run in parallel. The
`movie_agent/pipeline/` package provides incremental planning, rendering,
editing, and state seams without replacing the JSON store or adding a queue
service. The zero-build frontend keeps `static/app.js` as its compatibility
entry point while loading the `static/js/` ES-module registry and `static/css/`
semantic module boundaries. Crew Radio is derived from backend logs and SSE
events, so it cannot display fixed story copy from another project.

### P3 Production Hardening

Long-running failures now persist structured `error_code`, `error_message`,
`stage`, `retry_count`, `recoverable`, and timestamp metadata. SSE streams emit
the same redacted error object and, when a project already exists, return the
post-failure project snapshot so the UI can explain what happened without
guessing. Common credential fields such as API keys, tokens, passwords, and
secrets are redacted before they reach logs or the browser. Generation, Quality,
AI Edit, and provider failures can therefore be retried with an explicit reason.

`ProjectStore` still writes through a temporary file, and now keeps the last
known-good `project.json.bak` before each replacement. A corrupt primary JSON
automatically falls back to that snapshot; if both files are corrupt, the
service returns an explicit recovery error instead of silently creating an
empty project. `/api/health` exposes non-invasive capability checks for storage,
FFmpeg, FFprobe, ModelScope configuration, and the verified ComfyUI workflow.
`/api/health/ready` is a deployment readiness probe. These endpoints return
booleans only and never expose tokens, credentials, or internal host details.

Delivery media is fail-closed: Final Cut playback resolves only the current,
non-stale `Final Master`, Shot playback rejects stale revisions, and Rough Cut
playback requires a real Rough Cut state. The export endpoint never promotes a
Rough Cut, Screening Preview, or Working Proxy to a delivery master; without a
valid Final Master it rejects the request instead of exporting an old or
low-resolution file.

### P4 Resumability, Diagnostics, and Delivery Preflight

`movie_agent/pipeline/diagnostics.py` now provides one truthful, JSON-safe
project snapshot. It reports canonical pipeline state, shot pass/fail/stale
counts, dialogue-lock revision, Source/Proxy/Screening/Final Master
availability, recent activity, redacted failures, and ordered next actions.
The snapshot contains no media paths or credentials and is available through
`GET /api/projects/<project_id>/diagnostics`; the normal project payload also
includes it, so a browser refresh can restore the production context instead
of showing a blank waiting state.

`GET /api/projects/<project_id>/delivery-preflight` accepts `resolution`,
`aspect`, and `subtitle_mode` query parameters and explains export blockers and
warnings before a long encode starts. The video export endpoint runs the same
preflight contract before invoking FFmpeg: only an approved Final Cut, a
current Final Master, a locked dialogue revision, QC-passed shots, and a
master that meets the requested dimensions may enter delivery encoding. A
Proxy, Screening Preview, stale asset, or low-resolution source is never
silently promoted to a delivery file. The frontend surfaces the next safe
action and the latest redacted failure beside the Crew Assembly status.

### P5 Disconnect-Safe Job Ledger

Planning, Spark rendering, and AI Edit now write a durable `Job Ledger` for
each project. SSE remains the low-latency view, while the redacted event cursor
is persisted under the ignored project directory. After a browser refresh or a
short SSH-tunnel interruption, clients can call
`GET /api/projects/<project_id>/job?after=<cursor>` to recover recent progress.
Submitting the same project twice while a job is active returns
`409 JOB_ALREADY_RUNNING` instead of starting competing workers.

The ledger keeps terminal status, stage, progress, safe error metadata, and a
bounded recent event history. If the service restarts while a job was marked
`running`, the next read reports `orphaned / RESUME AVAILABLE`; retrying from
the current project contract is then explicit. It stores no prompts, media
paths, tokens, or full project payloads.

### Theme system

The compact `SCREENING / DESK` control represents two production states rather than a color inversion:

- **Screening Room** keeps the warm-black, amber-lit console for immersive production and review.
- **Production Desk** uses warm ivory, parchment surfaces, dark brown copy, and precise hairlines for script and archive reading.

Both surfaces consume one CSS design-token vocabulary for backgrounds, text, borders, accents, shadows, and glow. The light cue transitions over about 520ms. Without a manual choice the first visit follows `prefers-color-scheme`; a manual selection is persisted in `localStorage` under `movie-agent-theme`.

The audit-first redesign record, type roles, material rules, motion map, and regression checklist live in [docs/DESIGN_AUDIT.md](docs/DESIGN_AUDIT.md).

The zero-build frontend gives each production stage one signature interaction: the landing page uses a Fresnel opening plus a pointer-proximity darkroom reveal from screenplay glyphs to sketch, light, color, and a cinematic frame; Crew Assembly uses proximity lighting and a handoff signal along the Agent route; Storyboard is a draggable, inertia-assisted Film Strip with scroll snap whose cards develop from linework toward a keyframe; generated media arrives with a film-burn reveal; Production Bible uses an editorial reveal; Deliver uses a Before/After Final Look split with a synced sound timeline. Motion respects `prefers-reduced-motion`; low-performance devices disable ambient light, grain, and continuous animation. The interface keeps the browser-native cursor so contextual lighting never obscures production copy. The landing darkroom frame lives at `static/assets/cinematic-darkroom-frame.webp` and can be replaced with an authorized team asset.

AI Edit includes a formal sound department. The director brief, script emotion, visual style, shot rhythm, and runtime produce a reviewable `Music Brief` and per-shot `Emotional Arc` (style, BPM, instruments, entry, peak, fade-out, and intensity). Music can come from `AI automatic score`, `studio library`, or `user upload`, with a Deliver-side intensity control that persists to the project contract. The mix is always represented as four tracks — `Voice`, `Music`, `SFX`, and `Ambience` — with preview, enable/disable, and regenerate controls. Smart Ducking reads locked Dialogue Book timing, lowers Music during speech, and restores it with an attack/release curve. When `edge-tts` (or an injected Spark VoiceProvider) is configured, the editor writes one continuous English WAV, aligns subtitles to measured duration, and applies FFmpeg loudnorm/limiter plus 180ms dropout crossfade semantics. Without a provider, the project exposes an explicit pending-media state while retaining the complete reviewable sound design plan.

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

Open `http://127.0.0.1:9071`. The FastAPI interface provides the cinematic three-act workspace, SSE progress updates, shot timeline, monitor, screenplay lock/editor, prominent `SHOTS READY → AI Edit` entry point, Rough Cut preview, Final Cut Screening Room, real-video metadata, shot jumping, export presets, subtitle mode selection, premiere flow, and project exports. The Gradio `app.py` fallback also exposes dialogue/subtitle editing and locking, Rough Cut, approval, subtitle mode, and SRT/VTT delivery controls for a Space deployment.

### Configuration and Compliance

For Spark rendering, set `VIDEO_GENERATION_MODE=comfyui` only after ComfyUI, MiniMax-H3 weights, FFmpeg, and the verified workflow have been validated. Store tokens only in `.env` or platform secrets; never commit passwords, tokens, API keys, server credentials, model weights, caches, or media outputs. Use only original or licensed material.
