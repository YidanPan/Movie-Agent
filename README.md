# Movie-Agent

面向 ModelScope「AI + 影视流」创作的电影策划 Agent：从一句原创科幻创意出发，输出项目设定、剧本、视觉规范、可渲染分镜和可导出的制作计划。

面向 ModelScope「AI + 影视流」比赛的电影 Agent MVP。输入一句原创科幻创意，应用会生成项目设定、短剧本、视觉设定和可供 ComfyUI 执行的结构化分镜。

默认是 **mock 制作模式**：不会调用 ComfyUI 或生成真实视频，但会完整模拟“规划 → 镜头生成 → 质检 → 剪辑”的状态流，并保存每个镜头的任务状态。Spark 上将 `VIDEO_GENERATION_MODE=comfyui` 后，页面的“Spark 真实生成并合成”会逐镜提交已验证的 MiniMax-H3 工作流，保存 MP4 并用 FFmpeg 合片。

## 多 Agent 结构

`MovieOrchestrator` 负责共享状态和任务顺序；每个创作角色均为独立模块：导演、编剧、分镜、视觉设定、生成、质检和剪辑。当前模块使用确定性的 mock 实现，后续会分别接入 LLM、ComfyUI、视觉质检和 FFmpeg。

## 启用魔搭文本 API

默认 `MODEL_PROVIDER=mock`，不调用外部服务。要启用导演、编剧、分镜和视觉设定的真实文本生成，在 Spark 或魔搭创空间的 `.env` / Secrets 中配置：

```text
MODEL_PROVIDER=modelscope
MODELSCOPE_API_KEY=你的魔搭访问令牌
MODELSCOPE_MODEL=Qwen/Qwen3-30B-A3B-Instruct-2507
```

此阶段会由 ModelScope API 生成文字创作资产；API 客户端只依赖 Python 标准库。真实视频模式要求 Spark 本机 ComfyUI、MiniMax-H3 权重、FFmpeg 与 `workflows/minimax_h3_t2v_api.json` 均已验证。

## 当前能力

- 导演、编剧、视觉设定、分镜四个独立 Agent；真实 ModelScope 文本模式或离线 mock 模式均可运行。
- 6–10 个结构化分镜：镜头号、时长、景别、画面、动作、声音、生成方式和最终提示词。
- 质量门：检查镜头数、时长、提示词完整性、视觉卡完整性及预设影视 IP 风险。
- 项目自动保存、历史恢复、单镜头重新规划、JSON / Markdown 导出。
- 真实视频模式逐镜同步运行，首版未提供中途取消或断点续渲染；长项目应先小规模验证。

## 本地启动

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python app.py
```

Windows 上启动后访问 `http://127.0.0.1:9071`。其他系统请按其终端语法激活 `.venv`。

## 部署与参赛

完整的魔搭创空间部署步骤、验收清单和创作说明模板见 [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) 与 [docs/CREATION_NOTES.md](docs/CREATION_NOTES.md)。

访问令牌只能放在 `.env` 或创空间密文环境变量中，绝不能提交到 Git。模型通过 OpenAI 兼容的 `https://api-inference.modelscope.cn/v1` 接口调用。

已包含一个安全的 `ComfyUIClient`：它只会提交从 Spark ComfyUI 页面验证并导出的 API 工作流模板，且只能改写配置清单中明确声明的提示词、种子与时长节点。

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
- `workflows/`：存放已验证的 ComfyUI API 工作流 JSON 模板；见其中 README。
- `projects/`：运行时项目数据，不纳入 Git。

## 合规

仅使用原创或获授权的素材；不得使用现有影视 IP、角色、台词、片名、真人肖像或未经授权的声音。不要将密码、Token、API Key 或服务器信息提交到仓库。
