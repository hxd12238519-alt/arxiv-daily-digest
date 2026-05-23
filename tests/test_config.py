from __future__ import annotations

from pathlib import Path

from arxiv_digest.config import load_config


def test_load_config_defaults_without_files(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    config = load_config()

    assert config.llm.provider == "deepseek"
    assert config.llm.model == "deepseek-chat"
    assert config.default_profile == "physics_student"
    assert "physics_student" in config.profiles
    assert "spt_anomaly_generalized_symmetry" in config.profiles
    _, profile = config.get_profile(None)
    assert profile.arxiv.max_results_per_day == 100
    assert profile.arxiv.request_interval_seconds == 3
    assert profile.arxiv.categories == ["cond-mat.str-el"]
    assert profile.arxiv.keywords == []
    assert profile.arxiv.lookback_hours == 168
    assert config.output.min_relevance_score == 0
    assert config.output.top_n == 100
    assert config.database.path == "data/arxiv_digest.sqlite3"


def test_get_profile_reports_available_profiles() -> None:
    config = load_config()

    try:
        config.get_profile("missing")
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected missing profile to raise ValueError")

    assert "physics_student" in message
    assert "spt_anomaly_generalized_symmetry" in message


def test_environment_overrides_sensitive_runtime_fields(tmp_path: Path, monkeypatch) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
llm:
  provider: mock
  model: mock-v1
database:
  path: data/original.sqlite3
providers:
  custom_http:
    endpoint: ""
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("ARXIV_DIGEST_LLM_PROVIDER", "custom_http")
    monkeypatch.setenv("ARXIV_DIGEST_DATABASE_PATH", "data/override.sqlite3")
    monkeypatch.setenv("CUSTOM_LLM_ENDPOINT", "https://example.test/v1/chat/completions")

    config = load_config(config_file)

    assert config.llm.provider == "custom_http"
    assert config.database.path == "data/override.sqlite3"
    assert config.providers.custom_http.endpoint == "https://example.test/v1/chat/completions"
