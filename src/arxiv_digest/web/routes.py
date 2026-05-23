from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from arxiv_digest.models import TaskRun
from arxiv_digest.report import report_exists, report_paths
from arxiv_digest.services import has_today_window_report, resolve_provider, today_for_profile
from arxiv_digest.storage import Storage
from arxiv_digest.web.security import (
    ForceAuthError,
    assert_run_allowed,
    is_public_host,
    token_status,
)
from arxiv_digest.web.tasks import get_or_create_run, run_digest_task, web_should_use_sample_feed

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


class RunRequest(BaseModel):
    profile: str | None = None
    provider: str | None = None
    force: bool = False
    limit: int | None = Field(default=None, ge=1, le=100)
    lookback_hours: int | None = Field(default=None, ge=1, le=168)
    report_suffix: str = ""


@router.get("/", response_class=HTMLResponse)
def index(
    request: Request,
    background_tasks: BackgroundTasks,
    profile: str | None = None,
    provider: str | None = None,
    force: bool = False,
    authorization: str | None = Header(default=None),
):
    config = request.app.state.digest_config
    profile_name, profile_config = config.get_profile(profile or request.app.state.default_profile)
    provider_name = resolve_provider(config, provider or request.app.state.default_provider)
    today = today_for_profile(config, profile_name)
    report_ready = report_exists(config, report_date=today, profile_name=profile_name)
    seven_day_ready = report_exists(
        config,
        report_date=today,
        profile_name=profile_name,
        report_suffix="7d",
    )
    public_mode = _is_public_mode(request)
    run_requires_token = _run_requires_token(request)

    if force:
        _assert_run_allowed_fastapi(
            force=True,
            require_token=True,
            authorization=authorization,
        )

    storage = Storage(config.database.path)
    storage.init_db()
    active = storage.get_active_task_run(profile_name)
    if active and not force:
        return _status_template(request, active, profile_config.display_name_zh)

    auto_run_allowed = request.app.state.auto_run_on_open and (
        not run_requires_token or config.web.allow_public_auto_run
    )
    if auto_run_allowed and not report_ready:
        run, created = get_or_create_run(
            config,
            profile_name=profile_name,
            provider=provider_name,
            force=force,
        )
        if created:
            background_tasks.add_task(
                run_digest_task,
                run_id=run.id,
                config=config,
                profile_name=profile_name,
                provider=provider_name,
                sample=web_should_use_sample_feed(),
            )
        return _status_template(request, run, profile_config.display_name_zh)

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "title": "arXiv Physics Digest",
            "profile": profile_name,
            "profile_display_name": profile_config.display_name,
            "profile_display_name_zh": profile_config.display_name_zh,
            "provider": provider_name,
            "today": today.isoformat(),
            "report_ready": report_ready,
            "seven_day_ready": seven_day_ready,
            "admin_token_status": token_status(),
            "public_mode": public_mode,
            "run_requires_token": run_requires_token,
            "public_base_url": config.web.public_base_url,
        },
    )


@router.get("/reports/today", response_class=HTMLResponse)
def today_report(request: Request, profile: str | None = None, suffix: str = ""):
    config = request.app.state.digest_config
    profile_name, _ = config.get_profile(profile or request.app.state.default_profile)
    today = today_for_profile(config, profile_name)
    return report_by_date(request, today.isoformat(), profile_name, suffix)


@router.get("/reports/{report_date}", response_class=HTMLResponse)
def report_by_date(
    request: Request,
    report_date: str,
    profile: str | None = None,
    suffix: str = "",
):
    config = request.app.state.digest_config
    profile_name, _ = config.get_profile(profile or request.app.state.default_profile)
    target_date = date.fromisoformat(report_date)
    paths = report_paths(
        config,
        report_date=target_date,
        profile_name=profile_name,
        report_suffix=suffix,
    )
    if not paths["json"].exists():
        raise HTTPException(status_code=404, detail="Report not found.")
    data = json.loads(paths["json"].read_text(encoding="utf-8"))
    return templates.TemplateResponse("report.html", {"request": request, **data})


@router.get("/api/runs/{run_id}")
def api_run_status(run_id: str, request: Request):
    storage = Storage(request.app.state.digest_config.database.path)
    storage.init_db()
    run = storage.get_task_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found.")
    return _run_payload(run)


@router.get("/api/latest")
def api_latest(request: Request, profile: str | None = None, suffix: str = ""):
    config = request.app.state.digest_config
    profile_name, _ = config.get_profile(profile or request.app.state.default_profile)
    today = today_for_profile(config, profile_name)
    paths = report_paths(
        config,
        report_date=today,
        profile_name=profile_name,
        report_suffix=suffix,
    )
    return {
        "profile": profile_name,
        "date": today.isoformat(),
        "exists": paths["json"].exists(),
        "reports": {key: str(path) for key, path in paths.items()},
    }


@router.post("/api/run")
def api_run(
    payload: RunRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    authorization: str | None = Header(default=None),
):
    config = request.app.state.digest_config
    _assert_run_allowed_fastapi(
        force=payload.force,
        require_token=_run_requires_token(request),
        authorization=authorization,
    )
    profile_name, _ = config.get_profile(payload.profile or request.app.state.default_profile)
    provider_name = resolve_provider(config, payload.provider or request.app.state.default_provider)

    report_suffix = payload.report_suffix.strip()
    if (
        has_today_window_report(config, profile_name, report_suffix=report_suffix)
        and not payload.force
    ):
        return JSONResponse(
            {
                "run_id": None,
                "status": "succeeded",
                "status_url": None,
                "message": "Today's report already exists.",
            }
        )

    run, created = get_or_create_run(
        config,
        profile_name=profile_name,
        provider=provider_name,
        force=payload.force,
        lookback_hours=payload.lookback_hours,
        report_suffix=report_suffix,
    )
    if created:
        background_tasks.add_task(
            run_digest_task,
            run_id=run.id,
            config=config,
            profile_name=profile_name,
            provider=provider_name,
            limit=payload.limit,
            lookback_hours=payload.lookback_hours,
            report_suffix=report_suffix,
            sample=web_should_use_sample_feed(),
        )
    return {
        "run_id": run.id,
        "status": run.status.value,
        "status_url": f"/api/runs/{run.id}",
    }


def _status_template(request: Request, run: TaskRun, profile_display_name_zh: str):
    return templates.TemplateResponse(
        "status.html",
        {
            "request": request,
            "run": run,
            "profile_display_name_zh": profile_display_name_zh,
        },
    )


def _assert_run_allowed_fastapi(
    *,
    force: bool,
    require_token: bool,
    authorization: str | None,
) -> None:
    try:
        assert_run_allowed(
            force=force,
            authorization=authorization,
            require_token=require_token,
        )
    except ForceAuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


def _is_public_mode(request: Request) -> bool:
    config = request.app.state.digest_config
    host = os.getenv("ARXIV_DIGEST_WEB_HOST") or config.web.host
    return is_public_host(host)


def _run_requires_token(request: Request) -> bool:
    config = request.app.state.digest_config
    return _is_public_mode(request) and config.web.require_admin_token_for_run


def _run_payload(run: TaskRun) -> dict[str, object]:
    return {
        "run_id": run.id,
        "profile": run.profile,
        "provider": run.provider,
        "lookback_hours": run.lookback_hours,
        "report_suffix": run.report_suffix,
        "status": run.status.value,
        "status_message": run.status_message,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "error_message": run.error_message,
        "report_md_path": run.report_md_path,
        "report_html_path": run.report_html_path,
        "report_json_path": run.report_json_path,
        "report_url": (
            f"/reports/today?profile={run.profile}"
            f"{'&suffix=' + run.report_suffix if run.report_suffix else ''}"
        )
        if run.status.value == "succeeded"
        else None,
    }
