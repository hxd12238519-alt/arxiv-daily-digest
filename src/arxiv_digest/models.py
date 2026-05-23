from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Paper(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int | None = None
    arxiv_id: str
    title: str
    authors: list[str]
    abstract: str
    published: datetime
    updated: datetime
    primary_category: str | None = None
    categories: list[str] = Field(default_factory=list)
    abs_url: str
    pdf_url: str | None = None
    matched_profile: str | None = None
    keyword_hits: list[str] = Field(default_factory=list)
    raw_entry_json: dict[str, Any] = Field(default_factory=dict)


class AnalysisStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class TaskRunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class AnalysisJob(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int | None = None
    paper_id: int
    status: AnalysisStatus
    provider: str
    model: str
    profile: str = "physics_student"
    retry_count: int = 0
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class TaskRun(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    profile: str
    provider: str
    lookback_hours: int | None = None
    report_suffix: str = ""
    status: TaskRunStatus
    status_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_message: str | None = None
    report_md_path: str | None = None
    report_html_path: str | None = None
    report_json_path: str | None = None
    created_at: datetime
    updated_at: datetime
