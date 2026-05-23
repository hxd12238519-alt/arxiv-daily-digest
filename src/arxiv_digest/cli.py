from __future__ import annotations

import os
import sys
from datetime import date
from importlib.util import find_spec
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from arxiv_digest.config import AppConfig, load_config
from arxiv_digest.fetch_arxiv import fetch_arxiv_papers, sample_arxiv_papers_for_profile
from arxiv_digest.jobs import AnalysisProgress, analyze_pending_papers
from arxiv_digest.llm.base import ProviderError, ProviderFactory
from arxiv_digest.report import generate_reports
from arxiv_digest.services import run_daily_pipeline
from arxiv_digest.site import build_static_site
from arxiv_digest.storage import Storage

app = typer.Typer(help="Generate bilingual daily digests from the official arXiv API.")
console = Console()


@app.command("init-db")
def init_db(
    config: Path | None = typer.Option(None, "--config", help="Path to config YAML."),
) -> None:
    cfg = load_config(config)
    storage = Storage(cfg.database.path)
    storage.init_db()
    console.print(f"[green]Initialized database:[/green] {cfg.database.path}")


@app.command("fetch")
def fetch(
    profile: str | None = typer.Option(None, "--profile", help="Profile name."),
    sample: bool = typer.Option(False, "--sample", help="Use built-in sample Atom feed."),
    offline: bool = typer.Option(False, "--offline", help="Alias for --sample."),
    config: Path | None = typer.Option(None, "--config", help="Path to config YAML."),
) -> None:
    cfg = load_config(config)
    profile_name, _ = cfg.get_profile(profile)
    storage = Storage(cfg.database.path)
    storage.init_db()
    papers = _fetch_papers(cfg, profile_name=profile_name, sample=sample, offline=offline)
    inserted, duplicates = storage.insert_papers(papers)
    if not papers and not sample and not offline:
        console.print(
            "[yellow]No papers fetched. If the arXiv API is unreachable here, "
            "use --sample or --offline for a local demo.[/yellow]"
        )
    console.print(
        f"[green]Fetched {len(papers)} papers.[/green] New: {inserted}; duplicates: {duplicates}."
    )


@app.command("analyze")
def analyze(
    profile: str | None = typer.Option(None, "--profile", help="Profile name."),
    provider: str | None = typer.Option(None, "--provider", help="Override LLM provider."),
    model: str | None = typer.Option(None, "--model", help="Override model name."),
    limit: int | None = typer.Option(None, "--limit", min=1, help="Maximum papers to analyze."),
    config: Path | None = typer.Option(None, "--config", help="Path to config YAML."),
) -> None:
    cfg = load_config(config)
    storage = Storage(cfg.database.path)
    storage.init_db()
    result = analyze_pending_papers(
        cfg,
        storage,
        profile_name=profile,
        provider_override=provider,
        model_override=model,
        limit=limit,
        progress_callback=_print_analysis_progress,
    )
    console.print(
        "[green]Analysis finished.[/green] "
        f"queued={result.queued}, succeeded={result.succeeded}, "
        f"failed={result.failed}, skipped={result.skipped}"
    )


@app.command("report")
def report(
    profile: str | None = typer.Option(None, "--profile", help="Profile name."),
    report_date: str | None = typer.Option(None, "--date", help="Report date YYYY-MM-DD."),
    output_format: str = typer.Option("all", "--format", help="markdown/html/json/all."),
    config: Path | None = typer.Option(None, "--config", help="Path to config YAML."),
) -> None:
    cfg = load_config(config)
    storage = Storage(cfg.database.path)
    storage.init_db()
    target_date = date.fromisoformat(report_date) if report_date else None
    generated = generate_reports(
        storage,
        cfg,
        report_date=target_date,
        formats=[output_format],
        profile_name=profile,
    )
    for fmt, path in generated.items():
        console.print(f"[green]Generated {fmt} report:[/green] {path}")


@app.command("run-daily")
def run_daily(
    profile: str | None = typer.Option(None, "--profile", help="Profile name."),
    provider: str | None = typer.Option(None, "--provider", help="Override LLM provider."),
    model: str | None = typer.Option(None, "--model", help="Override model name."),
    limit: int | None = typer.Option(None, "--limit", min=1, help="Maximum papers to analyze."),
    sample: bool = typer.Option(False, "--sample", help="Use built-in sample Atom feed."),
    offline: bool = typer.Option(False, "--offline", help="Alias for --sample."),
    config: Path | None = typer.Option(None, "--config", help="Path to config YAML."),
) -> None:
    cfg = load_config(config)
    profile_name, _ = cfg.get_profile(profile)
    storage = Storage(cfg.database.path)
    console.print("[bold]Step 1/4 init-db[/bold]")
    storage.init_db()

    console.print("[bold]Step 2/4 fetch[/bold]")
    papers = _fetch_papers(cfg, profile_name=profile_name, sample=sample, offline=offline)
    inserted, duplicates = storage.insert_papers(papers)
    if not papers and not sample and not offline:
        console.print(
            "[yellow]No papers fetched. If the arXiv API is unreachable here, "
            "use --sample or --offline for a local demo.[/yellow]"
        )
    console.print(f"Fetched {len(papers)} papers. New: {inserted}; duplicates: {duplicates}.")

    console.print("[bold]Step 3/4 analyze[/bold]")
    result = analyze_pending_papers(
        cfg,
        storage,
        profile_name=profile_name,
        provider_override=provider,
        model_override=model,
        limit=limit,
        progress_callback=_print_analysis_progress,
    )
    console.print(
        f"Analysis: queued={result.queued}, succeeded={result.succeeded}, "
        f"failed={result.failed}, skipped={result.skipped}."
    )

    console.print("[bold]Step 4/4 report[/bold]")
    generated = generate_reports(storage, cfg, formats=["all"], profile_name=profile_name)
    for fmt, path in generated.items():
        console.print(f"Generated {fmt}: {path}")


@app.command("doctor")
def doctor(
    profile: str | None = typer.Option(None, "--profile", help="Profile name."),
    config: Path | None = typer.Option(None, "--config", help="Path to config YAML."),
) -> None:
    cfg = load_config(config)
    profile_name, selected_profile = cfg.get_profile(profile)
    table = Table(title="arxiv-daily-digest doctor")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Detail")

    table.add_row("Python", _ok(sys.version_info >= (3, 11)), sys.version.split()[0])
    table.add_row(
        "Config", _ok(bool(cfg.config_path)), cfg.config_path or "using built-in defaults"
    )
    table.add_row("Database path", _ok(True), cfg.database.path)
    db_parent = Path(cfg.database.path).parent
    table.add_row("Database directory", _ok(_is_writable_dir(db_parent)), str(db_parent))
    report_dir = Path(cfg.output.report_dir)
    table.add_row("Report directory", _ok(_is_writable_dir(report_dir)), str(report_dir))
    table.add_row("Provider", _ok(True), cfg.llm.provider)
    table.add_row("Default profile", _ok(True), cfg.default_profile)
    table.add_row("Available profiles", _ok(bool(cfg.profiles)), ", ".join(sorted(cfg.profiles)))
    table.add_row("Current profile", _ok(True), profile_name)
    table.add_row("Profile categories", _ok(True), ", ".join(selected_profile.arxiv.categories))
    table.add_row(
        "Excluded categories",
        _ok(True),
        ", ".join(selected_profile.arxiv.excluded_categories),
    )
    table.add_row(
        "Excluded keywords",
        _ok(True),
        ", ".join(selected_profile.arxiv.excluded_keywords),
    )

    api_key_env = _api_key_env_for_provider(cfg, cfg.llm.provider)
    if api_key_env:
        table.add_row(
            "Provider API key",
            _ok(bool(os.getenv(api_key_env))),
            f"{api_key_env} is {'set' if os.getenv(api_key_env) else 'not set'}",
        )
    else:
        table.add_row("Provider API key", _ok(True), "not required")

    for env_name in [
        "DEEPSEEK_API_KEY",
        "DASHSCOPE_API_KEY",
        "GEMINI_API_KEY",
        "ANTHROPIC_API_KEY",
    ]:
        table.add_row(
            env_name,
            _ok(bool(os.getenv(env_name))),
            "set" if os.getenv(env_name) else "missing",
        )

    try:
        ProviderFactory.create(cfg, profile_name=profile_name)
        table.add_row("Provider config", _ok(True), "provider can be constructed")
    except ProviderError as exc:
        table.add_row("Provider config", _ok(False), str(exc))

    console.print(table)


@app.command("web")
def web(
    host: str = typer.Option("127.0.0.1", "--host", help="Host to bind."),
    port: int = typer.Option(8000, "--port", help="Port to bind."),
    profile: str | None = typer.Option(None, "--profile", help="Default profile."),
    provider: str | None = typer.Option(None, "--provider", help="Default provider."),
    auto_run_on_open: bool = typer.Option(True, "--auto-run-on-open/--no-auto-run-on-open"),
    sample: bool = typer.Option(False, "--sample", help="Use built-in sample feed in web tasks."),
    public: bool = typer.Option(
        False,
        "--public",
        help="Bind 0.0.0.0 for sharing; run actions require WEB_ADMIN_TOKEN.",
    ),
    allow_public_auto_run: bool = typer.Option(
        False,
        "--allow-public-auto-run",
        help="Allow public visitors to auto-generate a missing report.",
    ),
    reload: bool = typer.Option(False, "--reload", help="Enable uvicorn reload."),
) -> None:
    if public and host == "127.0.0.1":
        host = "0.0.0.0"
    os.environ["ARXIV_DIGEST_WEB_HOST"] = host
    os.environ["ARXIV_DIGEST_WEB_PORT"] = str(port)
    os.environ["ARXIV_DIGEST_WEB_AUTO_RUN_ON_OPEN"] = "1" if auto_run_on_open else "0"
    if public:
        os.environ["ARXIV_DIGEST_WEB_REQUIRE_ADMIN_TOKEN_FOR_RUN"] = "1"
        os.environ["ARXIV_DIGEST_WEB_ALLOW_PUBLIC_AUTO_RUN"] = "1" if allow_public_auto_run else "0"
    if profile:
        os.environ["ARXIV_DIGEST_WEB_PROFILE"] = profile
    if provider:
        os.environ["ARXIV_DIGEST_PROVIDER"] = provider
    if sample:
        os.environ["ARXIV_DIGEST_WEB_SAMPLE"] = "1"
    if host not in {"127.0.0.1", "localhost", "::1"} and not os.getenv("WEB_ADMIN_TOKEN"):
        console.print(
            "[yellow]Warning: WEB_ADMIN_TOKEN is missing while host is not local. "
            "Public visitors can read reports, but run actions remain blocked.[/yellow]"
        )
    if public:
        console.print(
            "[yellow]Public sharing mode:[/yellow] reports are readable by visitors; "
            "fetch/analyze/rerun actions require WEB_ADMIN_TOKEN."
        )

    if find_spec("fastapi") is None or find_spec("uvicorn") is None:
        console.print(
            "[yellow]FastAPI/uvicorn are not installed. "
            "Falling back to the built-in stdlib web server.[/yellow]"
        )
        from arxiv_digest.web.simple_app import run_simple_web

        run_simple_web(
            host=host,
            port=port,
            profile=profile,
            provider=provider,
            auto_run_on_open=auto_run_on_open,
        )
        return

    import uvicorn

    uvicorn.run(
        "arxiv_digest.web.app:app",
        host=host,
        port=port,
        reload=reload,
    )


@app.command("live-smoke")
def live_smoke(
    profile: str = typer.Option("physics_student", "--profile", help="Profile name."),
    provider: str = typer.Option("deepseek", "--provider", help="Real provider name."),
    limit: int = typer.Option(2, "--limit", min=1, max=5, help="Maximum papers to analyze."),
    config: Path | None = typer.Option(None, "--config", help="Path to config YAML."),
) -> None:
    if os.getenv("ALLOW_LIVE_API_TEST") != "1":
        console.print(
            "[red]Refusing to run live API test.[/red] Set ALLOW_LIVE_API_TEST=1 explicitly."
        )
        raise typer.Exit(1)

    cfg = load_config(config)
    try:
        ProviderFactory.create(cfg, provider=provider, profile_name=profile)
        result = run_daily_pipeline(
            cfg,
            profile_name=profile,
            provider=provider,
            limit=min(limit, 5),
        )
    except ProviderError as exc:
        console.print(f"[red]Provider configuration error:[/red] {exc}")
        raise typer.Exit(1) from exc
    except Exception as exc:
        console.print(
            "[red]Live smoke test failed.[/red] "
            f"Check network access and provider settings. Detail: {exc}"
        )
        raise typer.Exit(1) from exc

    console.print(f"Fetched papers: {result.fetched}")
    console.print(f"Analyzed succeeded: {result.analysis.succeeded}")
    console.print(f"Analyzed failed: {result.analysis.failed}")
    for fmt, path in result.reports.items():
        console.print(f"{fmt}: {path}")


@app.command("build-site")
def build_site(
    site_dir: Path = typer.Option(Path("site"), "--site-dir", help="Static site output dir."),
    config: Path | None = typer.Option(None, "--config", help="Path to config YAML."),
) -> None:
    cfg = load_config(config)
    result = build_static_site(cfg, site_dir=site_dir)
    console.print(f"[green]Built static site:[/green] {result.site_dir}")
    console.print(f"Index: {result.index_path}")
    console.print(f"HTML reports: {result.report_count}")
    for profile, path in result.latest_paths.items():
        console.print(f"Latest {profile}: {path}")


def _ok(value: bool) -> str:
    return "[green]OK[/green]" if value else "[red]FAIL[/red]"


def _fetch_papers(
    config: AppConfig,
    *,
    profile_name: str,
    sample: bool,
    offline: bool,
):
    if sample or offline:
        console.print("[yellow]Using built-in sample arXiv feed; no network request made.[/yellow]")
        return sample_arxiv_papers_for_profile(config, profile_name)
    return fetch_arxiv_papers(config, profile_name=profile_name)


def _print_analysis_progress(progress: AnalysisProgress) -> None:
    bar = _progress_bar(progress.current, progress.total)
    base = (
        f"Analysis progress {bar} {progress.current}/{progress.total} "
        f"({progress.percent:.1f}%) profile={progress.profile} "
        f"status={progress.status} succeeded={progress.succeeded} "
        f"failed={progress.failed} skipped={progress.skipped}"
    )
    if progress.arxiv_id:
        base += f" arxiv={progress.arxiv_id}"
    if progress.title:
        base += f" title={_shorten(progress.title, 96)}"
    print(base, flush=True)


def _progress_bar(current: int, total: int, width: int = 24) -> str:
    filled = width if total <= 0 else min(width, max(0, round(width * current / total)))
    return f"[{'#' * filled}{'-' * (width - filled)}]"


def _shorten(value: str, limit: int) -> str:
    normalized = " ".join(value.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3] + "..."


def _is_writable_dir(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        return os.access(path, os.W_OK)
    except OSError:
        return False


def _api_key_env_for_provider(config: AppConfig, provider: str) -> str | None:
    provider_name = provider.lower()
    if provider_name == "custom_http":
        return config.providers.custom_http.api_key_env
    if provider_name == "litellm":
        return config.providers.litellm.api_key_env
    if provider_name == "gemini":
        return config.providers.gemini.api_key_env
    if provider_name == "claude":
        return config.providers.claude.api_key_env
    if provider_name == "deepseek":
        return config.providers.deepseek.api_key_env
    if provider_name == "qwen":
        return config.providers.qwen.api_key_env
    return None
