from pathlib import Path
from tempfile import TemporaryDirectory
from dataclasses import replace
import json
import unittest

from movie_agent.models import MovieProject, Shot
from movie_agent.services.render_input import RendererContractUnavailable, compile_renderer_input
from movie_agent.services.revisions import diff_renderer_contract, reconcile_generation_fingerprints
from movie_agent.services.shot_context import resolve_shot_context


def _project(shot: Shot) -> MovieProject:
    return MovieProject(
        "film-render-input",
        "A quiet signal.",
        4,
        "grounded",
        "planned",
        {},
        {},
        {"reference_seed": "42", "scene_lock": "A quiet room."},
        [shot],
    )


def _shot() -> Shot:
    return Shot(
        1,
        4,
        "medium shot",
        "A quiet room.",
        "The character notices a signal.",
        "Room tone.",
        "T2V",
        "Continue the signal.",
        "shot-01.mp4",
        scene_id="home",
        character_ids=["hero"],
    )


def _workflow(path: Path, *, checkpoint: str = "base") -> None:
    path.write_text(
        json.dumps(
            {
                "1": {"class_type": "Checkpoint", "inputs": {"name": checkpoint}},
                "6": {"class_type": "Prompt", "inputs": {"prompt": "", "length": 96}},
                "7": {"class_type": "Seed", "inputs": {"noise_seed": 0}},
                "_movie_agent": {
                    "prompt_node": "6",
                    "prompt_field": "prompt",
                    "seed_node": "7",
                    "seed_field": "noise_seed",
                    "duration_node": "6",
                    "duration_field": "length",
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _source_record(manifest) -> dict:
    return {
        **manifest.audit_dict(),
        "path": "shot-01.mp4",
        "stale": False,
        "generation_input_hash": manifest.fingerprint(),
    }


class RendererInputTests(unittest.TestCase):
    def test_renderer_manifest_is_deterministic(self) -> None:
        with TemporaryDirectory() as directory:
            workflow = Path(directory) / "workflow.json"
            _workflow(workflow)
            project = _project(_shot())
            context = resolve_shot_context(project.storyboard[0], project.visual_bible, project.story_world)
            first = compile_renderer_input(project, project.storyboard[0], None, context, workflow)
            second = compile_renderer_input(project, project.storyboard[0], None, context, workflow)
            self.assertEqual(first.to_dict(), second.to_dict())
            self.assertEqual(first.fingerprint(), second.fingerprint())

    def test_fingerprint_payload_excludes_audit_only_metadata(self) -> None:
        with TemporaryDirectory() as directory:
            workflow = Path(directory) / "workflow.json"
            _workflow(workflow)
            project = _project(_shot())
            context = resolve_shot_context(project.storyboard[0], project.visual_bible, project.story_world)
            manifest = compile_renderer_input(project, project.storyboard[0], None, context, workflow)
            changed_audit = replace(
                manifest,
                project_id="another-project",
                shot_number=99,
                context_digest="different-context-audit",
                workflow_identity="another-display-name",
                workflow_template_digest="different-template-audit",
                compiled_prompt="different readable prompt with the same submitted workflow",
            )
            self.assertEqual(manifest.fingerprint_payload(), changed_audit.fingerprint_payload())
            self.assertEqual(manifest.fingerprint(), changed_audit.fingerprint())
            self.assertNotIn("compiled_prompt", manifest.audit_dict())

    def test_missing_workflow_does_not_stale_existing_source(self) -> None:
        with TemporaryDirectory() as directory:
            workflow = Path(directory) / "workflow.json"
            _workflow(workflow)
            project = _project(_shot())
            shot = project.storyboard[0]
            context = resolve_shot_context(shot, project.visual_bible, project.story_world)
            manifest = compile_renderer_input(project, shot, None, context, workflow)
            shot.media_assets["source"] = _source_record(manifest)
            result = reconcile_generation_fingerprints(project, workflow_path=Path(directory) / "missing.json")
            self.assertEqual(result["contract_status"], "WORKFLOW_MISSING")
            self.assertEqual(result["affected_shots"], [])
            self.assertFalse(shot.stale)

    def test_invalid_workflow_reports_renderer_contract_unavailable(self) -> None:
        with TemporaryDirectory() as directory:
            workflow = Path(directory) / "invalid.json"
            workflow.write_text("{}", encoding="utf-8")
            project = _project(_shot())
            with self.assertRaises(RendererContractUnavailable) as raised:
                compile_renderer_input(project, project.storyboard[0], None, {}, workflow)
            self.assertEqual(raised.exception.status, "WORKFLOW_INVALID")

    def test_legacy_source_becomes_unverified_not_automatically_stale(self) -> None:
        with TemporaryDirectory() as directory:
            workflow = Path(directory) / "workflow.json"
            _workflow(workflow)
            project = _project(_shot())
            shot = project.storyboard[0]
            shot.media_assets["source"] = {"path": "legacy.mp4", "stale": False, "generation_input_hash": "old-algorithm"}
            shot.sound_design = "A changed sound cue."
            result = reconcile_generation_fingerprints(project, workflow_path=workflow)
            self.assertEqual(result["affected_shots"], [])
            self.assertFalse(shot.stale)
            self.assertEqual(shot.media_assets["source"]["renderer_verification_status"], "UNVERIFIED_LEGACY")

    def test_renderer_contract_diff_reports_prompt_change(self) -> None:
        with TemporaryDirectory() as directory:
            workflow = Path(directory) / "workflow.json"
            _workflow(workflow)
            project = _project(_shot())
            shot = project.storyboard[0]
            context = resolve_shot_context(shot, project.visual_bible, project.story_world)
            manifest = compile_renderer_input(project, shot, None, context, workflow)
            source = _source_record(manifest)
            source["compiled_prompt_digest"] = "different"
            diff = diff_renderer_contract(source, manifest)
            self.assertEqual(diff["reason"], "PROMPT_CHANGED")

    def test_renderer_contract_diff_reports_workflow_seed_and_duration_changes(self) -> None:
        with TemporaryDirectory() as directory:
            workflow = Path(directory) / "workflow.json"
            _workflow(workflow)
            project = _project(_shot())
            shot = project.storyboard[0]
            context = resolve_shot_context(shot, project.visual_bible, project.story_world)
            manifest = compile_renderer_input(project, shot, None, context, workflow)
            source = _source_record(manifest)
            source["submitted_workflow_digest"] = "different-workflow"
            self.assertEqual(diff_renderer_contract(source, manifest)["reason"], "WORKFLOW_CHANGED")
            source = _source_record(manifest)
            source["derived_seed"] = manifest.derived_seed + 1
            self.assertEqual(diff_renderer_contract(source, manifest)["reason"], "SEED_CHANGED")
            source = _source_record(manifest)
            source["source_duration_seconds"] = manifest.source_duration_seconds + 1
            self.assertEqual(diff_renderer_contract(source, manifest)["reason"], "SOURCE_DURATION_CHANGED")

    def test_generation_and_reconcile_use_same_film_language(self) -> None:
        with TemporaryDirectory() as directory:
            workflow = Path(directory) / "workflow.json"
            _workflow(workflow)
            project = _project(_shot())
            project.film_language = "fr"
            shot = project.storyboard[0]
            context = resolve_shot_context(shot, project.visual_bible, project.story_world)
            generated = compile_renderer_input(project, shot, None, context, workflow, film_language="fr")
            reconciled = compile_renderer_input(project, shot, None, context, workflow, film_language=project.film_language)
            self.assertIn("fr only", generated.compiled_prompt)
            self.assertEqual(generated.fingerprint(), reconciled.fingerprint())

    def test_submitted_workflow_digest_matches_overridden_payload(self) -> None:
        with TemporaryDirectory() as directory:
            workflow = Path(directory) / "workflow.json"
            _workflow(workflow)
            project = _project(_shot())
            context = resolve_shot_context(project.storyboard[0], project.visual_bible, project.story_world)
            manifest = compile_renderer_input(project, project.storyboard[0], None, context, workflow)
            self.assertTrue(manifest.workflow_template_digest)
            self.assertTrue(manifest.submitted_workflow_digest)
            self.assertNotEqual(manifest.workflow_template_digest, manifest.submitted_workflow_digest)

    def test_filename_only_change_is_not_the_version_contract(self) -> None:
        with TemporaryDirectory() as directory:
            first_path = Path(directory) / "first.json"
            second_path = Path(directory) / "renamed.json"
            _workflow(first_path)
            second_path.write_bytes(first_path.read_bytes())
            project = _project(_shot())
            context = resolve_shot_context(project.storyboard[0], project.visual_bible, project.story_world)
            first = compile_renderer_input(project, project.storyboard[0], None, context, first_path)
            second = compile_renderer_input(project, project.storyboard[0], None, context, second_path)
            self.assertEqual(first.fingerprint(), second.fingerprint())

    def test_fresh_render_does_not_self_invalidate_after_seed_assignment(self) -> None:
        with TemporaryDirectory() as directory:
            workflow = Path(directory) / "workflow.json"
            _workflow(workflow)
            project = _project(_shot())
            shot = project.storyboard[0]
            context = resolve_shot_context(shot, project.visual_bible, project.story_world)
            manifest = compile_renderer_input(project, shot, None, context, workflow)
            shot.seed = manifest.derived_seed
            shot.generation_seed = manifest.derived_seed
            shot.generation_input_hash = manifest.fingerprint()
            shot.media_assets["source"] = _source_record(manifest)
            result = reconcile_generation_fingerprints(project, workflow_path=workflow)
            self.assertEqual(result["affected_shots"], [])
            self.assertFalse(shot.stale)

    def test_reconcile_uses_source_asset_hash_not_mutable_shot_hash(self) -> None:
        with TemporaryDirectory() as directory:
            workflow = Path(directory) / "workflow.json"
            _workflow(workflow)
            project = _project(_shot())
            shot = project.storyboard[0]
            context = resolve_shot_context(shot, project.visual_bible, project.story_world)
            manifest = compile_renderer_input(project, shot, None, context, workflow)
            shot.media_assets["source"] = _source_record(manifest)
            shot.generation_input_hash = "mutable-diagnostic-value"
            result = reconcile_generation_fingerprints(project, workflow_path=workflow)
            self.assertEqual(result["affected_shots"], [])

    def test_sound_design_change_updates_renderer_hash(self) -> None:
        with TemporaryDirectory() as directory:
            workflow = Path(directory) / "workflow.json"
            _workflow(workflow)
            project = _project(_shot())
            shot = project.storyboard[0]
            context = resolve_shot_context(shot, project.visual_bible, project.story_world)
            first = compile_renderer_input(project, shot, None, context, workflow)
            shot.media_assets["source"] = _source_record(first)
            shot.sound_design = "A sharp electrical pulse."
            result = reconcile_generation_fingerprints(project, workflow_path=workflow)
            self.assertEqual(result["affected_shots"], [1])

    def test_planning_only_fields_do_not_stale_visual_source(self) -> None:
        with TemporaryDirectory() as directory:
            workflow = Path(directory) / "workflow.json"
            _workflow(workflow)
            project = _project(_shot())
            shot = project.storyboard[0]
            context = resolve_shot_context(shot, project.visual_bible, project.story_world)
            first = compile_renderer_input(project, shot, None, context, workflow)
            shot.media_assets["source"] = _source_record(first)
            shot.information_gain = 0.9
            shot.speech_policy = "DIALOGUE"
            result = reconcile_generation_fingerprints(project, workflow_path=workflow)
            self.assertEqual(result["affected_shots"], [])

    def test_workflow_content_change_invalidates_existing_source(self) -> None:
        with TemporaryDirectory() as directory:
            workflow = Path(directory) / "workflow.json"
            _workflow(workflow)
            project = _project(_shot())
            shot = project.storyboard[0]
            context = resolve_shot_context(shot, project.visual_bible, project.story_world)
            first = compile_renderer_input(project, shot, None, context, workflow)
            shot.media_assets["source"] = _source_record(first)
            _workflow(workflow, checkpoint="changed")
            result = reconcile_generation_fingerprints(project, workflow_path=workflow)
            self.assertEqual(result["affected_shots"], [1])
            self.assertTrue(shot.stale)


if __name__ == "__main__":
    unittest.main()
