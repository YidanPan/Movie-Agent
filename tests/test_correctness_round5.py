"""Production Completion Round 5 backend correctness contracts."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from movie_agent.models import Shot
from movie_agent.pipeline.jobs import JobIdempotencyConflict, JobLedger
from movie_agent.services.change_impact import RENDERER_INPUT_FIELDS, resolve_change_impact
from movie_agent.services.continuity import derive_shot_seed
from movie_agent.storage.reference_bank import ReferenceBankStore


def test_renderer_input_fields_include_narrative_state_and_sound_design():
    assert {"narrative_purpose", "state_delta", "emotional_shift", "sound_design"} <= RENDERER_INPUT_FIELDS
    impact = resolve_change_impact({"state_delta", "sound_design"})
    assert impact["renderer"] is True


def test_two_job_ledger_instances_preserve_a_live_job():
    with TemporaryDirectory() as directory:
        root = Path(directory) / "projects"
        first = JobLedger(root)
        second = JobLedger(root)
        job = first.start("film-1234abcd", kind="generation", stage="generation")
        assert second.runtime_state("film-1234abcd")["active_jobs"][0]["job_id"] == job["job_id"]


def test_expired_persisted_job_releases_capacity_before_counting():
    with TemporaryDirectory() as directory:
        root = Path(directory) / "projects"
        ledger = JobLedger(root)
        job = ledger.start("film-1234abcd", kind="generation", stage="generation")
        path = root / "film-1234abcd" / "job.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["lease_expires_at"] = "2000-01-01T00:00:00Z"
        path.write_text(json.dumps(payload), encoding="utf-8")
        replacement = ledger.start(
            "film-deadbeef", kind="generation", stage="generation", max_active_jobs=1
        )
        assert replacement["job_id"] != job["job_id"]
        assert ledger.summary("film-1234abcd")["status"] == "recoverable_failed"


def test_idempotency_key_reuse_with_different_input_is_a_conflict():
    with TemporaryDirectory() as directory:
        ledger = JobLedger(Path(directory) / "projects")
        ledger.start("film-1234abcd", kind="export", idempotency_key="export-1", expected_input_hash="hash-a")
        with pytest.raises(JobIdempotencyConflict) as error:
            ledger.start("film-1234abcd", kind="export", idempotency_key="export-1", expected_input_hash="hash-b")
        assert error.value.error_code == "IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_INPUT"
        assert error.value.snapshot["expected_input_hash"] == "hash-a"


def test_optional_pending_keyframe_is_omitted_and_flagged():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        pending = root / "pending.webp"
        pending.write_bytes(b"pending")
        store = ReferenceBankStore(root / "outputs")
        asset = store.register_file(
            "film-1234abcd", pending, kind="shot_keyframe", source="test", approved=False,
            shot_number=1, revision=1,
        )
        shot = Shot(1, 6, "medium", "image", "action", "sound", "T2V", "delta", "shot.mp4", revision=1,
                    media_generation={"keyframe_path": asset.path})
        inputs = store.approved_generation_inputs("film-1234abcd", shot, require_keyframe=False)
        assert inputs.get("keyframe") == [] or "keyframe" not in inputs
        assert "KEYFRAME_PENDING_OR_STALE_OMITTED" in inputs["reference_flags"]


def test_shot_reference_seed_is_independent_of_model_name():
    assert derive_shot_seed("film-1234abcd", "reference-seed", 1) != derive_shot_seed(
        "film-1234abcd", "different-model-name", 1
    )
