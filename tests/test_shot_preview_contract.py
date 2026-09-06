import json
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from movie_agent.config import Settings
from movie_agent.models import MovieProject, Shot
from movie_agent.orchestrator import MovieOrchestrator


ROOT = Path(__file__).resolve().parents[1]


def _node_contract(*statuses: str, stale: bool = False) -> dict[str, bool]:
    payload = json.dumps([{"status": status, "stale": stale} for status in statuses])
    script = (
        "import { shotCapabilities, shotPreviewable, shotReady } from './static/js/storyboard.js';"
        f"const shots = {payload};"
        "console.log(JSON.stringify({previewable: shotPreviewable(shots[0]), ready: shotReady(shots[0]), "
        "allReady: shots.every(shotReady), capabilities: shotCapabilities(shots[0])}));"
    )
    try:
        result = subprocess.run(
            ["node", "--input-type=module", "--eval", script],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as error:
        raise unittest.SkipTest("Node.js is required for the browser contract test.") from error
    return json.loads(result.stdout)


def _fixture(root: Path, status: str, *, stale: bool = False):
    settings = Settings(
        "http://127.0.0.1:8188",
        900,
        root / "workflows",
        9071,
        root / "projects",
        True,
        outputs_dir=root / "outputs",
    )
    orchestrator = MovieOrchestrator(settings)
    project_id = "film-a1b2c3d4"
    media_path = root / "outputs" / project_id / "shot-01.mp4"
    media_path.parent.mkdir(parents=True)
    media_path.write_bytes(b"shot preview")
    shot = Shot(
        number=1,
        duration_seconds=6,
        framing="medium shot",
        image_description="A locked preview frame",
        action="The subject turns toward the signal.",
        sound_design="Room tone",
        generation_mode="T2V",
        prompt="A locked preview shot",
        output_placeholder=str(media_path),
        status=status,
        stale=stale,
        media_assets={"source": {"path": str(media_path), "stale": False}},
    )
    project = MovieProject(
        project_id=project_id,
        idea="A signal arrives after midnight.",
        duration_seconds=6,
        visual_style="film sci-fi",
        status="awaiting_visual_review" if status == "awaiting_visual_review" else "ready_for_ai_edit",
        brief={},
        script={},
        visual_bible={},
        storyboard=[shot],
    )
    orchestrator.store.save(project)
    return settings, orchestrator, project


class ShotPreviewContractTests(unittest.TestCase):
    def test_awaiting_visual_review_is_previewable(self):
        contract = _node_contract("awaiting_visual_review")
        self.assertTrue(contract["previewable"])

    def test_awaiting_visual_review_is_not_shot_ready(self):
        contract = _node_contract("awaiting_visual_review")
        self.assertFalse(contract["ready"])

    def test_shot_capabilities_keep_review_and_ready_semantics_separate(self):
        review = _node_contract("awaiting_visual_review")["capabilities"]
        ready = _node_contract("approved_comfyui")["capabilities"]
        self.assertTrue(review["canPreview"])
        self.assertTrue(review["canApprove"])
        self.assertFalse(review["canEnterCut"])
        self.assertTrue(ready["canPreview"])
        self.assertFalse(ready["canApprove"])
        self.assertTrue(ready["canEnterCut"])

    def test_shot_video_endpoint_serves_awaiting_visual_review_media(self):
        import server
        from fastapi.testclient import TestClient

        with TemporaryDirectory() as temporary_directory:
            settings, orchestrator, project = _fixture(Path(temporary_directory), "awaiting_visual_review")
            with patch.object(server, "settings", settings), patch.object(server, "orchestrator", orchestrator):
                client = TestClient(server.app)
                response = client.get(f"/api/projects/{project.project_id}/shots/1/video")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.content, b"shot preview")
                self.assertEqual(client.head(f"/api/projects/{project.project_id}/shots/1/video").status_code, 200)

    def test_approved_shot_is_previewable_and_ready(self):
        contract = _node_contract("approved_comfyui")
        self.assertTrue(contract["previewable"])
        self.assertTrue(contract["ready"])
        self.assertTrue(contract["allReady"])

    def test_stale_shot_is_not_previewable(self):
        contract = _node_contract("approved_comfyui", stale=True)
        self.assertFalse(contract["previewable"])
        self.assertFalse(contract["ready"])

    def test_ai_edit_remains_disabled_until_all_shots_are_approved(self):
        generated = _node_contract("awaiting_visual_review", "approved_comfyui")
        approved = _node_contract("approved_comfyui", "approved_comfyui")
        self.assertFalse(generated["allReady"])
        self.assertTrue(approved["allReady"])


if __name__ == "__main__":
    unittest.main()
