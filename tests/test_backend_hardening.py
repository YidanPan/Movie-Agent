from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from movie_agent.agents.storyboard import StoryboardAgent
from movie_agent.services.llm import _parse_json_object
from movie_agent.storage.project_store import ProjectStore


class BackendHardeningTests(unittest.TestCase):
    def test_parser_accepts_a_short_model_preamble_and_nested_json(self) -> None:
        payload = _parse_json_object('结果如下： {"主题": "雨中的 { 城市 }", "镜头": 6} 谢谢')
        self.assertEqual(payload["主题"], "雨中的 { 城市 }")
        self.assertEqual(payload["镜头"], 6)

    def test_store_rejects_invalid_project_ids(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            store = ProjectStore(Path(temporary_directory))
            with self.assertRaisesRegex(ValueError, "项目 ID 格式无效"):
                store.load("../outside")

    def test_t2v_only_mode_normalizes_mock_storyboards(self) -> None:
        agent = StoryboardAgent(allowed_generation_modes={"T2V"})
        shots = agent.create(
            "一名守夜人发现空城每天都在等他下班。",
            48,
            "写实近未来",
            "film-1234abcd",
            {},
            {},
            {},
        )
        self.assertTrue(all(shot.generation_mode == "T2V" for shot in shots))
