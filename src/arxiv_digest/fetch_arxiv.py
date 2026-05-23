from __future__ import annotations

import calendar
import logging
import re
import time
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

import feedparser
import httpx
from tenacity import Retrying, stop_after_attempt, wait_exponential

from arxiv_digest.config import AppConfig, ProfileConfig
from arxiv_digest.models import Paper
from arxiv_digest.utils import normalize_whitespace

LOGGER = logging.getLogger(__name__)
ARXIV_API_ENDPOINT = "https://export.arxiv.org/api/query"
USER_AGENT = "arxiv-daily-digest/0.1 (+https://github.com/)"
SAMPLE_ATOM_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:arxiv="http://arxiv.org/schemas/atom">
  <title>Sample arXiv Physics Query Results</title>
  <entry>
    <id>http://arxiv.org/abs/2605.23001v1</id>
    <updated>2026-05-22T23:30:00Z</updated>
    <published>2026-05-22T23:30:00Z</published>
    <title>Quantum Anomalous Hall Effect in Magnetic Chern Insulators</title>
    <summary>
      We study the quantum anomalous Hall effect in a magnetic topological
      material described by a Chern insulator model. Berry curvature and chiral
      edge states are analyzed through quantum transport calculations.
    </summary>
    <author><name>Alice Smith</name></author>
    <author><name>Bob Chen</name></author>
    <arxiv:primary_category term="cond-mat.mes-hall"
                            scheme="http://arxiv.org/schemas/atom"/>
    <category term="cond-mat.mes-hall" scheme="http://arxiv.org/schemas/atom"/>
    <category term="quant-ph" scheme="http://arxiv.org/schemas/atom"/>
    <link href="https://arxiv.org/abs/2605.23001v1" rel="alternate" type="text/html"/>
    <link title="pdf" href="https://arxiv.org/pdf/2605.23001v1"
          rel="related" type="application/pdf"/>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2605.23002v1</id>
    <updated>2026-05-22T22:30:00Z</updated>
    <published>2026-05-22T22:30:00Z</published>
    <title>Superconductivity and Pairing in a Strongly Correlated Hubbard System</title>
    <summary>
      This paper studies superconductivity, pairing correlations, and Mott
      physics in a strongly correlated Hubbard model. Numerical calculations
      reveal a competition between superconducting order and magnetic tendencies.
    </summary>
    <author><name>Carla Zhang</name></author>
    <arxiv:primary_category term="cond-mat.str-el" scheme="http://arxiv.org/schemas/atom"/>
    <category term="cond-mat.str-el" scheme="http://arxiv.org/schemas/atom"/>
    <category term="cond-mat.supr-con" scheme="http://arxiv.org/schemas/atom"/>
    <link href="https://arxiv.org/abs/2605.23002v1" rel="alternate" type="text/html"/>
    <link title="pdf" href="https://arxiv.org/pdf/2605.23002v1"
          rel="related" type="application/pdf"/>
  </entry>
</feed>
"""


class HTTPClient(Protocol):
    def get(self, url: str, params: dict[str, Any]) -> httpx.Response: ...


def build_search_query(
    config: AppConfig,
    now: datetime | None = None,
    *,
    profile_name: str | None = None,
    include_exclusions: bool = True,
) -> str:
    _, profile = config.get_profile(profile_name)
    arxiv = profile.arxiv
    end = now or datetime.now(UTC)
    if end.tzinfo is None:
        end = end.replace(tzinfo=UTC)
    end = end.astimezone(UTC)
    start = end - timedelta(hours=arxiv.lookback_hours)
    date_clause = f"submittedDate:[{start:%Y%m%d%H%M} TO {end:%Y%m%d%H%M}]"
    category_clause = " OR ".join(f"cat:{category}" for category in arxiv.categories)
    keyword_clause = " OR ".join(_keyword_term(keyword) for keyword in arxiv.keywords)
    clauses = []
    if category_clause:
        clauses.append(f"({category_clause})")
    if keyword_clause:
        clauses.append(f"({keyword_clause})")
    clauses.append(date_clause)
    query = " AND ".join(clauses)
    excluded_clause = _excluded_clause(profile)
    if include_exclusions and excluded_clause:
        query = f"{query} ANDNOT ({excluded_clause})"
    return query


def fetch_arxiv_papers(
    config: AppConfig,
    *,
    client: HTTPClient | None = None,
    now: datetime | None = None,
    profile_name: str | None = None,
    sleep_func: Any = time.sleep,
) -> list[Paper]:
    resolved_profile_name, profile = config.get_profile(profile_name)
    try:
        papers = _fetch_arxiv_papers(
            config,
            profile_name=resolved_profile_name,
            profile=profile,
            include_exclusions=True,
            client=client,
            now=now,
            sleep_func=sleep_func,
        )
    except Exception as exc:
        if _excluded_clause(profile):
            LOGGER.warning(
                "arXiv query with exclusions failed; retrying without ANDNOT and "
                "using local post-filter: %s",
                exc,
            )
            try:
                papers = _fetch_arxiv_papers(
                    config,
                    profile_name=resolved_profile_name,
                    profile=profile,
                    include_exclusions=False,
                    client=client,
                    now=now,
                    sleep_func=sleep_func,
                )
            except Exception as fallback_exc:
                LOGGER.warning("Failed to fetch arXiv papers: %s", fallback_exc)
                return []
        else:
            LOGGER.warning("Failed to fetch arXiv papers: %s", exc)
            return []
    return apply_profile_filters(papers, resolved_profile_name, profile)


def _fetch_arxiv_papers(
    config: AppConfig,
    *,
    profile_name: str,
    profile: ProfileConfig,
    include_exclusions: bool,
    client: HTTPClient | None,
    now: datetime | None,
    sleep_func: Any,
) -> list[Paper]:
    search_query = build_search_query(
        config,
        now=now,
        profile_name=profile_name,
        include_exclusions=include_exclusions,
    )
    max_results = max(0, profile.arxiv.max_results_per_day)
    page_size = max(1, min(profile.arxiv.page_size, max_results or profile.arxiv.page_size))
    created_client = client is None
    if client is None:
        client = httpx.Client(
            timeout=httpx.Timeout(30.0),
            headers={"User-Agent": USER_AGENT},
        )

    papers: list[Paper] = []
    try:
        for start in range(0, max_results, page_size):
            params = {
                "search_query": search_query,
                "start": start,
                "max_results": min(page_size, max_results - start),
                "sortBy": "submittedDate",
                "sortOrder": "descending",
            }
            try:
                text = _request_page(client, params)
                page_papers = parse_arxiv_feed(text)
            except Exception:
                raise
            if not page_papers:
                break
            papers.extend(page_papers)
            if len(papers) >= max_results or len(page_papers) < params["max_results"]:
                break
            sleep_func(profile.arxiv.request_interval_seconds)
    finally:
        if created_client and hasattr(client, "close"):
            client.close()
    return papers[:max_results]


def sample_arxiv_papers() -> list[Paper]:
    return parse_arxiv_feed(SAMPLE_ATOM_FEED)


def sample_arxiv_papers_for_profile(
    config: AppConfig, profile_name: str | None = None
) -> list[Paper]:
    resolved_profile_name, profile = config.get_profile(profile_name)
    return apply_profile_filters(sample_arxiv_papers(), resolved_profile_name, profile)


def apply_profile_filters(
    papers: list[Paper],
    profile_name: str,
    profile: ProfileConfig,
) -> list[Paper]:
    filtered = []
    for paper in papers:
        if _is_excluded(paper, profile):
            continue
        keyword_hits = _keyword_hits(paper, profile)
        if profile.arxiv.keywords and not keyword_hits:
            continue
        paper.matched_profile = profile_name
        paper.keyword_hits = keyword_hits
        filtered.append(paper)
    return filtered


def parse_arxiv_feed(xml_text: str) -> list[Paper]:
    parsed = feedparser.parse(xml_text)
    if parsed.bozo and not parsed.entries:
        raise ValueError(f"Invalid arXiv Atom feed: {parsed.bozo_exception}")
    papers: list[Paper] = []
    for entry in parsed.entries:
        try:
            papers.append(_paper_from_entry(entry))
        except Exception as exc:
            LOGGER.warning("Failed to parse arXiv entry: %s", exc)
    return papers


def _request_page(client: HTTPClient, params: dict[str, Any]) -> str:
    for attempt in Retrying(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    ):
        with attempt:
            response = client.get(ARXIV_API_ENDPOINT, params=params)
            response.raise_for_status()
            return response.text
    raise RuntimeError("Unreachable retry state while requesting arXiv API.")


def _paper_from_entry(entry: Any) -> Paper:
    arxiv_id = _normalize_arxiv_id(str(entry.get("id", "")))
    title = normalize_whitespace(str(entry.get("title", "")))
    abstract = normalize_whitespace(str(entry.get("summary", "")))
    authors = _authors_from_entry(entry)
    published = _datetime_from_entry(entry, "published_parsed")
    updated = _datetime_from_entry(entry, "updated_parsed")
    primary_category = _primary_category_from_entry(entry)
    categories = _categories_from_entry(entry)
    abs_url = _link_from_entry(entry, rel="alternate") or f"https://arxiv.org/abs/{arxiv_id}"
    pdf_url = _pdf_link_from_entry(entry)
    return Paper(
        arxiv_id=arxiv_id,
        title=title,
        authors=authors,
        abstract=abstract,
        published=published,
        updated=updated,
        primary_category=primary_category,
        categories=categories,
        abs_url=abs_url,
        pdf_url=pdf_url,
        raw_entry_json=_entry_to_raw_json(entry),
    )


def _keyword_term(keyword: str) -> str:
    keyword = keyword.strip()
    if not keyword:
        return ""
    if re.search(r"\s", keyword):
        return f'all:"{keyword}"'
    return f"all:{keyword}"


def _excluded_clause(profile: ProfileConfig) -> str:
    terms = [f"cat:{category}" for category in profile.arxiv.excluded_categories]
    terms.extend(_keyword_term(keyword) for keyword in profile.arxiv.excluded_keywords)
    terms = [term for term in terms if term]
    return " OR ".join(terms)


def _is_excluded(paper: Paper, profile: ProfileConfig) -> bool:
    excluded_categories = set(profile.arxiv.excluded_categories)
    if excluded_categories.intersection(paper.categories):
        return True
    text = f"{paper.title} {paper.abstract}".lower()
    return any(keyword.lower() in text for keyword in profile.arxiv.excluded_keywords)


def _keyword_hits(paper: Paper, profile: ProfileConfig) -> list[str]:
    text = f"{paper.title} {paper.abstract} {' '.join(paper.categories)}".lower()
    return [keyword for keyword in profile.arxiv.keywords if keyword.lower() in text]


def _normalize_arxiv_id(entry_id: str) -> str:
    raw = entry_id.rstrip("/").split("/")[-1]
    return re.sub(r"v\d+$", "", raw)


def _authors_from_entry(entry: Any) -> list[str]:
    authors = []
    for author in entry.get("authors", []) or []:
        name = author.get("name") if isinstance(author, dict) else None
        if name:
            authors.append(str(name))
    if not authors and entry.get("author"):
        authors.append(str(entry.get("author")))
    return authors


def _datetime_from_entry(entry: Any, key: str) -> datetime:
    parsed_time = entry.get(key)
    if parsed_time:
        return datetime.fromtimestamp(calendar.timegm(parsed_time), tz=UTC)
    return datetime.now(UTC)


def _primary_category_from_entry(entry: Any) -> str | None:
    primary = entry.get("arxiv_primary_category")
    if isinstance(primary, dict):
        return primary.get("term")
    return None


def _categories_from_entry(entry: Any) -> list[str]:
    categories = []
    for tag in entry.get("tags", []) or []:
        term = tag.get("term") if isinstance(tag, dict) else None
        if term:
            categories.append(str(term))
    return categories


def _link_from_entry(entry: Any, *, rel: str) -> str | None:
    for link in entry.get("links", []) or []:
        if link.get("rel") == rel and link.get("href"):
            return str(link["href"])
    return None


def _pdf_link_from_entry(entry: Any) -> str | None:
    for link in entry.get("links", []) or []:
        if link.get("title") == "pdf" and link.get("href"):
            return str(link["href"])
        if link.get("type") == "application/pdf" and link.get("href"):
            return str(link["href"])
    return None


def _entry_to_raw_json(entry: Any) -> dict[str, Any]:
    return {
        "id": entry.get("id"),
        "title": entry.get("title"),
        "summary": entry.get("summary"),
        "published": entry.get("published"),
        "updated": entry.get("updated"),
        "authors": [
            {"name": author.get("name")}
            for author in (entry.get("authors", []) or [])
            if isinstance(author, dict)
        ],
        "tags": [
            {"term": tag.get("term"), "scheme": tag.get("scheme")}
            for tag in (entry.get("tags", []) or [])
            if isinstance(tag, dict)
        ],
        "links": [
            {
                "href": link.get("href"),
                "rel": link.get("rel"),
                "type": link.get("type"),
                "title": link.get("title"),
            }
            for link in (entry.get("links", []) or [])
            if isinstance(link, dict)
        ],
    }
