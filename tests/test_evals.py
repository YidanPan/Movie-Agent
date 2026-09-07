import json
from pathlib import Path

from evals.evaluate import evaluate_projects
from evals.prepare_golden import prepare_golden


def test_golden_evaluation_always_reports_three_projects_and_explicit_unavailable_metrics(tmp_path: Path):
    report = evaluate_projects(tmp_path / "projects", tmp_path / "reports", Path(__file__).parents[1] / "evals")
    assert len(report["projects"]) == 3
    assert report["projects"][0]["metrics"]["Availability"] == "PLAN ONLY"
    assert (tmp_path / "reports" / "eval-report.json").is_file()
    assert (tmp_path / "reports" / "eval-report.md").is_file()
    payload = json.loads((tmp_path / "reports" / "eval-report.json").read_text(encoding="utf-8"))
    assert payload["suite"] == "golden-film-evaluation"


def test_golden_plan_fixtures_produce_evidence_and_keep_media_honest(tmp_path: Path):
    projects = tmp_path / "projects"
    reports = tmp_path / "reports"
    assert len(prepare_golden(projects, Path(__file__).parents[1] / "evals")) == 3
    report = evaluate_projects(projects, reports, Path(__file__).parents[1] / "evals", require_plan_evidence=True)
    assert report["version"] == 3
    assert all(item["scorecard"]["plan_score"] is not None for item in report["projects"])
    assert all(item["scorecard"]["media_score_status"] == "AWAITING_RENDER" for item in report["projects"])
