"""Rough-cut and final delivery assembly with a mock-safe FFmpeg fallback."""

from __future__ import annotations

import subprocess
import shutil
from pathlib import Path
from typing import Any

from movie_agent.config import Settings
from movie_agent.models import MovieProject
from movie_agent.services.subtitles import (
    normalise_subtitle_mode,
    render_srt,
    render_vtt,
    script_subtitle_track,
)
from movie_agent.services.final_look import final_look_filter, normalise_final_look
from movie_agent.services.media_quality import (
    asset_record,
    best_master_path,
    probe_media,
    target_dimensions,
)


ASPECT_RATIOS = {
    "16:9": {"width": 1920, "height": 1080, "subtitle_margin_v": 60},
    "9:16": {"width": 1080, "height": 1920, "subtitle_margin_v": 120},
    "1:1":  {"width": 1080, "height": 1080, "subtitle_margin_v": 80},
}


class EditorAgent:
    """Keep rough-cut planning separate from final approval.

    A project can therefore be inspected after all shots are ready without
    accidentally presenting a final master. In mock mode the same metadata
    and sidecar exports are produced, while media paths remain placeholders.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @staticmethod
    def _require_locked_dialogue(project: MovieProject) -> None:
        if not bool((project.script or {}).get("dialogue_locked")):
            raise RuntimeError("Please review and lock the dialogue book / subtitle track in the writing stage before entering AI Edit.")

    def _output_dir(self, project: MovieProject) -> Path:
        output_dir = self.settings.outputs_dir / project.project_id
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir

    def _derive_preview(self, project: MovieProject, source: Path, *, tier: str, resolution: str) -> Path | None:
        """Create a bounded preview copy without ever replacing the source master."""

        if not source.is_file():
            return None
        width, height = target_dimensions(resolution)
        metadata = probe_media(source, self.settings.ffprobe_bin)
        output_dir = self._output_dir(project) / "previews"
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = "proxy" if tier == "working_proxy" else "screening"
        output = output_dir / f"{suffix}-{resolution}.mp4"
        source_width = metadata.get("width")
        if isinstance(source_width, int) and source_width <= width:
            # Do not silently upscale a low-res source. The UI will surface the
            # resulting LOW RES SOURCE quality label from the copied asset.
            shutil.copy2(source, output)
            return output
        command = [
            self.settings.ffmpeg_bin,
            "-y",
            "-i",
            str(source),
            "-vf",
            f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast" if tier == "working_proxy" else "fast",
            "-crf",
            "30" if tier == "working_proxy" else "22",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-movflags",
            "+faststart",
            str(output),
        ]
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        if completed.returncode != 0 or not output.is_file():
            output.unlink(missing_ok=True)
            return None
        return output

    def _register_cut_assets(self, project: MovieProject, source: Path, *, include_master: bool) -> None:
        """Persist proxy/screening/master records for the current cut."""

        assets: dict[str, dict[str, Any]] = {}
        proxy = self._derive_preview(project, source, tier="working_proxy", resolution="720p")
        screening = self._derive_preview(
            project,
            source,
            tier="screening_preview",
            resolution=str(project.target_resolution or "1080p"),
        )
        if proxy:
            assets["working_proxy"] = asset_record(
                proxy,
                tier="working_proxy",
                ffprobe_bin=self.settings.ffprobe_bin,
                target_resolution=project.target_resolution,
                source="cut",
            )
        if screening:
            assets["screening_preview"] = asset_record(
                screening,
                tier="screening_preview",
                ffprobe_bin=self.settings.ffprobe_bin,
                target_resolution=project.target_resolution,
                source="cut",
            )
        if include_master and source.is_file():
            assets["final_master"] = asset_record(
                source,
                tier="final_master",
                ffprobe_bin=self.settings.ffprobe_bin,
                target_resolution=project.target_resolution,
                source="final_cut",
            )
        project.video_assets = assets

    def normalize_resolution(self, project: MovieProject, resolution: str = "1080p") -> str:
        """Normalize every generated shot before AI Edit using a true master path.

        This is deliberately opt-in. It uses FFmpeg's deterministic scale/crop
        path today and records ``method=resolution_normalize`` so a future AI
        upscaler can replace the implementation without changing the project
        contract or allowing a proxy to become an export source.
        """

        resolution = str(resolution or project.target_resolution or "1080p").lower()
        width, height = target_dimensions(resolution)
        normalized_dir = self._output_dir(project) / "normalized" / "shots"
        normalized_dir.mkdir(parents=True, exist_ok=True)
        changed = 0
        for shot in project.storyboard:
            source = Path(shot.output_placeholder)
            if not source.is_file():
                continue
            output = normalized_dir / f"shot-{shot.number:02d}-{resolution}.mp4"
            if not output.is_file():
                command = [
                    self.settings.ffmpeg_bin,
                    "-y",
                    "-i",
                    str(source),
                    "-vf",
                    f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}",
                    "-r",
                    str(project.target_fps or 24),
                    "-c:v",
                    "libx264",
                    "-preset",
                    "medium",
                    "-crf",
                    "18",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "192k",
                    "-movflags",
                    "+faststart",
                    str(output),
                ]
                completed = subprocess.run(command, capture_output=True, text=True, check=False)
                if completed.returncode != 0 or not output.is_file():
                    raise RuntimeError(f"Resolution Normalize failed for Shot {shot.number}: {completed.stderr[-400:]}")
            shot.media_assets.setdefault("final_master", {})["original_path"] = str(source)
            shot.media_assets["final_master"] = asset_record(
                output,
                tier="final_master",
                ffprobe_bin=self.settings.ffprobe_bin,
                target_resolution=resolution,
                source="resolution_normalize",
                normalized=True,
            )
            shot.output_placeholder = str(output)
            changed += 1
        if not changed:
            raise RuntimeError("No real shot media is available for Resolution Normalize. Generate the shots first.")
        project.target_resolution = resolution
        project.edit_plan = {
            **(project.edit_plan or {}),
            "resolution_normalize": {
                "status": "READY",
                "method": "resolution_normalize",
                "resolution": resolution,
                "fps": project.target_fps or 24,
                "shots": changed,
            },
        }
        project.logs.append(f"Media Pipeline: Resolution Normalize completed for {changed} shots at {width}×{height} / {project.target_fps or 24}fps.")
        return f"Resolution Normalize: {changed} shots prepared at {resolution.upper()} / {project.target_fps or 24}fps."

    @staticmethod
    def _subtitle_filter(srt_path: Path, aspect: str = "16:9") -> str:
        """Build an FFmpeg subtitles filter with aspect-ratio-aware positioning."""

        config = ASPECT_RATIOS.get(aspect, ASPECT_RATIOS["16:9"])
        margin_v = config["subtitle_margin_v"]
        filter_path = srt_path.resolve().as_posix().replace(":", "\\:")
        return (
            f"subtitles='{filter_path}':force_style="
            f"'FontSize=22,MarginV={margin_v},Alignment=2'"
        )

    def write_subtitle_exports(self, project: MovieProject) -> tuple[Path, Path]:
        """Write canonical SRT/VTT sidecars from the locked subtitle track."""

        output_dir = self._output_dir(project)
        track = script_subtitle_track(project.script)
        srt_path = output_dir / "subtitles.srt"
        vtt_path = output_dir / "subtitles.vtt"
        srt_path.write_text(render_srt(track), encoding="utf-8")
        vtt_path.write_text(render_vtt(track), encoding="utf-8")
        return srt_path, vtt_path

    def _shot_paths(self, project: MovieProject) -> list[Path]:
        return [Path(shot.output_placeholder) for shot in project.storyboard]

    def _materialized_shot_paths(self, project: MovieProject) -> list[Path]:
        """Apply reversible editorial timing operations before concatenation."""

        paths: list[Path] = []
        timing_dir = self._output_dir(project) / "timing"
        for shot in project.storyboard:
            source = Path(shot.output_placeholder)
            native = int(shot.source_duration_seconds or shot.duration_seconds)
            desired = max(1, int(shot.duration_seconds))
            mode = str(shot.timing_mode or "native")
            if mode == "native" and desired == native:
                paths.append(source)
                continue
            timing_dir.mkdir(parents=True, exist_ok=True)
            target = timing_dir / f"shot-{shot.number:02d}-{mode}-{desired}s.mp4"
            if target.is_file():
                paths.append(target)
                continue
            filters: list[str] = []
            if mode == "slow_motion":
                factor = max(1.0, desired / max(0.1, native))
                filters.append(f"setpts={factor:.5f}*PTS")
            elif mode in {"extend", "hold_last_frame"} and desired > native:
                filters.append(f"tpad=stop_mode=clone:stop_duration={desired - native}")
            command = [self.settings.ffmpeg_bin, "-y", "-i", str(source)]
            if filters:
                command.extend(["-vf", ",".join(filters)])
            command.extend([
                "-t", str(desired),
                "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
                str(target),
            ])
            completed = subprocess.run(command, capture_output=True, text=True, check=False)
            if completed.returncode != 0 or not target.is_file():
                raise RuntimeError(f"FFmpeg timing operation failed for Shot {shot.number}: {completed.stderr[-400:]}")
            paths.append(target)
        return paths

    def _concat_media(self, project: MovieProject, output_path: Path) -> Path:
        """Concat verified shot files into a temporary or deliverable MP4."""

        shot_paths = self._shot_paths(project)
        if not shot_paths or not all(path.is_file() for path in shot_paths):
            raise RuntimeError("Cannot concat: some shots have not been generated successfully.")
        shot_paths = self._materialized_shot_paths(project)
        output_dir = self._output_dir(project)
        concat_file = output_dir / "concat.txt"
        concat_file.write_text(
            "".join(f"file '{path.resolve().as_posix()}'\n" for path in shot_paths), encoding="utf-8"
        )
        try:
            command = [
                self.settings.ffmpeg_bin,
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_file),
                "-c",
                "copy",
                str(output_path),
            ]
            completed = subprocess.run(command, capture_output=True, text=True, check=False)
            if completed.returncode != 0:
                command = [
                    self.settings.ffmpeg_bin,
                    "-y",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    str(concat_file),
                    "-c:v",
                    "libx264",
                    "-preset",
                    "medium",
                    "-crf",
                    "18",
                    "-c:a",
                    "aac",
                    "-movflags",
                    "+faststart",
                    str(output_path),
                ]
                completed = subprocess.run(command, capture_output=True, text=True, check=False)
            if completed.returncode != 0:
                raise RuntimeError(f"FFmpeg concat failed: {completed.stderr[-500:]}")
        finally:
            concat_file.unlink(missing_ok=True)
        return output_path

    def _mix_audio(self, project: MovieProject, picture_path: Path) -> Path:
        """Mix any real sound sources into the picture without faking media.

        Mock and AI-generated plans normally have no audio files yet, so the
        picture is returned unchanged. When a user upload or a future audio
        renderer provides ``media_path`` values, this method adds them as
        proper FFmpeg inputs and applies the stored volume / ducking settings.
        """

        if (project.mix_state or {}).get("media_mixed"):
            return picture_path
        sources: list[tuple[str, Path, float]] = []
        for key, track in (project.audio_tracks or {}).items():
            if track.get("enabled") is False:
                continue
            raw_path = track.get("media_path")
            if not raw_path:
                continue
            path = Path(str(raw_path))
            if path.is_file():
                try:
                    gain = float(track.get("volume_db", 0) or 0)
                except (TypeError, ValueError):
                    gain = 0.0
                sources.append((str(key), path, gain))
        if not sources or not picture_path.is_file():
            return picture_path

        # A lot of generated T2V clips are silent. Add a bounded room-tone
        # source in that case so an uploaded score can still be mixed in.
        probe = subprocess.run(
            [self.settings.ffprobe_bin, "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=index", "-of", "csv=p=0", str(picture_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        base_has_audio = bool(probe.stdout.strip())
        command = [self.settings.ffmpeg_bin, "-y", "-i", str(picture_path)]
        base_index = 0
        if not base_has_audio:
            command.extend([
                "-f", "lavfi",
                "-t", str(max(1, project.duration_seconds)),
                "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
            ])
            base_index = 1
        first_source_index = len([arg for arg in command if arg == "-i"])
        for _, path, _ in sources:
            command.extend(["-stream_loop", "-1", "-i", str(path)])
        filter_parts = [f"[{base_index}:a]anull[base]"]
        mix_labels = ["[base]"]
        music_label = None
        voice_label = None
        for offset, (key, _, gain) in enumerate(sources, start=first_source_index):
            label = f"track{offset}"
            volume_filter = f"volume={10 ** (gain / 20):.5f}"
            if key == "voice":
                # The voice signal feeds both the audible mix and the
                # sidechain detector, so split it before ducking Music.
                voice_label = f"{label}_sidechain"
                filter_parts.append(
                    f"[{offset}:a]{volume_filter},asplit=2[{label}][{voice_label}]"
                )
            else:
                filter_parts.append(f"[{offset}:a]{volume_filter}[{label}]")
            if key == "music":
                music_label = label
            mix_labels.append(f"[{label}]")
        if music_label and project.smart_ducking.get("enabled"):
            ducked = "music_ducked"
            sidechain = f"[{voice_label}]" if voice_label else f"[{base_index}:a]"
            filter_parts.append(
                f"[{music_label}]{sidechain}sidechaincompress=threshold=0.03:ratio=8:attack=0.12:release=0.42[{ducked}]"
            )
            # Replace the music input in the final mix with its ducked version.
            mix_labels = [label for label in mix_labels if label != f"[{music_label}]"] + [f"[{ducked}]"]
        filter_parts.append("".join(mix_labels) + f"amix=inputs={len(mix_labels)}:duration=first:dropout_transition=2[mix]")
        mixed_path = picture_path.with_name(f"{picture_path.stem}.mixed.mp4")
        command.extend([
            "-filter_complex", ";".join(filter_parts),
            "-map", "0:v:0",
            "-map", "[mix]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            "-movflags", "+faststart",
            str(mixed_path),
        ])
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        if completed.returncode != 0 or not mixed_path.is_file():
            mixed_path.unlink(missing_ok=True)
            return picture_path
        picture_path.unlink(missing_ok=True)
        mixed_path.replace(picture_path)
        project.mix_state["media_mixed"] = True
        return picture_path

    def _rough_cut_plan(self, project: MovieProject) -> dict[str, Any]:
        tracks = project.audio_tracks or {}
        return {
            "status": "rough_cut",
            "pipeline": ["picture_cut", "voice", "music", "sfx", "subtitles", "mix", "final_encode"],
            "sequence": [
                {
                    "shot": shot.number,
                    "source_duration_seconds": shot.source_duration_seconds or shot.duration_seconds,
                    "desired_duration_seconds": shot.duration_seconds,
                    "timing_mode": shot.timing_mode,
                    "trim": {"in_seconds": 0, "out_seconds": shot.duration_seconds},
                    "transition": "cut" if shot.number == 1 else "crossfade_6f",
                }
                for shot in project.storyboard
            ],
            "audio": {
                "tracks": {
                    key: {
                        "status": value.get("status"),
                        "enabled": value.get("enabled", True),
                        "volume_db": value.get("volume_db", 0),
                        "source": value.get("source", ""),
                    }
                    for key, value in tracks.items()
                },
                "smart_ducking": project.smart_ducking or {},
                "music_brief": project.music_brief or {},
            },
            "subtitles": {
                "enabled": normalise_subtitle_mode(project.subtitle_mode) != "none",
                "mode": normalise_subtitle_mode(project.subtitle_mode),
                "source": "locked subtitle track",
            },
        }

    def _mux_soft_subtitles(self, rough_path: Path, srt_path: Path, final_cut: Path) -> bool:
        """Try to package the subtitle track as a selectable MP4 subtitle stream."""

        command = [
            self.settings.ffmpeg_bin,
            "-y",
            "-i",
            str(rough_path),
            "-i",
            str(srt_path),
            "-map",
            "0",
            "-map",
            "1:0",
            "-c",
            "copy",
            "-c:s",
            "mov_text",
            "-metadata:s:s:0",
            "language=eng",
            "-movflags",
            "+faststart",
            str(final_cut),
        ]
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        return completed.returncode == 0 and final_cut.is_file()

    def create_rough_cut(self, project: MovieProject) -> str:
        """Build an editable Rough Cut, never a final delivery master."""

        self._require_locked_dialogue(project)
        project.subtitle_mode = normalise_subtitle_mode(project.subtitle_mode)
        project.script["subtitle_mode"] = project.subtitle_mode
        self.write_subtitle_exports(project)
        project.edit_plan = self._rough_cut_plan(project)
        rough_path = self._output_dir(project) / "rough-cut.mp4"
        if all(path.is_file() for path in self._shot_paths(project)):
            self._concat_media(project, rough_path)
            self._mix_audio(project, rough_path)
            project.rough_cut_placeholder = str(rough_path)
            self._register_cut_assets(project, rough_path, include_master=False)
            return "Editor Agent: Rough Cut complete. Picture Cut, Voice, Music, SFX, Subtitles, and Mix are ready."
        project.rough_cut_placeholder = f"outputs/{project.project_id}/rough-cut.mp4"
        return "Editor Agent: Rough Cut simulated. Four-track audio design and subtitle plan are ready; preview available once real shot media exist."

    def assemble_mock(self, project: MovieProject) -> str:
        """Create the mock final-delivery placeholder after explicit approval."""

        self._require_locked_dialogue(project)
        project.subtitle_mode = normalise_subtitle_mode(project.subtitle_mode)
        project.script["subtitle_mode"] = project.subtitle_mode
        self.write_subtitle_exports(project)
        project.final_output_placeholder = f"outputs/{project.project_id}/final-cut.mp4"
        project.edit_plan = {**(project.edit_plan or {}), "status": "final_approved", "approved": True}
        return f"Editor Agent: Mock final cut approved (subtitle mode: {project.subtitle_mode}; four-track mix confirmed)."

    def assemble(self, project: MovieProject, subtitle_mode: str | None = None) -> str:
        """Render the final master from locked dialogue and the selected subtitle mode."""

        self._require_locked_dialogue(project)
        project.subtitle_mode = normalise_subtitle_mode(subtitle_mode or project.subtitle_mode)
        project.script["subtitle_mode"] = project.subtitle_mode
        srt_path, _ = self.write_subtitle_exports(project)
        output_dir = self._output_dir(project)
        rough_path = output_dir / "rough-cut.mp4"
        if not rough_path.is_file():
            self._concat_media(project, rough_path)
        self._mix_audio(project, rough_path)
        final_cut = output_dir / "final-cut.mp4"

        if project.subtitle_mode == "burned":
            # Burn-in is best-effort because font packages differ between the
            # local machine and Spark. A clean concat fallback still leaves
            # the canonical SRT sidecar available for review.
            command = [
                self.settings.ffmpeg_bin,
                "-y",
                "-i",
                str(rough_path),
                "-vf",
                self._subtitle_filter(srt_path),
                "-c:v",
                "libx264",
                "-c:a",
                "aac",
                "-movflags",
                "+faststart",
                str(final_cut),
            ]
            completed = subprocess.run(command, capture_output=True, text=True, check=False)
            if completed.returncode != 0:
                self._concat_media(project, final_cut)
        elif project.subtitle_mode == "soft":
            # Prefer a selectable MP4 subtitle stream while keeping canonical
            # SRT/VTT sidecars available for external players and delivery.
            if not self._mux_soft_subtitles(rough_path, srt_path, final_cut):
                self._concat_media(project, final_cut)
        else:
            # none mode delivers the clean picture and retains exports for
            # users who want to add subtitles later.
            self._concat_media(project, final_cut)
        project.final_output_placeholder = str(final_cut)
        self._register_cut_assets(project, final_cut, include_master=True)
        project.edit_plan = {**(project.edit_plan or {}), "status": "final_approved", "approved": True}
        return f"Editor Agent: Assembled {len(project.storyboard)} shots with FFmpeg (subtitle mode: {project.subtitle_mode})."

    def apply_final_look(self, project: MovieProject, look: dict[str, Any], source_path: Path) -> Path | None:
        """Render an applied whole-film look when a real Final Cut exists."""

        source = Path(source_path)
        if not source.is_file():
            return None
        video_filter = final_look_filter(look)
        if video_filter == "null":
            return source
        output_dir = self._output_dir(project)
        revision = max(1, int((look or {}).get("revision", 1) or 1))
        output = output_dir / f"final-look-v{revision}.mp4"
        command = [
            self.settings.ffmpeg_bin,
            "-y",
            "-i",
            str(source),
            "-vf",
            video_filter,
            "-map",
            "0:v:0",
            "-map",
            "0:a?",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            str(output),
        ]
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        if completed.returncode != 0 or not output.is_file():
            output.unlink(missing_ok=True)
            return None
        project.video_assets["final_master"] = asset_record(
            output,
            tier="final_master",
            ffprobe_bin=self.settings.ffprobe_bin,
            target_resolution=project.target_resolution,
            source="final_look",
        )
        return output

    def export_variant(
        self,
        project: MovieProject,
        *,
        container: str = "mp4",
        resolution: str = "1080p",
        aspect: str = "16:9",
        subtitle_mode: str = "burned",
    ) -> Path:
        """Encode a selectable delivery variant from the approved Final Master.

        Screening previews and working proxies are intentionally excluded from
        this path. The saved Final Look is applied to the master source unless
        that exact source is already the rendered look. Mock projects
        deliberately fail here because their placeholder paths are not media
        files.
        """

        self._require_locked_dialogue(project)
        if not str(project.status).startswith("completed"):
            raise RuntimeError("Please complete and approve the final cut before exporting a delivery variant.")
        container = str(container).lower().strip()
        resolution = str(resolution).lower().strip()
        aspect = str(aspect).strip()
        subtitle_mode = normalise_subtitle_mode(subtitle_mode)
        if container not in {"mp4", "mov", "webm"}:
            raise ValueError("Container format must be MP4, MOV, or WebM.")
        if resolution not in {"720p", "1080p"}:
            raise ValueError("Resolution must be 720p or 1080p.")
        if aspect not in {"16:9", "9:16", "1:1"}:
            raise ValueError("Aspect ratio must be 16:9, 9:16, or 1:1.")
        output_dir = self._output_dir(project)
        rough_path = output_dir / "rough-cut.mp4"
        # Exports are always sourced from the final-master contract. A
        # screening preview or working proxy can never silently become a
        # delivery source.
        source = best_master_path(project)
        if source is None:
            final_path = Path(project.final_output_placeholder or "")
            source = final_path if final_path.is_file() else (rough_path if rough_path.is_file() else None)
        if source is None or not source.is_file():
            raise RuntimeError("The Final Cut has not been rendered to a real video file yet; cannot export.")
        look = normalise_final_look(project.final_look or {})
        look_media = Path(str(look.get("media_path") or ""))
        look_already_on_source = bool(
            look.get("applied")
            and look_media.is_file()
            and look_media.resolve() == source.resolve()
        )
        look_filter = "null" if look_already_on_source else final_look_filter(look)

        base_height = 1080 if resolution == "1080p" else 720
        ratio_config = ASPECT_RATIOS.get(aspect, ASPECT_RATIOS["16:9"])
        scale = base_height / ratio_config["height"]
        width = int(round(ratio_config["width"] * scale))
        height = base_height
        source_metadata = probe_media(source, self.settings.ffprobe_bin)
        if (
            isinstance(source_metadata.get("width"), int)
            and isinstance(source_metadata.get("height"), int)
            and (source_metadata["width"] < width or source_metadata["height"] < height)
        ):
            actual = f"{source_metadata['width']}×{source_metadata['height']}"
            raise RuntimeError(
                f"LOW RES SOURCE ({actual}) cannot produce a {resolution.upper()} {aspect} Final Master. "
                "Run AI Upscale / Resolution Normalize before exporting."
            )
        scale_filter = f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}"
        srt_path, _ = self.write_subtitle_exports(project)
        output_path = output_dir / f"final-{resolution}-{aspect.replace(':', 'x')}-{subtitle_mode}.{container}"

        command = [self.settings.ffmpeg_bin, "-y", "-i", str(source)]
        if subtitle_mode == "soft":
            command.extend(["-i", str(srt_path)])
        command.extend(["-map", "0:v:0", "-map", "0:a?"])
        if subtitle_mode == "soft":
            command.extend(["-map", "1:0"])
        video_filters = [scale_filter]
        if look_filter != "null":
            video_filters.append(look_filter)
        if subtitle_mode == "burned":
            video_filters.append(self._subtitle_filter(srt_path, aspect))
        command.extend(["-vf", ",".join(video_filters)])

        if container in {"mp4", "mov"}:
            command.extend(["-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k"])
            if subtitle_mode == "soft":
                command.extend(["-c:s", "mov_text", "-metadata:s:s:0", "language=eng"])
            command.extend(["-movflags", "+faststart"])
        else:
            command.extend(["-c:v", "libvpx-vp9", "-crf", "32", "-b:v", "0", "-c:a", "libopus"])
            if subtitle_mode == "soft":
                command.extend(["-c:s", "webvtt", "-metadata:s:s:0", "language=eng"])
        command.append(str(output_path))
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        if completed.returncode != 0 or not output_path.is_file():
            raise RuntimeError(f"Export failed: {completed.stderr[-700:]}")
        return output_path
