from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

from typer.testing import CliRunner

from arxiv_digest.cli import app
from arxiv_digest.config import load_config
from arxiv_digest.jobs import analyze_pending_papers
from arxiv_digest.llm.base import LLMProvider
from arxiv_digest.llm.providers.mock_provider import MockProvider
from arxiv_digest.llm.schemas import PaperAnalysis
from arxiv_digest.models import AnalysisStatus, Paper
from arxiv_digest.storage import Storage


def test_job_failure_does_not_stop_other_jobs(tmp_path: Path) -> None:
    config = load_config()
    config.database.path = str(tmp_path / "digest.sqlite3")
    config.llm.max_retries = 1
    config.llm.request_interval_seconds = 0

    storage = Storage(config.database.path)
    storage.init_db()
    storage.insert_paper(_paper("2401.00001", "This paper should fail"))
    storage.insert_paper(_paper("2401.00002", "Superconductivity in a Hubbard System"))
    provider = FailingProvider(config)

    result = analyze_pending_papers(
        config,
        storage,
        provider_instance=provider,
        limit=2,
        sleep_func=lambda _: None,
    )

    failed_jobs = storage.list_jobs_by_status(AnalysisStatus.FAILED)
    _, profile = config.get_profile("physics_student")
    records = storage.list_report_records_for_date(
        date(2024, 1, 1),
        profile.arxiv.timezone,
        "physics_student",
    )

    assert result.failed == 1
    assert result.succeeded == 1
    assert len(failed_jobs) == 1
    assert "forced failure" in (failed_jobs[0].error_message or "")
    assert len(records) == 1


class FailingProvider(LLMProvider):
    def __init__(self, config):
        super().__init__(config, "test", "test-model", profile_name="physics_student")
        self.mock = MockProvider(config, "test", "test-model", profile_name="physics_student")

    def analyze_paper(self, paper: Paper) -> PaperAnalysis:
        if "fail" in paper.title.lower():
            raise RuntimeError("forced failure")
        return self.mock.analyze_paper(paper)


def _paper(arxiv_id: str, title: str) -> Paper:
    return Paper(
        arxiv_id=arxiv_id,
        title=title,
        authors=["Alice"],
        abstract="We study superconductivity and quantum transport.",
        published=datetime(2024, 1, 1, tzinfo=UTC),
        updated=datetime(2024, 1, 1, tzinfo=UTC),
        primary_category="cond-mat.str-el",
        categories=["cond-mat.str-el"],
        abs_url=f"https://arxiv.org/abs/{arxiv_id}",
        pdf_url=f"https://arxiv.org/pdf/{arxiv_id}",
        matched_profile="physics_student",
        keyword_hits=["superconductivity", "quantum transport"],
        raw_entry_json={},
    )


def test_run_daily_profile_with_sample_feed(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "run-daily",
            "--profile",
            "physics_student",
            "--provider",
            "mock",
            "--sample",
        ],
    )

    assert result.exit_code == 0, result.output
    assert (tmp_path / "reports" / "2026-05-23-physics_student.md").exists()
