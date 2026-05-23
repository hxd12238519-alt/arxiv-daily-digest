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
    )

    assert set(generated) == {"markdown", "html", "json"}
    markdown = generated["markdown"].read_text(encoding="utf-8")
    html = generated["html"].read_text(encoding="utf-8")
    payload = json.loads(generated["json"].read_text(encoding="utf-8"))

    assert paper.title in markdown
    assert analysis.title_zh in markdown
    assert "研究问题" in markdown
    assert "物理体系" in markdown
    assert "关键物理概念" in markdown
    assert "主要结果" in markdown
    assert "physics_student" in generated["markdown"].name
    assert paper.title in html
    assert analysis.title_zh in html
    assert payload["papers"][0]["title_en"] == paper.title
    assert payload["papers"][0]["title_zh"] == analysis.title_zh


def _paper() -> Paper:
    return Paper(
        arxiv_id="2401.00001",
        title="Quantum Hall Transport in a Topological Material",
        authors=["Alice"],
        abstract="We study quantum Hall transport and Berry curvature.",
        published=datetime(2024, 1, 1, 1, 0, tzinfo=UTC),
        updated=datetime(2024, 1, 1, 1, 0, tzinfo=UTC),
        primary_category="cond-mat.mes-hall",
        categories=["cond-mat.mes-hall"],
        abs_url="https://arxiv.org/abs/2401.00001",
        pdf_url="https://arxiv.org/pdf/2401.00001",
        matched_profile="physics_student",
        keyword_hits=["quantum Hall"],
        raw_entry_json={},
    )
