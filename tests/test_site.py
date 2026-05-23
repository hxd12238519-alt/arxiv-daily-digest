from __future__ import annotations

from pathlib import Path

from arxiv_digest.config import load_config
from arxiv_digest.report import generate_reports
from arxiv_digest.services import run_daily_pipeline
from arxiv_digest.site import build_static_site
from arxiv_digest.storage import Storage


def test_build_static_site_contains_latest_report(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    config = load_config()
    run_daily_pipeline(config, profile_name="physics_student", provider="mock", sample=True)
    storage = Storage(config.database.path)
    generate_reports(
        storage,
        config,
        formats=["all"],
        profile_name="physics_student",
        lookback_hours=168,
        report_suffix="7d",
    )

    result = build_static_site(config, site_dir=tmp_path / "site")
    index_html = result.index_path.read_text(encoding="utf-8")

    assert result.report_count == 2
    assert "physics_student" in index_html
    assert "近 36 小时" in index_html
    assert "近 7 天" in index_html
    assert (tmp_path / "site" / "latest" / "physics_student.html").exists()
    assert (tmp_path / "site" / "latest" / "physics_student-7d.html").exists()
    assert (tmp_path / "site" / "reports").exists()
