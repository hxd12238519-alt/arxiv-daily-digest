from __future__ import annotations

import json
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
                "latest_groups": _latest_groups(latest_by_profile, latest_paths),
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
            metadata = _report_metadata(report_dir, source)
            profile = str(metadata.get("profile") or match.group("profile"))
            report_suffix = str(metadata.get("report_suffix") or "")
            report_key = str(metadata.get("report_key") or _report_key(profile, report_suffix))
            items.append(
                {
                    "date": report_date.isoformat(),
                    "profile": profile,
                    "report_suffix": report_suffix,
                    "report_key": report_key,
                    "window_label": metadata.get("window_label") or "近 36 小时",
                    "filename": source.name,
                    "path": destination,
                    "href": f"reports/{source.name}",
                    "sort_key": (report_date.isoformat(), profile, report_suffix),
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
        existing = latest.get(item["report_key"])
        if existing is None or item["date"] > existing["date"]:
            latest[item["report_key"]] = item
    return latest


def _write_latest_reports(
    latest_by_profile: dict[str, dict[str, Any]],
    latest_output_dir: Path,
) -> dict[str, Path]:
    latest_paths: dict[str, Path] = {}
    for report_key, item in latest_by_profile.items():
        destination = latest_output_dir / f"{report_key}.html"
        shutil.copy2(item["path"], destination)
        latest_paths[report_key] = destination
    return latest_paths


def _index_item_for_latest(item: dict[str, Any], path: Path) -> dict[str, Any]:
    return {
        **item,
        "filename": path.name,
        "href": f"latest/{path.name}",
    }


def _latest_groups(
    latest_by_profile: dict[str, dict[str, Any]],
    latest_paths: dict[str, Path],
) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for report_key, item in latest_by_profile.items():
        profile = item["profile"]
        group = grouped.setdefault(
            profile,
            {
                "profile": profile,
                "profile_display_name": item["profile_display_name"],
                "profile_display_name_zh": item["profile_display_name_zh"],
                "windows": [],
            },
        )
        group["windows"].append(_index_item_for_latest(item, latest_paths[report_key]))
    for group in grouped.values():
        group["windows"].sort(key=lambda item: (item["report_suffix"] != "", item["window_label"]))
    return sorted(grouped.values(), key=lambda item: item["profile"])


def _report_metadata(report_dir: Path, html_source: Path) -> dict[str, Any]:
    json_path = report_dir / f"{html_source.stem}.json"
    if not json_path.exists():
        return {}
    try:
        return json.loads(json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _report_key(profile: str, report_suffix: str) -> str:
    return f"{profile}-{report_suffix}" if report_suffix else profile


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
      --bg: #f4f6f8;
      --fg: #17202a;
      --muted: #667085;
      --line: #d6dce2;
      --panel: #ffffff;
      --accent: #0b6b74;
      --accent-strong: #084c61;
      --accent-soft: #dff3f5;
      --shadow: 0 10px 28px rgba(22, 34, 51, 0.08);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background:
        linear-gradient(180deg, #eef4f7 0, var(--bg) 280px),
        var(--bg);
      color: var(--fg);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.55;
    }
    header, main { max-width: 1120px; margin: 0 auto; padding: 28px 24px; }
    header { border-bottom: 1px solid var(--line); }
    h1 { margin: 0 0 8px; font-size: 32px; letter-spacing: 0; }
    h2 { margin-top: 28px; font-size: 22px; }
    a { color: var(--accent); }
    .muted { color: var(--muted); }
    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 20px;
      margin: 18px 0;
      box-shadow: var(--shadow);
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
      padding: 18px;
      box-shadow: var(--shadow);
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
    .eyebrow {
      margin: 0 0 6px;
      color: var(--accent-strong);
      font-size: 12px;
      font-weight: 800;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }
    .actions { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 14px; }
    .button {
      display: inline-block;
      border: 1px solid var(--accent);
      background: var(--accent);
      color: #fff;
      border-radius: 6px;
      padding: 8px 12px;
      text-decoration: none;
    }
    .button.secondary {
      background: var(--accent-strong);
      border-color: var(--accent-strong);
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
      {% if latest_groups %}
      <div class="grid">
        {% for group in latest_groups %}
        <article class="card">
          <p class="eyebrow">{{ group.profile }}</p>
          <h3>{{ group.profile_display_name }}</h3>
          <p class="muted">{{ group.profile_display_name_zh }}</p>
          <div class="actions">
            {% for report in group.windows %}
            <a
              class="button {{ 'secondary' if report.report_suffix else '' }}"
              href="{{ report.href }}"
            >
              {{ report.window_label }} · {{ report.date }}
            </a>
            {% endfor %}
          </div>
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
          <tr><th>日期</th><th>窗口</th><th>Profile</th><th>报告</th></tr>
        </thead>
        <tbody>
          {% for report in reports %}
          <tr>
            <td>{{ report.date }}</td>
            <td>{{ report.window_label }}</td>
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
