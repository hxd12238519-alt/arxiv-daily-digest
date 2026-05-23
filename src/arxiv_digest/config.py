from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field

PHYSICS_STUDENT_TOPICS = [
    {"topic": "Condensed Matter Physics", "topic_zh": "凝聚态物理"},
    {"topic": "Topological Quantum Matter", "topic_zh": "拓扑量子物态"},
    {"topic": "Quantum Hall / Anomalous Hall", "topic_zh": "量子霍尔 / 反常霍尔"},
    {"topic": "Superconductivity", "topic_zh": "超导物理"},
    {"topic": "Strongly Correlated Systems", "topic_zh": "强关联体系"},
    {"topic": "Quantum Magnetism", "topic_zh": "量子磁性"},
    {"topic": "Quantum Gases / Cold Atoms", "topic_zh": "量子气体 / 冷原子"},
    {"topic": "Quantum Optics", "topic_zh": "量子光学"},
    {"topic": "Statistical Mechanics", "topic_zh": "统计物理"},
    {"topic": "Mathematical Physics", "topic_zh": "数学物理"},
    {"topic": "Applied Physics / Materials", "topic_zh": "应用物理 / 材料"},
    {"topic": "Other Physics", "topic_zh": "其他物理方向"},
]

QAH_TOPICS = [
    {"topic": "Quantum Anomalous Hall / QAHE", "topic_zh": "量子反常霍尔 / QAHE"},
    {"topic": "Chern Insulators", "topic_zh": "陈绝缘体"},
    {"topic": "Topological Insulators", "topic_zh": "拓扑绝缘体"},
    {"topic": "Topological Semimetals", "topic_zh": "拓扑半金属"},
    {"topic": "Topological Superconductivity", "topic_zh": "拓扑超导"},
    {"topic": "Magnetic Topological Materials", "topic_zh": "磁性拓扑材料"},
    {"topic": "Moiré / Twistronics", "topic_zh": "莫尔材料 / 扭转电子学"},
    {
        "topic": "Quantum Hall / Fractional Chern Phases",
        "topic_zh": "量子霍尔 / 分数量子陈相",
    },
    {"topic": "Strongly Correlated Topological Phases", "topic_zh": "强关联拓扑相"},
    {"topic": "Topological Quantum Matter Theory", "topic_zh": "拓扑量子物态理论"},
    {"topic": "Materials Synthesis / Experiment", "topic_zh": "材料制备 / 实验"},
    {"topic": "Other Condensed Matter", "topic_zh": "其他凝聚态方向"},
]

ML_EXCLUDED_CATEGORIES = ["cs.AI", "cs.LG", "cs.CL", "cs.CV", "stat.ML"]
ML_EXCLUDED_KEYWORDS = [
    "machine learning",
    "deep learning",
    "neural network",
    "large language model",
    "LLM",
    "generative AI",
    "diffusion model",
    "transformer",
    "foundation model",
    "RAG",
    "retrieval augmented generation",
    "AI agent",
]

PHYSICS_STUDENT_KEYWORDS = [
    "condensed matter",
    "quantum matter",
    "quantum phase",
    "quantum transport",
    "quantum Hall",
    "anomalous Hall",
    "topological",
    "Berry curvature",
    "superconductivity",
    "superconductor",
    "strongly correlated",
    "spin liquid",
    "quantum criticality",
    "low-dimensional",
    "two-dimensional",
    "2D material",
    "graphene",
    "van der Waals",
    "moire",
    "moiré",
    "cold atoms",
    "optical lattice",
    "quantum simulation",
    "quantum optics",
    "many-body",
    "field theory",
    "statistical mechanics",
]

QAH_KEYWORDS = [
    "quantum anomalous Hall",
    "QAH",
    "QAHE",
    "anomalous Hall",
    "quantum Hall",
    "Chern insulator",
    "Chern number",
    "Chern band",
    "fractional Chern insulator",
    "fractional quantum Hall",
    "topological insulator",
    "magnetic topological insulator",
    "axion insulator",
    "topological superconductor",
    "topological superconductivity",
    "Majorana",
    "Weyl semimetal",
    "Dirac semimetal",
    "topological semimetal",
    "Berry curvature",
    "Berry phase",
    "spin orbit coupling",
    "spin-orbit coupling",
    "chiral edge state",
    "edge state",
    "surface state",
    "topological phase",
    "topological order",
    "topological invariant",
    "Haldane model",
    "Kane-Mele",
    "moire",
    "moiré",
    "twisted bilayer",
    "magic angle",
    "graphene",
    "van der Waals",
    "MnBi2Te4",
    "magnetic doping",
    "quantum transport",
    "Hall conductance",
    "anomalous Hall conductivity",
]

PHYSICS_STUDENT_CATEGORIES = [
    "cond-mat.mes-hall",
    "cond-mat.mtrl-sci",
    "cond-mat.str-el",
    "cond-mat.supr-con",
    "cond-mat.stat-mech",
    "cond-mat.quant-gas",
    "quant-ph",
    "physics.atom-ph",
    "physics.optics",
    "physics.app-ph",
    "math-ph",
]

QAH_CATEGORIES = [
    "cond-mat.mes-hall",
    "cond-mat.mtrl-sci",
    "cond-mat.str-el",
    "cond-mat.supr-con",
    "cond-mat.stat-mech",
    "cond-mat.quant-gas",
    "quant-ph",
    "physics.app-ph",
    "math-ph",
]

DEFAULT_CONFIG: dict[str, Any] = {
    "default_profile": "physics_student",
    "profiles": {
        "physics_student": {
            "display_name": "Physics Student",
            "display_name_zh": "物理系学生通用方向",
            "description": (
                "General physics literature profile for a physics student, excluding "
                "machine learning centered papers."
            ),
            "arxiv": {
                "categories": PHYSICS_STUDENT_CATEGORIES,
                "keywords": PHYSICS_STUDENT_KEYWORDS,
                "excluded_categories": ML_EXCLUDED_CATEGORIES,
                "excluded_keywords": ML_EXCLUDED_KEYWORDS,
                "max_results_per_day": 100,
                "page_size": 50,
                "request_interval_seconds": 3,
                "lookback_hours": 24,
                "timezone": "Asia/Tokyo",
            },
            "topics": PHYSICS_STUDENT_TOPICS,
        },
        "condensed_matter_topology_qah": {
            "display_name": "Condensed Matter / Topology / Quantum Anomalous Hall",
            "display_name_zh": "凝聚态 / 拓扑物态 / 量子反常霍尔",
            "description": (
                "Focused profile for condensed matter, topological phases, quantum "
                "anomalous Hall effect, Chern insulators, and quantum materials."
            ),
            "arxiv": {
                "categories": QAH_CATEGORIES,
                "keywords": QAH_KEYWORDS,
                "excluded_categories": ML_EXCLUDED_CATEGORIES,
                "excluded_keywords": [
                    keyword
                    for keyword in ML_EXCLUDED_KEYWORDS
                    if keyword != "retrieval augmented generation"
                ],
                "max_results_per_day": 100,
                "page_size": 50,
                "request_interval_seconds": 3,
                "lookback_hours": 24,
                "timezone": "Asia/Tokyo",
            },
            "topics": QAH_TOPICS,
        },
    },
    "llm": {
        "provider": "mock",
        "model": "mock-v1",
        "temperature": 0.2,
        "timeout_seconds": 60,
        "max_retries": 3,
        "request_interval_seconds": 1,
        "mode": "abstract_only",
    },
    "providers": {
        "custom_http": {
            "endpoint": "",
            "api_key_env": "CUSTOM_LLM_API_KEY",
            "model": "",
        },
        "litellm": {
            "api_key_env": "LITELLM_API_KEY",
            "model": "",
            "base_url": "",
        },
        "gemini": {
            "api_key_env": "GEMINI_API_KEY",
            "model": "",
        },
        "claude": {
            "api_key_env": "ANTHROPIC_API_KEY",
            "model": "",
        },
        "deepseek": {
            "api_key_env": "DEEPSEEK_API_KEY",
            "model": "",
            "base_url": "https://api.deepseek.com",
        },
        "qwen": {
            "api_key_env": "DASHSCOPE_API_KEY",
            "model": "",
        },
        "ollama": {
            "base_url": "http://localhost:11434",
            "model": "qwen2.5:7b",
        },
    },
    "output": {
        "report_dir": "reports",
        "formats": ["markdown", "html", "json"],
        "min_relevance_score": 60,
        "top_n": 50,
    },
    "database": {
        "path": "data/arxiv_digest.sqlite3",
    },
    "web": {
        "host": "127.0.0.1",
        "port": 8000,
        "auto_run_on_open": True,
        "enable_scheduler": True,
        "daily_run_time": "09:00",
        "require_admin_token_for_force": True,
        "require_admin_token_for_run": True,
        "allow_public_auto_run": False,
        "public_base_url": "",
    },
}


class ProfileArxivConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    categories: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    excluded_categories: list[str] = Field(default_factory=list)
    excluded_keywords: list[str] = Field(default_factory=list)
    max_results_per_day: int = 100
    page_size: int = 50
    request_interval_seconds: float = 3
    lookback_hours: int = 24
    timezone: str = "Asia/Tokyo"


class TopicConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    topic: str
    topic_zh: str


class ProfileConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    display_name: str
    display_name_zh: str
    description: str
    arxiv: ProfileArxivConfig = Field(default_factory=ProfileArxivConfig)
    topics: list[TopicConfig] = Field(default_factory=list)

    @property
    def fallback_topic(self) -> TopicConfig:
        if self.topics:
            return self.topics[-1]
        return TopicConfig(topic="Other Physics", topic_zh="其他物理方向")


class LLMConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    provider: str = "mock"
    model: str = "mock-v1"
    temperature: float = 0.2
    timeout_seconds: float = 60
    max_retries: int = 3
    request_interval_seconds: float = 1
    mode: str = "abstract_only"


class CustomHTTPConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    endpoint: str = ""
    api_key_env: str = "CUSTOM_LLM_API_KEY"
    model: str = ""


class LiteLLMConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    api_key_env: str = "LITELLM_API_KEY"
    model: str = ""
    base_url: str = ""


class KeyedProviderConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    api_key_env: str
    model: str = ""


class DeepSeekConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    api_key_env: str = "DEEPSEEK_API_KEY"
    model: str = ""
    base_url: str = "https://api.deepseek.com"


class OllamaConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    base_url: str = "http://localhost:11434"
    model: str = "qwen2.5:7b"


class ProvidersConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    custom_http: CustomHTTPConfig = Field(default_factory=CustomHTTPConfig)
    litellm: LiteLLMConfig = Field(default_factory=LiteLLMConfig)
    gemini: KeyedProviderConfig = Field(
        default_factory=lambda: KeyedProviderConfig(api_key_env="GEMINI_API_KEY")
    )
    claude: KeyedProviderConfig = Field(
        default_factory=lambda: KeyedProviderConfig(api_key_env="ANTHROPIC_API_KEY")
    )
    deepseek: DeepSeekConfig = Field(default_factory=DeepSeekConfig)
    qwen: KeyedProviderConfig = Field(
        default_factory=lambda: KeyedProviderConfig(api_key_env="DASHSCOPE_API_KEY")
    )
    ollama: OllamaConfig = Field(default_factory=OllamaConfig)


class OutputConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    report_dir: str = "reports"
    formats: list[str] = Field(default_factory=lambda: ["markdown", "html", "json"])
    min_relevance_score: int = 60
    top_n: int = 50


class DatabaseConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    path: str = "data/arxiv_digest.sqlite3"


class WebConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    host: str = "127.0.0.1"
    port: int = 8000
    auto_run_on_open: bool = True
    enable_scheduler: bool = True
    daily_run_time: str = "09:00"
    require_admin_token_for_force: bool = True
    require_admin_token_for_run: bool = True
    allow_public_auto_run: bool = False
    public_base_url: str = ""


class AppConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    default_profile: str = "physics_student"
    profiles: dict[str, ProfileConfig] = Field(default_factory=dict)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    providers: ProvidersConfig = Field(default_factory=ProvidersConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    web: WebConfig = Field(default_factory=WebConfig)
    config_path: str | None = None

    def get_profile(self, profile_name: str | None = None) -> tuple[str, ProfileConfig]:
        selected = profile_name or self.default_profile
        if selected not in self.profiles:
            available = ", ".join(sorted(self.profiles)) or "(none)"
            raise ValueError(f"Unknown profile '{selected}'. Available profiles: {available}.")
        return selected, self.profiles[selected]


def load_config(config_path: str | Path | None = None) -> AppConfig:
    load_dotenv()
    resolved_path = _resolve_config_path(config_path)
    data = copy.deepcopy(DEFAULT_CONFIG)
    if resolved_path and resolved_path.exists():
        file_data = yaml.safe_load(resolved_path.read_text(encoding="utf-8")) or {}
        _deep_merge(data, file_data)
    _apply_environment_overrides(data)
    config = AppConfig.model_validate(data)
    config.config_path = str(resolved_path) if resolved_path else None
    return config


def _resolve_config_path(config_path: str | Path | None) -> Path | None:
    if config_path:
        return Path(config_path)
    config_yaml = Path("config.yaml")
    if config_yaml.exists():
        return config_yaml
    example_yaml = Path("config.example.yaml")
    if example_yaml.exists():
        return example_yaml
    return None


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> None:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


def _apply_environment_overrides(data: dict[str, Any]) -> None:
    env_map = {
        "ARXIV_DIGEST_DEFAULT_PROFILE": ("default_profile",),
        "ARXIV_DIGEST_PROVIDER": ("llm", "provider"),
        "ARXIV_DIGEST_LLM_PROVIDER": ("llm", "provider"),
        "ARXIV_DIGEST_LLM_MODEL": ("llm", "model"),
        "ARXIV_DIGEST_DATABASE_PATH": ("database", "path"),
        "ARXIV_DIGEST_REPORT_DIR": ("output", "report_dir"),
        "ARXIV_DIGEST_WEB_HOST": ("web", "host"),
        "ARXIV_DIGEST_WEB_PORT": ("web", "port"),
        "ARXIV_DIGEST_WEB_AUTO_RUN_ON_OPEN": ("web", "auto_run_on_open"),
        "ARXIV_DIGEST_WEB_ENABLE_SCHEDULER": ("web", "enable_scheduler"),
        "ARXIV_DIGEST_WEB_REQUIRE_ADMIN_TOKEN_FOR_RUN": (
            "web",
            "require_admin_token_for_run",
        ),
        "ARXIV_DIGEST_WEB_ALLOW_PUBLIC_AUTO_RUN": ("web", "allow_public_auto_run"),
        "ARXIV_DIGEST_WEB_PUBLIC_BASE_URL": ("web", "public_base_url"),
        "CUSTOM_LLM_ENDPOINT": ("providers", "custom_http", "endpoint"),
        "CUSTOM_LLM_MODEL": ("providers", "custom_http", "model"),
        "LITELLM_BASE_URL": ("providers", "litellm", "base_url"),
        "LITELLM_MODEL": ("providers", "litellm", "model"),
        "DEEPSEEK_BASE_URL": ("providers", "deepseek", "base_url"),
        "DEEPSEEK_MODEL": ("providers", "deepseek", "model"),
        "DASHSCOPE_MODEL": ("providers", "qwen", "model"),
        "GEMINI_MODEL": ("providers", "gemini", "model"),
        "ANTHROPIC_MODEL": ("providers", "claude", "model"),
        "OLLAMA_BASE_URL": ("providers", "ollama", "base_url"),
        "OLLAMA_MODEL": ("providers", "ollama", "model"),
    }
    for env_name, path in env_map.items():
        value = os.getenv(env_name)
        if value:
            target = data
            for key in path[:-1]:
                target = target.setdefault(key, {})
            target[path[-1]] = value
