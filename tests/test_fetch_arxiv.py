from __future__ import annotations

from datetime import UTC, datetime

from arxiv_digest.config import load_config
from arxiv_digest.fetch_arxiv import (
    apply_profile_filters,
    build_search_query,
    parse_arxiv_feed,
    sample_arxiv_papers,
)
from arxiv_digest.models import Paper

SAMPLE_ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:arxiv="http://arxiv.org/schemas/atom">
  <title>ArXiv Query Results</title>
  <entry>
    <id>http://arxiv.org/abs/2401.00001v1</id>
    <updated>2024-01-02T03:04:05Z</updated>
    <published>2024-01-01T01:02:03Z</published>
    <title>Large Language Model Agents for Reasoning</title>
    <summary>
      We study large language model agents and retrieval augmented reasoning.
    </summary>
    <author><name>Alice Smith</name></author>
    <author><name>Bob Chen</name></author>
    <arxiv:primary_category term="cs.AI" scheme="http://arxiv.org/schemas/atom"/>
    <category term="cs.AI" scheme="http://arxiv.org/schemas/atom"/>
    <category term="cs.LG" scheme="http://arxiv.org/schemas/atom"/>
    <link href="http://arxiv.org/abs/2401.00001v1" rel="alternate" type="text/html"/>
    <link title="pdf" href="http://arxiv.org/pdf/2401.00001v1"
          rel="related" type="application/pdf"/>
  </entry>
</feed>
"""


def test_parse_arxiv_feed_from_local_sample() -> None:
    papers = parse_arxiv_feed(SAMPLE_ATOM)

    assert len(papers) == 1
    paper = papers[0]
    assert paper.arxiv_id == "2401.00001"
    assert paper.title == "Large Language Model Agents for Reasoning"
    assert paper.authors == ["Alice Smith", "Bob Chen"]
    assert paper.primary_category == "cs.AI"
    assert paper.categories == ["cs.AI", "cs.LG"]
    assert paper.abs_url == "http://arxiv.org/abs/2401.00001v1"
    assert paper.pdf_url == "http://arxiv.org/pdf/2401.00001v1"


def test_build_search_query_includes_categories_keywords_and_utc_window() -> None:
    config = load_config()
    now = datetime(2024, 1, 2, 12, 30, tzinfo=UTC)

    query = build_search_query(config, now=now)

    positive_part = query.split("ANDNOT")[0]
    assert "cat:cond-mat.mes-hall" in positive_part
    assert "cat:cs.AI" not in positive_part
    assert "cat:cs.LG" not in positive_part
    assert "cat:stat.ML" not in positive_part
    assert 'all:"quantum transport"' in query
    assert 'all:"machine learning"' in query
    assert "all:LLM" in query
    assert "submittedDate:[202401011230 TO 202401021230]" in query


def test_spt_profile_query_contains_anomaly_and_symmetry_terms() -> None:
    config = load_config()
    query = build_search_query(config, profile_name="spt_anomaly_generalized_symmetry")

    assert "cat:hep-th" in query
    assert 'all:"symmetry-protected topological"' in query
    assert 'all:"quantum anomaly"' in query
    assert 'all:"generalized global symmetry"' in query
    assert "quantum anomalous Hall" not in query
    assert "ANDNOT" in query


def test_profile_post_filter_excludes_machine_learning() -> None:
    config = load_config()
    profile_name, profile = config.get_profile("physics_student")
    paper = Paper(
        arxiv_id="2401.00003",
        title="Machine Learning for Quantum Matter",
        authors=["Alice"],
        abstract="A neural network studies quantum transport.",
        published=datetime(2024, 1, 1, tzinfo=UTC),
        updated=datetime(2024, 1, 1, tzinfo=UTC),
        primary_category="cs.LG",
        categories=["cs.LG"],
        abs_url="https://arxiv.org/abs/2401.00003",
        pdf_url=None,
        raw_entry_json={},
    )

    assert apply_profile_filters([paper], profile_name, profile) == []


def test_sample_arxiv_papers_uses_local_feed() -> None:
    papers = sample_arxiv_papers()

    assert len(papers) == 2
    assert papers[0].arxiv_id == "2605.23001"
    assert "Symmetry-Protected Topological" in papers[0].title
