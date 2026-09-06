from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from movie_agent.storage.reference_bank import ReferenceBankStore
from movie_agent.models import Shot


class ReferenceBankTests(unittest.TestCase):
    def test_registers_real_files_and_persists_across_store_instances(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "character.webp"
            source.write_bytes(b"reference")
            store = ReferenceBankStore(root / "outputs")
            asset = store.register_file(
                "film-test",
                source,
                kind="character_hero",
                source="visual_bible",
                approved=True,
            )

            loaded = ReferenceBankStore(root / "outputs").load("film-test")
            self.assertEqual(len(loaded.assets), 1)
            self.assertEqual(loaded.assets[0].reference_id, asset.reference_id)
            self.assertTrue(Path(loaded.assets[0].path).is_file())

    def test_manual_promotion_only_approves_the_current_shot_revision(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            frame_a = root / "a.jpg"
            frame_b = root / "b.jpg"
            frame_a.touch()
            frame_b.touch()
            store = ReferenceBankStore(root / "outputs")
            store.register_file("film-test", frame_a, kind="review_keyframe", source="qc", shot_number=1, revision=1)
            store.register_file("film-test", frame_b, kind="review_keyframe", source="qc", shot_number=1, revision=2)
            self.assertEqual(store.promote_shot_references("film-test", 1, 2), 1)
            bank = store.load("film-test")
            self.assertFalse(bank.assets[0].approved)
            self.assertTrue(bank.assets[1].approved)
            self.assertEqual(bank.assets[1].kind, "previous_approved_shot_ending_frame")

    def test_qc_inputs_prefer_persistent_approved_references(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            character = root / "character.webp"
            scene = root / "scene.webp"
            ending = root / "ending.jpg"
            for path in (character, scene, ending):
                path.touch()
            store = ReferenceBankStore(root / "outputs")
            store.register_file("film-test", character, kind="character_hero", source="visual_bible", approved=True)
            store.register_file("film-test", scene, kind="scene", source="visual_bible", approved=True)
            store.register_file(
                "film-test",
                ending,
                kind="previous_approved_shot_ending_frame",
                source="approved_keyframe",
                approved=True,
                shot_number=1,
            )
            inputs = store.qc_reference_paths("film-test", 2)
            self.assertEqual(inputs["character_hero"], [Path(store.load("film-test").assets[0].path)])
            self.assertEqual(len(inputs["current_scene"]), 1)
            self.assertEqual(len(inputs["previous_approved_shot_ending_frame"]), 1)

    def test_new_approved_revision_stales_previous_shot_reference(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            old_frame = root / "old.jpg"
            new_frame = root / "new.jpg"
            old_frame.touch()
            new_frame.touch()
            store = ReferenceBankStore(root / "outputs")
            store.register_file("film-test", old_frame, kind="review_keyframe", source="qc", shot_number=1, revision=1)
            store.promote_shot_references("film-test", 1, 1)
            store.register_file("film-test", new_frame, kind="review_keyframe", source="qc", shot_number=1, revision=2)
            store.promote_shot_references("film-test", 1, 2)
            bank = store.load("film-test")
            inputs = store.qc_reference_paths("film-test", 2)
            self.assertEqual(inputs["previous_approved_shot_ending_frame"], [Path(bank.assets[-1].path)])

    def test_generation_references_filter_by_scene_and_character(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            character_a = root / "character-a.webp"
            character_b = root / "character-b.webp"
            scene_a = root / "scene-a.webp"
            scene_b = root / "scene-b.webp"
            palette = root / "palette.webp"
            for path in (character_a, character_b, scene_a, scene_b, palette):
                path.touch()
            store = ReferenceBankStore(root / "outputs")
            store.register_file("film-test", character_a, kind="character", source="visual_bible", approved=True, character_id="mother")
            store.register_file("film-test", character_b, kind="character", source="visual_bible", approved=True, character_id="child")
            store.register_file("film-test", scene_a, kind="scene", source="visual_bible", approved=True, scene_id="home")
            store.register_file("film-test", scene_b, kind="scene", source="visual_bible", approved=True, scene_id="hospital")
            store.register_file("film-test", palette, kind="palette", source="visual_bible", approved=True, role="palette")
            shot = Shot(2, 6, "medium", "image", "action", "sound", "T2V", "delta", "shot.mp4", scene_id="hospital", character_ids=["child"])
            refs = store.generation_reference_paths("film-test", shot)
            self.assertEqual(refs["character"], [Path(store.load("film-test").assets[1].path)])
            self.assertEqual(refs["scene"], [Path(store.load("film-test").assets[3].path)])
            self.assertEqual(len(refs["palette"]), 1)


if __name__ == "__main__":
    unittest.main()
