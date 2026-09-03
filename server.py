"""AI 片场前端服务：FastAPI + SSE，复用 MovieOrchestrator 的完整能力。

本地或 Spark 上运行：
    python server.py
然后访问 http://127.0.0.1:9071（端口跟随 PORT 环境变量）。

创空间仍以 app.py（Gradio）作为保底入口；本服务提供完整的三幕式体验。
"""

from __future__ import annotations

import asyncio
import json
import mimetypes
import re
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError, field_validator

from movie_agent.config import Settings
from movie_agent.orchestrator import MovieOrchestrator
from movie_agent.services.subtitles import render_srt, render_vtt, script_subtitle_track

settings = Settings.from_env()
orchestrator = MovieOrchestrator(settings)

STATIC_DIR = Path(__file__).parent / "static"
render_lock = threading.Lock()

app = FastAPI(title="Movie-Agent · AI 片场")


@app.middleware("http")
async def prevent_stale_frontend_cache(request: Request, call_next):
    """Keep the single-page console and its assets in sync after deployments."""
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["Pragma"] = "no-cache"
    return response


class CreateProjectPayload(BaseModel):
    idea: str = Field(min_length=10, max_length=2_000)
    duration: int = Field(ge=30, le=80)
    visual_style: str = Field(min_length=2, max_length=80)

    @field_validator("idea", "visual_style")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("不能为空。")
        return cleaned


class UpdateShotPayload(BaseModel):
    """Editable fields exposed by the expanded Shot Workspace."""

    duration_seconds: int | None = Field(default=None, ge=1, le=80)
    framing: str | None = Field(default=None, min_length=1, max_length=120)
    image_description: str | None = Field(default=None, min_length=1, max_length=4_000)
    action: str | None = Field(default=None, min_length=1, max_length=2_000)
    sound_design: str | None = Field(default=None, min_length=1, max_length=2_000)
    generation_mode: str | None = Field(default=None, min_length=1, max_length=20)
    prompt: str | None = Field(default=None, min_length=1, max_length=12_000)

    @field_validator("framing", "image_description", "action", "sound_design", "generation_mode", "prompt")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("不能保存空文本。")
        return cleaned


class UpdateDialoguePayload(BaseModel):
    """Editable writer output kept separate from visual shot fields."""

    dialogue_book: list[dict[str, Any]] = Field(default_factory=list, max_length=20)
    subtitle_track: list[dict[str, Any]] | None = Field(default=None, max_length=20)


class ApproveEditPayload(BaseModel):
    subtitle_mode: Literal["none", "soft", "burned"] = "burned"


class AudioDesignPayload(BaseModel):
    music_mode: Literal["ai", "library", "upload"] = "ai"
    music_intensity: float | None = Field(default=None, ge=0, le=1)
    smart_ducking: bool = True
    music_asset_name: str = Field(default="", max_length=240)
    track_enabled: dict[str, bool] = Field(default_factory=dict)

    @field_validator("music_asset_name")
    @classmethod
    def strip_asset_name(cls, value: str) -> str:
        return re.split(r"[\\/]", value.strip())[-1][:240] if value else ""


class FinalLookPayload(BaseModel):
    preset: Literal[
        "original",
        "film_narrative",
        "cool_gray_future",
        "dream_surreal",
        "documentary_desaturated",
        "cyber_night",
    ] = "original"
    intensity: float = Field(default=0.72, ge=0, le=1)
    grain: float = Field(default=0, ge=0, le=1)
    vignette: float = Field(default=0, ge=0, le=1)
    highlight_soften: float = Field(default=0, ge=0, le=1)
    scope: Literal["whole_film", "current_scene", "current_shot"] = "whole_film"
    apply: bool = True


class ExportVideoPayload(BaseModel):
    container: Literal["mp4", "mov", "webm"] = "mp4"
    resolution: Literal["720p", "1080p"] = "1080p"
    aspect: Literal["16:9", "9:16", "1:1"] = "16:9"
    subtitle_mode: Literal["none", "soft", "burned"] = "burned"


def sse_chunk(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def project_not_found(project_id: str) -> JSONResponse:
    return JSONResponse({"error": f"找不到项目 {project_id}。"}, status_code=404)


def invalid_project_id(error: ValueError) -> JSONResponse:
    return JSONResponse({"error": str(error)}, status_code=400)


def invalid_payload(error: ValidationError) -> JSONResponse:
    first = error.errors()[0]
    field = "、".join(str(part) for part in first.get("loc", ()))
    return JSONResponse(
        {"error": f"提交内容不正确：{field} {first.get('msg', '无效')}"}, status_code=400
    )


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
    except ValueError as error:
        return invalid_project_id(error)  # type: ignore[return-value]


@app.post("/api/projects/stream")
async def create_project_stream(request: Request) -> StreamingResponse:
    try:
        payload = CreateProjectPayload.model_validate(await request.json())
    except (ValidationError, ValueError) as error:
        if isinstance(error, ValidationError):
            return invalid_payload(error)  # type: ignore[return-value]
        return JSONResponse({"error": "请求必须是合法 JSON。"}, status_code=400)  # type: ignore[return-value]

    def work(emit: Callable[[dict], None]) -> None:
        project = orchestrator.create_project(
            payload.idea, payload.duration, payload.visual_style, event_callback=emit
        )
        emit({"type": "done", "project": project.to_dict()})

    return run_with_sse(request, work)


@app.patch("/api/projects/{project_id}/script")
async def update_script(project_id: str, request: Request):
    try:
        payload = UpdateDialoguePayload.model_validate(await request.json())
    except (ValidationError, ValueError) as error:
        if isinstance(error, ValidationError):
            return invalid_payload(error)
        return JSONResponse({"error": "请求必须是合法 JSON。"}, status_code=400)
    try:
        project = orchestrator.update_dialogue(
            project_id,
            dialogue_book=payload.dialogue_book,
            subtitle_track=payload.subtitle_track,
        )
    except FileNotFoundError:
        return project_not_found(project_id)
    except ValueError as error:
        return JSONResponse({"error": str(error)}, status_code=400)
    return project.to_dict()


@app.post("/api/projects/{project_id}/script/lock")
def lock_script(project_id: str):
    try:
        project = orchestrator.lock_dialogue(project_id)
    except FileNotFoundError:
        return project_not_found(project_id)
    except ValueError as error:
        return JSONResponse({"error": str(error)}, status_code=400)
    return project.to_dict()


@app.post("/api/projects/{project_id}/script/unlock")
def unlock_script(project_id: str):
    try:
        project = orchestrator.unlock_dialogue(project_id)
    except FileNotFoundError:
        return project_not_found(project_id)
    except ValueError as error:
        return JSONResponse({"error": str(error)}, status_code=400)
    return project.to_dict()


@app.post("/api/projects/{project_id}/edit/stream")
async def create_rough_cut_stream(project_id: str, request: Request) -> StreamingResponse:
    try:
        raw_payload = await request.json()
        payload = AudioDesignPayload.model_validate(raw_payload or {})
    except (ValidationError, ValueError):
        payload = AudioDesignPayload()
    try:
        orchestrator.store.load(project_id)
    except FileNotFoundError:
        return project_not_found(project_id)
    except ValueError as error:
        return invalid_project_id(error)

    def work(emit: Callable[[dict], None]) -> None:
        with render_lock:
            def on_progress(description: str) -> None:
                try:
                    snapshot = orchestrator.store.load(project_id).to_dict()
                except Exception:  # noqa: BLE001 - snapshot is best-effort
                    snapshot = None
                emit({"type": "edit_progress", "description": description, "project": snapshot})

            project = orchestrator.create_rough_cut(
                project_id,
                progress_callback=on_progress,
                music_mode=payload.music_mode,
                music_intensity=payload.music_intensity,
                smart_ducking=payload.smart_ducking,
                music_asset_name=payload.music_asset_name,
                track_enabled=payload.track_enabled,
            )
            emit({"type": "done", "project": project.to_dict()})

    return run_with_sse(request, work)


@app.patch("/api/projects/{project_id}/audio/design")
async def update_audio_design(project_id: str, request: Request):
    try:
        payload = AudioDesignPayload.model_validate(await request.json())
    except (ValidationError, ValueError) as error:
        if isinstance(error, ValidationError):
            return invalid_payload(error)
        return JSONResponse({"error": "请求必须是合法 JSON。"}, status_code=400)
    try:
        project = orchestrator.set_audio_design(
            project_id,
            music_mode=payload.music_mode,
            music_intensity=payload.music_intensity,
            smart_ducking=payload.smart_ducking,
            music_asset_name=payload.music_asset_name,
            track_enabled=payload.track_enabled,
        )
    except FileNotFoundError:
        return project_not_found(project_id)
    except ValueError as error:
        return JSONResponse({"error": str(error)}, status_code=400)
    return project.to_dict()


@app.patch("/api/projects/{project_id}/final-look")
async def update_final_look(project_id: str, request: Request):
    try:
        payload = FinalLookPayload.model_validate(await request.json())
    except (ValidationError, ValueError) as error:
        if isinstance(error, ValidationError):
            return invalid_payload(error)
        return JSONResponse({"error": "请求必须是合法 JSON。"}, status_code=400)
    try:
        with render_lock:
            project = orchestrator.set_final_look(
                project_id,
                preset=payload.preset,
                intensity=payload.intensity,
                grain=payload.grain,
                vignette=payload.vignette,
                highlight_soften=payload.highlight_soften,
                scope=payload.scope,
                apply=payload.apply,
            )
    except FileNotFoundError:
        return project_not_found(project_id)
    except ValueError as error:
        return JSONResponse({"error": str(error)}, status_code=400)
    except RuntimeError as error:
        return JSONResponse({"error": str(error)}, status_code=409)
    return project.to_dict()


@app.post("/api/projects/{project_id}/audio/tracks/{track_key}/regenerate")
def regenerate_audio_track(project_id: str, track_key: str):
    try:
        project = orchestrator.regenerate_audio_track(project_id, track_key)
    except FileNotFoundError:
        return project_not_found(project_id)
    except ValueError as error:
        return JSONResponse({"error": str(error)}, status_code=400)
    return project.to_dict()


@app.post("/api/projects/{project_id}/audio/upload")
async def upload_music(project_id: str, request: Request):
    """Accept a raw browser audio upload without requiring multipart extras.

    The client sends the file bytes with an X-Filename header. Keeping this
    endpoint small makes it usable on Spark and leaves the eventual audio
    renderer free to replace the stored source.
    """

    try:
        project = orchestrator.store.load(project_id)
    except FileNotFoundError:
        return project_not_found(project_id)
    filename = Path(request.headers.get("x-filename", "uploaded-score")).name
    filename = re.sub(r"[^\w.\- ]+", "_", filename).strip(" .") or "uploaded-score"
    if len(filename) > 120:
        filename = filename[-120:]
    body = await request.body()
    if not body:
        return JSONResponse({"error": "上传文件为空。"}, status_code=400)
    if len(body) > 120 * 1024 * 1024:
        return JSONResponse({"error": "音频文件不能超过 120MB。"}, status_code=413)
    audio_dir = settings.outputs_dir / project_id / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    target = audio_dir / filename
    target.write_bytes(body)
    project = orchestrator.set_audio_design(
        project_id,
        music_mode="upload",
        smart_ducking=bool((project.smart_ducking or {}).get("enabled", True)),
        music_asset_name=filename,
    )
    project.audio_tracks.setdefault("music", {})["preview_url"] = f"/api/projects/{project_id}/audio/tracks/music"
    project.audio_tracks["music"]["media_path"] = str(target)
    project.audio_tracks["music"]["status"] = "FILE READY"
    project.logs.append(f"声音设计 Agent：已接收用户上传配乐 {filename}。")
    orchestrator.store.save(project)
    return project.to_dict()


@app.post("/api/projects/{project_id}/edit/approve")
async def approve_edit(project_id: str, request: Request):
    try:
        payload = ApproveEditPayload.model_validate(await request.json())
    except (ValidationError, ValueError) as error:
        if isinstance(error, ValidationError):
            return invalid_payload(error)
        return JSONResponse({"error": "请求必须是合法 JSON。"}, status_code=400)
    try:
        project = orchestrator.approve_edit(project_id, payload.subtitle_mode)
    except FileNotFoundError:
        return project_not_found(project_id)
    except ValueError as error:
        return JSONResponse({"error": str(error)}, status_code=400)
    except RuntimeError as error:
        return JSONResponse({"error": str(error)}, status_code=502)
    return project.to_dict()


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
    except ValueError as error:
        return invalid_project_id(error)

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


@app.patch("/api/projects/{project_id}/shots/{shot_number}")
async def update_shot(project_id: str, shot_number: int, request: Request):
    try:
        payload = UpdateShotPayload.model_validate(await request.json())
    except (ValidationError, ValueError) as error:
        if isinstance(error, ValidationError):
            return invalid_payload(error)
        return JSONResponse({"error": "请求必须是合法 JSON。"}, status_code=400)
    try:
        project = orchestrator.store.load(project_id)
        if not 1 <= shot_number <= len(project.storyboard):
            raise ValueError(f"镜头号必须在 1–{len(project.storyboard)} 之间。")
        shot = project.storyboard[shot_number - 1]
        updates = {
            key: value
            for key, value in payload.model_dump(exclude_unset=True).items()
            if value is not None
        }
        for key, value in updates.items():
            setattr(shot, key, value)
        project.logs.append(f"场记：已保存镜头 {shot_number} 的 Inspector 编辑。")
        orchestrator.store.save(project)
    except FileNotFoundError:
        return project_not_found(project_id)
    except ValueError as error:
        return JSONResponse({"error": str(error)}, status_code=400)
    return project.to_dict()


@app.post("/api/projects/{project_id}/shots/{shot_number}/render")
def render_single_shot(project_id: str, shot_number: int):
    if settings.video_generation_mode != "comfyui":
        return JSONResponse(
            {"error": "当前为 mock 模式。请在 Spark 的 .env 设置 VIDEO_GENERATION_MODE=comfyui 后再生成镜头。"},
            status_code=400,
        )
    try:
        with render_lock:
            project = orchestrator.render_shot(project_id, shot_number)
    except FileNotFoundError:
        return project_not_found(project_id)
    except ValueError as error:
        return JSONResponse({"error": str(error)}, status_code=400)
    except Exception as error:  # noqa: BLE001 - surface generation failures to the inspector
        return JSONResponse({"error": str(error)}, status_code=502)
    return project.to_dict()


@app.get("/api/projects/{project_id}/export/json")
def export_json(project_id: str):
    try:
        paths = orchestrator.store.export(project_id)
    except FileNotFoundError:
        return project_not_found(project_id)
    except ValueError as error:
        return invalid_project_id(error)
    return FileResponse(paths[0], filename=f"{project_id}-project.json", media_type="application/json")


@app.get("/api/projects/{project_id}/export/markdown")
def export_markdown(project_id: str):
    try:
        paths = orchestrator.store.export(project_id)
    except FileNotFoundError:
        return project_not_found(project_id)
    except ValueError as error:
        return invalid_project_id(error)
    return FileResponse(
        paths[1], filename=f"{project_id}-movie-plan.md", media_type="text/markdown"
    )


def _load_project_or_http(project_id: str):
    try:
        return orchestrator.store.load(project_id)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=f"找不到项目 {project_id}。") from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get("/api/projects/{project_id}/subtitles.srt")
def subtitles_srt(project_id: str):
    project = _load_project_or_http(project_id)
    return Response(
        content=render_srt(script_subtitle_track(project.script)).encode("utf-8"),
        media_type="application/x-subrip; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{project_id}-subtitles.srt"'},
    )


@app.get("/api/projects/{project_id}/subtitles.vtt")
def subtitles_vtt(project_id: str):
    project = _load_project_or_http(project_id)
    return Response(
        content=render_vtt(script_subtitle_track(project.script)).encode("utf-8"),
        media_type="text/vtt",
        headers={"Content-Disposition": f'attachment; filename="{project_id}-subtitles.vtt"'},
    )


def _resolve_final_video(project_id: str) -> Path:
    try:
        project = orchestrator.store.load(project_id)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=f"找不到项目 {project_id}。") from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    path = Path(project.final_output_placeholder or "")
    if not path.is_file():
        raise HTTPException(status_code=404, detail="成片尚未生成。")
    return path


def _resolve_rough_cut(project_id: str) -> Path:
    project = _load_project_or_http(project_id)
    path = Path(project.rough_cut_placeholder or "")
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Rough Cut 尚未生成真实视频文件。")
    return path


def _resolve_shot_video(project_id: str, shot_number: int) -> Path:
    try:
        project = orchestrator.store.load(project_id)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=f"找不到项目 {project_id}。") from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
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


@app.post("/api/projects/{project_id}/export/video")
async def export_video(project_id: str, request: Request):
    """Encode a user-selected delivery variant from the approved cut."""

    try:
        payload = ExportVideoPayload.model_validate(await request.json())
    except (ValidationError, ValueError) as error:
        if isinstance(error, ValidationError):
            return invalid_payload(error)
        return JSONResponse({"error": "请求必须是合法 JSON。"}, status_code=400)
    try:
        project = orchestrator.store.load(project_id)
        with render_lock:
            path = orchestrator.editor.export_variant(project, **payload.model_dump())
    except FileNotFoundError:
        return project_not_found(project_id)
    except ValueError as error:
        return JSONResponse({"error": str(error)}, status_code=400)
    except RuntimeError as error:
        return JSONResponse({"error": str(error)}, status_code=409)
    media_types = {"mp4": "video/mp4", "mov": "video/quicktime", "webm": "video/webm"}
    return FileResponse(path, filename=path.name, media_type=media_types[payload.container])


@app.get("/api/projects/{project_id}/rough-cut")
def rough_cut_video(project_id: str):
    return FileResponse(_resolve_rough_cut(project_id), media_type="video/mp4")


@app.head("/api/projects/{project_id}/rough-cut")
def rough_cut_video_head(project_id: str):
    _resolve_rough_cut(project_id)
    return Response(status_code=200)


@app.get("/api/projects/{project_id}/shots/{shot_number}/video")
def shot_video(project_id: str, shot_number: int):
    return FileResponse(_resolve_shot_video(project_id, shot_number), media_type="video/mp4")


@app.head("/api/projects/{project_id}/shots/{shot_number}/video")
def shot_video_head(project_id: str, shot_number: int):
    _resolve_shot_video(project_id, shot_number)
    return Response(status_code=200)


@app.get("/api/projects/{project_id}/audio/tracks/{track_key}")
def audio_track_preview(project_id: str, track_key: str):
    """Stream an uploaded/generated track when a real media path exists."""

    project = _load_project_or_http(project_id)
    track = (project.audio_tracks or {}).get(str(track_key).lower()) or {}
    raw_path = track.get("media_path")
    if not raw_path:
        raise HTTPException(status_code=404, detail="该音轨尚未生成可试听的音频文件。")
    path = Path(raw_path).resolve()
    allowed_root = (settings.outputs_dir / project_id).resolve()
    if allowed_root not in path.parents or not path.is_file():
        raise HTTPException(status_code=404, detail="该音轨试听文件不存在。")
    media_type = mimetypes.guess_type(path.name)[0] or "audio/mpeg"
    return FileResponse(path, media_type=media_type, filename=path.name)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=settings.port)
