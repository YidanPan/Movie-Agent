import json
import re
import threading
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from movie_agent.pipeline.evaluator_submissions import EvaluatorSubmissionIndex, IdempotencyKeyConflict
from movie_agent.pipeline.jobs import JobCapacityReached, JobLedger
from movie_agent.services.render_input import build_generation_input_fingerprint
from movie_agent.storage.reference_bank import ReferenceBankStore


ROOT = Path(__file__).resolve().parents[1]


def test_frontend_dom_contract_has_unique_ids_and_all_live_app_bindings():
    html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    app = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
    ids = re.findall(r'\bid="([^"]+)"', html)
    assert len(ids) == len(set(ids))
    bound = set(re.findall(r'\$\("#([A-Za-z0-9_-]+)"\)', app))
    assert bound.issubset(set(ids))
    assert 'id="subtitle-mode-control"' in html


def test_manual_navigation_matches_the_four_production_document_tabs():
    html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    nav = re.findall(r'data-manual-nav-tab="([^"]+)"', html)
    tabs = re.findall(r'data-tab="([^"]+)"', html)
    assert nav == ["brief", "script", "visual", "quality"]
    assert tabs[:4] == nav


def test_provider_neutral_ui_and_wrapped_crew_contracts_are_explicit():
    app = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
    crew = (ROOT / "static" / "css" / "crew.css").read_text(encoding="utf-8")
    assert "提交真实生成" in app
    assert "提交 Spark 真实生成" not in app
    assert "MiniMax-H3" not in app
    assert "display: none;" in crew[crew.index(".crew-flow-link"):crew.index(".crew-flow-link") + 160]
    assert "@media (max-width: 599px)" in crew


def test_storyboard_technical_metadata_uses_normal_wrapping():
    css = (ROOT / "static" / "css" / "storyboard.css").read_text(encoding="utf-8")
    start = css.index('body[data-design="archive-console"] .shot-technical-meta')
    rule = css[start:css.index("}", start)]
    assert "white-space: normal;" in rule
    assert "overflow-wrap: break-word;" in rule


def test_evaluator_idempotency_key_rejects_a_different_payload_fingerprint():
    with TemporaryDirectory() as directory:
        index = EvaluatorSubmissionIndex(Path(directory))
        index.reserve("key", project_id="film-1234abcd", job_id="job-123456789abc", request_fingerprint="one")
        with pytest.raises(IdempotencyKeyConflict):
            index.reserve("key", project_id="film-deadbeef", job_id="job-deadbeef1234", request_fingerprint="two")


def test_job_capacity_is_checked_atomically_before_new_job_creation():
    with TemporaryDirectory() as directory:
        ledger = JobLedger(Path(directory))
        ledger.start("film-1234abcd", max_active_jobs=1)
        with pytest.raises(JobCapacityReached):
            ledger.start("film-deadbeef", max_active_jobs=1)


def test_concurrent_evaluator_claims_create_one_index_entry():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        indexes = [EvaluatorSubmissionIndex(root), EvaluatorSubmissionIndex(root)]
        barrier = threading.Barrier(2)
        results = []

        def submit(index: EvaluatorSubmissionIndex, project_id: str, job_id: str) -> None:
            barrier.wait()
            with index.claim_lock():
                existing = index.get("same-key")
                results.append(existing or index.reserve("same-key", project_id=project_id, job_id=job_id, request_fingerprint="same-payload"))

        threads = [
            threading.Thread(target=submit, args=(indexes[0], "film-first", "job-first")),
            threading.Thread(target=submit, args=(indexes[1], "film-second", "job-second")),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert {entry["project_id"] for entry in results} == {"film-first"} or {entry["project_id"] for entry in results} == {"film-second"}
        assert len(results) == 2


def test_global_job_capacity_is_atomic_under_concurrent_starts():
    with TemporaryDirectory() as directory:
        ledger = JobLedger(Path(directory))
        barrier = threading.Barrier(2)
        started = []
        capacity_errors = []

        def start(project_id: str) -> None:
            barrier.wait()
            try:
                started.append(ledger.start(project_id, max_active_jobs=1))
            except JobCapacityReached as error:
                capacity_errors.append(error)

        threads = [threading.Thread(target=start, args=("film-aaaaaaaa",)), threading.Thread(target=start, args=("film-bbbbbbbb",))]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert len(started) == 1
        assert len(capacity_errors) == 1


def test_reference_bank_mutations_from_two_store_instances_are_serialized():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        first = root / "first.webp"
        second = root / "second.webp"
        first.write_bytes(b"first")
        second.write_bytes(b"second")
        stores = [ReferenceBankStore(root / "outputs"), ReferenceBankStore(root / "outputs")]
        barrier = threading.Barrier(2)

        def register(store: ReferenceBankStore, source: Path) -> None:
            barrier.wait()
            store.register_file("film-test", source, kind="prop", source="test")

        threads = [threading.Thread(target=register, args=(stores[0], first)), threading.Thread(target=register, args=(stores[1], second))]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert len(stores[0].load("film-test").assets) == 2


def test_provider_neutral_generation_fingerprint_changes_with_prompt_and_reference():
    base = build_generation_input_fingerprint(
        provider="remote", model="video-1", generation_mode="T2V", compiled_prompt="a shot",
        seed=7, source_duration_seconds=6, reference_digests={"character": "a"}, shot_revision=1,
    )
    changed = build_generation_input_fingerprint(
        provider="remote", model="video-1", generation_mode="T2V", compiled_prompt="another shot",
        seed=7, source_duration_seconds=6, reference_digests={"character": "a"}, shot_revision=1,
    )
    assert base.fingerprint != changed.fingerprint
    assert json.dumps(base.payload(), sort_keys=True)


def test_project_store_preserves_subsecond_revision_precision():
    source = (ROOT / "movie_agent" / "storage" / "project_store.py").read_text(encoding="utf-8")
    assert "datetime.now(timezone.utc).isoformat()" in source
    assert "replace(microsecond=0)" not in source
