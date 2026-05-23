from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

from arxiv_digest.config import load_config
from arxiv_digest.llm.providers.mock_provider import MockProvider
from arxiv_digest.models import Paper
from arxiv_digest.report import generate_reports
from arxiv_digest.storage import Storage


def test_generate_markdown_html_and_json_reports(tmp_path: Path) -> None:
    config = load_config()
    config.database.path = str(tmp_path / "digest.sqlite3")
    config.output.report_dir = str(tmp_path / "reports")
    config.output.min_relevance_score = 0
    config.output.top_n = 1

    storage = Storage(config.database.path)
    storage.init_db()
    provider = MockProvider(config, "mock", "mock-v1")
    paper = _paper()
    later_paper = _paper(
        arxiv_id="2401.00002",
        title="Mott Physics in a Correlated Lattice Model",
        published=datetime(2024, 1, 1, 2, 0, tzinfo=UTC),
    )
    for item in [paper, later_paper]:
        paper_id, _ = storage.insert_paper(item)
        storage.save_analysis(
            paper_id,
            "physics_student",
            "mock",
            "mock-v1",
            provider.analyze_paper(item),
        )
    analysis = provider.analyze_paper(paper)

    generated = generate_reports(
        storage,
        config,
        report_date=date(2024, 1, 1),
        formats=["all"],
        profile_name="physics_student",
    )

    assert set(generated) == {"markdown", "html", "json"}
    markdown = generated["markdown"].read_text(encoding="utf-8")
    html = generated["html"].read_text(encoding="utf-8")
    payload = json.loads(generated["json"].read_text(encoding="utf-8"))

    assert paper.title in markdown
    assert analysis.title_zh in markdown
    assert "摘要中文对应" in markdown
    assert "英文摘要" in markdown
    assert "中文摘要" in markdown
    assert "研究问题" not in markdown
    assert "physics_student" in generated["markdown"].name
    assert paper.title in html
    assert analysis.title_zh in html
    assert "摘要中文对应" in html
    assert "English abstract" in html
    assert "中文摘要" in html
    assert "研究问题" not in html
    assert payload["report_mode"] == "abstract_translation"
    assert payload["window_label"] == "近 36 小时"
    assert payload["report_suffix"] == ""
    assert len(payload["papers"]) == 2
    papers_by_title = {item["title_en"]: item for item in payload["papers"]}
    assert papers_by_title[paper.title]["title_zh"] == analysis.title_zh
    assert later_paper.title in papers_by_title


def test_generate_suffix_report(tmp_path: Path) -> None:
    config = load_config()
    config.database.path = str(tmp_path / "digest.sqlite3")
    config.output.report_dir = str(tmp_path / "reports")
    config.output.min_relevance_score = 0

    storage = Storage(config.database.path)
    storage.init_db()
    paper = _paper()
    paper_id, _ = storage.insert_paper(paper)
    analysis = MockProvider(config, "mock", "mock-v1").analyze_paper(paper)
    storage.save_analysis(paper_id, "physics_student", "mock", "mock-v1", analysis)

    generated = generate_reports(
        storage,
        config,
        report_date=date(2024, 1, 1),
        formats=["all"],
        profile_name="physics_student",
        lookback_hours=168,
        report_suffix="7d",
    )
    payload = json.loads(generated["json"].read_text(encoding="utf-8"))

    assert generated["html"].name == "2024-01-01-physics_student-7d.html"
    assert payload["window_label"] == "近 7 天"
    assert payload["report_suffix"] == "7d"


def _paper(
    *,
    arxiv_id: str = "2401.00001",
    title: str = "Superconductivity and Cooper Pairing in a Strongly Correlated System",
    published: datetime = datetime(2024, 1, 1, 1, 0, tzinfo=UTC),
) -> Paper:
    return Paper(
        arxiv_id=arxiv_id,
        title=title,
        authors=["Alice"],
        abstract="We study superconductivity and pairing in a correlated Hubbard system.",
        published=published,
        updated=published,
        primary_category="cond-mat.str-el",
        categories=["cond-mat.str-el"],
        abs_url=f"https://arxiv.org/abs/{arxiv_id}",
        pdf_url=f"https://arxiv.org/pdf/{arxiv_id}",
        matched_profile="physics_student",
        keyword_hits=[],
        raw_entry_json={},
    )
