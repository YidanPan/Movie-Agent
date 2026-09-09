# Project Description

## Short summary

Movie-Agent 把一句原创科幻创意拆解为可审阅、可恢复、可交付的电影制作流程，并在 ModelScope Studio 中提供安全的 Mock 演示闭环。

## Project description (submission draft)

Movie-Agent 是一个面向 AI 影视创作的多智能体制作工作台。用户从一句原创科幻创意开始，系统先建立项目 brief、世界观与角色约束，再由导演、编剧、视觉设定、分镜、生成、质检和剪辑 Agent 协同推进。每一步都以结构化项目快照、版本、事件日志和质量门保存，支持从中断处恢复，并把对白、字幕、视觉连续性、镜头时长和交付规格纳入同一条生产链。系统采用 FastAPI 后端与原生前端，媒体处理通过 FFmpeg/FFprobe 完成，Provider 适配层隔离 ModelScope 文本/图片能力、ComfyUI 与远程视频任务。当前公开可复现的演示配置为 Mock-only：不消耗真实模型额度，仍能展示规划、分镜审阅、失败闭环、项目恢复和交付检查。部署目标是一个私有 ModelScope Docker Studio，运行数据放在 `/mnt/workspace`，代码和配置边界清晰，便于评审先验证工程可靠性，再由授权环境切换到真实 Provider。项目的核心价值不是替代创作者，而是把创意到交付之间容易丢失的上下文、责任和验证证据固定下来，让复杂创作流程能够被观察、复盘和复现。

## Technical highlights

1. 多 Agent 分工与显式编排：规划、视觉、生成、质检、剪辑职责清晰。
2. P0 级可靠性闭环：幂等键、租约、心跳、事件序列、CAS 写入和可恢复任务状态。
3. 媒体交付契约：区分 Source、Proxy、Preview、Final Master，并用 FFmpeg/FFprobe 做规格验证。
4. Provider 隔离：Mock、ModelScope、ComfyUI 与远程视频任务可独立切换，失败时不伪造成功。
5. 私有 Docker Studio：固定 `0.0.0.0:7860`，`/mnt/workspace` 持久化，健康检查不暴露密钥。

## Agent design concept

系统把电影制作看成一个有状态的协作图，而不是一次性文本生成。Director 负责边界与节奏，Writer 负责故事和对白，Visual Bible 负责角色、场景和风格连续性，Storyboard 负责把叙事转为镜头契约，Generation 只处理已批准的生成任务，Reviewer 检查结构、版权风险和媒体质量，Editor 负责粗剪、字幕、声音与交付。Orchestrator 统一维护项目 revision、任务 ledger 和质量门；任何外部 Provider 只通过适配器进入，结果先验证再晋级。这样既能在 Mock 模式下离线演示全链路，也能在受控环境中逐 Provider 进行真实验收。Agent 之间通过明确的输入输出契约协作，失败会停留在可解释状态，人工可以审阅、修改并继续推进，而不是被隐藏的自动重试带入错误结果。

## Film design concept: 《付费解锁人生》

这是独立的影片创作概念，不等同于当前 `film-f55e58de` 演示候选。故事设定在订阅制社会：记忆、亲情、疼痛和告别都被拆成可购买的功能包，算法根据人的脆弱时刻动态定价。主人公为了保留与家人的最后一段真实关系，发现自己必须先完成一连串“情感增值服务”。影片以冷静的商业界面和逐渐失真的家庭场景形成反差，讨论技术商业化如何把人的经验变成商品，也保留荒诞、讽刺和情感反转。视觉上采用洁净的冷色、重复的价格标签和逐步逼近的构图，让观众感到生活正在被一层层锁定；声音则从顺滑的提示音过渡到家庭对话中的空白，强化“付费后才被允许感受”的悖论。
