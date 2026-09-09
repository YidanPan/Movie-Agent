# Movie-Agent 架构说明

```text
用户创意、时长、风格
        │
        ▼
FastAPI / static frontend
        │
        ▼
MovieOrchestrator
        ├── Planning：Director → Writer → Visual Bible → Storyboard
        ├── Generation：Generation Agent → Video Provider
        ├── Quality：Reviewer Agent + planning/continuity gates
        └── Edit / Deliver：Editor Agent → FFmpeg（真实模式）
        │
        ▼
ProjectStore（project.json + Job Ledger）
        │
        ├── 当前部署：Mock providers / truthful degraded state
        └── 可选 Provider：ModelScope text/image、ComfyUI、Remote Video
```

## Agent inventory

| Agent | Responsibility | Input | Output | Stage |
| --- | --- | --- | --- | --- |
| Director Agent | 主题、叙事边界与合规约束 | 原创创意、时长、风格 | 项目 brief | Planning |
| Writer Agent | 剧本、旁白、台词与字幕节奏 | 创意、导演 brief | screenplay、Dialogue Book、Subtitle Track | Planning |
| Visual Bible Agent | 角色、场景、风格与摄影锁定 | brief、剧本 | Visual Bible、continuity locks | Previs |
| Storyboard Agent | 将故事拆为可渲染镜头 | brief、剧本、Visual Bible | 6–10 个结构化 shots | Previs |
| Generation Agent | 调用统一视频 Provider contract | approved shots、provider config | shot state、asset metadata | Render |
| Reviewer Agent | 结构、质量、连续性与版权风险检查 | project、shots、media metadata | QC report、blockers | QC |
| Editor Agent | 粗剪、声音设计、Final Master 与导出 | approved shots、locked dialogue | Rough Cut、Final Master、delivery metadata | Edit / Deliver |

## 状态边界

- 文本创作可以用 `MODEL_PROVIDER=mock` 或 `MODEL_PROVIDER=modelscope`；当前部署使用 mock。
- 项目状态保存在 `projects/<project_id>/project.json`，目录默认不进入 Git。
- 视频生成由 `movie_agent/services/video_generation.py` 的 `VideoGenerationProvider` contract 统一接入。ComfyUI 只是一个 adapter；只有经过人工验证并导出的 ComfyUI API 工作流 JSON 才能进入 `workflows/`。
- 任何模型、媒体、密钥、项目输出均不提交到 Git。

## 可复现约束

1. 所有配置从环境变量读取。
2. 不在代码中写入 API Key、服务器地址或密码。
3. Mock 模式始终可用，用于评审演示、单元测试和无 GPU 环境。
4. 真实视频模式将逐镜生成、质检、重试，最后由 FFmpeg 拼接；当前部署不启用真实 Provider。

## Provider boundary

```text
GenerationAgent
      ↓
VideoGenerationProvider
      ├── MockVideoProvider
      ├── ComfyUIVideoProvider
      └── RemoteVideoProvider
```

镜头状态采用 provider-neutral 的 `generated` / `awaiting_visual_review` /
`approved` 语义，同时读取旧项目中的 `*_comfyui` 别名。只有 approved 且非
stale 的当前 revision 才能进入 AI Edit；generated 媒体可以先播放并等待人工审片。
