import json
from pathlib import Path

from evals.evaluate import evaluate_projects


def test_golden_evaluation_always_reports_three_projects_and_explicit_unavailable_metrics(tmp_path: Path):
    report = evaluate_projects(tmp_path / "projects", tmp_path / "reports", Path(__file__).parents[1] / "evals")
    assert len(report["projects"]) == 3
    assert report["projects"][0]["metrics"]["Availability"] == "PLAN ONLY"
    assert (tmp_path / "reports" / "eval-report.json").is_file()
    assert (tmp_path / "reports" / "eval-report.md").is_file()
    payload = json.loads((tmp_path / "reports" / "eval-report.json").read_text(encoding="utf-8"))
    assert payload["suite"] == "golden-film-evaluation"
