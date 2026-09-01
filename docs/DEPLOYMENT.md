# 魔搭创空间部署清单

## 1. 推送代码

将仓库推送到 GitHub。不要提交 `.env`、`models/`、`outputs/` 或 `projects/`。

## 2. 创建创空间

在魔搭创空间新建 Gradio 应用，并导入仓库。入口文件为 `app.py`，依赖文件为 `requirements.txt`。

## 3. 添加 Secrets

在创空间的环境变量 / Secrets 中设置：

```text
MODEL_PROVIDER=modelscope
MODELSCOPE_API_KEY=<仅在创空间后台填写>
MODELSCOPE_API_BASE=https://api-inference.modelscope.cn/v1
MODELSCOPE_MODEL=Qwen/Qwen3-30B-A3B-Instruct-2507
PORT=7860
```

不要把 Key 填进 Git、README、网页日志或项目导出文件。

## 4. 验收

- 应用可以公开打开。
- 输入原创科幻创意后，页面出现项目设定、剧本、视觉卡、6–10 个分镜和任务日志。
- 能打开已保存项目，且可导出 JSON 与 Markdown。
- 无 API Key 时仍可切换为 mock 模式演示。
- 视频能力未就绪时，页面明确标注为 mock 视频流程，不能将占位路径宣传为真实成片。

## 5. Spark 视频模式（后续）

将验证过的 ComfyUI 服务限定为 `127.0.0.1:8188`，由 Movie-Agent 后端调用。前端创空间不直接暴露 Spark 的 ComfyUI 端口或任何凭据。
