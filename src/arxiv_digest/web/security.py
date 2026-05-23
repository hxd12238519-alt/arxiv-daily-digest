from __future__ import annotations

import os


class ForceAuthError(RuntimeError):
    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code


def get_admin_token() -> str | None:
    token = os.getenv("WEB_ADMIN_TOKEN")
    return token.strip() if token and token.strip() else None


def is_local_host(host: str) -> bool:
    return host in {"127.0.0.1", "localhost", "::1"}


def is_public_host(host: str) -> bool:
    return not is_local_host(host)


def assert_force_allowed(*, force: bool, authorization: str | None = None) -> None:
    assert_run_allowed(force=force, authorization=authorization, require_token=False)


def assert_run_allowed(
    *,
    force: bool,
    authorization: str | None = None,
    require_token: bool = False,
) -> None:
    if not force and not require_token:
        return
    token = get_admin_token()
    if not token:
        action = "force=true" if force else "starting runs in public mode"
        raise ForceAuthError(f"{action} requires WEB_ADMIN_TOKEN.", 403)
    expected = f"Bearer {token}"
    if authorization != expected:
        action = "force rerun" if force else "starting a run"
        raise ForceAuthError(f"Invalid or missing bearer token for {action}.", 401)


def token_status() -> str:
    return "set" if get_admin_token() else "missing"
