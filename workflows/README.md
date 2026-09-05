# ComfyUI 工作流模板

将**在 Spark 的 ComfyUI 中验证通过**的固定 API 工作流放在此目录。

`minimax_h3_t2v_api.json` 是由官方 MiniMax-H3 T2V 模板整理出的静态 API 工作流，已在 Spark 上以 608×352、5 秒、8 steps 的设置生成 MP4。它不包含模型权重或生成结果；运行时只改写清单许可的提示词与随机种子。

不要由 Agent 从零构造 ComfyUI 节点图。每个模板需增加以下 `_movie_agent` 清单；实际提交前，应用会自动移除该清单，只向 ComfyUI 发送原始节点图。

```json
"_movie_agent": {
  "prompt_node": "替换为提示词节点 ID",
  "prompt_field": "text（可选；H3 使用 prompt）",
  "seed_node": "替换为随机种子节点 ID",
  "seed_field": "noise_seed（可选）",
  "duration_node": "可选：替换为时长节点 ID",
  "duration_field": "duration_seconds（可选）",
  "duration_transform": "seconds（可选；H3 使用 minimax_h3_frames）"
}
```

默认提示词字段为 `inputs.text`、种子字段为 `inputs.noise_seed`。若工作流的字段不同，使用 `prompt_field`、`seed_field` 与 `duration_field` 声明。时长节点如启用，默认字段为 `inputs.duration_seconds`；MiniMax-H3 会将秒数对齐到模型的 `17k+5` 帧网格。
