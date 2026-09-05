# Movie Agent 视觉审计与重构记录

本次改造采用 `design-taste-frontend` 的 audit-first 方法。目标不是把 Movie Agent 变成另一个 SaaS 仪表盘，而是把已有三幕工作流收敛成一套 **Cinematic Operating System**：用户输入创意，剧组接力，分镜显影，最后在放映室完成声音、调色与交付。

## Design Read

这是一个面向电影创作者、参赛评审和技术演示的生产工具重构。视觉语言保留黑金片场气质，吸收编辑部档案、数字场记和剪辑台的秩序感；动效只服务于显影、状态、交接和交付。

## Project dials

| Dial | Value | 用法 |
| --- | ---: | --- |
| `DESIGN_VARIANCE` | `7` | 首页采用非对称片场构图，分镜采用横向 Film Strip，Crew 采用连续生产链。 |
| `MOTION_INTENSITY` | `7` | 首页显影、节点交接、镜头冲印、Final Look 对比使用 lerp / transform / opacity；不堆叠装饰动画。 |
| `VISUAL_DENSITY` | `5` | 生产元数据保持可扫读，长文进入阅读模式，Crew Radio 默认折叠。 |

## Baseline audit

### 保留并强化

- `PLAN / PREVIS / RENDER / DELIVER` 四阶段导航和既有锚点，避免破坏用户熟悉的生产路径。
- 黑金、琥珀金、胶片帧、监视器和制作手册等品牌资产。
- 首页暗房显影、Crew 交接光点、Film Strip 惯性、Storyboard to Video morph、Final Look 前后对比和声音时间线。
- 项目状态、SSE 进度、Crew Radio、字幕锁定和项目恢复等真实生产语义。

### 退休或收敛

- 以 Serif 覆盖产品正文和表单的做法。
- 每个模块都有的外发光、重阴影、backdrop blur 和玻璃卡片。
- 七张等权重卡片、居中式通用 AI Hero、装饰性自定义光标和与状态无关的持续动画。
- 首页重复滚动的剧组跑马灯，收敛为单条静态 Agent 路线索引；实时流动只留在 Crew 交接状态。
- 用模糊或低 opacity 隐藏阅读内容；Production Bible 改为高对比、窄阅读列的 editorial mode。

## Implemented system

### Type roles

- **Serif**：片名、章节标题、制作手册的编辑部标题。
- **Premium Sans**：产品 UI、面板标题、正文、表单、状态和操作标签。
- **Mono**：镜头号、节点号、时间码、规格和系统 metadata。

### Material rules

- 面板使用稳定的语义表面和细边框；默认不发光。
- 局部暖金高光只用于输入聚焦、当前节点、鼠标 proximity、镜头显影和任务交接。
- `Screening Room` 保留克制环境光；`Production Desk` 以羊皮纸、清晰边界和低阴影为主，关闭玻璃模糊，文字不再使用持续光晕。

### Motion rules

| 页面 | 唯一主动态 | 语义 |
| --- | --- | --- |
| 首页 | Cursor proximity darkroom reveal | 一句话从剧本逐层显影为电影帧 |
| Crew Assembly | Agent handoff data flow | 完成状态沿生产线交接 |
| Storyboard | Inertial Film Strip + frame develop | 分镜从线稿变成 keyframe |
| Render | Storyboard to Video morph | 静态分镜被生成成视频 |
| Production Bible | Editorial reveal | 档案章节被打开，正文保持锐利 |
| Deliver | Final Look split + audio playhead | 完成审片、混音、调色和交付 |

所有连续指针数值都经过 `0..1` proximity 映射与 lerp；`prefers-reduced-motion` 和低性能模式会关闭环境光、颗粒和持续动画。

## Regression checklist

- [x] Desktop Hero 为非对称布局，标题、CTA 和暗房画面不互相遮挡。
- [x] Crew Assembly 是 Director 到 Editor 的连续节点路径，Crew Radio 读取真实事件。
- [x] Film Strip 支持 scroll snap、拖拽和轻惯性，Inspector 切换不重复进出动画。
- [x] Production Bible 正文使用 Sans、高对比和有限阅读宽度。
- [x] Deliver 按 `Final Cut → Sound Design → Final Look → Export` 排序，并在没有视频时明确显示缺省态。
- [x] Dark / Light 两套主题共享语义 token，手动选择持久化并支持系统偏好。
- [x] 页面没有自定义光标或大范围背景 blur；媒体区仍保留影院黑作为内容表面。
- [x] `node --check static/app.js`、Python 编译检查和测试套件通过。

## Typography / alignment polish

本轮精修继续沿用 audit-first 原则，只处理三类高频阅读与决策界面：Crew Assembly、Production Bible 和 Deliver。

- 文字角色固定为 Serif（片名与章节）/ Premium Sans（产品界面、剧本、Agent 产出与按钮）/ Mono（镜头号、状态、时间码和技术规格）。有用信息不再依赖低于 0.75 的 opacity，正文默认 15px、行高 1.65–1.8。
- `Screening Room` 使用高亮暖白 `#F0EBE2`、正文 `#C9C1B5`、辅助 `#A49A8D`、metadata `#81776B`；`Production Desk` 使用暖黑 `#352E27`、正文 `#51483E`、辅助 `#71675C`、metadata `#908577`，并以 `#D8D0C3` 作为纸张细边框。
- Crew 节点按 NODE / AGENT / TITLE / STATUS / BODY / IN→OUT 分层，当前状态才获得琥珀高光；已完成状态使用低饱和绿色，等待节点保持清晰灰阶。Crew Radio 改为真实可读的时间、Agent、状态和消息行，移除模糊与文字阴影。
- Production Bible 使用居中的 `min(1180px, calc(100vw - 64px))` 页面壳。Art Department 的视觉卡在内部做受控右移，采用双列 52px 间距；角色、场景、风格和声音对象统一转换为可读键值块，不再直接显示 JSON。
- Shot Detail 的标题、描述、事实字段和 Prompt 重新建立尺寸层级，Prompt 使用稳定的深色技术面 `#26211B` / `#5D4930`，不通过 blur、scale、父级 opacity 制造氛围。
- Deliver 遵循“label 弱、value 强”：技术信息、声音设计、Final Look 和导出状态都提高正文对比度，但保持电影工业风的克制边界。

## Homepage Hero polish

首页 Hero 本轮采用定向演进，不改变全站信息架构：左侧是三拍式创意宣言，右侧是已经通电的电影监视器待机画面。

- 标题节奏改为“把一句话， / 拍成一部 / 电影。”，只让“电影”承担暖金色的落点，减少单纯放大换行造成的生硬感。
- proximity 光源统一由 Hero 的 pointer 坐标驱动，标题、CTA、监视器和背景竖向光纹共享同一组 focus 值。`requestAnimationFrame` 中使用更轻阻尼的 lerp，响应更快但保留回弹重量。
- 监视器新增 `MONITOR STANDBY`、场景、帧号、镜头和 `HOLD FOR SIGNAL` 待机层。即使没有移动鼠标，也保持 15%–25% 的可见信息和轻微场记脉冲；靠近后再逐层显影。
- 桌面 Hero 使用约 52 / 48 的非对称双栏，右侧预览略微上移并扩大，HUD 仍保持底部细线层，不覆盖标题。

## Semantic micro-type system

小字号不再由一套全局 `Mono + 暗灰 + 宽字距` 规则统一处理。页面现在按语义拆成五类：

- `System Metadata`：12px Mono / 600 / 0.055em，用于镜头号、时间、ID、计数和生产路线。
- `UI Label`：14px Sans / 500 / 正常字距，用于字段标题和分组名称。
- `Helper Text`：14px Sans / 400 / 1.62 行高，用于解释、空状态和操作提示。
- `Control Text`：14px Sans / 500 / 正常字距，用于风格预设、导航、按钮和可操作项。
- `Status Text`：14px Sans / 400 / 正常字距，用于引擎、Agent、渲染和交付状态值。

Dark `Screening Room` 与 Light `Production Desk` 共用这套角色，但颜色由主题 token 提供。`text-muted` 仅保留给非必要 metadata，用户需要阅读的正文、字段、控制和状态都提升到 `text-body` 或更高层级。中文界面不再额外拉大字距，英文工业 metadata 才保留适度 Mono tracking。

## Sound Console / Progressive Disclosure

本轮声音设计页不再把 Voice、Music、SFX、Ambience 做成四张等权重参数卡，而是按声音制作的决策顺序重排为：

1. **Music Direction**：先确认来源、风格、BPM、进出点和版本；完整 AI 解释收进默认关闭的 `SHOW NOTES` disclosure。
2. **Emotional Arc**：以每个 Shot 的能量柱呈现情绪走势，作为配乐和剪辑节奏的共同参考。
3. **Sound Timeline**：扩大时间线高度，使用 48 段 waveform、Shot 分段、Subtitle cue、SFX cue marker、Smart Ducking 区间和可移动播放头；不再用斜线纹理模拟“动态”。
4. **Track Mixer**：四条音轨收敛成一组平面列表，保留监听、启停、试听和重新规划；点击一条轨道才打开共享 Inspector，增益、声像和 ducking 等高级参数在此渐进披露。

时间线动效只响应真实媒体语义：播放/暂停驱动 waveform 呼吸，播放器的 `timeupdate` 驱动 playhead 与字幕高亮，Shot/SFX cue 可跳转，Smart Ducking 以绿色区间标出语音让位。`prefers-reduced-motion` 下关闭 waveform 连续动画和 Inspector 入场动画。声音页的排版采用 12–20px 的 Sans / Mono 层级，避免把中文说明压成 9–10px 的低对比 metadata。

Inspector 的 `volume_db`、`pan` 与 `ducking` 通过 `/api/projects/{project_id}/audio/design` 持久化，并在后端限制到安全范围；Music Intensity 会同步更新 Music 轨增益，避免 UI 强度和混音合同脱节。这样声音设计既保持黑金片场气质，也更接近专业但易用的 AI Film Sound Console。

## Production Route / INPUT → PROCESS → OUTPUT

首页下半部分不再用七位 Agent 的纯文本箭头跑马灯，也不让三张阶段卡因为不同宽度形成视觉误导。现在以一条连续的 film ruler / production slate line 组织宏观流程：

1. **01 GREENLIGHT / INPUT**：接收创意、时长和视觉方向，生成可拍摄的 brief。
2. **02 CREW ASSEMBLY / PROCESS**：七位 Agent 收在同一阶段内按 Director → Writer → Art Director → Storyboard → QC → Generation → Editor 接力，产出 Script、Visual、Shot List 和 Quality Gate。
3. **03 DELIVERY / OUTPUT**：把 Final Cut、Music、Subtitle、Final Look 和 Export 收束为交付结果。

三张阶段卡使用相同的列宽、最小高度、内边距和标题基线，外部几何是统一的；内部则分别采用输入规格表、Agent 名单与交付栈，不再复制“标题 + 描述”的 SaaS 卡片模板。`REC / 24 FPS / AI FILM STUDIO / TIMECODE` 继续保留在 Hero HUD，作为整条路线的场记标尺。路线线条与阶段节点保持静态清晰，实时数据流只由 Crew Assembly 页面真实状态驱动。

## Global Header Alignment

Header 现在由固定的 `LEFT / CENTER / RIGHT` 三栏组成：品牌位于左栏，`PLAN / PREVIS / RENDER / DELIVER` 位于中栏，`OFF / DESK / REC` 共享右栏固定轨道。首页仅把中栏设为不可见而不移除轨道，工作区则显示阶段导航；两种状态都不会重新分配右侧控件的位置。右侧按钮使用稳定的最小宽度和统一 36px 高度，窄屏隐藏中栏并保留左右锚点，避免页面切换时发生横向漂移或状态框重叠。

## Production Desk Monitor

Light / `Production Desk` 下的片场监视器采用“纸张工作台中的嵌入式设备”处理：

- `monitor-hardware` 负责浅暖灰设备框体、细 brass 边线和与页面之间的留白；`monitor-screen` 使用 `#28231D` 到 `#242019` 的 warm charcoal 介质面，不再直接贴在暖白面板上。
- 屏幕只保留轻微暗角、扫描纹理和内缘线，避免大面积 blur、外发光与玻璃拟态。`6/6 READY`、`100%`、时间码和状态说明使用独立的高对比 monitor token，确保屏内信息不比页面 metadata 更难读。
- shot 状态条与进度线使用低饱和 brass / moss 色，表达监看设备状态灯而不是游戏 HUD。Spark 真实生成按钮在 disabled 时保持可读文字、去除高光并禁止 pointer，不依赖低 opacity 制造不可用感。
- 监视器下方日志改为默认折叠的 `AGENT ACTIVITY`。摘要持续显示最新三条事件，展开后读取完整 `log-feed`，让监视器保持主视觉而不丢失可审阅的生产记录。

## Quiet workspace / quality disclosure pass

本轮继续保持 `Cinematic Operating System` 的视觉骨架，但把电影感从特效转回信息组织：

- Production Bible 收敛为左侧 Scene / Shot / Character 导航与右侧 Production Document。正文限定阅读宽度，正文使用 Sans，章节标题使用 Serif，SHOT / REV / QC 等工业字段使用 Mono；工作台不再依赖 glow、blur 或卡片阴影制造层级。
- Sound 首屏只保留 Music Direction、Emotional Arc、Timeline 和紧凑 Mix Summary。高级音量、声像、provider、source、alignment 与 loudness 收进 `SHOW MIX CONTROLS`，轨道仍可通过共享 Inspector 展开。
- Deliver 把 Final Cut 作为唯一主角，Final Look 默认保持简洁，Fine Tune 与技术摘要下沉。Quality strip 明确区分 `AUTO / PROXY / SCREENING / ORIGINAL`，同时展示 SOURCE、SCREENING 和 MASTER，低清源直接标记 `LOW RES SOURCE`，不使用 CSS sharpening、scale 或 blur 掩盖 conform 的真实限制。
- Theme 切换继续采用 Screening Room / Production Desk 的 exposure change：布局和内容保持稳定，只有 work light、表面、背景与 ambient 在分层时序内变化，并遵守 `prefers-reduced-motion`。
- 前端 domain logic 已开始从 legacy `static/app.js` 迁移到 `static/js/`：theme、player、storyboard、state、sound、deliver 现在提供实际可调用的模块 API，legacy 层保留 DOM orchestration 和兼容入口，不再保留同一业务函数的第二份实现。
