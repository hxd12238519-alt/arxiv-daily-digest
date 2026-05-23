from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field

PHYSICS_STUDENT_TOPICS = [
    {"topic": "Strongly Correlated Systems", "topic_zh": "强关联体系"},
    {"topic": "Mott Physics / Hubbard Models", "topic_zh": "莫特物理 / Hubbard 模型"},
    {"topic": "Quantum Magnetism", "topic_zh": "量子磁性"},
    {"topic": "Unconventional Superconductivity", "topic_zh": "非常规超导"},
    {"topic": "Charge / Spin / Orbital Order", "topic_zh": "电荷 / 自旋 / 轨道有序"},
    {"topic": "Frustrated Magnets / Spin Liquids", "topic_zh": "阻挫磁性 / 自旋液体"},
    {"topic": "Heavy Fermions / Kondo Physics", "topic_zh": "重费米子 / 近藤物理"},
    {"topic": "Moiré Correlated Materials", "topic_zh": "莫尔强关联材料"},
    {"topic": "Correlated Topological Phases", "topic_zh": "强关联拓扑相"},
    {"topic": "Numerical Many-Body Methods", "topic_zh": "多体数值方法"},
    {"topic": "Other Strong-Correlation Physics", "topic_zh": "其他强关联物理"},
]

SPT_ANOMALY_TOPICS = [
    {
        "topic": "Symmetry-Protected Topological Phases / SPT",
        "topic_zh": "对称性保护拓扑相 / SPT",
    },
    {"topic": "Quantum Anomalies / Anomaly Matching", "topic_zh": "量子反常 / 反常匹配"},
    {"topic": "Generalized Global Symmetries", "topic_zh": "广义全局对称性"},
    {"topic": "Higher-Form Symmetries", "topic_zh": "高形式对称性"},
    {
        "topic": "Non-Invertible / Categorical Symmetries",
        "topic_zh": "非可逆 / 范畴对称性",
    },
    {"topic": "Symmetry-Enriched Topological Order", "topic_zh": "对称性富集拓扑序"},
    {"topic": "Topological Field Theory / Cobordism", "topic_zh": "拓扑场论 / 配边理论"},
    {"topic": "Boundary Anomaly / Anomaly Inflow", "topic_zh": "边界反常 / 反常流入"},
    {"topic": "Lattice Models and Spin Systems", "topic_zh": "晶格模型与自旋体系"},
    {"topic": "Other SPT / Symmetry Physics", "topic_zh": "其他 SPT / 对称性物理"},
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

PHYSICS_STUDENT_KEYWORDS: list[str] = []

SPT_ANOMALY_KEYWORDS = [
    "symmetry protected topological",
    "symmetry-protected topological",
    "SPT phase",
    "SPT phases",
    "SPT order",
    "bosonic SPT",
    "fermionic SPT",
    "short-range entangled",
    "invertible topological phase",
    "invertible phase",
    "topological response",
    "topological theta term",
    "quantum anomaly",
    "quantum anomalies",
    "anomaly matching",
    "anomalous symmetry",
    "mixed anomaly",
    "mixed anomalies",
    "global anomaly",
    "gauge anomaly",
    "chiral anomaly",
    "gravitational anomaly",
    "anomaly inflow",
    "t Hooft anomaly",
    "generalized symmetry",
    "generalized symmetries",
    "generalized global symmetry",
    "generalized global symmetries",
    "higher-form symmetry",
    "higher-form symmetries",
    "higher form symmetry",
    "higher form symmetries",
    "higher-group symmetry",
    "higher group symmetry",
    "one-form symmetry",
    "one-form symmetries",
    "1-form symmetry",
    "1-form symmetries",
    "two-form symmetry",
    "two-form symmetries",
    "2-form symmetry",
    "2-form symmetries",
    "subsystem symmetry",
    "subsystem symmetries",
    "non-invertible symmetry",
    "non-invertible symmetries",
    "noninvertible symmetry",
    "noninvertible symmetries",
    "categorical symmetry",
    "categorical symmetries",
    "fusion category symmetry",
    "symmetry defect",
    "topological defect",
    "duality defect",
    "symmetry fractionalization",
    "symmetry enriched topological",
    "SET phase",
    "Lieb-Schultz-Mattis anomaly",
    "LSM anomaly",
    "boundary anomaly",
    "gapless boundary",
    "anomalous boundary",
    "group cohomology",
    "cobordism",
    "cobordism classification",
    "topological quantum field theory",
    "TQFT",
]

PHYSICS_STUDENT_CATEGORIES = [
    "cond-mat.str-el",
]

SPT_ANOMALY_CATEGORIES = [
    "cond-mat.mes-hall",
    "cond-mat.other",
    "cond-mat.mtrl-sci",
    "cond-mat.str-el",
    "cond-mat.supr-con",
    "cond-mat.stat-mech",
    "quant-ph",
    "hep-th",
    "math-ph",
]

DEFAULT_CONFIG: dict[str, Any] = {
    "default_profile": "physics_student",
    "profiles": {
        "physics_student": {
            "display_name": "Strongly Correlated Electrons",
            "display_name_zh": "强关联电子方向",
            "description": (
                "Daily digest for all new arXiv cond-mat.str-el papers, excluding "
                "machine learning centered papers."
            ),
            "arxiv": {
                "categories": PHYSICS_STUDENT_CATEGORIES,
                "keywords": PHYSICS_STUDENT_KEYWORDS,
                "excluded_categories": ML_EXCLUDED_CATEGORIES,
                "excluded_keywords": ML_EXCLUDED_KEYWORDS,
                "max_results_per_day": 500,
                "page_size": 50,
                "request_interval_seconds": 3,
                "lookback_hours": 168,
                "timezone": "Asia/Tokyo",
            },
            "topics": PHYSICS_STUDENT_TOPICS,
        },
        "spt_anomaly_generalized_symmetry": {
            "display_name": "SPT / Quantum Anomaly / Generalized Symmetry",
            "display_name_zh": "SPT / 量子反常 / 广义对称性",
            "description": (
                "Focused profile for symmetry-protected topological phases, quantum "
                "anomalies, generalized symmetries, higher-form symmetries, and "
                "related topological field theory or lattice model work."
            ),
            "arxiv": {
                "categories": SPT_ANOMALY_CATEGORIES,
                "keywords": SPT_ANOMALY_KEYWORDS,
                "excluded_categories": ML_EXCLUDED_CATEGORIES,
                "excluded_keywords": ML_EXCLUDED_KEYWORDS,
                "max_results_per_day": 100,
                "page_size": 50,
                "request_interval_seconds": 3,
                "lookback_hours": 168,
                "timezone": "Asia/Tokyo",
            },
            "topics": SPT_ANOMALY_TOPICS,
        },
    },
    "llm": {
        "provider": "deepseek",
        "model": "deepseek-chat",
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
            "model": "deepseek-chat",
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
        "min_relevance_score": 0,
        "top_n": 100,
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

    provider: str = "deepseek"
    model: str = "deepseek-chat"
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
    min_relevance_score: int = 0
    top_n: int = 100


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
