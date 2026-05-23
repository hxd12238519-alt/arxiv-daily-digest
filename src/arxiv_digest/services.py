from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from arxiv_digest.config import AppConfig
from arxiv_digest.fetch_arxiv import fetch_arxiv_papers, sample_arxiv_papers_for_profile
from arxiv_digest.jobs import AnalyzeResult, analyze_pending_papers
from arxiv_digest.report import generate_reports, report_exists
from arxiv_digest.storage import Storage
from arxiv_digest.utils import today_in_timezone


class DailyRunResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    profile: str
    provider: str
    fetched: int
    inserted: int
    duplicates: int
    analysis: AnalyzeResult
    reports: dict[str, Path]


def resolve_provider(config: AppConfig, provider_override: str | None = None) -> str:
    return provider_override or config.llm.provider


def today_for_profile(config: AppConfig, profile_name: str) -> date:
    _, profile = config.get_profile(profile_name)
    return today_in_timezone(profile.arxiv.timezone)


def has_today_report(config: AppConfig, profile_name: str) -> bool:
    return report_exists(
        config,
        report_date=today_for_profile(config, profile_name),
        profile_name=profile_name,
    )


def has_today_window_report(
    config: AppConfig,
    profile_name: str,
    *,
    report_suffix: str | None = None,
) -> bool:
    return report_exists(
        config,
        report_date=today_for_profile(config, profile_name),
        profile_name=profile_name,
        report_suffix=report_suffix,
    )


def run_daily_pipeline(
    config: AppConfig,
    *,
    profile_name: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    limit: int | None = None,
    sample: bool = False,
    sleep_func: Any | None = None,
    lookback_hours: int | None = None,
    report_suffix: str | None = None,
) -> DailyRunResult:
    resolved_profile_name, _ = config.get_profile(profile_name)
    run_config = _config_with_lookback(config, resolved_profile_name, lookback_hours)
    resolved_provider = resolve_provider(config, provider)
    storage = Storage(run_config.database.path)
    storage.init_db()

    if sample:
        papers = sample_arxiv_papers_for_profile(run_config, resolved_profile_name)
    else:
        kwargs = {"profile_name": resolved_profile_name}
        if sleep_func is not None:
            kwargs["sleep_func"] = sleep_func
        papers = fetch_arxiv_papers(run_config, **kwargs)

    inserted, duplicates = storage.insert_papers(papers)
    analysis = analyze_pending_papers(
        run_config,
        storage,
        profile_name=resolved_profile_name,
        provider_override=resolved_provider,
        model_override=model,
        limit=limit,
        sleep_func=sleep_func or _default_sleep,
    )
    reports = generate_reports(
        storage,
        run_config,
        formats=["all"],
        profile_name=resolved_profile_name,
        lookback_hours=lookback_hours,
        report_suffix=report_suffix,
    )
    return DailyRunResult(
        profile=resolved_profile_name,
        provider=resolved_provider,
        fetched=len(papers),
        inserted=inserted,
        duplicates=duplicates,
        analysis=analysis,
        reports=reports,
    )


def _default_sleep(seconds: float) -> None:
    import time

    time.sleep(seconds)


def _config_with_lookback(
    config: AppConfig,
    profile_name: str,
    lookback_hours: int | None,
) -> AppConfig:
    if lookback_hours is None:
        return config
    cloned = config.model_copy(deep=True)
    cloned.profiles[profile_name].arxiv.lookback_hours = max(1, int(lookback_hours))
    return cloned
