# Movie-Agent 架构说明

```text
用户创意、时长、风格
        │
        ▼
导演 Agent ──► 编剧 Agent ──► 视觉设定 Agent ──► 分镜 Agent
        │                                              │
        └────────────── 创作上下文 ────────────────────┘
                                                       ▼
                                               质量门 / 版权风险检查
                                                       │
                                                       ▼
                                             ProjectStore（project.json）
                                                       │
                        ┌──────────────────────────────┴─────────────────────────────┐
                        ▼                                                            ▼
             当前：mock 生成与剪辑                                      后续：ComfyUI + H3 + FFmpeg
```

## 状态边界

- 文本创作可以用 `MODEL_PROVIDER=mock` 或 `MODEL_PROVIDER=modelscope`。
- 项目状态保存在 `projects/<project_id>/project.json`，目录默认不进入 Git。
- 视频生成接口已保留在 `movie_agent/services/comfyui.py`；只有经过人工验证并导出的 ComfyUI API 工作流 JSON 才能进入 `workflows/`。
- 任何模型、媒体、密钥、项目输出均不提交到 Git。

## 可复现约束

1. 所有配置从环境变量读取。
2. 不在代码中写入 API Key、服务器地址或密码。
3. Mock 模式始终可用，用于评审演示、单元测试和无 GPU 环境。
4. 真实视频模式将逐镜生成、质检、重试，最后由 FFmpeg 拼接。
