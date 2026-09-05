# Movie-Agent

面向 ModelScope「AI + 影视流」比赛的电影 Agent MVP。输入一句原创科幻创意，应用会生成项目设定、短剧本、视觉设定和可供 ComfyUI 执行的结构化分镜。

当前版本为 **mock 规划模式**：不会下载模型、调用 ComfyUI 或生成真实视频。它用于先验证从创意到分镜的完整工作流；后续将在 Spark 上接入 MiniMax-H3、ComfyUI、质检重试和 FFmpeg 剪辑。

## 本地运行

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env
python app.py
```

默认访问地址为 `http://127.0.0.1:9071`。在 Spark 上运行时，通过 `PORT` 调整服务端口；ComfyUI 地址通过 `COMFY_BASE_URL` 配置。

## 项目结构

- `movie_agent/agents`：后续的导演、编剧、分镜、质检等 Agent 实现。
- `movie_agent/services`：外部能力适配层；当前为 mock，后续加入 ComfyUI 与 FFmpeg。
- `workflows/`：后续存放已验证的 ComfyUI API 工作流 JSON 模板。
- `projects/`：运行时项目数据，不纳入 Git。

## 合规

仅使用原创或获授权的素材；不得使用现有影视 IP、角色、台词、片名、真人肖像或未经授权的声音。不要将密码、Token、API Key 或服务器信息提交到仓库。
