from pathlib import Path
from tempfile import TemporaryDirectory
import wave
import unittest

from movie_agent.config import Settings
from movie_agent.orchestrator import MovieOrchestrator
from movie_agent.services.subtitles import align_script_to_audio
from movie_agent.services.voice import ContinuousVoiceService, locked_voice_text


class _WaveVoiceProvider:
    def synthesize(self, text: str, output_path: Path, voice_profile: dict) -> Path:
        self.text = text
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(output_path), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(8_000)
            handle.writeframes(b"\x00\x00" * 8_000 * 3)
        return output_path


class ContinuousVoiceTests(unittest.TestCase):
    def test_alignment_uses_measured_media_duration_and_preserves_cue_count(self) -> None:
        script = {
            "dialogue_locked": True,
            "dialogue_book": [
                {"line_id": "L1", "shot": 1, "text": "The signal is still here."},
                {"line_id": "L2", "shot": 2, "text": "We wait for the light."},
            ],
            "subtitle_track": [
                {"line_id": "L1", "shot": 1, "text": "The signal is still here."},
                {"line_id": "L2", "shot": 2, "text": "We wait for the light."},
            ],
        }
        aligned = align_script_to_audio(script, 3.0)
        self.assertEqual(len(aligned["subtitle_track"]), 2)
        self.assertEqual(aligned["subtitle_track"][-1]["end_seconds"], 3.0)
        self.assertEqual(aligned["voice_alignment"]["status"], "MEASURED")

    def test_service_writes_one_continuous_track_and_updates_voice_cues(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            settings = Settings(
                "http://127.0.0.1:8188", 900, root / "workflows", 9071, root / "projects", True,
                outputs_dir=root / "outputs", tts_provider="none",
            )
            orchestrator = MovieOrchestrator(settings)
            project = orchestrator.create_project("A night watchman follows a signal beyond the moon.", 48, "film sci-fi")
            project = orchestrator.lock_dialogue(project.project_id)
            provider = _WaveVoiceProvider()
            result = ContinuousVoiceService(settings, provider=provider).synthesize(project)
            self.assertEqual(result.status, "READY")
            self.assertEqual(result.duration_seconds, 3.0)
            self.assertEqual(project.audio_tracks["voice"]["generation_strategy"], "continuous_voice_track")
            self.assertEqual(project.audio_tracks["voice"]["duration_source"], "measured_media")
            self.assertTrue(Path(project.audio_tracks["voice"]["media_path"]).is_file())
            self.assertEqual(project.script["voice_alignment"]["media_duration_seconds"], 3.0)
            self.assertEqual(project.smart_ducking["signal_source"], "continuous_voice_track")
            self.assertGreater(len(locked_voice_text(project)), 20)


if __name__ == "__main__":
    unittest.main()
