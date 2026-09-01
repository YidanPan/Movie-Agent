"""Gradio entry point for the Movie-Agent MVP."""

from __future__ import annotations

import gradio as gr

from movie_agent.config import Settings
from movie_agent.orchestrator import MovieOrchestrator


settings = Settings.from_env()
orchestrator = MovieOrchestrator(settings)


def create_project(idea: str, duration: int, visual_style: str):
    try:
        project = orchestrator.create_project(idea, duration, visual_style)
    except Exception as error:
        return ("", "", "", "", "", f"## 任务日志\n- 失败：{error}", f"创作失败：{error}", "", gr.update())
    text_mode = "ModelScope AI 文案" if orchestrator.using_creative_llm else "mock 文案"
    return _project_outputs(
        project,
        f"已完成：{text_mode} + mock 视频流程（{project.project_id}）",
        gr.update(choices=orchestrator.store.list_project_ids(), value=project.project_id),
    )


def load_project(project_id: str):
    if not project_id:
        return ("", "", "", "", "", "## 任务日志\n- 请先选择一个项目。", "尚未选择项目", "", gr.update())
    try:
        project = orchestrator.store.load(project_id)
    except Exception as error:
        return ("", "", "", "", "", f"## 任务日志\n- 失败：{error}", f"读取失败：{error}", "", gr.update())
    return _project_outputs(project, f"已恢复项目：{project.project_id}", gr.update(value=project.project_id))


def refresh_history():
    project_ids = orchestrator.store.list_project_ids()
    return gr.update(choices=project_ids, value=project_ids[0] if project_ids else None)


def _project_outputs(project, status_message: str, history_update):
    return (
        project.project_id,
        project.brief_as_markdown(),
        project.script_as_markdown(),
        project.visual_bible_as_markdown(),
        project.storyboard_as_markdown(),
        project.log_as_markdown(),
        status_message,
        project.final_output_placeholder or "",
        history_update,
    )


with gr.Blocks(title="Movie-Agent") as demo:
    gr.Markdown(
        "# Movie-Agent\n"
        "输入一句原创科幻创意，生成可交给 Spark / ComfyUI 执行的电影制作计划。"
    )
    with gr.Row():
        with gr.Column(scale=1):
            idea = gr.Textbox(
                label="原创科幻创意",
                lines=5,
                placeholder="例如：最后一位城市值班员每天点亮空城，直到发现整座城市都在等待他下班。",
            )
            duration = gr.Slider(30, 80, value=48, step=1, label="目标时长（秒）")
            visual_style = gr.Dropdown(
                ["写实近未来", "胶片科幻", "极简冷色", "梦境超现实"],
                value="写实近未来",
                label="视觉风格",
            )
            submit = gr.Button("开始创作", variant="primary")
            gr.Markdown("### 项目历史")
            history = gr.Dropdown(
                choices=orchestrator.store.list_project_ids(), label="已保存项目", interactive=True
            )
            with gr.Row():
                refresh = gr.Button("刷新历史")
                load = gr.Button("打开项目")
        with gr.Column(scale=2):
            status = gr.Textbox(label="状态", interactive=False)
            project_id = gr.Textbox(label="项目 ID", interactive=False)
            final_output = gr.Textbox(label="成片输出（mock 预留路径）", interactive=False)
            brief = gr.Markdown(label="项目设定")
            script = gr.Markdown(label="剧本与旁白")
            visual_bible = gr.Markdown(label="视觉设定")
            storyboard = gr.Markdown(label="分镜")
            logs = gr.Markdown(label="任务日志")

    # Keep creation and history recovery on the same display contract.
    submit.click(
        create_project,
        inputs=[idea, duration, visual_style],
        outputs=[project_id, brief, script, visual_bible, storyboard, logs, status, final_output, history],
    )
    refresh.click(refresh_history, outputs=history)
    load.click(
        load_project,
        inputs=history,
        outputs=[project_id, brief, script, visual_bible, storyboard, logs, status, final_output, history],
    )


if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=settings.port)
