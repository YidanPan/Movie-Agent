# Movie-Agent 项目介绍

## 作品名称

Movie-Agent：从一句原创科幻创意到可审阅的短片制作工作台。

## 创作动机

短片创作常在剧本、分镜、视觉设定、生成和后期之间反复断裂。Movie-Agent
把这些环节组织为可协作的 Agent，并把每次创作决策、资产版本、质检结果和
恢复信息保存为项目状态，方便审阅、恢复和后续交付。

## Agent 分工

- 导演 Agent：把创意转为主题、叙事边界和合规约束。
- 编剧 Agent：生成短剧本、旁白、Dialogue Book 和 Subtitle Track。
- 视觉设定 Agent：建立角色、场景、风格和摄影锁定。
- 分镜 Agent：把故事拆成 6–10 个带时长、动作和镜头提示的结构化镜头。
- 生成 Agent：通过统一 Provider contract 管理 Mock、ComfyUI 或远程视频适配器。
- 质检 Agent：检查结构、时长、提示词、连续性和版权风险。
- 剪辑 Agent：生成 Rough Cut、声音设计、Final Master 和交付导出计划。

## 当前演示模式

当前 ModelScope Studio 使用 Mock-only 配置：文本、图片、视频均不发起真实
生成请求，语音使用 `TTS_PROVIDER=none`。演示可以稳定展示规划、分镜、质检、
台词锁定、AI Edit 状态、交付预检、导出档案和恢复路径；Mock placeholder 不会
被宣传为真实视频。真实 Provider 适配器和前置阶段验证结果属于可选架构能力，
并未在当前部署中启用。

## 推荐演示用例

使用原创概念：

> A courier returns to a silent orbital hospital to deliver a letter from her mother.

展示路径：进入片场 → 开机制作 → Crew Assembly → Storyboard / 场记单 → 锁定
Dialogue Book → AI Edit / Rough Cut → Deliver / Final Look → 项目 JSON、Markdown
和 SRT/VTT 导出。整个路径不依赖 paid provider，可在浏览器刷新后恢复项目。

## 技术亮点

FastAPI + SSE、MovieOrchestrator、Provider-neutral video contract、ProjectStore
原子持久化、Job Ledger、provider task identity、asset lineage、QC gate、FFmpeg
后期管线，以及 ModelScope Docker Studio 的 `/mnt/workspace` 持久化部署。

## 复现方式

1. 使用 `.env.example` 创建本地 `.env`，保持 `MODEL_PROVIDER=mock` 和
   `VIDEO_GENERATION_MODE=mock`。
2. 运行 `python server.py`，访问 `http://127.0.0.1:7860`。
3. 输入原创科幻创意，查看 Crew Assembly、Storyboard、Production Bible 和
   Deliver 页面；可恢复项目、查看诊断并导出制作档案。

## 提交边界

本文件描述 Movie-Agent 工程交付，不等同于最终 AI 短片交付。最终短片、录屏、
截图、比赛表单、团队信息和评委访问 private Studio 等事项，须按实际比赛要求
由操作者单独确认。
