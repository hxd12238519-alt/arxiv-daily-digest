from __future__ import annotations

import logging
import time
from typing import Any

from pydantic import BaseModel

from arxiv_digest.config import AppConfig
from arxiv_digest.llm.base import LLMProvider, ProviderFactory
from arxiv_digest.storage import Storage

LOGGER = logging.getLogger(__name__)


class AnalyzeResult(BaseModel):
    queued: int = 0
    succeeded: int = 0
    failed: int = 0
    skipped: int = 0


def analyze_pending_papers(
    config: AppConfig,
    storage: Storage,
    *,
    provider_override: str | None = None,
    model_override: str | None = None,
    profile_name: str | None = None,
    limit: int | None = None,
    provider_instance: LLMProvider | None = None,
    sleep_func: Any = time.sleep,
) -> AnalyzeResult:
    resolved_profile_name, _ = config.get_profile(profile_name)
    provider = provider_instance or ProviderFactory.create(
        config,
        provider=provider_override,
        model=model_override,
        profile_name=resolved_profile_name,
    )
    result = AnalyzeResult()

    papers = storage.list_unanalyzed_papers(
        provider.name,
        provider.model,
        resolved_profile_name,
        limit=limit,
    )
    for paper in papers:
        if paper.id is None:
            result.skipped += 1
            continue
        storage.ensure_analysis_job(paper.id, provider.name, provider.model, resolved_profile_name)
        result.queued += 1

    jobs = storage.list_runnable_jobs(
        provider.name,
        provider.model,
        resolved_profile_name,
        max_retries=config.llm.max_retries,
        limit=limit,
    )
    for index, job in enumerate(jobs):
        if job.id is None:
            result.skipped += 1
            continue
        paper = storage.get_paper(job.paper_id)
        if paper is None:
            storage.mark_job_failed(job.id, f"Paper id {job.paper_id} no longer exists.")
            result.failed += 1
            continue

        storage.mark_job_running(job.id)
        try:
            analysis = provider.analyze_paper(paper)
            storage.save_analysis(
                job.paper_id,
                resolved_profile_name,
                provider.name,
                provider.model,
                analysis,
                raw_response_json=analysis.model_dump(),
            )
            storage.mark_job_succeeded(job.id)
            result.succeeded += 1
        except Exception as exc:
            LOGGER.exception("Analysis failed for paper %s: %s", paper.arxiv_id, exc)
            storage.mark_job_failed(job.id, str(exc))
            result.failed += 1

        if index < len(jobs) - 1:
            sleep_func(config.llm.request_interval_seconds)
    return result
