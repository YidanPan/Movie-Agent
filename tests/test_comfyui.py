import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from movie_agent.services.comfyui import WorkflowOverrides, load_verified_workflow


class VerifiedWorkflowTests(unittest.TestCase):
    def test_only_manifest_inputs_are_replaced(self) -> None:
        template = {
            "10": {"inputs": {"text": "old prompt"}},
            "20": {"inputs": {"noise_seed": 1}},
            "30": {"inputs": {"duration_seconds": 5}},
            "_movie_agent": {"prompt_node": "10", "seed_node": "20", "duration_node": "30"},
        }
        with TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "workflow.json"
            path.write_text(json.dumps(template), encoding="utf-8")
            workflow = load_verified_workflow(path, WorkflowOverrides("new prompt", 42, 7))

        self.assertEqual(workflow["10"]["inputs"]["text"], "new prompt")
        self.assertEqual(workflow["20"]["inputs"]["noise_seed"], 42)
        self.assertEqual(workflow["30"]["inputs"]["duration_seconds"], 7)
        self.assertNotIn("_movie_agent", workflow)
