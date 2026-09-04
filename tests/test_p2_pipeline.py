from pathlib import Path
from tempfile import TemporaryDirectory

from movie_agent.config import Settings
from movie_agent.orchestrator import MovieOrchestrator
from movie_agent.services.media_quality import asset_record, best_master_path, best_screening_path
from movie_agent.services.revisions import dependency_chain, hash_shot_prompt
from movie_agent.storage.project_store import ProjectStore


def make_orchestrator(root: Path) -> MovieOrchestrator:
    settings = Settings(
        "http://127.0.0.1:8188",
        900,
        root / "workflows",
        9071,
        root / "projects",
        True,
        outputs_dir=root / "outputs",
    )
    return MovieOrchestrator(settings)


def test_shot_edit_marks_assets_stale_and_preserves_history():
    with TemporaryDirectory() as temporary_directory:
        root = Path(temporary_directory)
        orchestrator = make_orchestrator(root)
        project = orchestrator.create_project("A night watchman follows a signal beyond the moon.", 48, "film sci-fi")
        shot = project.storyboard[0]
        shot.media_assets["source"] = {"path": "old-shot.mp4", "revision": 1, "stale": False}
        project.video_assets["final_master"] = {"path": "old-final.mp4", "revision": 1, "stale": False}
        project.final_output_placeholder = "old-final.mp4"
        orchestrator.store.save(project)

        updated = orchestrator.update_shot(project.project_id, shot.number, {"prompt": "A new shot delta."})
        current = updated.storyboard[0]
        assert current.revision == 2
        assert current.prompt_hash == hash_shot_prompt(current)
        assert current.stale is True
        assert current.qc_status == "STALE"
        assert current.media_assets["source"]["stale"] is True
        assert current.asset_history and current.asset_history[-1]["assets"]["source"]["stale"] is True
        assert updated.video_assets["final_master"]["stale"] is True
        assert updated.video_asset_history[-1]["assets"][0]["key"] == "final_master"
        assert updated.final_output_placeholder is None
        assert updated.invalidation_events[-1]["source"] == "shot"
        assert updated.status == "ready_for_comfyui_render"


def test_timeline_edit_keeps_source_media_but_invalidates_cuts():
    with TemporaryDirectory() as temporary_directory:
        root = Path(temporary_directory)
        orchestrator = make_orchestrator(root)
        project = orchestrator.create_project("A night watchman follows a signal beyond the moon.", 48, "film sci-fi")
        project.storyboard[0].media_assets["source"] = {"path": "source.mp4", "revision": 1, "stale": False}
        project.video_assets["screening_preview"] = {"path": "screening.mp4", "revision": 1, "stale": False}
        orchestrator.store.save(project)
        updated = orchestrator.update_shot_timing(project.project_id, 1, desired_duration=9, timing_mode="extend")
        assert updated.storyboard[0].stale is False
        assert updated.storyboard[0].media_assets["source"]["stale"] is False
        assert updated.video_assets["screening_preview"]["stale"] is True
        assert updated.video_asset_history
        assert updated.invalidation_events[-1]["source"] == "shot_timing"


def test_stale_media_is_not_resolved_as_current_master_or_screening():
    with TemporaryDirectory() as temporary_directory:
        root = Path(temporary_directory)
        source = root / "source.mp4"
        source.write_bytes(b"not a real media file")
        project = make_orchestrator(root).create_project("A night watchman follows a signal beyond the moon.", 48, "film sci-fi")
        project.video_assets = {
            "final_master": {"path": str(source), "stale": True},
            "screening_preview": {"path": str(source), "stale": True},
        }
        project.final_output_placeholder = str(source)
        project.rough_cut_placeholder = str(source)
        assert best_master_path(project) is None
        assert best_screening_path(project) is None


def test_legacy_asset_records_receive_revision_metadata_on_load():
    with TemporaryDirectory() as temporary_directory:
        root = Path(temporary_directory)
        orchestrator = make_orchestrator(root)
        project = orchestrator.create_project("A night watchman follows a signal beyond the moon.", 48, "film sci-fi")
        payload = project.to_dict()
        payload["schema_version"] = 1
        payload["video_assets"] = {"screening_preview": {"path": "legacy-preview.mp4", "width": 608, "height": 352}}
        payload["storyboard"][0]["media_assets"] = {
            "source": {"path": "legacy-shot.mp4", "width": 608, "height": 352}
        }
        migrated = project.from_dict(payload)
        record = migrated.storyboard[0].media_assets["source"]
        assert migrated.schema_version == 2
        assert record["revision"] == migrated.storyboard[0].revision
        assert record["source_resolution"] == "608x352"
        assert "prompt_hash" in record and "created_at" in record
        assert migrated.video_assets["screening_preview"]["qc_status"] == "PENDING"


def test_project_store_writes_schema_and_update_timestamps():
    with TemporaryDirectory() as temporary_directory:
        root = Path(temporary_directory)
        orchestrator = make_orchestrator(root)
        project = orchestrator.create_project("A night watchman follows a signal beyond the moon.", 48, "film sci-fi")
        payload = (root / "projects" / project.project_id / "project.json").read_text(encoding="utf-8")
        assert '"schema_version": 2' in payload
        assert project.created_at and project.updated_at


def test_p2_pipeline_boundaries_and_project_store_contract():
    assert "rough_cut" in dependency_chain("shot")
    assert dependency_chain("dialogue")[0] == "voice"
    assert (Path(__file__).parents[1] / "movie_agent" / "pipeline" / "planning.py").exists()
    assert (Path(__file__).parents[1] / "movie_agent" / "pipeline" / "rendering.py").exists()
    assert (Path(__file__).parents[1] / "static" / "js" / "app.js").exists()
    assert (Path(__file__).parents[1] / "static" / "css" / "tokens.css").exists()
