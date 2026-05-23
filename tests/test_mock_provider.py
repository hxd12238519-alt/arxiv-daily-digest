from __future__ import annotations

from datetime import UTC, datetime

from arxiv_digest.config import load_config
from arxiv_digest.llm.providers.mock_provider import MockProvider
from arxiv_digest.llm.schemas import PaperAnalysis
from arxiv_digest.models import Paper


def test_mock_provider_outputs_valid_schema() -> None:
    config = load_config()
    provider = MockProvider(config, "mock", "mock-v1")

    analysis = provider.analyze_paper(_paper())

    assert isinstance(analysis, PaperAnalysis)
    assert 0 <= analysis.relevance_score <= 100
    assert analysis.key_concepts_en
    assert analysis.key_concepts_zh
    assert analysis.title_zh.startswith("Mock 中文标题")


def test_mock_provider_classifies_qah_profile() -> None:
    config = load_config()
    provider = MockProvider(
        config,
        "mock",
        "mock-v1",
        profile_name="condensed_matter_topology_qah",
    )
    analysis = provider.analyze_paper(_qah_paper())

    assert analysis.topic == "Quantum Anomalous Hall / QAHE"


def test_mock_provider_classifies_superconductivity() -> None:
    config = load_config()
    provider = MockProvider(config, "mock", "mock-v1", profile_name="physics_student")
    analysis = provider.analyze_paper(_superconductivity_paper())

    assert analysis.topic == "Superconductivity"


def _paper() -> Paper:
    return Paper(
        arxiv_id="2401.00001",
        title="Topological Quantum Matter with Berry Curvature",
        authors=["Alice"],
        abstract="This paper studies topological quantum matter and Berry curvature.",
        published=datetime(2024, 1, 1, tzinfo=UTC),
        updated=datetime(2024, 1, 1, tzinfo=UTC),
        primary_category="cond-mat.mes-hall",
        categories=["cond-mat.mes-hall"],
        abs_url="https://arxiv.org/abs/2401.00001",
        pdf_url="https://arxiv.org/pdf/2401.00001",
        matched_profile="physics_student",
        keyword_hits=["topological", "Berry curvature"],
        raw_entry_json={},
    )


def _qah_paper() -> Paper:
    paper = _paper()
    paper.title = "Quantum Anomalous Hall Effect in a Chern Insulator"
    paper.abstract = "We study QAH and QAHE physics with chiral edge states."
    paper.keyword_hits = ["quantum anomalous Hall", "QAH", "QAHE"]
    paper.matched_profile = "condensed_matter_topology_qah"
    return paper


def _superconductivity_paper() -> Paper:
    paper = _paper()
    paper.title = "Superconductivity and Cooper Pairing"
    paper.abstract = "We study superconductivity and pairing in a correlated system."
    paper.keyword_hits = ["superconductivity"]
    return paper
