from pathlib import Path
from tempfile import TemporaryDirectory

from movie_agent.config import Settings
from movie_agent.orchestrator import MovieOrchestrator
from movie_agent.services.cache_cleanup import clean_working_cache, storage_summary


def test_cache_cleanup_preserves_sources_and_current_master():
    with TemporaryDirectory() as temporary_directory:
        root = Path(temporary_directory)
        settings = Settings("http://127.0.0.1:8188", 900, root / "workflows", 9071, root / "projects", True, outputs_dir=root / "outputs")
        orchestrator = MovieOrchestrator(settings)
        project = orchestrator.create_project("A quiet signal", 48, "film sci-fi")
        project_root = settings.outputs_dir / project.project_id
        source = project_root / "shots" / "source.mp4"
        master = project_root / "final-cut-mezzanine.mov"
        stale_proxy = project_root / "previews" / "proxy-1080p.mp4"
        old_normalized = project_root / "normalized" / "shots" / "old.mov"
        for path in (source, master, stale_proxy, old_normalized):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"cache")
        shot = project.storyboard[0]
        shot.media_assets["source"] = {"path": str(source), "tier": "source", "revision": 1}
        project.video_assets["final_master"] = {"path": str(master), "tier": "final_master", "stale": False}
        project.video_assets["screening_preview"] = {"path": str(stale_proxy), "tier": "screening_preview", "stale": True}
        project.video_asset_history.append({"path": str(old_normalized), "tier": "final_master", "stale": True})
        before = storage_summary(project, settings.outputs_dir)
        result = clean_working_cache(project, settings.outputs_dir)
        assert before["cleanable_file_count"] >= 2
        assert result["removed_files"] >= 2
        assert source.is_file()
        assert master.is_file()
        assert not stale_proxy.is_file()
        assert not old_normalized.is_file()
