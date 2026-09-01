"""Gradio entry point for the Movie-Agent MVP."""

from __future__ import annotations

import os

import gradio as gr

from movie_agent.config import Settings
from movie_agent.orchestrator import MovieOrchestrator


settings = Settings.from_env()
orchestrator = MovieOrchestrator(settings)


def create_project(idea: str, duration: int, visual_style: str):
    project = orchestrator.create_project(idea, duration, visual_style)
    return (
        project.project_id,
        project.brief_as_markdown(),
        project.script_as_markdown(),
        project.visual_bible_as_markdown(),
        project.storyboard_as_markdown(),
        project.log_as_markdown(),
        f"已完成 mock 制作流程：{project.project_id}",
        project.final_output_placeholder or "",
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
            submit = gr.Button("开始 mock 制作", variant="primary")
        with gr.Column(scale=2):
            status = gr.Textbox(label="状态", interactive=False)
            project_id = gr.Textbox(label="项目 ID", interactive=False)
            final_output = gr.Textbox(label="成片输出（mock 预留路径）", interactive=False)
            brief = gr.Markdown(label="项目设定")
            script = gr.Markdown(label="剧本与旁白")
            visual_bible = gr.Markdown(label="视觉设定")
            storyboard = gr.Markdown(label="分镜")
            logs = gr.Markdown(label="任务日志")

    submit.click(
        create_project,
        inputs=[idea, duration, visual_style],
        outputs=[project_id, brief, script, visual_bible, storyboard, logs, status, final_output],
    )


if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=settings.port)
