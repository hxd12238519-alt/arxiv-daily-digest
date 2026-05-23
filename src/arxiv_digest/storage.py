from __future__ import annotations

import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any

from arxiv_digest.llm.schemas import PROMPT_VERSION, SCHEMA_VERSION, PaperAnalysis
from arxiv_digest.models import AnalysisJob, AnalysisStatus, Paper, TaskRun, TaskRunStatus
from arxiv_digest.utils import date_in_timezone, json_dumps, json_loads, parse_datetime, utc_now

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS papers (
  id INTEGER PRIMARY KEY,
  arxiv_id TEXT UNIQUE NOT NULL,
  title TEXT NOT NULL,
  authors_json TEXT NOT NULL,
  abstract TEXT NOT NULL,
  published TEXT NOT NULL,
  updated TEXT NOT NULL,
  primary_category TEXT,
  categories_json TEXT NOT NULL,
  abs_url TEXT NOT NULL,
  pdf_url TEXT,
  matched_profile TEXT,
  keyword_hits_json TEXT NOT NULL DEFAULT '[]',
  raw_entry_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS analysis_jobs (
  id INTEGER PRIMARY KEY,
  paper_id INTEGER NOT NULL,
  status TEXT NOT NULL,
  provider TEXT NOT NULL,
  model TEXT NOT NULL,
  profile TEXT NOT NULL DEFAULT 'physics_student',
  retry_count INTEGER NOT NULL DEFAULT 0,
  error_message TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (paper_id) REFERENCES papers(id)
);

CREATE TABLE IF NOT EXISTS paper_analyses (
  id INTEGER PRIMARY KEY,
  paper_id INTEGER NOT NULL,
  profile TEXT NOT NULL DEFAULT 'physics_student',
  provider TEXT NOT NULL,
  model TEXT NOT NULL,
  prompt_version TEXT NOT NULL,
  schema_version TEXT NOT NULL,
  topic TEXT NOT NULL,
  topic_zh TEXT NOT NULL,
  title_zh TEXT NOT NULL,
  abstract_zh TEXT NOT NULL,
  summary_en TEXT NOT NULL,
  summary_zh TEXT NOT NULL,
  key_contributions_en_json TEXT NOT NULL,
  key_contributions_zh_json TEXT NOT NULL,
  method_type TEXT NOT NULL DEFAULT 'unknown',
  method_en TEXT NOT NULL,
  method_zh TEXT NOT NULL,
  physical_system_en TEXT NOT NULL DEFAULT 'Not specified in the abstract.',
  physical_system_zh TEXT NOT NULL DEFAULT '摘要中未明确说明。',
  physics_problem_en TEXT NOT NULL DEFAULT 'Not specified in the abstract.',
  physics_problem_zh TEXT NOT NULL DEFAULT '摘要中未明确说明。',
  key_concepts_en_json TEXT NOT NULL DEFAULT '["Not specified in the abstract."]',
  key_concepts_zh_json TEXT NOT NULL DEFAULT '["摘要中未明确说明。"]',
  main_results_en TEXT NOT NULL DEFAULT 'Not specified in the abstract.',
  main_results_zh TEXT NOT NULL DEFAULT '摘要中未明确说明。',
  experiments_en TEXT NOT NULL,
  experiments_zh TEXT NOT NULL,
  limitations_en TEXT NOT NULL,
  limitations_zh TEXT NOT NULL,
  why_relevant_en TEXT NOT NULL DEFAULT 'Not specified in the abstract.',
  why_relevant_zh TEXT NOT NULL DEFAULT '摘要中未明确说明。',
  suggested_reading_priority TEXT NOT NULL DEFAULT 'low',
  keywords_en_json TEXT NOT NULL,
  keywords_zh_json TEXT NOT NULL,
  relevance_score INTEGER NOT NULL,
  recommended_reason_zh TEXT NOT NULL,
  raw_response_json TEXT NOT NULL,
  input_tokens INTEGER,
  output_tokens INTEGER,
  estimated_cost REAL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (paper_id) REFERENCES papers(id)
);

CREATE TABLE IF NOT EXISTS task_runs (
  id TEXT PRIMARY KEY,
  profile TEXT NOT NULL,
  provider TEXT NOT NULL,
  lookback_hours INTEGER,
  report_suffix TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL,
  status_message TEXT,
  started_at TEXT,
  finished_at TEXT,
  error_message TEXT,
  report_md_path TEXT,
  report_html_path TEXT,
  report_json_path TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

"""

INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_papers_published ON papers(published);
CREATE INDEX IF NOT EXISTS idx_papers_profile ON papers(matched_profile);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON analysis_jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_profile ON analysis_jobs(profile);
CREATE INDEX IF NOT EXISTS idx_analyses_paper ON paper_analyses(paper_id);
CREATE INDEX IF NOT EXISTS idx_analyses_profile ON paper_analyses(profile);
CREATE INDEX IF NOT EXISTS idx_task_runs_profile_status ON task_runs(profile, status);
"""

MIGRATIONS: dict[str, dict[str, str]] = {
    "papers": {
        "matched_profile": "TEXT",
        "keyword_hits_json": "TEXT NOT NULL DEFAULT '[]'",
    },
    "analysis_jobs": {
        "profile": "TEXT NOT NULL DEFAULT 'physics_student'",
    },
    "paper_analyses": {
        "profile": "TEXT NOT NULL DEFAULT 'physics_student'",
        "method_type": "TEXT NOT NULL DEFAULT 'unknown'",
        "physical_system_en": "TEXT NOT NULL DEFAULT 'Not specified in the abstract.'",
        "physical_system_zh": "TEXT NOT NULL DEFAULT '摘要中未明确说明。'",
        "physics_problem_en": "TEXT NOT NULL DEFAULT 'Not specified in the abstract.'",
        "physics_problem_zh": "TEXT NOT NULL DEFAULT '摘要中未明确说明。'",
        "key_concepts_en_json": "TEXT NOT NULL DEFAULT '[\"Not specified in the abstract.\"]'",
        "key_concepts_zh_json": "TEXT NOT NULL DEFAULT '[\"摘要中未明确说明。\"]'",
        "main_results_en": "TEXT NOT NULL DEFAULT 'Not specified in the abstract.'",
        "main_results_zh": "TEXT NOT NULL DEFAULT '摘要中未明确说明。'",
        "why_relevant_en": "TEXT NOT NULL DEFAULT 'Not specified in the abstract.'",
        "why_relevant_zh": "TEXT NOT NULL DEFAULT '摘要中未明确说明。'",
        "suggested_reading_priority": "TEXT NOT NULL DEFAULT 'low'",
    },
    "task_runs": {
        "lookback_hours": "INTEGER",
        "report_suffix": "TEXT NOT NULL DEFAULT ''",
    },
}


class Storage:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def init_db(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.executescript(SCHEMA_SQL)
            self._migrate_schema(conn)
            conn.executescript(INDEX_SQL)

    def insert_paper(self, paper: Paper) -> tuple[int, bool]:
        now = utc_now().isoformat()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO papers (
                  arxiv_id, title, authors_json, abstract, published, updated,
                  primary_category, categories_json, abs_url, pdf_url,
                  matched_profile, keyword_hits_json, raw_entry_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    paper.arxiv_id,
                    paper.title,
                    json_dumps(paper.authors),
                    paper.abstract,
                    paper.published.isoformat(),
                    paper.updated.isoformat(),
                    paper.primary_category,
                    json_dumps(paper.categories),
                    paper.abs_url,
                    paper.pdf_url,
                    paper.matched_profile,
                    json_dumps(paper.keyword_hits),
                    json_dumps(paper.raw_entry_json),
                    now,
                ),
            )
            inserted = cursor.rowcount == 1
            if not inserted:
                conn.execute(
                    """
                    UPDATE papers
                    SET title = ?,
                        authors_json = ?,
                        abstract = ?,
                        published = ?,
                        updated = ?,
                        primary_category = ?,
                        categories_json = ?,
                        abs_url = ?,
                        pdf_url = ?,
                        matched_profile = ?,
                        keyword_hits_json = ?,
                        raw_entry_json = ?
                    WHERE arxiv_id = ?
                    """,
                    (
                        paper.title,
                        json_dumps(paper.authors),
                        paper.abstract,
                        paper.published.isoformat(),
                        paper.updated.isoformat(),
                        paper.primary_category,
                        json_dumps(paper.categories),
                        paper.abs_url,
                        paper.pdf_url,
                        paper.matched_profile,
                        json_dumps(paper.keyword_hits),
                        json_dumps(paper.raw_entry_json),
                        paper.arxiv_id,
                    ),
                )
            row = conn.execute(
                "SELECT id FROM papers WHERE arxiv_id = ?", (paper.arxiv_id,)
            ).fetchone()
            if row is None:
                raise RuntimeError(f"Failed to read paper after insert: {paper.arxiv_id}")
            return int(row["id"]), inserted

    def insert_papers(self, papers: list[Paper]) -> tuple[int, int]:
        inserted = 0
        duplicates = 0
        for paper in papers:
            _, was_inserted = self.insert_paper(paper)
            if was_inserted:
                inserted += 1
            else:
                duplicates += 1
        return inserted, duplicates

    def get_paper(self, paper_id: int) -> Paper | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM papers WHERE id = ?", (paper_id,)).fetchone()
        return _paper_from_row(row) if row else None

    def list_papers(self) -> list[Paper]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM papers ORDER BY published DESC").fetchall()
        return [_paper_from_row(row) for row in rows]

    def list_papers_by_date(
        self,
        target_date: date,
        timezone_name: str,
        profile: str | None = None,
    ) -> list[Paper]:
        return [
            paper
            for paper in self.list_papers()
            if date_in_timezone(paper.published, timezone_name) == target_date
            and (profile is None or paper.matched_profile == profile)
        ]

    def list_papers_by_window(
        self,
        start: datetime,
        end: datetime,
        profile: str | None = None,
    ) -> list[Paper]:
        return [
            paper
            for paper in self.list_papers()
            if start <= paper.published < end
            and (profile is None or paper.matched_profile == profile)
        ]

    def list_unanalyzed_papers(
        self,
        provider: str,
        model: str,
        profile: str,
        limit: int | None = None,
    ) -> list[Paper]:
        sql = """
            SELECT p.* FROM papers p
            WHERE p.matched_profile = ?
              AND NOT EXISTS (
                SELECT 1 FROM paper_analyses a
                WHERE a.paper_id = p.id
                  AND a.profile = ?
                  AND a.provider = ?
                  AND a.model = ?
                  AND a.schema_version = ?
              )
            ORDER BY p.published DESC
        """
        params: list[Any] = [profile, profile, provider, model, SCHEMA_VERSION]
        if limit is not None:
            sql += " LIMIT ?"
            params.append(int(limit))
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [_paper_from_row(row) for row in rows]

    def ensure_analysis_job(
        self,
        paper_id: int,
        provider: str,
        model: str,
        profile: str,
    ) -> AnalysisJob:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM analysis_jobs
                WHERE paper_id = ? AND provider = ? AND model = ? AND profile = ?
                  AND status IN ('pending', 'running', 'failed')
                ORDER BY id DESC LIMIT 1
                """,
                (paper_id, provider, model, profile),
            ).fetchone()
            if row:
                return _job_from_row(row)
            now = utc_now().isoformat()
            cursor = conn.execute(
                """
                INSERT INTO analysis_jobs (
                  paper_id, status, provider, model, profile, retry_count,
                  error_message, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 0, NULL, ?, ?)
                """,
                (paper_id, AnalysisStatus.PENDING.value, provider, model, profile, now, now),
            )
            row = conn.execute(
                "SELECT * FROM analysis_jobs WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
            if row is None:
                raise RuntimeError("Failed to create analysis job.")
            return _job_from_row(row)

    def list_runnable_jobs(
        self,
        provider: str,
        model: str,
        profile: str,
        max_retries: int,
        limit: int | None = None,
    ) -> list[AnalysisJob]:
        sql = """
            SELECT * FROM analysis_jobs
            WHERE provider = ? AND model = ? AND profile = ?
              AND (
                status = 'pending' OR (status = 'failed' AND retry_count < ?)
              )
            ORDER BY created_at ASC
        """
        params: list[Any] = [provider, model, profile, int(max_retries)]
        if limit is not None:
            sql += " LIMIT ?"
            params.append(int(limit))
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [_job_from_row(row) for row in rows]

    def mark_job_running(self, job_id: int) -> None:
        self._update_job(job_id, AnalysisStatus.RUNNING, None, increment_retry=False)

    def mark_job_succeeded(self, job_id: int) -> None:
        self._update_job(job_id, AnalysisStatus.SUCCEEDED, None, increment_retry=False)

    def mark_job_failed(self, job_id: int, error_message: str) -> None:
        self._update_job(job_id, AnalysisStatus.FAILED, error_message, increment_retry=True)

    def save_analysis(
        self,
        paper_id: int,
        profile: str,
        provider: str,
        model: str,
        analysis: PaperAnalysis,
        *,
        raw_response_json: dict[str, Any] | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        estimated_cost: float | None = None,
    ) -> int:
        now = utc_now().isoformat()
        raw_payload = raw_response_json or analysis.model_dump()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO paper_analyses (
                  paper_id, profile, provider, model, prompt_version, schema_version,
                  topic, topic_zh, title_zh, abstract_zh, summary_en, summary_zh,
                  key_contributions_en_json, key_contributions_zh_json,
                  method_type, method_en, method_zh, physical_system_en,
                  physical_system_zh, physics_problem_en, physics_problem_zh,
                  key_concepts_en_json, key_concepts_zh_json, main_results_en,
                  main_results_zh, experiments_en, experiments_zh, limitations_en,
                  limitations_zh, why_relevant_en, why_relevant_zh,
                  suggested_reading_priority, keywords_en_json, keywords_zh_json,
                  relevance_score, recommended_reason_zh, raw_response_json,
                  input_tokens, output_tokens, estimated_cost, created_at
                ) VALUES (
                  ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                  ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    paper_id,
                    profile,
                    provider,
                    model,
                    PROMPT_VERSION,
                    SCHEMA_VERSION,
                    analysis.topic,
                    analysis.topic_zh,
                    analysis.title_zh,
                    analysis.abstract_zh,
                    analysis.main_results_en,
                    analysis.main_results_zh,
                    json_dumps(analysis.key_concepts_en),
                    json_dumps(analysis.key_concepts_zh),
                    analysis.method_type,
                    analysis.method_en,
                    analysis.method_zh,
                    analysis.physical_system_en,
                    analysis.physical_system_zh,
                    analysis.physics_problem_en,
                    analysis.physics_problem_zh,
                    json_dumps(analysis.key_concepts_en),
                    json_dumps(analysis.key_concepts_zh),
                    analysis.main_results_en,
                    analysis.main_results_zh,
                    analysis.experiments_or_calculations_en,
                    analysis.experiments_or_calculations_zh,
                    analysis.limitations_en,
                    analysis.limitations_zh,
                    analysis.why_relevant_en,
                    analysis.why_relevant_zh,
                    analysis.suggested_reading_priority,
                    json_dumps(analysis.keywords_en),
                    json_dumps(analysis.keywords_zh),
                    analysis.relevance_score,
                    analysis.recommended_reason_zh,
                    json_dumps(raw_payload),
                    input_tokens,
                    output_tokens,
                    estimated_cost,
                    now,
                ),
            )
            return int(cursor.lastrowid)

    def list_report_records_for_date(
        self,
        target_date: date,
        timezone_name: str,
        profile: str,
    ) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                  p.id AS paper_id, p.arxiv_id, p.title, p.authors_json, p.abstract,
                  p.published, p.updated, p.primary_category, p.categories_json,
                  p.abs_url, p.pdf_url, p.matched_profile, p.keyword_hits_json,
                  p.raw_entry_json,
                  a.id AS analysis_id, a.profile, a.provider, a.model, a.topic,
                  a.topic_zh, a.title_zh, a.abstract_zh, a.method_type,
                  a.physical_system_en, a.physical_system_zh, a.physics_problem_en,
                  a.physics_problem_zh, a.key_concepts_en_json,
                  a.key_concepts_zh_json, a.main_results_en, a.main_results_zh,
                  a.method_en, a.method_zh, a.experiments_en, a.experiments_zh,
                  a.limitations_en, a.limitations_zh, a.why_relevant_en,
                  a.why_relevant_zh, a.suggested_reading_priority,
                  a.keywords_en_json, a.keywords_zh_json, a.relevance_score,
                  a.recommended_reason_zh, a.raw_response_json,
                  a.created_at AS analysis_created_at
                FROM paper_analyses a
                JOIN papers p ON p.id = a.paper_id
                WHERE a.profile = ?
                  AND a.schema_version = ?
                  AND a.id IN (
                    SELECT MAX(id)
                    FROM paper_analyses
                    WHERE profile = ? AND schema_version = ?
                    GROUP BY paper_id
                  )
                ORDER BY a.relevance_score DESC, p.published DESC
                """,
                (profile, SCHEMA_VERSION, profile, SCHEMA_VERSION),
            ).fetchall()
        records = []
        for row in rows:
            paper = _paper_from_prefixed_row(row)
            if date_in_timezone(paper.published, timezone_name) != target_date:
                continue
            records.append(
                {
                    "paper": paper,
                    "analysis": _analysis_from_row(row),
                    "provider": row["provider"],
                    "model": row["model"],
                    "analysis_id": row["analysis_id"],
                    "profile": row["profile"],
                }
            )
        return records

    def list_report_records_for_window(
        self,
        start: datetime,
        end: datetime,
        profile: str,
    ) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                  p.id AS paper_id, p.arxiv_id, p.title, p.authors_json, p.abstract,
                  p.published, p.updated, p.primary_category, p.categories_json,
                  p.abs_url, p.pdf_url, p.matched_profile, p.keyword_hits_json,
                  p.raw_entry_json,
                  a.id AS analysis_id, a.profile, a.provider, a.model, a.topic,
                  a.topic_zh, a.title_zh, a.abstract_zh, a.method_type,
                  a.physical_system_en, a.physical_system_zh, a.physics_problem_en,
                  a.physics_problem_zh, a.key_concepts_en_json,
                  a.key_concepts_zh_json, a.main_results_en, a.main_results_zh,
                  a.method_en, a.method_zh, a.experiments_en, a.experiments_zh,
                  a.limitations_en, a.limitations_zh, a.why_relevant_en,
                  a.why_relevant_zh, a.suggested_reading_priority,
                  a.keywords_en_json, a.keywords_zh_json, a.relevance_score,
                  a.recommended_reason_zh, a.raw_response_json,
                  a.created_at AS analysis_created_at
                FROM paper_analyses a
                JOIN papers p ON p.id = a.paper_id
                WHERE a.profile = ?
                  AND a.schema_version = ?
                  AND a.id IN (
                    SELECT MAX(id)
                    FROM paper_analyses
                    WHERE profile = ? AND schema_version = ?
                    GROUP BY paper_id
                  )
                ORDER BY a.relevance_score DESC, p.published DESC
                """,
                (profile, SCHEMA_VERSION, profile, SCHEMA_VERSION),
            ).fetchall()
        records = []
        for row in rows:
            paper = _paper_from_prefixed_row(row)
            if not (start <= paper.published < end):
                continue
            records.append(
                {
                    "paper": paper,
                    "analysis": _analysis_from_row(row),
                    "provider": row["provider"],
                    "model": row["model"],
                    "analysis_id": row["analysis_id"],
                    "profile": row["profile"],
                }
            )
        return records

    def list_jobs_by_status(self, status: AnalysisStatus) -> list[AnalysisJob]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM analysis_jobs WHERE status = ? ORDER BY created_at",
                (status.value,),
            ).fetchall()
        return [_job_from_row(row) for row in rows]

    def create_task_run(
        self,
        run_id: str,
        profile: str,
        provider: str,
        *,
        lookback_hours: int | None = None,
        report_suffix: str = "",
        status: TaskRunStatus = TaskRunStatus.QUEUED,
        status_message: str | None = None,
    ) -> TaskRun:
        now = utc_now().isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO task_runs (
                  id, profile, provider, lookback_hours, report_suffix, status,
                  status_message, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    profile,
                    provider,
                    lookback_hours,
                    report_suffix,
                    status.value,
                    status_message,
                    now,
                    now,
                ),
            )
            row = conn.execute("SELECT * FROM task_runs WHERE id = ?", (run_id,)).fetchone()
        if row is None:
            raise RuntimeError(f"Failed to create task run {run_id}.")
        return _task_run_from_row(row)

    def get_task_run(self, run_id: str) -> TaskRun | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM task_runs WHERE id = ?", (run_id,)).fetchone()
        return _task_run_from_row(row) if row else None

    def get_active_task_run(self, profile: str, report_suffix: str = "") -> TaskRun | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM task_runs
                WHERE profile = ? AND report_suffix = ? AND status IN ('queued', 'running')
                ORDER BY created_at DESC LIMIT 1
                """,
                (profile, report_suffix),
            ).fetchone()
        return _task_run_from_row(row) if row else None

    def update_task_run(
        self,
        run_id: str,
        *,
        status: TaskRunStatus | None = None,
        status_message: str | None = None,
        started_at: str | None = None,
        finished_at: str | None = None,
        error_message: str | None = None,
        report_md_path: str | None = None,
        report_html_path: str | None = None,
        report_json_path: str | None = None,
    ) -> None:
        updates: dict[str, Any] = {"updated_at": utc_now().isoformat()}
        if status is not None:
            updates["status"] = status.value
        if status_message is not None:
            updates["status_message"] = status_message
        if started_at is not None:
            updates["started_at"] = started_at
        if finished_at is not None:
            updates["finished_at"] = finished_at
        if error_message is not None:
            updates["error_message"] = error_message
        if report_md_path is not None:
            updates["report_md_path"] = report_md_path
        if report_html_path is not None:
            updates["report_html_path"] = report_html_path
        if report_json_path is not None:
            updates["report_json_path"] = report_json_path
        assignments = ", ".join(f"{key} = ?" for key in updates)
        params = list(updates.values()) + [run_id]
        with self._connect() as conn:
            conn.execute(f"UPDATE task_runs SET {assignments} WHERE id = ?", params)

    def _update_job(
        self,
        job_id: int,
        status: AnalysisStatus,
        error_message: str | None,
        *,
        increment_retry: bool,
    ) -> None:
        now = utc_now().isoformat()
        with self._connect() as conn:
            if increment_retry:
                conn.execute(
                    """
                    UPDATE analysis_jobs
                    SET status = ?, error_message = ?, retry_count = retry_count + 1,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (status.value, error_message, now, job_id),
                )
            else:
                conn.execute(
                    """
                    UPDATE analysis_jobs
                    SET status = ?, error_message = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (status.value, error_message, now, job_id),
                )

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 30000")
        return conn

    def _migrate_schema(self, conn: sqlite3.Connection) -> None:
        for table, columns in MIGRATIONS.items():
            existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
            for column, definition in columns.items():
                if column not in existing:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _paper_from_row(row: sqlite3.Row) -> Paper:
    return Paper(
        id=int(row["id"]),
        arxiv_id=row["arxiv_id"],
        title=row["title"],
        authors=json_loads(row["authors_json"], []),
        abstract=row["abstract"],
        published=parse_datetime(row["published"]),
        updated=parse_datetime(row["updated"]),
        primary_category=row["primary_category"],
        categories=json_loads(row["categories_json"], []),
        abs_url=row["abs_url"],
        pdf_url=row["pdf_url"],
        matched_profile=row["matched_profile"],
        keyword_hits=json_loads(row["keyword_hits_json"], []),
        raw_entry_json=json_loads(row["raw_entry_json"], {}),
    )


def _paper_from_prefixed_row(row: sqlite3.Row) -> Paper:
    return Paper(
        id=int(row["paper_id"]),
        arxiv_id=row["arxiv_id"],
        title=row["title"],
        authors=json_loads(row["authors_json"], []),
        abstract=row["abstract"],
        published=parse_datetime(row["published"]),
        updated=parse_datetime(row["updated"]),
        primary_category=row["primary_category"],
        categories=json_loads(row["categories_json"], []),
        abs_url=row["abs_url"],
        pdf_url=row["pdf_url"],
        matched_profile=row["matched_profile"],
        keyword_hits=json_loads(row["keyword_hits_json"], []),
        raw_entry_json=json_loads(row["raw_entry_json"], {}),
    )


def _job_from_row(row: sqlite3.Row) -> AnalysisJob:
    return AnalysisJob(
        id=int(row["id"]),
        paper_id=int(row["paper_id"]),
        status=AnalysisStatus(row["status"]),
        provider=row["provider"],
        model=row["model"],
        profile=row["profile"],
        retry_count=int(row["retry_count"]),
        error_message=row["error_message"],
        created_at=parse_datetime(row["created_at"]),
        updated_at=parse_datetime(row["updated_at"]),
    )


def _task_run_from_row(row: sqlite3.Row) -> TaskRun:
    keys = row.keys()
    lookback_hours = row["lookback_hours"] if "lookback_hours" in keys else None
    return TaskRun(
        id=row["id"],
        profile=row["profile"],
        provider=row["provider"],
        lookback_hours=int(lookback_hours) if lookback_hours is not None else None,
        report_suffix=row["report_suffix"] if "report_suffix" in keys else "",
        status=TaskRunStatus(row["status"]),
        status_message=row["status_message"],
        started_at=parse_datetime(row["started_at"]) if row["started_at"] else None,
        finished_at=parse_datetime(row["finished_at"]) if row["finished_at"] else None,
        error_message=row["error_message"],
        report_md_path=row["report_md_path"],
        report_html_path=row["report_html_path"],
        report_json_path=row["report_json_path"],
        created_at=parse_datetime(row["created_at"]),
        updated_at=parse_datetime(row["updated_at"]),
    )


def _analysis_from_row(row: sqlite3.Row) -> PaperAnalysis:
    return PaperAnalysis(
        topic=row["topic"],
        topic_zh=row["topic_zh"],
        title_zh=row["title_zh"],
        abstract_zh=row["abstract_zh"],
        physics_problem_en=row["physics_problem_en"],
        physics_problem_zh=row["physics_problem_zh"],
        physical_system_en=row["physical_system_en"],
        physical_system_zh=row["physical_system_zh"],
        key_concepts_en=json_loads(row["key_concepts_en_json"], []),
        key_concepts_zh=json_loads(row["key_concepts_zh_json"], []),
        method_type=row["method_type"],
        method_en=row["method_en"],
        method_zh=row["method_zh"],
        main_results_en=row["main_results_en"],
        main_results_zh=row["main_results_zh"],
        experiments_or_calculations_en=row["experiments_en"],
        experiments_or_calculations_zh=row["experiments_zh"],
        limitations_en=row["limitations_en"],
        limitations_zh=row["limitations_zh"],
        why_relevant_en=row["why_relevant_en"],
        why_relevant_zh=row["why_relevant_zh"],
        suggested_reading_priority=row["suggested_reading_priority"],
        keywords_en=json_loads(row["keywords_en_json"], []),
        keywords_zh=json_loads(row["keywords_zh_json"], []),
        relevance_score=int(row["relevance_score"]),
        recommended_reason_zh=row["recommended_reason_zh"],
    )
