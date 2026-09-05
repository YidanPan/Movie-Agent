from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from movie_agent.storage.reference_bank import ReferenceBankStore


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


if __name__ == "__main__":
    unittest.main()
