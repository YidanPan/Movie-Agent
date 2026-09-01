"""Editor agent: later replaced by an FFmpeg-backed implementation."""

from movie_agent.models import MovieProject


class EditorAgent:
    def assemble_mock(self, project: MovieProject) -> str:
        project.final_output_placeholder = f"outputs/{project.project_id}/final-cut.mp4"
        return "剪辑 Agent：已模拟合并镜头、字幕和音轨。"
