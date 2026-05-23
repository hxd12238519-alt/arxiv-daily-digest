from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader, select_autoescape
from typer.testing import CliRunner

from arxiv_digest.cli import app
from arxiv_digest.config import load_config
from arxiv_digest.models import TaskRunStatus
from arxiv_digest.report import report_paths
from arxiv_digest.services import has_today_report, run_daily_pipeline, today_for_profile
from arxiv_digest.storage import Storage
from arxiv_digest.web.security import ForceAuthError, assert_force_allowed, assert_run_allowed
from arxiv_digest.web.tasks import get_or_create_run, run_digest_task


def test_web_index_creates_task_when_report_missing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    config = load_config()
    profile_name = "physics_student"

    assert not has_today_report(config, profile_name)
    run, created = get_or_create_run(
        config,
        profile_name=profile_name,
        provider="mock",
        force=False,
    )

    assert created is True
    assert run.status == TaskRunStatus.QUEUED
    assert _task_count(tmp_path) == 1


def test_web_index_existing_report_does_not_create_task(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    config = load_config()
    run_daily_pipeline(config, profile_name="physics_student", provider="mock", sample=True)

    assert has_today_report(config, "physics_student")
    assert _task_count(tmp_path) == 0


def test_web_refresh_reuses_running_task(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    config = load_config()
    storage = Storage(config.database.path)
    storage.init_db()
    original = storage.create_task_run("existing", "physics_student", "mock")

    run, created = get_or_create_run(
        config,
        profile_name="physics_student",
        provider="mock",
        force=False,
    )

    assert created is False
    assert run.id == original.id
    assert _task_count(tmp_path) == 1


def test_web_api_run_status(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    config = load_config()
    storage = Storage(config.database.path)
    storage.init_db()
    storage.create_task_run("run-1", "physics_student", "mock")

    run = storage.get_task_run("run-1")

    assert run is not None
    assert run.id == "run-1"
    assert run.status == TaskRunStatus.QUEUED


def test_web_api_force_without_token_fails_without_leaking_token(monkeypatch) -> None:
    monkeypatch.setenv("WEB_ADMIN_TOKEN", "super-secret-token")

    with pytest.raises(ForceAuthError) as exc_info:
        assert_force_allowed(force=True, authorization=None)

    assert exc_info.value.status_code == 401
    assert "super-secret-token" not in str(exc_info.value)


def test_public_run_requires_token_without_leaking_token(monkeypatch) -> None:
    monkeypatch.setenv("WEB_ADMIN_TOKEN", "public-secret-token")

    with pytest.raises(ForceAuthError) as exc_info:
        assert_run_allowed(force=False, require_token=True, authorization=None)

    assert exc_info.value.status_code == 401
    assert "public-secret-token" not in str(exc_info.value)


def test_public_run_accepts_bearer_token(monkeypatch) -> None:
    monkeypatch.setenv("WEB_ADMIN_TOKEN", "public-secret-token")

    assert_run_allowed(
        force=False,
        require_token=True,
        authorization="Bearer public-secret-token",
    )


def test_web_task_run_completes_with_mock_sample(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    config = load_config()
    run, _ = get_or_create_run(
        config,
        profile_name="physics_student",
        provider="mock",
        force=False,
    )

    run_digest_task(
        run_id=run.id,
        config=config,
        profile_name="physics_student",
        provider="mock",
        sample=True,
    )
    finished = Storage(config.database.path).get_task_run(run.id)

    assert finished is not None
    assert finished.status == TaskRunStatus.SUCCEEDED
    assert finished.report_html_path


def test_web_report_page_contains_physics_sections(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    config = load_config()
    run_daily_pipeline(config, profile_name="physics_student", provider="mock", sample=True)
    today = today_for_profile(config, "physics_student")
    paths = report_paths(config, report_date=today, profile_name="physics_student")
    data = json.loads(paths["json"].read_text(encoding="utf-8"))
    html = _render_report_template(data)

    assert "摘要中文对应" in html
    assert "English abstract" in html
    assert "中文摘要" in html
    assert "研究问题" not in html


def test_live_smoke_refuses_without_allow_env(monkeypatch) -> None:
    monkeypatch.delenv("ALLOW_LIVE_API_TEST", raising=False)
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["live-smoke", "--profile", "physics_student", "--provider", "mock"],
    )

    assert result.exit_code == 1
    assert "Refusing to run live API test" in result.output


def _task_count(tmp_path: Path) -> int:
    db_path = tmp_path / "data" / "arxiv_digest.sqlite3"
    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT COUNT(*) FROM task_runs").fetchone()
    return int(row[0])


def _render_report_template(data: dict[str, object]) -> str:
    template_dir = Path(__file__).parents[1] / "src" / "arxiv_digest" / "web" / "templates"
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(default=True),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    return env.get_template("report.html").render(request=object(), **data)
