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
