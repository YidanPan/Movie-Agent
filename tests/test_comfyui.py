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

    def test_manifest_can_declare_nonstandard_input_fields(self) -> None:
        template = {
            "6": {"inputs": {"prompt": "old prompt"}},
            "7": {"inputs": {"noise_seed": 1}},
            "_movie_agent": {
                "prompt_node": "6",
                "prompt_field": "prompt",
                "seed_node": "7",
                "seed_field": "noise_seed",
            },
        }
        with TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "workflow.json"
            path.write_text(json.dumps(template), encoding="utf-8")
            workflow = load_verified_workflow(path, WorkflowOverrides("new prompt", 42))

        self.assertEqual(workflow["6"]["inputs"]["prompt"], "new prompt")
        self.assertEqual(workflow["7"]["inputs"]["noise_seed"], 42)

    def test_minimax_h3_duration_is_snapped_to_valid_frame_grid(self) -> None:
        template = {
            "6": {"inputs": {"length": 124}},
            "_movie_agent": {
                "prompt_node": "6",
                "seed_node": "6",
                "duration_node": "6",
                "duration_field": "length",
                "duration_transform": "minimax_h3_frames",
            },
        }
        template["6"]["inputs"].update({"text": "old", "noise_seed": 1})
        with TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "workflow.json"
            path.write_text(json.dumps(template), encoding="utf-8")
            workflow = load_verified_workflow(path, WorkflowOverrides("new", 2, 5))

        self.assertEqual(workflow["6"]["inputs"]["length"], 124)
