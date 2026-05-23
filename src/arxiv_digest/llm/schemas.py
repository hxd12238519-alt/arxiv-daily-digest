from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

SCHEMA_VERSION = "2.0"
PROMPT_VERSION = "2.0"

METHOD_TYPES = {
    "theory",
    "numerical",
    "experiment",
    "materials_synthesis",
    "quantum_transport",
    "spectroscopy",
    "cold_atoms",
    "review",
    "unknown",
}
READING_PRIORITIES = {"high", "medium", "low"}

TEXT_DEFAULTS = {
    "topic": "Other Physics",
    "topic_zh": "其他物理方向",
    "title_zh": "摘要中未明确说明。",
    "abstract_zh": "摘要中未明确说明。",
    "physics_problem_en": "Not specified in the abstract.",
    "physics_problem_zh": "摘要中未明确说明。",
    "physical_system_en": "Not specified in the abstract.",
    "physical_system_zh": "摘要中未明确说明。",
    "method_en": "Not specified in the abstract.",
    "method_zh": "摘要中未明确说明。",
    "main_results_en": "Not specified in the abstract.",
    "main_results_zh": "摘要中未明确说明。",
    "experiments_or_calculations_en": "Not specified in the abstract.",
    "experiments_or_calculations_zh": "摘要中未明确说明。",
    "limitations_en": "Not specified in the abstract.",
    "limitations_zh": "摘要中未明确说明。",
    "why_relevant_en": "Not specified in the abstract.",
    "why_relevant_zh": "摘要中未明确说明。",
    "recommended_reason_zh": "摘要信息有限，建议按需阅读。",
}

LIST_DEFAULTS = {
    "key_concepts_en": ["Not specified in the abstract."],
    "key_concepts_zh": ["摘要中未明确说明。"],
    "keywords_en": ["physics"],
    "keywords_zh": ["物理"],
}


class PaperAnalysis(BaseModel):
    model_config = ConfigDict(extra="ignore")

    topic: str
    topic_zh: str
    title_zh: str
    abstract_zh: str
    physics_problem_en: str
    physics_problem_zh: str
    physical_system_en: str
    physical_system_zh: str
    key_concepts_en: list[str] = Field(min_length=1)
    key_concepts_zh: list[str] = Field(min_length=1)
    method_type: Literal[
        "theory",
        "numerical",
        "experiment",
        "materials_synthesis",
        "quantum_transport",
        "spectroscopy",
        "cold_atoms",
        "review",
        "unknown",
    ]
    method_en: str
    method_zh: str
    main_results_en: str
    main_results_zh: str
    experiments_or_calculations_en: str
    experiments_or_calculations_zh: str
    limitations_en: str
    limitations_zh: str
    why_relevant_en: str
    why_relevant_zh: str
    suggested_reading_priority: Literal["high", "medium", "low"]
    relevance_score: int = Field(ge=0, le=100)
    keywords_en: list[str] = Field(min_length=1)
    keywords_zh: list[str] = Field(min_length=1)
    recommended_reason_zh: str

    @field_validator(
        "topic",
        "topic_zh",
        "title_zh",
        "abstract_zh",
        "physics_problem_en",
        "physics_problem_zh",
        "physical_system_en",
        "physical_system_zh",
        "method_en",
        "method_zh",
        "main_results_en",
        "main_results_zh",
        "experiments_or_calculations_en",
        "experiments_or_calculations_zh",
        "limitations_en",
        "limitations_zh",
        "why_relevant_en",
        "why_relevant_zh",
        "recommended_reason_zh",
    )
    @classmethod
    def non_empty_text(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("text fields must not be empty")
        return value.strip()

    @field_validator(
        "key_concepts_en",
        "key_concepts_zh",
        "keywords_en",
        "keywords_zh",
    )
    @classmethod
    def non_empty_list(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value if item and item.strip()]
        if not cleaned:
            raise ValueError("list fields must not be empty")
        return cleaned


def validate_analysis_payload(
    payload: dict[str, Any],
    profile_topics: Sequence[Any] | None = None,
) -> PaperAnalysis:
    normalized = dict(payload)
    for key, default in TEXT_DEFAULTS.items():
        if not normalized.get(key):
            normalized[key] = default
    for key, default in LIST_DEFAULTS.items():
        value = normalized.get(key)
        if not isinstance(value, list) or not any(str(item).strip() for item in value):
            normalized[key] = default
    if normalized.get("method_type") not in METHOD_TYPES:
        normalized["method_type"] = "unknown"
    if normalized.get("suggested_reading_priority") not in READING_PRIORITIES:
        normalized["suggested_reading_priority"] = "low"
    if "relevance_score" not in normalized:
        normalized["relevance_score"] = 0
    _normalize_topic(normalized, profile_topics)
    return PaperAnalysis.model_validate(normalized)


def _normalize_topic(normalized: dict[str, Any], profile_topics: Sequence[Any] | None) -> None:
    if not profile_topics:
        return
    topic_map: dict[str, str] = {}
    for item in profile_topics:
        topic = getattr(item, "topic", None) or item.get("topic")
        topic_zh = getattr(item, "topic_zh", None) or item.get("topic_zh")
        if topic and topic_zh:
            topic_map[str(topic)] = str(topic_zh)
    if not topic_map:
        return
    fallback_topic = next(reversed(topic_map))
    selected = normalized.get("topic")
    if selected not in topic_map:
        normalized["topic"] = fallback_topic
        normalized["topic_zh"] = topic_map[fallback_topic]
    else:
        normalized["topic_zh"] = topic_map[str(selected)]
