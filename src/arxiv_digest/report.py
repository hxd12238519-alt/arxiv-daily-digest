from __future__ import annotations

from collections import Counter, defaultdict
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from jinja2 import Environment, select_autoescape

from arxiv_digest.config import AppConfig
from arxiv_digest.storage import Storage
from arxiv_digest.utils import ensure_dir, json_dumps, today_in_timezone

FORMAT_ALIASES = {
    "md": "markdown",
    "markdown": "markdown",
    "html": "html",
    "json": "json",
    "all": "all",
}


def report_paths(
    config: AppConfig,
    *,
    report_date: date,
    profile_name: str,
) -> dict[str, Path]:
    stem = f"{report_date.isoformat()}-{profile_name}"
    output_dir = Path(config.output.report_dir)
    return {
        "markdown": output_dir / f"{stem}.md",
        "html": output_dir / f"{stem}.html",
        "json": output_dir / f"{stem}.json",
    }


def report_exists(config: AppConfig, *, report_date: date, profile_name: str) -> bool:
    paths = report_paths(config, report_date=report_date, profile_name=profile_name)
    return paths["html"].exists() and paths["json"].exists()


def generate_reports(
    storage: Storage,
    config: AppConfig,
    *,
    report_date: date | None = None,
    formats: list[str] | None = None,
    profile_name: str | None = None,
) -> dict[str, Path]:
    resolved_profile_name, profile = config.get_profile(profile_name)
    target_date = report_date or today_in_timezone(profile.arxiv.timezone)
    selected_formats = _normalize_formats(formats or config.output.formats)
    report_data = build_report_data(storage, config, target_date, resolved_profile_name)
    output_dir = ensure_dir(config.output.report_dir)
    generated: dict[str, Path] = {}

    stem = f"{target_date.isoformat()}-{resolved_profile_name}"
    if "markdown" in selected_formats:
        path = output_dir / f"{stem}.md"
        path.write_text(render_markdown(report_data), encoding="utf-8")
        generated["markdown"] = path
    if "html" in selected_formats:
        path = output_dir / f"{stem}.html"
        path.write_text(render_html(report_data), encoding="utf-8")
        generated["html"] = path
    if "json" in selected_formats:
        path = output_dir / f"{stem}.json"
        path.write_text(json_dumps(report_data), encoding="utf-8")
        generated["json"] = path
    return generated


def build_report_data(
    storage: Storage,
    config: AppConfig,
    target_date: date,
    profile_name: str | None = None,
) -> dict[str, Any]:
    resolved_profile_name, profile = config.get_profile(profile_name)
    window_start, window_end = _report_window(
        target_date,
        timezone_name=profile.arxiv.timezone,
        lookback_hours=profile.arxiv.lookback_hours,
    )
    all_papers = storage.list_papers_by_window(
        window_start,
        window_end,
        profile=resolved_profile_name,
    )
    records = storage.list_report_records_for_window(
        window_start,
        window_end,
        resolved_profile_name,
    )
    paper_items = [_record_to_item(record, profile.arxiv.timezone) for record in records]
    topic_counter = Counter((item["topic"], item["topic_zh"]) for item in paper_items)
    topics = [
        {"topic": topic, "topic_zh": topic_zh, "count": count}
        for (topic, topic_zh), count in topic_counter.most_common()
    ]
    recommended_all = [
        item for item in paper_items if item["relevance_score"] >= config.output.min_relevance_score
    ]
    recommended_all.sort(key=lambda item: item["relevance_score"], reverse=True)
    recommended = recommended_all[: config.output.top_n]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in recommended:
        grouped[item["topic"]].append(item)

    return {
        "date": target_date.isoformat(),
        "timezone": profile.arxiv.timezone,
        "window_start": _format_datetime(window_start.astimezone(ZoneInfo(profile.arxiv.timezone))),
        "window_end": _format_datetime(window_end.astimezone(ZoneInfo(profile.arxiv.timezone))),
        "profile": resolved_profile_name,
        "profile_display_name": profile.display_name,
        "profile_display_name_zh": profile.display_name_zh,
        "profile_description": profile.description,
        "excluded_categories": profile.arxiv.excluded_categories,
        "excluded_keywords": profile.arxiv.excluded_keywords,
        "total_papers": len(all_papers),
        "analyzed_papers": len(paper_items),
        "recommended_papers": len(recommended_all),
        "topics": topics,
        "papers": recommended,
        "papers_by_topic": [
            {"topic": topic, "papers": papers}
            for topic, papers in sorted(grouped.items(), key=lambda pair: pair[0])
        ],
    }


def render_markdown(data: dict[str, Any]) -> str:
    template = _environment(autoescape=False).from_string(MARKDOWN_TEMPLATE)
    return template.render(**data).strip() + "\n"


def render_html(data: dict[str, Any]) -> str:
    template = _environment(autoescape=True).from_string(HTML_TEMPLATE)
    return template.render(**data).strip() + "\n"


def _record_to_item(record: dict[str, Any], timezone_name: str) -> dict[str, Any]:
    paper = record["paper"]
    analysis = record["analysis"]
    local_tz = ZoneInfo(timezone_name)
    published_local = paper.published.astimezone(local_tz)
    updated_local = paper.updated.astimezone(local_tz)
    return {
        "arxiv_id": paper.arxiv_id,
        "title_en": paper.title,
        "title_zh": analysis.title_zh,
        "authors": paper.authors,
        "authors_text": ", ".join(paper.authors),
        "abstract_en": paper.abstract,
        "abstract_zh": analysis.abstract_zh,
        "published": _format_datetime(published_local),
        "updated": _format_datetime(updated_local),
        "primary_category": paper.primary_category,
        "categories": paper.categories,
        "categories_text": ", ".join(paper.categories),
        "keyword_hits": paper.keyword_hits,
        "keyword_hits_text": ", ".join(paper.keyword_hits) if paper.keyword_hits else "-",
        "abs_url": paper.abs_url,
        "pdf_url": paper.pdf_url,
        "topic": analysis.topic,
        "topic_zh": analysis.topic_zh,
        "physics_problem_en": analysis.physics_problem_en,
        "physics_problem_zh": analysis.physics_problem_zh,
        "physical_system_en": analysis.physical_system_en,
        "physical_system_zh": analysis.physical_system_zh,
        "key_concepts_en": analysis.key_concepts_en,
        "key_concepts_zh": analysis.key_concepts_zh,
        "method_type": analysis.method_type,
        "method_en": analysis.method_en,
        "method_zh": analysis.method_zh,
        "main_results_en": analysis.main_results_en,
        "main_results_zh": analysis.main_results_zh,
        "experiments_or_calculations_en": analysis.experiments_or_calculations_en,
        "experiments_or_calculations_zh": analysis.experiments_or_calculations_zh,
        "limitations_en": analysis.limitations_en,
        "limitations_zh": analysis.limitations_zh,
        "why_relevant_en": analysis.why_relevant_en,
        "why_relevant_zh": analysis.why_relevant_zh,
        "suggested_reading_priority": analysis.suggested_reading_priority,
        "keywords_en": analysis.keywords_en,
        "keywords_zh": analysis.keywords_zh,
        "relevance_score": analysis.relevance_score,
        "recommended_reason_zh": analysis.recommended_reason_zh,
        "provider": record["provider"],
        "model": record["model"],
        "profile": record["profile"],
    }


def _normalize_formats(formats: list[str]) -> set[str]:
    normalized = {FORMAT_ALIASES.get(item.lower(), item.lower()) for item in formats}
    if "all" in normalized:
        return {"markdown", "html", "json"}
    unsupported = normalized - {"markdown", "html", "json"}
    if unsupported:
        raise ValueError(f"Unsupported report format(s): {', '.join(sorted(unsupported))}")
    return normalized


def _format_datetime(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M %Z")


def _report_window(
    target_date: date,
    *,
    timezone_name: str,
    lookback_hours: int,
) -> tuple[datetime, datetime]:
    local_tz = ZoneInfo(timezone_name)
    end_local = datetime.combine(target_date + timedelta(days=1), time.min, tzinfo=local_tz)
    start_local = end_local - timedelta(hours=max(1, lookback_hours))
    return start_local.astimezone(UTC), end_local.astimezone(UTC)


def _environment(*, autoescape: bool) -> Environment:
    return Environment(
        autoescape=select_autoescape(default=autoescape),
        trim_blocks=True,
        lstrip_blocks=True,
    )


MARKDOWN_TEMPLATE = """
# arXiv Physics Digest - {{ date }}

方向：{{ profile_display_name }} / {{ profile_display_name_zh }}
今日共抓取 {{ total_papers }} 篇相关论文，其中完成分析 {{ analyzed_papers }} 篇。
统计窗口：{{ window_start }} 至 {{ window_end }}。

## 今日主题分布

| 主题 | 中文主题 | 数量 |
|---|---|---:|
{% for topic in topics -%}
| {{ topic.topic }} | {{ topic.topic_zh }} | {{ topic.count }} |
{% else -%}
| - | - | 0 |
{% endfor %}

## 论文分析与总结

{% for paper in papers %}
### {{ loop.index }}. {{ paper.title_en }}

**中文标题**：{{ paper.title_zh }}
**arXiv**：{{ paper.abs_url }}
**PDF**：{{ paper.pdf_url or "N/A" }}
**作者**：{{ paper.authors_text }}
**arXiv 分类**：{{ paper.categories_text }}
**命中关键词**：{{ paper.keyword_hits_text }}
**主题**：{{ paper.topic }} / {{ paper.topic_zh }}
**推荐分数**：{{ paper.relevance_score }}
**阅读优先级**：{{ paper.suggested_reading_priority }}

**研究问题**

{{ paper.physics_problem_zh }}

**物理体系 / 材料体系 / 模型**

{{ paper.physical_system_zh }}

**关键物理概念**
{% for item in paper.key_concepts_zh %}
- {{ item }}
{% endfor %}

**方法类型**

{{ paper.method_type }}

**主要结果**

{{ paper.main_results_zh }}

**实验或计算内容**

{{ paper.experiments_or_calculations_zh }}

**局限性**

{{ paper.limitations_zh }}

**为什么值得读**

{{ paper.why_relevant_zh }}

**英文摘要总结**

{{ paper.main_results_en }}
{% else %}
暂无已完成分析的论文。
{% endfor %}
"""

HTML_TEMPLATE = """
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>arXiv Physics Digest - {{ date }} - {{ profile }}</title>
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
      --high: #b42318;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--fg);
      line-height: 1.55;
    }
    header, main { max-width: 1080px; margin: 0 auto; padding: 24px; }
    header { border-bottom: 1px solid var(--line); }
    h1 { margin: 0 0 8px; font-size: 32px; letter-spacing: 0; }
    h2 { margin-top: 32px; font-size: 22px; }
    h3 { margin: 0 0 10px; font-size: 18px; }
    a { color: var(--accent); }
    .meta { color: var(--muted); display: flex; flex-wrap: wrap; gap: 12px; }
    .topics { width: 100%; border-collapse: collapse; background: var(--panel); }
    .topics th, .topics td {
      padding: 10px;
      border-bottom: 1px solid var(--line);
      text-align: left;
    }
    .topics td:last-child, .topics th:last-child { text-align: right; }
    .card {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 18px;
      margin: 16px 0;
    }
    .card.high { border-left: 5px solid var(--high); }
    .badge {
      display: inline-block;
      padding: 2px 8px;
      border-radius: 999px;
      background: var(--accent-soft);
      color: #0b5f59;
      font-size: 13px;
      margin-right: 6px;
    }
    .score { font-weight: 700; color: var(--high); }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 8px 16px;
    }
    ul { padding-left: 20px; }
    .section-label { font-weight: 700; margin-top: 14px; }
  </style>
</head>
<body>
  <header>
    <h1>arXiv Physics Digest - {{ date }}</h1>
    <div class="meta">
      <span>{{ profile_display_name }} / {{ profile_display_name_zh }}</span>
      <span>Total: {{ total_papers }}</span>
      <span>Analyzed: {{ analyzed_papers }}</span>
      <span>Timezone: {{ timezone }}</span>
      <span>Window: {{ window_start }} - {{ window_end }}</span>
    </div>
  </header>
  <main>
    <h2>今日主题分布</h2>
    <table class="topics">
      <thead><tr><th>主题</th><th>中文主题</th><th>数量</th></tr></thead>
      <tbody>
      {% for topic in topics %}
        <tr><td>{{ topic.topic }}</td><td>{{ topic.topic_zh }}</td><td>{{ topic.count }}</td></tr>
      {% else %}
        <tr><td>-</td><td>-</td><td>0</td></tr>
      {% endfor %}
      </tbody>
    </table>

    <h2>论文分析与总结</h2>
    {% for paper in papers %}
      <article class="card {% if paper.relevance_score >= 80 %}high{% endif %}">
        <h3>{{ paper.title_en }}</h3>
        <p><strong>{{ paper.title_zh }}</strong></p>
        <p>
          <span class="badge">{{ paper.topic_zh }}</span>
          <span class="badge">{{ paper.method_type }}</span>
          <span class="badge">{{ paper.suggested_reading_priority }}</span>
          <span class="score">Score {{ paper.relevance_score }}</span>
        </p>
        <div class="grid">
          <div><strong>Authors</strong><br>{{ paper.authors_text }}</div>
          <div><strong>Categories</strong><br>{{ paper.categories_text }}</div>
          <div><strong>Keyword hits</strong><br>{{ paper.keyword_hits_text }}</div>
          <div><strong>Links</strong><br>
            <a href="{{ paper.abs_url }}">abs</a>
            {% if paper.pdf_url %} / <a href="{{ paper.pdf_url }}">PDF</a>{% endif %}
          </div>
        </div>
        <p class="section-label">研究问题</p>
        <p>{{ paper.physics_problem_zh }}</p>
        <p class="section-label">物理体系 / 材料体系 / 模型</p>
        <p>{{ paper.physical_system_zh }}</p>
        <p class="section-label">关键物理概念</p>
        <ul>{% for item in paper.key_concepts_zh %}<li>{{ item }}</li>{% endfor %}</ul>
        <p class="section-label">主要结果</p>
        <p>{{ paper.main_results_zh }}</p>
        <p class="section-label">实验或计算内容</p>
        <p>{{ paper.experiments_or_calculations_zh }}</p>
        <p class="section-label">局限性</p>
        <p>{{ paper.limitations_zh }}</p>
        <p class="section-label">为什么值得读</p>
        <p>{{ paper.why_relevant_zh }}</p>
        <p class="section-label">English summary</p>
        <p>{{ paper.main_results_en }}</p>
      </article>
    {% else %}
      <p>暂无已完成分析的论文。</p>
    {% endfor %}
  </main>
</body>
</html>
"""
