"""Output integrity checks for generated shots."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from movie_agent.config import Settings
from movie_agent.models import Shot
from movie_agent.services.llm import ModelScopeLLM, build_vision_llm
from movie_agent.services.revisions import ensure_shot_metadata
from movie_agent.services.shot_context import ResolvedShotContext, resolve_shot_context
from movie_agent.storage.reference_bank import ReferenceBankStore


VISUAL_QC_FLAGS = {
    "STYLE_DRIFT",
    "CHARACTER_DRIFT",
    "SCENE_DRIFT",
    "NARRATIVE_STATE_DRIFT",
    "PROP_DRIFT",
}


def normalise_visual_review(review: dict[str, Any] | None) -> dict[str, Any]:
    """Convert legacy reviewer output into the one persisted score schema."""

    raw = review if isinstance(review, dict) else {}
    dimensions = raw.get("dimensions") if isinstance(raw.get("dimensions"), dict) else {}
    legacy_only = not isinstance(raw.get("scores"), dict) and not dimensions
    legacy = {
        "character_identity": raw.get("character_identity", raw.get("character_consistency")),
        "costume": raw.get("costume", raw.get("costume_consistency")),
        "face_hair": raw.get("face_hair", raw.get("face_hair_consistency")),
        "scene_geometry": raw.get("scene_geometry", raw.get("scene_consistency")),
        "props": raw.get("props", raw.get("props_consistency")),
        "palette": raw.get("palette", raw.get("palette_consistency")),
        "lighting": raw.get("lighting", raw.get("lighting_consistency")),
        "camera_language": raw.get("camera_language", raw.get("camera_language_consistency", raw.get("camera_style_consistency"))),
        "film_texture": raw.get("film_texture", raw.get("film_texture_consistency")),
        "narrative_state": raw.get("narrative_state"),
    }
    scores = {}
    for key, value in legacy.items():
        if value is None:
            value = dimensions.get(key)
        if value is None:
            if legacy_only and key in {"palette", "lighting", "camera_language", "film_texture"}:
                value = 100
        if value is None:
            scores[key] = None
            continue
        try:
            scores[key] = max(0, min(100, int(float(value))))
        except (TypeError, ValueError):
            scores[key] = None
    flags = [str(flag).strip().upper() for flag in (raw.get("drift_flags") or []) if str(flag).strip().upper() in VISUAL_QC_FLAGS]
    details = raw.get("drift_details") if isinstance(raw.get("drift_details"), dict) else {}
    return {
        "verdict": str(raw.get("verdict") or "review").strip().lower(),
        "scores": scores,
        "drift_flags": list(dict.fromkeys(flags)),
        "drift_details": details,
        "copyright_risk": str(raw.get("copyright_risk") or "medium").strip().lower(),
        "review_note": str(raw.get("review_note") or "Visual review completed.").strip(),
    }


class ReviewerAgent:
    def __init__(self, settings: Settings, vision_llm: ModelScopeLLM | None = None) -> None:
        self.settings = settings
        self.vision_llm = vision_llm or build_vision_llm(settings)
        self.reference_bank = ReferenceBankStore(settings.outputs_dir)

    @staticmethod
    def _sync_qc_flags(shot: Shot) -> None:
        details = shot.qc_details or {}
        flags: list[str] = []
        for namespace in ("planning", "media", "visual", "manual_review"):
            value = details.get(namespace) or {}
            if isinstance(value, dict):
                flags.extend(str(flag) for flag in (value.get("flags") or []))
        # Rebuild known visual flags from the current visual review only. This
        # lets a later PASS remove a drift flag that an earlier revision set.
        flags.extend(
            str(flag)
            for flag in (shot.qc_flags or [])
            if str(flag).upper() not in VISUAL_QC_FLAGS and str(flag) not in flags
        )
        shot.qc_flags = list(dict.fromkeys(flags))

    def review_mock(self, shot: Shot) -> str:
        ensure_shot_metadata(shot, provider="mock", model="mock-quality-gate")
        shot.status = "approved_mock"
        shot.stale = False
        shot.qc_status = "PASSED_MOCK"
        record = (shot.media_assets or {}).get("source") if isinstance(shot.media_assets, dict) else None
        if isinstance(record, dict):
            record["qc_status"] = shot.qc_status
            record["stale"] = False
        return f"Quality Agent: Shot {shot.number} passed mock consistency and compliance checks."

    def review_generated(
        self,
        shot: Shot,
        *,
        project_id: str | None = None,
        visual_bible: dict[str, str] | None = None,
        previous_shot: Shot | None = None,
        story_world: dict[str, Any] | None = None,
        context: ResolvedShotContext | None = None,
    ) -> str:
        if shot.status != "generated_comfyui":
            raise RuntimeError(f"Shot {shot.number} has not been generated yet; cannot enter quality review.")
        video_path = Path(shot.output_placeholder)
        ensure_shot_metadata(shot, provider="comfyui", model="verified-comfyui-workflow", seed=shot.seed or shot.generation_seed)
        duration = self._video_duration(video_path)
        # Review the native media against the length requested from the video
        # model.  Editorial timing may intentionally trim, extend, hold, or
        # slow the shot later, so ``duration_seconds`` is not the right QC
        # expectation once a timeline edit has been made.
        expected_duration = float(shot.source_duration_seconds or shot.duration_seconds)
        tolerance = max(1.5, expected_duration * 0.25)
        if abs(duration - expected_duration) > tolerance:
            raise RuntimeError(
                f"Shot {shot.number} duration anomaly: native target {expected_duration:g}s, actual {duration:.2f}s."
            )
        if project_id is None:
            project_id = "ad-hoc-review"
        frames = self._extract_keyframes(project_id, shot, video_path, duration)
        ending_frame = self._extract_ending_frame(project_id, shot, video_path, duration)
        context = context or resolve_shot_context(shot, visual_bible or {}, story_world, previous_shot)
        generation_references = self.reference_bank.generation_reference_paths(project_id, shot, previous_shot, context=context)
        reference_inputs = {
            "character_hero": generation_references["character"],
            "current_scene": generation_references["scene"],
            "previous_approved_shot_ending_frame": generation_references["previous_frame"],
            "prop": generation_references.get("prop", []),
            "palette": generation_references["palette"],
            "reference_flags": generation_references.get("reference_flags", []),
        }
        reference_strategy = {
            key: [str(path) for path in paths]
            for key, paths in reference_inputs.items()
            if key != "reference_flags"
        }
        reference_flags = list(reference_inputs.get("reference_flags") or [])
        if self.vision_llm is None:
            self._archive_review_frames(project_id, shot, frames, approved=False)
            self._archive_ending_frame(project_id, shot, ending_frame, approved=False)
            shot.qc_flags = list(dict.fromkeys([*shot.qc_flags, "MANUAL_VISUAL_REVIEW"]))
            shot.qc_details = {
                **(shot.qc_details or {}),
                "media": {"integrity": {"state": "MEDIA_INTEGRITY_PASSED", "duration_seconds": duration}},
                "manual_review": {
                    "review_state": "MEDIA_INTEGRITY_PASSED",
                    "next_action": "APPROVE_SHOT",
                    "reference_strategy": reference_strategy,
                    "flags": ["MANUAL_VISUAL_REVIEW"],
                },
                "review_state": "MEDIA_INTEGRITY_PASSED",
                "next_action": "APPROVE_SHOT",
                "reference_strategy": reference_strategy,
                "reference_flags": reference_flags,
            }
            self._sync_qc_flags(shot)
            shot.status = "awaiting_visual_review"
            shot.stale = False
            shot.qc_status = "AWAITING_VISUAL_REVIEW"
            source_record = (shot.media_assets or {}).get("source") if isinstance(shot.media_assets, dict) else None
            if isinstance(source_record, dict):
                source_record["qc_status"] = shot.qc_status
                source_record["stale"] = False
            return (
                f"Quality Agent: Shot {shot.number} integrity passed ({duration:.2f}s), "
                f"{len(frames)} keyframes persisted; no vision model configured; MANUAL VISUAL REVIEW required before approval."
            )

        review = normalise_visual_review(self._review_visual_consistency(
            project_id,
            shot,
            visual_bible or {},
            frames,
            reference_paths=[
                *reference_inputs["character_hero"],
                *reference_inputs["current_scene"],
                *reference_inputs["prop"],
                *reference_inputs["previous_approved_shot_ending_frame"],
            ],
            context=context,
        ))
        self._write_visual_review(project_id, shot.number, review)
        verdict = str(review.get("verdict", "")).strip().lower()
        scores = review.get("scores") or {}
        character_score = scores.get("character_identity")
        scene_score = scores.get("scene_geometry")
        drift_flags = list(review.get("drift_flags") or [])
        shot.qc_details = {
            **(shot.qc_details or {}),
            "review_state": "VISION_REVIEWED",
            "visual": {
                "reference_strategy": reference_strategy,
                "dimensions": scores,
                "drift_details": review.get("drift_details") or {},
                "scores": scores,
                "reference_flags": reference_flags,
                "flags": drift_flags,
            },
            "reference_strategy": reference_strategy,
            "dimensions": scores,
            "drift_details": review.get("drift_details") or {},
            "copyright_risk": review.get("copyright_risk"),
        }
        self._sync_qc_flags(shot)
        copyright_risk = str(review.get("copyright_risk", "")).strip().lower()
        required_dimensions = ["palette", "lighting", "camera_language", "film_texture"]
        if shot.character_ids:
            required_dimensions.extend(["character_identity", "costume", "face_hair"])
        if shot.scene_id:
            required_dimensions.append("scene_geometry")
        if shot.prop_ids:
            required_dimensions.append("props")
        missing_dimensions = [key for key in required_dimensions if scores.get(key) is None]
        low_scores = [value for key, value in scores.items() if key in required_dimensions and value is not None and value < 70]
        if (
            verdict == "fail"
            or verdict == "review"
            or missing_dimensions
            or low_scores
            or copyright_risk == "high"
            or len(drift_flags) >= 2
        ):
            self._archive_ending_frame(project_id, shot, ending_frame, approved=False)
            shot.status = "qc_failed_continuity"
            flag_text = ", ".join(drift_flags) if drift_flags else "none"
            raise RuntimeError(
                f"Shot {shot.number} visual quality check failed: missing {', '.join(missing_dimensions) or 'none'}, "
                f"low scores {low_scores or 'none'}, copyright risk {copyright_risk or 'unknown'}, flags {flag_text}."
            )
        self._archive_review_frames(project_id, shot, frames, approved=True)
        self._archive_ending_frame(project_id, shot, ending_frame, approved=True)
        shot.status = "approved_comfyui"
        shot.stale = False
        shot.qc_status = "PASSED_VISION"
        source_record = (shot.media_assets or {}).get("source") if isinstance(shot.media_assets, dict) else None
        if isinstance(source_record, dict):
            source_record["qc_status"] = shot.qc_status
            source_record["stale"] = False
        review_note = str(review.get("review_note", "Visual review completed.")).strip()
        return (
            f"Quality Agent: Shot {shot.number} integrity and visual review passed ({duration:.2f}s, "
            f"character {character_score if character_score is not None else 'N/A'}/100, scene {scene_score if scene_score is not None else 'N/A'}/100). {review_note}"
        )

    def approve_manual(self, shot: Shot, *, project_id: str) -> str:
        """Approve a media-integrity-passed shot after an explicit human review."""

        if shot.status != "awaiting_visual_review" or shot.qc_status != "AWAITING_VISUAL_REVIEW":
            raise ValueError(f"Shot {shot.number} is not waiting for manual visual review.")
        promoted = self.reference_bank.promote_shot_references(
            project_id,
            shot.number,
            int(getattr(shot, "revision", 1) or 1),
        )
        shot.qc_flags = [flag for flag in (shot.qc_flags or []) if flag != "MANUAL_VISUAL_REVIEW"]
        shot.qc_details = {
            **(shot.qc_details or {}),
            "manual_review": {
                "review_state": "APPROVED",
                "approved_by": "manual",
                "next_action": "READY_FOR_EDIT",
                "flags": [flag for flag in (shot.qc_details.get("manual_review", {}).get("flags") or []) if flag != "MANUAL_VISUAL_REVIEW"],
            },
            "review_state": "APPROVED",
            "approved_by": "manual",
            "next_action": "READY_FOR_EDIT",
        }
        self._sync_qc_flags(shot)
        shot.status = "approved_comfyui"
        shot.qc_status = "APPROVED_MANUAL"
        shot.stale = False
        source_record = (shot.media_assets or {}).get("source") if isinstance(shot.media_assets, dict) else None
        if isinstance(source_record, dict):
            source_record["qc_status"] = shot.qc_status
            source_record["stale"] = False
        return f"Quality Agent: Shot {shot.number} manually approved; {promoted} review references promoted to the persistent bank."

    def _archive_review_frames(self, project_id: str, shot: Shot, frames: list[Path], *, approved: bool) -> None:
        for index, frame in enumerate(frames, start=1):
            if not Path(frame).is_file():
                continue
            self.reference_bank.register_file(
                project_id,
                Path(frame),
                kind="approved_keyframe" if approved else "review_keyframe",
                source="continuity_qc",
                approved=approved,
                shot_number=shot.number,
                revision=int(getattr(shot, "revision", 1) or 1),
                name=f"shot-{shot.number:02d}-rev-{int(getattr(shot, 'revision', 1) or 1):02d}-frame-{index:02d}",
                scene_id=shot.scene_id,
                character_id=shot.character_ids[0] if shot.character_ids else "",
                character_ids=list(shot.character_ids),
                role="qc_keyframe",
                metadata={
                    "role": "qc_keyframe",
                    "scene_id": shot.scene_id,
                    "character_ids": list(shot.character_ids),
                    "prop_ids": list(shot.prop_ids),
                },
            )

    def _archive_ending_frame(self, project_id: str, shot: Shot, frame: Path | None, *, approved: bool) -> None:
        if frame is None or not Path(frame).is_file():
            return
        self.reference_bank.register_file(
            project_id,
            Path(frame),
            kind="previous_approved_shot_ending_frame" if approved else "review_keyframe",
            source="continuity_qc",
            approved=approved,
            shot_number=shot.number,
            revision=int(getattr(shot, "revision", 1) or 1),
            name=f"shot-{shot.number:02d}-rev-{int(getattr(shot, 'revision', 1) or 1):02d}-transition-ending",
            scene_id=shot.scene_id,
            character_id=shot.character_ids[0] if shot.character_ids else "",
            character_ids=list(shot.character_ids),
            role="transition_ending_frame",
            metadata={
                "role": "transition_ending_frame",
                "from_scene_id": shot.scene_id,
                "character_ids": list(shot.character_ids),
                "prop_ids": list(shot.prop_ids),
                "transition_type": shot.transition_type,
                "shot_revision": int(getattr(shot, "revision", 1) or 1),
            },
        )

    def _extract_keyframes(self, project_id: str, shot: Shot, video_path: Path, duration: float) -> list[Path]:
        output_dir = self.settings.outputs_dir / project_id / "quality" / f"shot-{shot.number:02d}"
        output_dir.mkdir(parents=True, exist_ok=True)
        frames: list[Path] = []
        for index, timestamp in enumerate(
            self._keyframe_timestamps(duration, self.settings.vision_keyframes_per_shot), start=1
        ):
            frame_path = output_dir / f"frame-{index:02d}-{timestamp:.2f}s.jpg"
            command = [
                self.settings.ffmpeg_bin,
                "-y",
                "-ss",
                f"{timestamp:.3f}",
                "-i",
                str(video_path),
                "-frames:v",
                "1",
                "-q:v",
                "3",
                str(frame_path),
            ]
            completed = subprocess.run(command, capture_output=True, text=True, check=False)
            if completed.returncode != 0 or not frame_path.is_file():
                raise RuntimeError(f"Shot {shot.number} keyframe extraction failed: {completed.stderr[-300:]}")
            frames.append(frame_path)
        return frames

    def _extract_ending_frame(self, project_id: str, shot: Shot, video_path: Path, duration: float) -> Path | None:
        """Extract a dedicated transition frame near the actual media end."""

        if not video_path.is_file():
            return None
        output_dir = self.settings.outputs_dir / project_id / "quality" / f"shot-{shot.number:02d}"
        output_dir.mkdir(parents=True, exist_ok=True)
        frame_path = output_dir / f"ending-rev-{int(getattr(shot, 'revision', 1) or 1):02d}.jpg"
        timestamp = max(0.01, float(duration) - 0.15)
        command = [
            self.settings.ffmpeg_bin,
            "-y",
            "-ss",
            f"{timestamp:.3f}",
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            "-q:v",
            "3",
            str(frame_path),
        ]
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        if completed.returncode != 0 or not frame_path.is_file():
            raise RuntimeError(f"Shot {shot.number} ending frame extraction failed: {completed.stderr[-300:]}")
        return frame_path

    @staticmethod
    def _keyframe_timestamps(duration: float, count: int) -> list[float]:
        """Choose interior samples so fades on the first/last frame do not dominate review."""
        return [max(0.01, duration * index / (count + 1)) for index in range(1, count + 1)]

    def _review_visual_consistency(
        self,
        project_id: str,
        shot: Shot,
        visual_bible: dict[str, str],
        frames: list[Path],
        reference_paths: list[Path] | None = None,
        context: ResolvedShotContext | None = None,
    ) -> dict[str, Any]:
        approved_references = [path for path in (reference_paths or []) if Path(path).is_file()]
        images = approved_references + frames
        reference_note = (
            "The first images are persistent approved character, scene, and previous-shot references; subsequent images are keyframes from the current shot."
            if approved_references
            else "No persistent approved reference exists yet; judge the current shot against the locked visual specifications and choose review when uncertain."
        )
        context = context or resolve_shot_context(shot, visual_bible)
        cinematography_lock = context.cinematography_lock
        character_lock = "\n".join(
            f"{item.get('character_id')}: {item.get('lock', '')}" for item in context.character_locks
        ) or "not provided"
        scene_lock = context.scene_lock.get("lock", "")
        prop_lock = "\n".join(
            f"{item.get('prop_id')}: {item.get('lock', '')}" for item in context.prop_locks
        ) or "not provided"
        return self.vision_llm.complete_vision_json(
            "You are a film post-production visual quality inspector. Review only the active shot context: character identity, costume, face/hair, scene geometry, props, palette, lighting, camera language, film texture, narrative state, and originality risk based only on the provided frames and active visual specifications. "
            "Do not speculate about information not visible in the images; choose 'review' when uncertain. "
            "Check for STYLE_DRIFT, CHARACTER_DRIFT, SCENE_DRIFT, NARRATIVE_STATE_DRIFT (expected action/state is missing), and PROP_DRIFT (required prop changed or disappeared).",
            "Review this shot and return only JSON: "
            '{"verdict":"pass|review|fail","scores":{"character_identity":0,"costume":0,"face_hair":0,"scene_geometry":0,"props":0,"palette":0,"lighting":0,"camera_language":0,"film_texture":0,"narrative_state":0},'
            '"drift_details":{"STYLE_DRIFT":[],"CHARACTER_DRIFT":[],"SCENE_DRIFT":[],"NARRATIVE_STATE_DRIFT":[],"PROP_DRIFT":[]},'
            '"copyright_risk":"low|medium|high","review_note":"Brief English conclusion",'
            '"drift_flags":["STYLE_DRIFT","CHARACTER_DRIFT","SCENE_DRIFT"] or []}.\n'
            f"Shot {shot.number}: {shot.image_description}; action: {shot.action}.\n"
            f"Expected story function: {shot.story_function or shot.narrative_purpose or 'not provided'}\n"
            f"Expected primary action: {shot.main_action or shot.action or 'not provided'}\n"
            f"Expected secondary action: {shot.secondary_action or 'not provided'}\n"
            f"Expected character state/reaction: {shot.character_reaction or 'not provided'}\n"
            f"Expected environment reaction: {shot.environment_reaction or 'not provided'}\n"
            f"Expected starting state: {shot.starting_state or shot.continuity_from or 'not provided'}\n"
            f"Expected ending state: {shot.ending_state or shot.continuity_to or 'not provided'}\n"
            f"Expected visual motif/props: {shot.visual_motif or 'not provided'}\n"
            f"ACTIVE CHARACTER IDS: {', '.join(context.character_ids) or 'none'}\n"
            f"ACTIVE CHARACTER LOCKS: {character_lock}\n"
            f"CURRENT SCENE ID: {context.scene_id or 'none'}\n"
            f"CURRENT SCENE LOCK: {scene_lock or 'not provided'}\n"
            f"ACTIVE PROP IDS: {', '.join(context.prop_ids) or 'none'}\n"
            f"ACTIVE PROP LOCKS: {prop_lock}\n"
            f"Style spec: {visual_bible.get('style_card', 'not provided')}\n"
            f"Cinematography lock: {cinematography_lock or 'not provided'}\n"
            f"{reference_note}",
            images,
        )

    def _write_visual_review(self, project_id: str, shot_number: int, review: dict[str, Any]) -> None:
        review_path = self.settings.outputs_dir / project_id / "quality" / f"shot-{shot_number:02d}" / "review.json"
        review_path.write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _score(value: Any) -> int:
        try:
            return max(0, min(100, int(float(value))))
        except (TypeError, ValueError):
            return 0

    def _video_duration(self, path: Path) -> float:
        if not path.is_file():
            raise RuntimeError("Quality review cannot find shot MP4 file.")
        command = [
            self.settings.ffprobe_bin,
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=codec_type",
            "-of",
            "json",
            str(path),
        ]
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            raise RuntimeError(f"ffprobe cannot read shot file: {completed.stderr[-300:]}")
        try:
            payload = json.loads(completed.stdout)
            duration = float(payload["format"]["duration"])
            streams = payload.get("streams", [])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise RuntimeError("ffprobe returned unparseable media info.") from error
        if duration <= 0 or not any(stream.get("codec_type") == "video" for stream in streams):
            raise RuntimeError("Shot file missing valid video stream or duration.")
        return duration
