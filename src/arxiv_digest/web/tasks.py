from __future__ import annotations

import logging
import os
import uuid

from arxiv_digest.config import AppConfig
from arxiv_digest.models import TaskRun, TaskRunStatus
from arxiv_digest.report import report_paths
from arxiv_digest.services import run_daily_pipeline, today_for_profile
from arxiv_digest.storage import Storage
from arxiv_digest.utils import utc_now

LOGGER = logging.getLogger(__name__)


def get_or_create_run(
    config: AppConfig,
    *,
    profile_name: str,
    provider: str,
    force: bool = False,
) -> tuple[TaskRun, bool]:
    storage = Storage(config.database.path)
    storage.init_db()
    if not force:
        active = storage.get_active_task_run(profile_name)
        if active:
            return active, False
    run = storage.create_task_run(
        str(uuid.uuid4()),
        profile_name,
        provider,
        status=TaskRunStatus.QUEUED,
        status_message="Queued.",
    )
    return run, True


def run_digest_task(
    *,
    run_id: str,
    config: AppConfig,
    profile_name: str,
    provider: str,
    limit: int | None = None,
    sample: bool = False,
) -> None:
    storage = Storage(config.database.path)
    storage.init_db()
    try:
        storage.update_task_run(
            run_id,
            status=TaskRunStatus.RUNNING,
            status_message="Initializing database and fetching arXiv papers.",
            started_at=utc_now().isoformat(),
        )
        result = run_daily_pipeline(
            config,
            profile_name=profile_name,
            provider=provider,
            limit=limit,
            sample=sample,
        )
        paths = result.reports
        storage.update_task_run(
            run_id,
            status=TaskRunStatus.SUCCEEDED,
            status_message=(
                f"Done. fetched={result.fetched}, "
                f"analyzed={result.analysis.succeeded}, failed={result.analysis.failed}."
            ),
            finished_at=utc_now().isoformat(),
            report_md_path=str(paths.get("markdown", "")),
            report_html_path=str(paths.get("html", "")),
            report_json_path=str(paths.get("json", "")),
        )
    except Exception as exc:
        LOGGER.exception("Task run failed: %s", exc)
        storage.update_task_run(
            run_id,
            status=TaskRunStatus.FAILED,
            status_message="Failed.",
            finished_at=utc_now().isoformat(),
            error_message=str(exc),
        )


def existing_report_paths(config: AppConfig, profile_name: str) -> dict[str, str]:
    today = today_for_profile(config, profile_name)
    return {
        key: str(path)
        for key, path in report_paths(config, report_date=today, profile_name=profile_name).items()
    }


def web_should_use_sample_feed() -> bool:
    return os.getenv("ARXIV_DIGEST_WEB_SAMPLE", "").strip().lower() in {"1", "true", "yes"}
