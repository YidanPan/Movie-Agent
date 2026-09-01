# ComfyUI 工作流模板

将**在 Spark 的 ComfyUI 页面中验证通过**的工作流导出为 API JSON 后放在此目录。

不要由 Agent 从零构造 ComfyUI 节点图。每个模板需增加以下 `_movie_agent` 清单；实际提交前，应用会自动移除该清单，只向 ComfyUI 发送原始节点图。

```json
"_movie_agent": {
  "prompt_node": "替换为提示词节点 ID",
  "seed_node": "替换为随机种子节点 ID",
  "duration_node": "可选：替换为时长节点 ID"
}
```

提示词节点必须包含 `inputs.text`，种子节点必须包含 `inputs.noise_seed`。时长节点如启用，必须包含 `inputs.duration_seconds`。
