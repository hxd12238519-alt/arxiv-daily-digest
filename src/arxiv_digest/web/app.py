from __future__ import annotations

import logging
import os

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from arxiv_digest.config import load_config
from arxiv_digest.services import has_today_report, resolve_provider
from arxiv_digest.web.routes import router
from arxiv_digest.web.security import is_local_host
from arxiv_digest.web.tasks import get_or_create_run, run_digest_task, web_should_use_sample_feed

LOGGER = logging.getLogger(__name__)


def create_app() -> FastAPI:
    config = load_config()
    profile_name, _ = config.get_profile(os.getenv("ARXIV_DIGEST_WEB_PROFILE"))
    provider = resolve_provider(config, os.getenv("ARXIV_DIGEST_PROVIDER"))

    app = FastAPI(title="arXiv Physics Digest")
    app.state.digest_config = config
    app.state.default_profile = profile_name
    app.state.default_provider = provider
    app.state.auto_run_on_open = _env_bool(
        "ARXIV_DIGEST_WEB_AUTO_RUN_ON_OPEN",
        config.web.auto_run_on_open,
    )
    app.state.scheduler = None

    static_dir = os.path.join(os.path.dirname(__file__), "static")
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    app.include_router(router)

    @app.on_event("startup")
    def _startup() -> None:
        config = app.state.digest_config
        host = os.getenv("ARXIV_DIGEST_WEB_HOST") or config.web.host
        if not is_local_host(host) and not os.getenv("WEB_ADMIN_TOKEN"):
            LOGGER.warning(
                "WEB_ADMIN_TOKEN is missing while host is not local. "
                "Public visitors can read reports, but run actions will remain blocked."
            )
        if config.web.enable_scheduler:
            scheduler = BackgroundScheduler(timezone="Asia/Tokyo")
            hour, minute = _parse_daily_time(config.web.daily_run_time)
            scheduler.add_job(
                _scheduled_daily_run,
                "cron",
                hour=hour,
                minute=minute,
                args=[app],
                id="daily_digest",
                replace_existing=True,
            )
            scheduler.start()
            app.state.scheduler = scheduler

    @app.on_event("shutdown")
    def _shutdown() -> None:
        scheduler = getattr(app.state, "scheduler", None)
        if scheduler:
            scheduler.shutdown(wait=False)

    return app


def _scheduled_daily_run(app: FastAPI) -> None:
    config = app.state.digest_config
    profile_name = app.state.default_profile
    provider = app.state.default_provider
    if has_today_report(config, profile_name):
        return
    run, created = get_or_create_run(
        config,
        profile_name=profile_name,
        provider=provider,
        force=False,
    )
    if created:
        run_digest_task(
            run_id=run.id,
            config=config,
            profile_name=profile_name,
            provider=provider,
            sample=web_should_use_sample_feed(),
        )


def _parse_daily_time(value: str) -> tuple[int, int]:
    hour_text, minute_text = value.split(":", maxsplit=1)
    return int(hour_text), int(minute_text)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


app = create_app()
