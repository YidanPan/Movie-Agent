"""Continuous English voice generation and media-aware subtitle alignment.

The sound department treats narration/dialogue as one editorial voice track,
not as a set of unrelated per-shot TTS clips.  A provider is injected so the
same project contract works with Edge TTS, a Spark-local provider, or a test
double.  When no provider is configured we keep the plan honest and do not
write a fake audio file.
"""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from movie_agent.config import Settings
from movie_agent.services.alignment import PROPORTIONAL, WORD_LEVEL
from movie_agent.services.story_world import canonical_entity_id, world_entities
from movie_agent.services.subtitles import align_script_to_audio, script_subtitle_track
from movie_agent.services.voice_timeline import compose_voice_timeline


class VoiceProvider(Protocol):
    """Provider contract for one continuous synthesis request."""

    def synthesize(self, text: str, output_path: Path, voice_profile: dict[str, Any]) -> Path:
        """Render *text* to *output_path* and return the resulting media path."""


@dataclass(frozen=True)
class VoiceSynthesisResult:
    status: str
    media_path: str | None
    duration_seconds: float | None
    method: str
    alignment_method: str
    error: str | None = None
    word_boundaries: list[dict[str, Any]] | None = None


_RESERVED_SPEAKERS = {"NARRATOR", "SYSTEM"}
_DEFAULT_SPEAKER_VOICES = ("en-US-GuyNeural", "en-US-JennyNeural", "en-US-AriaNeural", "en-US-DavisNeural")


def _speaker_text(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")


def resolve_speaker_id(project: Any, entry: dict[str, Any] | None) -> str:
    """Map display names and aliases to a canonical Story World speaker ID."""

    item = entry if isinstance(entry, dict) else {}
    explicit = str(item.get("character_id") or item.get("speaker_id") or "").strip()
    raw = explicit or str(item.get("speaker") or "NARRATOR").strip()
    if raw.upper() in _RESERVED_SPEAKERS:
        return raw.upper()
    world = getattr(project, "story_world", {}) or {}
    for entity in world_entities(world, "characters"):
        entity_id = str(entity.get("character_id") or "").strip()
        name = str(entity.get("name") or "").strip()
        aliases = {entity_id.casefold(), name.casefold(), _speaker_text(name).casefold()}
        if raw.casefold() in aliases or explicit.casefold() in aliases:
            return entity_id or canonical_entity_id(raw, fallback="speaker", index=0)
    return canonical_entity_id(raw, fallback="speaker", index=0)


def locked_voice_text(project: Any) -> str:
    """Return the locked English dialogue/narration in screenplay order."""

    script = getattr(project, "script", {}) or {}
    policies = script.get("speech_policy_by_shot") or {}
    if policies and all(str(value).upper() in {"SILENT", "AMBIENCE_ONLY"} for value in policies.values()):
        return ""
    entries = script.get("dialogue_book") or script_subtitle_track(script)
    lines: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        text = str(entry.get("text") or entry.get("dialogue") or "").strip()
        if not text or text.lower() == "(silence)":
            continue
        # Speaker labels are metadata, not words to be spoken by the narrator.
        lines.append(text)
    if lines:
        return " ".join(lines)
    return str(script.get("narration") or script.get("story") or "").strip()


def ensure_voice_cast(project: Any) -> dict[str, dict[str, Any]]:
    """Persist stable speaker-to-voice identities without requiring cloning."""

    base = dict(getattr(project, "voice_profile", {}) or {})
    existing = dict(getattr(project, "voice_cast", {}) or {})
    cast: dict[str, dict[str, Any]] = {}
    for key, profile in existing.items():
        canonical = str(key).upper() if str(key).upper() in _RESERVED_SPEAKERS else _speaker_text(key)
        if canonical:
            cast[canonical] = dict(profile or {})
    entries = ((getattr(project, "script", {}) or {}).get("dialogue_book") or [])
    speakers = {resolve_speaker_id(project, item) for item in entries if isinstance(item, dict)}
    speakers.add("NARRATOR")
    custom_voice_ids = base.get("voice_ids") if isinstance(base.get("voice_ids"), list) else []
    voice_ids = [str(value) for value in custom_voice_ids if str(value).strip()] or list(_DEFAULT_SPEAKER_VOICES)
    for index, speaker in enumerate(sorted(speakers)):
        explicit_profile = dict(cast.get(speaker) or {})
        profile = dict(explicit_profile)
        profile = {**base, **profile}
        if "voice_id" not in explicit_profile:
            profile["voice_id"] = base.get("voice_id") if speaker == "NARRATOR" and base.get("voice_id") else voice_ids[index % len(voice_ids)]
        profile.setdefault("fallback", "NARRATOR")
        profile["speaker"] = speaker
        cast[speaker] = profile
    project.voice_cast = cast
    return cast


def _dialogue_entries(project: Any) -> list[dict[str, Any]]:
    entries = ((getattr(project, "script", {}) or {}).get("dialogue_book") or [])
    return [
        dict(item, speaker_id=resolve_speaker_id(project, item))
        for item in entries
        if isinstance(item, dict) and str(item.get("text") or item.get("dialogue") or "").strip() not in {"", "(silence)"}
    ]


def _assemble_multispeaker_wav(rendered: dict[str, Path], entries: list[dict[str, Any]], output_path: Path) -> Path:
    """Interleave per-speaker performances in screenplay order without per-shot TTS."""

    handles: dict[str, tuple[wave._wave_params, bytes, int]] = {}
    for speaker, path in rendered.items():
        with wave.open(str(path), "rb") as source:
            params = source.getparams()
            frames = source.readframes(source.getnframes())
            handles[speaker] = (params, frames, source.getnframes())
    if not handles:
        raise RuntimeError("No speaker voice tracks were rendered.")
    first_params = next(iter(handles.values()))[0]
    if any(params.nchannels != first_params.nchannels or params.sampwidth != first_params.sampwidth or params.framerate != first_params.framerate for params, _, _ in handles.values()):
        raise RuntimeError("Multi-speaker providers must return matching WAV formats.")
    words_by_speaker: dict[str, int] = {}
    for entry in entries:
        speaker = str(entry["speaker_id"])
        words_by_speaker[speaker] = words_by_speaker.get(speaker, 0) + max(1, len(str(entry.get("text") or "").split()))
    consumed: dict[str, int] = {speaker: 0 for speaker in rendered}
    output = bytearray()
    frame_width = first_params.nchannels * first_params.sampwidth
    for entry in entries:
        speaker = str(entry["speaker_id"])
        params, frames, frame_count = handles[speaker]
        count = max(1, round(frame_count * max(1, len(str(entry.get("text") or "").split())) / max(1, words_by_speaker[speaker])))
        start = consumed[speaker]
        end = min(frame_count, start + count)
        output.extend(frames[start * frame_width:end * frame_width])
        consumed[speaker] = end
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(output_path), "wb") as target:
        target.setparams(first_params._replace(nframes=len(output) // frame_width))
        target.writeframes(bytes(output))
    return output_path


def _audio_duration(path: Path, ffprobe_bin: str = "ffprobe") -> float | None:
    """Probe a media duration, with a WAV fallback for test/local providers."""

    if not path.is_file():
        return None
    command = [
        ffprobe_bin,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(path),
    ]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        payload = json.loads(completed.stdout or "{}")
        raw = (payload.get("format") or {}).get("duration")
        if raw is not None:
            value = float(raw)
            if value > 0:
                return round(value, 3)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        pass
    try:
        with wave.open(str(path), "rb") as handle:
            rate = handle.getframerate()
            frames = handle.getnframes()
            if rate:
                return round(frames / float(rate), 3)
    except (OSError, wave.Error, ZeroDivisionError):
        return None
    return None


class EdgeTTSVoiceProvider:
    """Optional Edge TTS provider used when the ``edge-tts`` package exists.

    Edge TTS writes an MP3 stream.  We transcode it to the project's stable
    48 kHz stereo WAV contract so downstream FFmpeg filters have predictable
    sample-rate/channel input.  Importing this class is safe even when the
    optional dependency is not installed.
    """

    def __init__(self, *, ffmpeg_bin: str = "ffmpeg", timeout_seconds: int = 240) -> None:
        self.ffmpeg_bin = ffmpeg_bin
        self.timeout_seconds = max(10, int(timeout_seconds))

    def synthesize(self, text: str, output_path: Path, voice_profile: dict[str, Any]) -> Path:
        if not text.strip():
            raise ValueError("Cannot synthesize an empty voice track.")
        try:
            import edge_tts  # type: ignore[import-not-found]  # optional dependency
        except ImportError as exc:  # pragma: no cover - depends on deployment extras
            raise RuntimeError("edge-tts is not installed; configure a Spark TTS provider or install edge-tts.") from exc

        # Keep the provider call synchronous for the orchestrator and FastAPI
        # worker thread while using the package's async API under the hood.
        import asyncio

        voice = str(voice_profile.get("voice_id") or "en-US-GuyNeural")
        rate = voice_profile.get("speaking_rate", 1.0)
        try:
            rate_value = float(rate)
        except (TypeError, ValueError):
            rate_value = 1.0
        rate_percent = int(round((rate_value - 1.0) * 100))
        rate_arg = f"{rate_percent:+d}%"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="movie-agent-tts-") as temporary_directory:
            mp3_path = Path(temporary_directory) / "voice.mp3"

            async def render() -> None:
                communication = edge_tts.Communicate(text, voice, rate=rate_arg)
                await communication.save(str(mp3_path))

            asyncio.run(render())
            command = [
                self.ffmpeg_bin,
                "-y",
                "-i",
                str(mp3_path),
                "-ar",
                "48000",
                "-ac",
                "2",
                "-c:a",
                "pcm_s16le",
                str(output_path),
            ]
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
                timeout=self.timeout_seconds,
            )
            if completed.returncode != 0 or not output_path.is_file():
                raise RuntimeError(f"Voice normalization failed: {completed.stderr[-500:]}")
        return output_path


class ContinuousVoiceService:
    """Generate one voice asset and align the locked subtitle track to it."""

    def __init__(self, settings: Settings, provider: VoiceProvider | None = None) -> None:
        self.settings = settings
        self.provider = provider

    def synthesize(self, project: Any, provider: VoiceProvider | None = None) -> VoiceSynthesisResult:
        ensure_voice_cast(project)
        script = getattr(project, "script", {}) or {}
        if not bool(script.get("dialogue_locked")):
            raise RuntimeError("Lock the Dialogue Book before generating the continuous voice track.")
        text = locked_voice_text(project)
        if not text:
            result = VoiceSynthesisResult(
                "BYPASSED · NO SPEECH",
                None,
                None,
                "continuous_voice_track",
                "not_applicable",
                None,
            )
            self._persist_result(project, result)
            return result

        active_provider = provider or self.provider
        configured_provider = str(getattr(self.settings, "tts_provider", "edge_tts") or "edge_tts").lower()
        if active_provider is None and configured_provider in {"none", "mock", "disabled", "off"}:
            active_provider = None
        if active_provider is None and configured_provider not in {"none", "mock", "disabled", "off"}:
            # Default to the optional Edge provider, but make a missing
            # dependency an explicit pending state instead of a fake success.
            active_provider = EdgeTTSVoiceProvider(
                ffmpeg_bin=self.settings.ffmpeg_bin,
                timeout_seconds=getattr(self.settings, "tts_timeout_seconds", 240),
            )
        if active_provider is None:
            result = VoiceSynthesisResult(
                "PROVIDER REQUIRED",
                None,
                None,
                "continuous_voice_track",
                "pending_media",
                "TTS_PROVIDER is disabled; configure an English voice provider before rendering.",
            )
            self._persist_result(project, result)
            return result
        output_path = self.settings.outputs_dir / project.project_id / "audio" / "voice.wav"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        word_boundaries: list[dict[str, Any]] = []
        dialogue_entries = _dialogue_entries(project)
        speaker_ids = list(dict.fromkeys(str(item["speaker_id"]) for item in dialogue_entries)) or ["NARRATOR"]
        voice_cast = ensure_voice_cast(project)
        try:
            if len(speaker_ids) == 1:
                rendered_value = active_provider.synthesize(
                    text,
                    output_path,
                    dict(voice_cast.get(speaker_ids[0]) or getattr(project, "voice_profile", {}) or {}),
                )
            else:
                with tempfile.TemporaryDirectory(prefix="movie-agent-speakers-") as temporary_directory:
                    rendered_tracks: dict[str, Path] = {}
                    for speaker in speaker_ids:
                        speaker_text = " ".join(str(item.get("text") or item.get("dialogue") or "").strip() for item in dialogue_entries if item["speaker_id"] == speaker)
                        speaker_path = Path(temporary_directory) / f"{_speaker_text(speaker) or 'speaker'}.wav"
                        rendered_tracks[speaker] = Path(active_provider.synthesize(speaker_text, speaker_path, dict(voice_cast[speaker])))
                    rendered_value = _assemble_multispeaker_wav(rendered_tracks, dialogue_entries, output_path)
            rendered = Path(rendered_value or output_path)
            duration = _audio_duration(rendered, self.settings.ffprobe_bin)
            if duration is None or duration <= 0:
                raise RuntimeError("The voice provider returned media without a measurable duration.")
            result = VoiceSynthesisResult(
                "READY",
                str(rendered),
                duration,
                "continuous_voice_track",
                PROPORTIONAL,
            )
            native = getattr(active_provider, "word_boundaries", None) if len(speaker_ids) == 1 else None
            if native is None and callable(getattr(active_provider, "get_word_boundaries", None)):
                native = active_provider.get_word_boundaries(text, rendered)
            if native:
                word_boundaries = [item for item in native if isinstance(item, (dict, list, tuple))]
                result = VoiceSynthesisResult(
                    result.status,
                    result.media_path,
                    result.duration_seconds,
                    result.method,
                    WORD_LEVEL,
                    word_boundaries=word_boundaries,
                )
        except (OSError, RuntimeError, TypeError, ValueError, subprocess.SubprocessError) as exc:
            output_path.unlink(missing_ok=True)
            result = VoiceSynthesisResult(
                "PROVIDER REQUIRED",
                None,
                None,
                "continuous_voice_track",
                "pending_media",
                str(exc),
            )
        timeline = None
        if result.media_path and result.duration_seconds:
            project.script = align_script_to_audio(
                getattr(project, "script", {}) or {},
                result.duration_seconds,
                word_boundaries=result.word_boundaries,
            )
            timeline = compose_voice_timeline(
                project,
                Path(result.media_path),
                result.duration_seconds,
                ffmpeg_bin=self.settings.ffmpeg_bin,
                word_boundaries=result.word_boundaries,
            )
            timeline_cues = timeline.get("cues") or []
            project.script["dialogue_book"] = timeline_cues
            project.script["subtitle_track"] = timeline_cues
            project.script["voice_timeline"] = {
                "duration_seconds": timeline.get("duration_seconds"),
                "status": timeline.get("status"),
                "overflow": timeline.get("overflow") or [],
            }
            if timeline.get("overflow"):
                result = VoiceSynthesisResult(
                    "SCRIPT_TIMING_REVIEW",
                    result.media_path,
                    result.duration_seconds,
                    result.method,
                    result.alignment_method,
                    result.error,
                    result.word_boundaries,
                )
            result = VoiceSynthesisResult(
                result.status,
                str(timeline.get("media_path") or result.media_path),
                result.duration_seconds,
                result.method,
                result.alignment_method,
                result.error,
                result.word_boundaries,
            )
        self._persist_result(project, result, timeline=timeline)
        return result

    @staticmethod
    def _persist_result(project: Any, result: VoiceSynthesisResult, *, timeline: dict[str, Any] | None = None) -> None:
        track = (getattr(project, "audio_tracks", {}) or {}).setdefault("voice", {})
        track.update(
            {
                "status": result.status,
                "source": "CONTINUOUS ENGLISH VOICE TRACK",
                "generation_strategy": result.method,
                "alignment_method": result.alignment_method,
                "duration_seconds": result.duration_seconds,
                "duration_source": "measured_media" if result.duration_seconds else "pending_provider",
                "provider_error": result.error,
                "timeline_status": (timeline or {}).get("status") if timeline else ("BYPASSED" if result.status == "BYPASSED · NO SPEECH" else None),
                "timeline_duration_seconds": (timeline or {}).get("duration_seconds") if timeline else None,
                "raw_media_path": (timeline or {}).get("raw_media_path") if timeline else None,
                "speaker_ids": sorted((getattr(project, "voice_cast", {}) or {}).keys()),
                "speaker_count": len((getattr(project, "voice_cast", {}) or {})),
            }
        )
        if result.media_path:
            track["media_path"] = result.media_path
            track["preview_url"] = f"/api/projects/{project.project_id}/audio/tracks/voice"
        else:
            track.pop("media_path", None)
            track["preview_url"] = None
        if result.status == "BYPASSED · NO SPEECH":
            project.smart_ducking = {
                **(getattr(project, "smart_ducking", {}) or {}),
                "voice_cues": [],
                "status": "BYPASSED",
                "signal_source": "no_speech",
            }
        if result.duration_seconds:
            script = getattr(project, "script", {}) or {}
            if not timeline:
                script = align_script_to_audio(script, result.duration_seconds, word_boundaries=result.word_boundaries)
                project.script = script
            film_cues = (timeline or {}).get("cues") or script_subtitle_track(script)
            voice_cues = [
                {
                    "shot": entry.get("shot", 0),
                    "start_seconds": entry.get("start_seconds", 0),
                    "end_seconds": entry.get("end_seconds", 0),
                    "timeline_start_seconds": entry.get("timeline_start_seconds", entry.get("start_seconds", 0)),
                    "timeline_end_seconds": entry.get("timeline_end_seconds", entry.get("end_seconds", 0)),
                    "text": entry.get("text", ""),
                }
                for entry in film_cues
                if isinstance(entry, dict) and str(entry.get("text") or "").strip() not in {"", "(silence)"}
            ]
            regions: list[dict[str, float]] = []
            for cue in voice_cues:
                start = float(cue["timeline_start_seconds"] or 0)
                end = float(cue["timeline_end_seconds"] or 0)
                if end <= start:
                    continue
                if regions and start <= regions[-1]["end_seconds"]:
                    regions[-1]["end_seconds"] = max(regions[-1]["end_seconds"], end)
                else:
                    regions.append({"start_seconds": start, "end_seconds": end})
            project.smart_ducking = {
                **(getattr(project, "smart_ducking", {}) or {}),
                "voice_cues": voice_cues,
                "voice_activity_regions": regions,
                "status": "ACTIVE" if (getattr(project, "smart_ducking", {}) or {}).get("enabled", True) else "OFF",
                "signal_source": "continuous_voice_track",
            }
        track["alignment"] = {
            "status": "MEASURED" if result.duration_seconds else "PENDING",
            "media_duration_seconds": result.duration_seconds,
            "method": result.alignment_method,
            "word_level_timestamps": result.alignment_method == WORD_LEVEL,
            "time_domain": "FILM_TIMELINE" if timeline else "VOICE_LOCAL",
        }
        if result.word_boundaries:
            track["alignment"]["word_count"] = len(result.word_boundaries)


def synthesize_continuous_voice(
    project: Any,
    settings: Settings,
    provider: VoiceProvider | None = None,
) -> VoiceSynthesisResult:
    """Functional wrapper used by integrations and small scripts."""

    return ContinuousVoiceService(settings, provider=provider).synthesize(project)


def mark_voice_alignment_stale(project: Any, reason: str = "upstream_timeline_changed") -> None:
    """Mark an existing voice asset for re-alignment without deleting source media."""

    track = (getattr(project, "audio_tracks", {}) or {}).setdefault("voice", {})
    if track.get("media_path") or track.get("duration_seconds"):
        track["status"] = "STALE · REGENERATE"
        alignment = dict(track.get("alignment") or {})
        alignment.update({"status": "STALE", "stale_reason": reason})
        track["alignment"] = alignment
        mix_state = getattr(project, "mix_state", {}) or {}
        mix_state["voice_alignment_status"] = "STALE"
        mix_state["voice_alignment_stale_reason"] = reason
        setattr(project, "mix_state", mix_state)


__all__ = [
    "ContinuousVoiceService",
    "EdgeTTSVoiceProvider",
    "VoiceProvider",
    "VoiceSynthesisResult",
    "locked_voice_text",
    "ensure_voice_cast",
    "mark_voice_alignment_stale",
    "synthesize_continuous_voice",
]
