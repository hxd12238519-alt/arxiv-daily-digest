from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from jinja2 import Environment, select_autoescape

from arxiv_digest.config import AppConfig

REPORT_RE = re.compile(r"^(?P<date>\d{4}-\d{2}-\d{2})-(?P<profile>.+)\.html$")
PUBLISH_SUFFIXES = {".html", ".json", ".md"}


@dataclass(frozen=True)
class StaticSiteResult:
    site_dir: Path
    index_path: Path
    report_count: int
    latest_paths: dict[str, Path]


def build_static_site(
    config: AppConfig,
    *,
    site_dir: str | Path = "site",
) -> StaticSiteResult:
    report_dir = Path(config.output.report_dir)
    output_dir = Path(site_dir)
    reports_output_dir = output_dir / "reports"
    latest_output_dir = output_dir / "latest"

    _reset_dir(output_dir)
    reports_output_dir.mkdir(parents=True, exist_ok=True)
    latest_output_dir.mkdir(parents=True, exist_ok=True)

    report_items = _copy_reports(report_dir, reports_output_dir)
    _attach_profile_names(report_items, config)
    latest_by_profile = _latest_reports_by_profile(report_items)
    latest_paths = _write_latest_reports(latest_by_profile, latest_output_dir)
    index_path = output_dir / "index.html"
    index_path.write_text(
        _render_index(
            {
                "title": "arXiv Physics Digest",
                "reports": sorted(report_items, key=lambda item: item["sort_key"], reverse=True),
                "latest_reports": [
                    _index_item_for_latest(item, latest_paths[item["profile"]])
                    for item in sorted(
                        latest_by_profile.values(),
                        key=lambda value: value["profile"],
                    )
                ],
                "public_base_url": config.web.public_base_url,
            }
        ),
        encoding="utf-8",
    )

    return StaticSiteResult(
        site_dir=output_dir,
        index_path=index_path,
        report_count=len(report_items),
        latest_paths=latest_paths,
    )


def _reset_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def _copy_reports(report_dir: Path, reports_output_dir: Path) -> list[dict[str, Any]]:
    if not report_dir.exists():
        return []
    items: list[dict[str, Any]] = []
    for source in sorted(report_dir.iterdir()):
        if not source.is_file() or source.suffix not in PUBLISH_SUFFIXES:
            continue
        destination = reports_output_dir / source.name
        shutil.copy2(source, destination)
        match = REPORT_RE.match(source.name)
        if source.suffix == ".html" and match:
            report_date = date.fromisoformat(match.group("date"))
            profile = match.group("profile")
            items.append(
                {
                    "date": report_date.isoformat(),
                    "profile": profile,
                    "filename": source.name,
                    "path": destination,
                    "href": f"reports/{source.name}",
                    "sort_key": (report_date.isoformat(), profile),
                }
            )
    return items


def _attach_profile_names(report_items: list[dict[str, Any]], config: AppConfig) -> None:
    for item in report_items:
        profile = config.profiles.get(item["profile"])
        item["profile_display_name"] = profile.display_name if profile else item["profile"]
        item["profile_display_name_zh"] = profile.display_name_zh if profile else item["profile"]


def _latest_reports_by_profile(report_items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for item in report_items:
        existing = latest.get(item["profile"])
        if existing is None or item["date"] > existing["date"]:
            latest[item["profile"]] = item
    return latest


def _write_latest_reports(
    latest_by_profile: dict[str, dict[str, Any]],
    latest_output_dir: Path,
) -> dict[str, Path]:
    latest_paths: dict[str, Path] = {}
    for profile, item in latest_by_profile.items():
        destination = latest_output_dir / f"{profile}.html"
        shutil.copy2(item["path"], destination)
        latest_paths[profile] = destination
    return latest_paths


def _index_item_for_latest(item: dict[str, Any], path: Path) -> dict[str, Any]:
    return {
        **item,
        "filename": path.name,
        "href": f"latest/{path.name}",
    }


def _render_index(data: dict[str, Any]) -> str:
    template = Environment(
        autoescape=select_autoescape(default=True),
        trim_blocks=True,
        lstrip_blocks=True,
    ).from_string(INDEX_TEMPLATE)
    return template.render(**data).strip() + "\n"


INDEX_TEMPLATE = """
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ title }}</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f6f7f5;
      --fg: #1f2933;
      --muted: #667085;
      --line: #d8d9d4;
      --panel: #ffffff;
      --accent: #0f766e;
      --accent-soft: #d8f3ee;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--fg);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.55;
    }
    header, main { max-width: 1080px; margin: 0 auto; padding: 24px; }
    header { border-bottom: 1px solid var(--line); }
    h1 { margin: 0 0 8px; font-size: 32px; letter-spacing: 0; }
    h2 { margin-top: 28px; font-size: 22px; }
    a { color: var(--accent); }
    .muted { color: var(--muted); }
    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 18px;
      margin: 18px 0;
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 12px;
    }
    .card {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
    }
    .card h3 { margin: 0 0 8px; font-size: 18px; }
    table { width: 100%; border-collapse: collapse; background: var(--panel); }
    th, td { padding: 10px; border-bottom: 1px solid var(--line); text-align: left; }
    .badge {
      display: inline-block;
      background: var(--accent-soft);
      color: #0b5f59;
      border-radius: 999px;
      padding: 3px 9px;
      font-size: 13px;
    }
  </style>
</head>
<body>
  <header>
    <h1>arXiv Physics Digest</h1>
    <p class="muted">
      物理文献速读公开查阅页。这里只发布静态报告，不包含 API key，也不会触发 LLM 调用。
    </p>
    {% if public_base_url %}
    <p><a href="{{ public_base_url }}">{{ public_base_url }}</a></p>
    {% endif %}
  </header>
  <main>
    <section class="panel">
      <h2>最新报告</h2>
      {% if latest_reports %}
      <div class="grid">
        {% for report in latest_reports %}
        <article class="card">
          <h3>{{ report.profile_display_name }}</h3>
          <p class="muted">{{ report.profile_display_name_zh }}</p>
          <p><span class="badge">{{ report.date }}</span></p>
          <p><a href="{{ report.href }}">打开最新报告</a></p>
        </article>
        {% endfor %}
      </div>
      {% else %}
      <p class="muted">暂无报告。请先运行每日任务生成报告。</p>
      {% endif %}
    </section>

    <section>
      <h2>历史报告</h2>
      {% if reports %}
      <table>
        <thead>
          <tr><th>日期</th><th>Profile</th><th>报告</th></tr>
        </thead>
        <tbody>
          {% for report in reports %}
          <tr>
            <td>{{ report.date }}</td>
            <td>{{ report.profile }}</td>
            <td><a href="{{ report.href }}">{{ report.filename }}</a></td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
      {% else %}
      <p class="muted">暂无历史报告。</p>
      {% endif %}
    </section>
  </main>
</body>
</html>
"""
