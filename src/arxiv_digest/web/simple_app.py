from __future__ import annotations

import json
import os
import threading
from datetime import date
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

from jinja2 import Environment, FileSystemLoader, select_autoescape

from arxiv_digest.config import AppConfig, load_config
from arxiv_digest.models import TaskRun
from arxiv_digest.report import report_exists, report_paths
from arxiv_digest.services import has_today_report, resolve_provider, today_for_profile
from arxiv_digest.storage import Storage
from arxiv_digest.web.security import (
    ForceAuthError,
    assert_run_allowed,
    get_admin_token,
    is_public_host,
    token_status,
)
from arxiv_digest.web.tasks import get_or_create_run, run_digest_task, web_should_use_sample_feed


class SimpleWebState:
    def __init__(
        self,
        config: AppConfig,
        *,
        default_profile: str,
        default_provider: str,
        auto_run_on_open: bool,
        bind_host: str,
    ):
        self.config = config
        self.default_profile = default_profile
        self.default_provider = default_provider
        self.auto_run_on_open = auto_run_on_open
        self.bind_host = bind_host
        self.templates = Environment(
            loader=FileSystemLoader(str(Path(__file__).parent / "templates")),
            autoescape=select_autoescape(default=True),
            trim_blocks=True,
            lstrip_blocks=True,
        )


class DigestHTTPServer(ThreadingHTTPServer):
    def __init__(self, server_address, RequestHandlerClass, state: SimpleWebState):
        super().__init__(server_address, RequestHandlerClass)
        self.state = state


class DigestRequestHandler(BaseHTTPRequestHandler):
    server: DigestHTTPServer

    def log_message(self, format: str, *args) -> None:
        # Keep local server logs compact and avoid echoing request headers.
        return

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        try:
            if parsed.path == "/":
                self._handle_index(query)
            elif parsed.path == "/reports/today":
                self._handle_report_today(query)
            elif parsed.path.startswith("/reports/"):
                self._handle_report_date(parsed.path.removeprefix("/reports/"), query)
            elif parsed.path.startswith("/api/runs/"):
                self._handle_api_run(parsed.path.removeprefix("/api/runs/"))
            elif parsed.path == "/api/latest":
                self._handle_api_latest(query)
            elif parsed.path.startswith("/static/"):
                self._handle_static(parsed.path.removeprefix("/static/"))
            else:
                self._send_text("Not found", status=HTTPStatus.NOT_FOUND)
        except Exception as exc:
            self._send_html(
                self._render("error.html", {"message": str(exc)}),
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/run":
            self._send_json({"detail": "Not found"}, status=HTTPStatus.NOT_FOUND)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length).decode("utf-8") if length else "{}"
            payload = json.loads(raw or "{}")
            self._handle_api_run_create(payload)
        except Exception as exc:
            self._send_json({"detail": str(exc)}, status=HTTPStatus.BAD_REQUEST)

    def _handle_index(self, query: dict[str, list[str]]) -> None:
        state = self.server.state
        profile_name, profile = state.config.get_profile(
            _first(query, "profile") or state.default_profile
        )
        provider = resolve_provider(
            state.config, _first(query, "provider") or state.default_provider
        )
        force = _first(query, "force") == "true"
        today = today_for_profile(state.config, profile_name)
        ready = report_exists(state.config, report_date=today, profile_name=profile_name)
        public_mode = self._is_public_mode()
        run_requires_token = self._run_requires_token()
        if force and not self._assert_run_allowed(force=True, require_token=True):
            return
        if ready and not force:
            self._redirect(f"/reports/today?profile={profile_name}")
            return

        storage = Storage(state.config.database.path)
        storage.init_db()
        active = storage.get_active_task_run(profile_name)
        if active and not force:
            self._send_status(active, profile.display_name_zh)
            return

        auto_run_allowed = state.auto_run_on_open and (
            not run_requires_token or state.config.web.allow_public_auto_run
        )
        if auto_run_allowed:
            run, created = get_or_create_run(
                state.config,
                profile_name=profile_name,
                provider=provider,
                force=force,
            )
            if created:
                _start_background_run(state.config, run.id, profile_name, provider)
            self._send_status(run, profile.display_name_zh)
            return

        self._send_html(
            self._render(
                "index.html",
                {
                    "title": "arXiv Physics Digest",
                    "profile": profile_name,
                    "profile_display_name": profile.display_name,
                    "profile_display_name_zh": profile.display_name_zh,
                    "provider": provider,
                    "today": today.isoformat(),
                    "report_ready": ready,
                    "admin_token_status": token_status(),
                    "public_mode": public_mode,
                    "run_requires_token": run_requires_token,
                    "public_base_url": state.config.web.public_base_url,
                },
            )
        )

    def _handle_report_today(self, query: dict[str, list[str]]) -> None:
        state = self.server.state
        profile_name, _ = state.config.get_profile(
            _first(query, "profile") or state.default_profile
        )
        today = today_for_profile(state.config, profile_name)
        self._handle_report_date(today.isoformat(), {"profile": [profile_name]})

    def _handle_report_date(self, report_date: str, query: dict[str, list[str]]) -> None:
        state = self.server.state
        profile_name, _ = state.config.get_profile(
            _first(query, "profile") or state.default_profile
        )
        target_date = date.fromisoformat(report_date)
        paths = report_paths(state.config, report_date=target_date, profile_name=profile_name)
        if not paths["json"].exists():
            self._send_text("Report not found", status=HTTPStatus.NOT_FOUND)
            return
        data = json.loads(paths["json"].read_text(encoding="utf-8"))
        self._send_html(self._render("report.html", data))

    def _handle_api_run(self, run_id: str) -> None:
        storage = Storage(self.server.state.config.database.path)
        storage.init_db()
        run = storage.get_task_run(run_id)
        if run is None:
            self._send_json({"detail": "Run not found"}, status=HTTPStatus.NOT_FOUND)
            return
        self._send_json(_run_payload(run))

    def _handle_api_latest(self, query: dict[str, list[str]]) -> None:
        state = self.server.state
        profile_name, _ = state.config.get_profile(
            _first(query, "profile") or state.default_profile
        )
        today = today_for_profile(state.config, profile_name)
        paths = report_paths(state.config, report_date=today, profile_name=profile_name)
        self._send_json(
            {
                "profile": profile_name,
                "date": today.isoformat(),
                "exists": paths["json"].exists(),
                "reports": {key: str(path) for key, path in paths.items()},
            }
        )

    def _handle_api_run_create(self, payload: dict[str, object]) -> None:
        state = self.server.state
        force = bool(payload.get("force", False))
        if not self._assert_run_allowed(
            force=force,
            require_token=self._run_requires_token(),
        ):
            return
        profile_name, _ = state.config.get_profile(
            str(payload.get("profile") or state.default_profile)
        )
        provider = resolve_provider(
            state.config, str(payload.get("provider") or state.default_provider)
        )
        limit = payload.get("limit")
        limit_int = int(limit) if limit is not None else None
        if has_today_report(state.config, profile_name) and not force:
            self._send_json(
                {
                    "run_id": None,
                    "status": "succeeded",
                    "status_url": None,
                    "message": "Today's report already exists.",
                }
            )
            return
        run, created = get_or_create_run(
            state.config,
            profile_name=profile_name,
            provider=provider,
            force=force,
        )
        if created:
            _start_background_run(state.config, run.id, profile_name, provider, limit=limit_int)
        self._send_json(
            {
                "run_id": run.id,
                "status": run.status.value,
                "status_url": f"/api/runs/{run.id}",
            }
        )

    def _handle_static(self, relative_path: str) -> None:
        static_root = (Path(__file__).parent / "static").resolve()
        static_path = (static_root / relative_path).resolve()
        if not static_path.is_file() or static_root not in static_path.parents:
            self._send_text("Not found", status=HTTPStatus.NOT_FOUND)
            return
        content_type = "text/css" if static_path.suffix == ".css" else "application/javascript"
        self._send_bytes(static_path.read_bytes(), content_type=content_type)

    def _send_status(self, run: TaskRun, profile_display_name_zh: str) -> None:
        self._send_html(
            self._render(
                "status.html",
                {
                    "run": run,
                    "profile_display_name_zh": profile_display_name_zh,
                },
            )
        )

    def _render(self, template_name: str, context: dict[str, object]) -> str:
        template = self.server.state.templates.get_template(template_name)
        context = {"request": SimpleNamespace(url=self.path), **context}
        return template.render(**context)

    def _assert_run_allowed(self, *, force: bool, require_token: bool) -> bool:
        authorization = self.headers.get("Authorization")
        try:
            assert_run_allowed(
                force=force,
                authorization=authorization,
                require_token=require_token,
            )
        except ForceAuthError as exc:
            self._send_json({"detail": str(exc)}, status=HTTPStatus(exc.status_code))
            return False
        return True

    def _is_public_mode(self) -> bool:
        return is_public_host(self.server.state.bind_host)

    def _run_requires_token(self) -> bool:
        return self._is_public_mode() and self.server.state.config.web.require_admin_token_for_run

    def _redirect(self, location: str) -> None:
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Location", location)
        self.end_headers()

    def _send_html(self, html: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        self._send_bytes(
            html.encode("utf-8"), status=status, content_type="text/html; charset=utf-8"
        )

    def _send_text(self, text: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        self._send_bytes(
            text.encode("utf-8"), status=status, content_type="text/plain; charset=utf-8"
        )

    def _send_json(self, payload: dict[str, object], status: HTTPStatus = HTTPStatus.OK) -> None:
        self._send_bytes(
            json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            status=status,
            content_type="application/json; charset=utf-8",
        )

    def _send_bytes(
        self,
        content: bytes,
        *,
        status: HTTPStatus = HTTPStatus.OK,
        content_type: str,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


def run_simple_web(
    *,
    host: str = "127.0.0.1",
    port: int = 8000,
    profile: str | None = None,
    provider: str | None = None,
    auto_run_on_open: bool = True,
) -> None:
    config = load_config()
    profile_name, _ = config.get_profile(profile or os.getenv("ARXIV_DIGEST_WEB_PROFILE"))
    provider_name = resolve_provider(config, provider or os.getenv("ARXIV_DIGEST_PROVIDER"))
    state = SimpleWebState(
        config,
        default_profile=profile_name,
        default_provider=provider_name,
        auto_run_on_open=auto_run_on_open,
        bind_host=host,
    )
    server = DigestHTTPServer((host, port), DigestRequestHandler, state)
    print(f"Serving arXiv Physics Digest on http://{host}:{port}")
    if host not in {"127.0.0.1", "localhost", "::1"} and not get_admin_token():
        print("Warning: WEB_ADMIN_TOKEN is missing while host is not local.")
    server.serve_forever()


def _start_background_run(
    config: AppConfig,
    run_id: str,
    profile_name: str,
    provider: str,
    *,
    limit: int | None = None,
) -> None:
    thread = threading.Thread(
        target=run_digest_task,
        kwargs={
            "run_id": run_id,
            "config": config,
            "profile_name": profile_name,
            "provider": provider,
            "limit": limit,
            "sample": web_should_use_sample_feed(),
        },
        daemon=True,
    )
    thread.start()


def _first(query: dict[str, list[str]], key: str) -> str | None:
    values = query.get(key)
    return values[0] if values else None


def _run_payload(run: TaskRun) -> dict[str, object]:
    return {
        "run_id": run.id,
        "profile": run.profile,
        "provider": run.provider,
        "status": run.status.value,
        "status_message": run.status_message,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "error_message": run.error_message,
        "report_md_path": run.report_md_path,
        "report_html_path": run.report_html_path,
        "report_json_path": run.report_json_path,
        "report_url": f"/reports/today?profile={run.profile}"
        if run.status.value == "succeeded"
        else None,
    }
