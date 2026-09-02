"""AI 片场前端服务：FastAPI + SSE，复用 MovieOrchestrator 的完整能力。

本地或 Spark 上运行：
    python server.py
然后访问 http://127.0.0.1:9071（端口跟随 PORT 环境变量）。

创空间仍以 app.py（Gradio）作为保底入口；本服务提供完整的三幕式体验。
"""

from __future__ import annotations

import asyncio
import json
import threading
from collections.abc import Callable
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from movie_agent.config import Settings
from movie_agent.orchestrator import MovieOrchestrator

settings = Settings.from_env()
orchestrator = MovieOrchestrator(settings)

STATIC_DIR = Path(__file__).parent / "static"
render_lock = threading.Lock()

app = FastAPI(title="Movie-Agent · AI 片场")


def sse_chunk(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def project_not_found(project_id: str) -> JSONResponse:
    return JSONResponse({"error": f"找不到项目 {project_id}。"}, status_code=404)


def run_with_sse(
    request: Request,
    work: Callable[[Callable[[dict], None]], None],
) -> StreamingResponse:
    """Run a blocking orchestrator call on a worker thread and stream its events."""
    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()

    def emit(payload: dict) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, payload)

    def worker() -> None:
        try:
            work(emit)
        except Exception as error:  # noqa: BLE001 - surface every failure to the stream
            emit({"type": "error", "message": str(error)})

    threading.Thread(target=worker, daemon=True).start()

    async def stream():
        while True:
            if await request.is_disconnected():
                break
            try:
                payload = await asyncio.wait_for(queue.get(), timeout=15.0)
            except asyncio.TimeoutError:
                yield ": keep-alive\n\n"
                continue
            yield sse_chunk(payload)
            if payload.get("type") in {"done", "error"}:
                break

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "text_mode": "modelscope" if orchestrator.using_creative_llm else "mock",
        "video_mode": settings.video_generation_mode,
    }


@app.get("/api/projects")
def list_projects() -> dict:
    return {
        "projects": orchestrator.store.list_project_ids(),
        "text_mode": "modelscope" if orchestrator.using_creative_llm else "mock",
        "video_mode": settings.video_generation_mode,
    }


@app.get("/api/projects/{project_id}")
def get_project(project_id: str) -> dict:
    try:
        return orchestrator.store.load(project_id).to_dict()
    except FileNotFoundError:
        return project_not_found(project_id)  # type: ignore[return-value]


@app.post("/api/projects/stream")
async def create_project_stream(request: Request) -> StreamingResponse:
    body = await request.json()
    idea = str(body.get("idea", ""))
    duration = int(body.get("duration", 48))
    visual_style = str(body.get("visual_style", "写实近未来"))

    def work(emit: Callable[[dict], None]) -> None:
        project = orchestrator.create_project(idea, duration, visual_style, event_callback=emit)
        emit({"type": "done", "project": project.to_dict()})

    return run_with_sse(request, work)


@app.post("/api/projects/{project_id}/render/stream")
async def render_project_stream(project_id: str, request: Request) -> StreamingResponse:
    if settings.video_generation_mode != "comfyui":
        return JSONResponse(
            {"error": "当前为 mock 模式。请在 Spark 的 .env 设置 VIDEO_GENERATION_MODE=comfyui 后再渲染。"},
            status_code=400,
        )
    try:
        orchestrator.store.load(project_id)
    except FileNotFoundError:
        return project_not_found(project_id)

    def work(emit: Callable[[dict], None]) -> None:
        with render_lock:
            def on_progress(completed: int, total: int, description: str) -> None:
                try:
                    snapshot = orchestrator.store.load(project_id).to_dict()
                except Exception:  # noqa: BLE001 - snapshot is best-effort
                    snapshot = None
                emit(
                    {
                        "type": "render_progress",
                        "completed": completed,
                        "total": total,
                        "description": description,
                        "project": snapshot,
                    }
                )

            project = orchestrator.render_project(project_id, progress_callback=on_progress)
            emit({"type": "done", "project": project.to_dict()})

    return run_with_sse(request, work)


@app.post("/api/projects/{project_id}/shots/{shot_number}/regenerate")
def regenerate_shot(project_id: str, shot_number: int):
    try:
        project = orchestrator.regenerate_shot(project_id, shot_number)
    except FileNotFoundError:
        return project_not_found(project_id)
    except ValueError as error:
        return JSONResponse({"error": str(error)}, status_code=400)
    return project.to_dict()


@app.get("/api/projects/{project_id}/export/json")
def export_json(project_id: str):
    try:
        paths = orchestrator.store.export(project_id)
    except FileNotFoundError:
        return project_not_found(project_id)
    return FileResponse(paths[0], filename=f"{project_id}-project.json", media_type="application/json")


@app.get("/api/projects/{project_id}/export/markdown")
def export_markdown(project_id: str):
    try:
        paths = orchestrator.store.export(project_id)
    except FileNotFoundError:
        return project_not_found(project_id)
    return FileResponse(
        paths[1], filename=f"{project_id}-movie-plan.md", media_type="text/markdown"
    )


def _resolve_final_video(project_id: str) -> Path:
    try:
        project = orchestrator.store.load(project_id)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=f"找不到项目 {project_id}。") from error
    path = Path(project.final_output_placeholder or "")
    if not path.is_file():
        raise HTTPException(status_code=404, detail="成片尚未生成。")
    return path


def _resolve_shot_video(project_id: str, shot_number: int) -> Path:
    try:
        project = orchestrator.store.load(project_id)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=f"找不到项目 {project_id}。") from error
    if not 1 <= shot_number <= len(project.storyboard):
        raise HTTPException(status_code=400, detail="镜头号超出范围。")
    path = Path(project.storyboard[shot_number - 1].output_placeholder)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="该镜头视频尚未生成。")
    return path


@app.get("/api/projects/{project_id}/final-video")
def final_video(project_id: str):
    return FileResponse(_resolve_final_video(project_id), media_type="video/mp4")


@app.head("/api/projects/{project_id}/final-video")
def final_video_head(project_id: str):
    _resolve_final_video(project_id)
    return Response(status_code=200)


@app.get("/api/projects/{project_id}/shots/{shot_number}/video")
def shot_video(project_id: str, shot_number: int):
    return FileResponse(_resolve_shot_video(project_id, shot_number), media_type="video/mp4")


@app.head("/api/projects/{project_id}/shots/{shot_number}/video")
def shot_video_head(project_id: str, shot_number: int):
    _resolve_shot_video(project_id, shot_number)
    return Response(status_code=200)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=settings.port)
