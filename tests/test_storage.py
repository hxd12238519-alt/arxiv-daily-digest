from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from arxiv_digest.models import Paper
from arxiv_digest.storage import Storage


def test_storage_init_insert_and_dedupe(tmp_path: Path) -> None:
    db_path = tmp_path / "digest.sqlite3"
    storage = Storage(db_path)
    storage.init_db()

    with sqlite3.connect(db_path) as conn:
        tables = {
            row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
    assert {"papers", "analysis_jobs", "paper_analyses"} <= tables

    paper = _paper("2401.00001")
    first_id, inserted = storage.insert_paper(paper)
    second_id, duplicate_inserted = storage.insert_paper(paper)

    assert inserted is True
    assert duplicate_inserted is False
    assert first_id == second_id
    assert len(storage.list_papers()) == 1


def test_list_unanalyzed_papers(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "digest.sqlite3")
    storage.init_db()
    storage.insert_paper(_paper("2401.00001"))

    papers = storage.list_unanalyzed_papers("mock", "mock-v1", "physics_student")

    assert len(papers) == 1
    assert papers[0].id is not None


def _paper(arxiv_id: str) -> Paper:
    return Paper(
        arxiv_id=arxiv_id,
        title="Quantum Transport in a Topological Material",
        authors=["Alice"],
        abstract="We study quantum transport in a topological material.",
        published=datetime(2024, 1, 1, tzinfo=UTC),
        updated=datetime(2024, 1, 1, tzinfo=UTC),
        primary_category="cond-mat.mes-hall",
        categories=["cond-mat.mes-hall"],
        abs_url=f"https://arxiv.org/abs/{arxiv_id}",
        pdf_url=f"https://arxiv.org/pdf/{arxiv_id}",
        matched_profile="physics_student",
        keyword_hits=["quantum transport"],
        raw_entry_json={"id": arxiv_id},
    )
