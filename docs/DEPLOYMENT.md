# 魔搭创空间部署清单

## 1. 推送代码

将仓库推送到 GitHub。不要提交 `.env`、`models/`、`outputs/` 或 `projects/`。

## 2. 创建创空间

在魔搭创空间新建 Gradio 应用，并导入仓库。入口文件为 `app.py`，依赖文件为 `requirements.txt`。

## 3. 添加 Secrets

在创空间的环境变量 / Secrets 中设置：

```text
MODEL_PROVIDER=modelscope
MODELSCOPE_API_KEY=<仅在创空间后台填写>
MODELSCOPE_API_BASE=https://api-inference.modelscope.cn/v1
MODELSCOPE_MODEL=Qwen/Qwen3-30B-A3B-Instruct-2507
PORT=7860
```

不要把 Key 填进 Git、README、网页日志或项目导出文件。

## 4. 验收

- 应用可以公开打开。
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

### P4 运行诊断与交付预检

部署后可用下面两个只读接口检查一个项目是否能安全继续：

```text
GET /api/projects/<project_id>/diagnostics
GET /api/projects/<project_id>/delivery-preflight?resolution=1080p&aspect=16:9&subtitle_mode=burned
```

`diagnostics` 返回规范化阶段、镜头通过/失败/过期计数、最近日志、脱敏错误和下一步恢复动作；不会返回媒体路径、Token 或主机信息。刷新项目时普通 `GET /api/projects/<project_id>` 也会携带同一份快照。

`delivery-preflight` 会在导出前检查 Final Cut 是否批准、当前 Final Master 是否存在且未过期、台词本是否锁定、镜头是否全部通过质检、目标分辨率是否满足以及 FFmpeg 是否可用。导出接口会重复执行这份检查，失败时返回 `409 DELIVERY_NOT_READY` 和可读的 `blocking_reasons`，避免把 Proxy、Screening Preview 或低清素材误当成交付母版。

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
```

点击页面的“Spark 真实生成”后，应用会逐镜调用固定 API 工作流；每个镜头完成即保存 `project.json`，全部通过质检后显示 `SHOTS READY` 并推进到 `DELIVER`。点击 AI Edit 后按 Picture Cut、Voice、Music、SFX、Subtitles、Mix、Final Encode 顺序生成可预览的 `rough-cut.mp4`，用户确认字幕与声音设计后批准才输出 `final-cut.mp4`。放映室可重新剪辑已批准项目，并通过导出配置接口生成不同容器、分辨率、画幅与字幕模式的交付文件。已通过质检的镜头会在再次点击后跳过；单镜生成或媒体完整性质检失败时，会按 `COMFY_MAX_RETRIES` 自动重试。
