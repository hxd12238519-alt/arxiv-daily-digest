from __future__ import annotations

import json

from arxiv_digest.config import ProfileConfig
from arxiv_digest.llm.schemas import PaperAnalysis
from arxiv_digest.models import Paper

SPT_ANOMALY_FOCUS = [
    "symmetry-protected topological phases and SPT classifications",
    "quantum anomalies, anomaly matching, and anomaly inflow",
    "'t Hooft anomalies and mixed anomalies",
    "generalized global symmetries",
    "higher-form symmetries",
    "non-invertible and categorical symmetries",
    "symmetry defects and topological defects",
    "symmetry fractionalization and symmetry-enriched topological order",
    "cobordism, group cohomology, and invertible phases",
    "gapless or degenerate boundaries required by anomalies",
    "lattice models, spin systems, and field-theory descriptions of SPT physics",
]


def build_analysis_messages(
    paper: Paper,
    *,
    profile_name: str,
    profile: ProfileConfig,
) -> list[dict[str, str]]:
    if profile_name == "physics_student":
        system_content = (
            "You translate arXiv physics metadata for a Chinese reader. Use only the "
            "supplied title, abstract, authors, and arXiv categories. Return strict JSON only."
        )
    else:
        system_content = (
            "You are a careful physics research assistant helping a physics student "
            "read arXiv papers. Analyze only from the supplied title, abstract, "
            "authors, and arXiv categories. Return strict JSON only."
        )
    return [
        {
            "role": "system",
            "content": system_content,
        },
        {
            "role": "user",
            "content": build_analysis_prompt(
                paper,
                profile_name=profile_name,
                profile=profile,
            ),
        },
    ]


def build_analysis_prompt(paper: Paper, *, profile_name: str, profile: ProfileConfig) -> str:
    if profile_name == "physics_student":
        return _build_abstract_translation_prompt(paper, profile_name=profile_name, profile=profile)

    schema = json.dumps(PaperAnalysis.model_json_schema(), ensure_ascii=False)
    topics = "\n".join(f"- {item.topic}: {item.topic_zh}" for item in profile.topics)
    special_focus = ""
    if profile_name == "spt_anomaly_generalized_symmetry":
        special_focus = "\nSpecial focus:\n" + "\n".join(f"- {item}" for item in SPT_ANOMALY_FOCUS)
    return f"""
你是一个物理学研究助理，正在帮助物理系学生阅读 arXiv 论文。
请只根据给定标题、摘要、作者和 arXiv 分类分析论文，不要编造摘要中没有的信息。

输出必须是严格 JSON，不要 Markdown。

你需要判断：
1. 论文属于哪个物理主题。
2. 研究问题是什么。
3. 研究的物理体系、材料体系或模型是什么。
4. 关键物理概念是什么。
5. 使用的是理论、数值模拟、材料制备、输运实验、光谱实验、冷原子实验，还是其他方法。
6. 主要结果是什么。
7. 摘要中是否明确说明实验或数值结果。
8. 对物理系学生是否值得优先阅读。
9. 如果摘要没有说明某项内容，请明确写：
   - "Not specified in the abstract."
   - "摘要中未明确说明。"

中文解释要适合物理系学生阅读。不要把物理术语翻译得过于机械：
- Chern insulator 翻译为“陈绝缘体”
- Berry curvature 翻译为“贝里曲率”
- chiral edge state 翻译为“手性边缘态”
- topological insulator 翻译为“拓扑绝缘体”
- Weyl semimetal 翻译为“外尔半金属”
- Dirac semimetal 翻译为“狄拉克半金属”
- symmetry-protected topological phase / SPT 翻译为“对称性保护拓扑相 / SPT”
- quantum anomaly 翻译为“量子反常”
- generalized global symmetry 翻译为“广义全局对称性”
- higher-form symmetry 翻译为“高形式对称性”
- non-invertible symmetry 翻译为“非可逆对称性”
- anomaly inflow 翻译为“反常流入”
{special_focus}

Profile:
- name: {profile_name}
- display_name: {profile.display_name}
- display_name_zh: {profile.display_name_zh}
- description: {profile.description}

Topic must be selected from this profile topic list:
{topics}

Required JSON schema:
{schema}

Paper:
Title: {paper.title}
Authors: {", ".join(paper.authors)}
Primary category: {paper.primary_category or ""}
Categories: {", ".join(paper.categories)}
Keyword hits: {", ".join(paper.keyword_hits)}
Abstract: {paper.abstract}
""".strip()


def _build_abstract_translation_prompt(
    paper: Paper,
    *,
    profile_name: str,
    profile: ProfileConfig,
) -> str:
    schema = json.dumps(PaperAnalysis.model_json_schema(), ensure_ascii=False)
    fallback_topic = profile.fallback_topic
    primary_topic = profile.topics[0] if profile.topics else fallback_topic
    return f"""
你正在为 arXiv 强关联电子方向日报整理论文条目。
这个 profile 只需要“英文标题/摘要”和“中文标题/摘要”的对应。
不要做研究问题、物理机制、方法、结果、局限性或阅读优先级分析。

输出必须是严格 JSON，不要 Markdown。

请完成：
1. 将论文标题翻译成自然、准确的中文，写入 title_zh。
2. 将英文摘要完整翻译成中文，写入 abstract_zh。
3. 其他必填字段只用于兼容 JSON schema，不要展开分析：
   - topic 使用 "{primary_topic.topic}"。
   - topic_zh 使用 "{primary_topic.topic_zh}"。
   - method_type 使用 "unknown"。
   - suggested_reading_priority 使用 "low"。
   - relevance_score 使用 0。
   - 研究问题、物理体系、方法、主要结果、实验或计算、局限性、相关性等字段统一写：
     - 英文："Translation-only profile; not analyzed."
     - 中文："本方向仅做标题和摘要中文对应，不进行深度分析。"
   - key_concepts_en 使用 ["abstract translation"]。
   - key_concepts_zh 使用 ["摘要中文对应"]。
   - keywords_en 使用 ["cond-mat.str-el"]。
   - keywords_zh 使用 ["强关联电子"]。
   - recommended_reason_zh 使用 "本方向仅做摘要中文对应。"

Required JSON schema:
{schema}

Profile:
- name: {profile_name}
- display_name: {profile.display_name}
- display_name_zh: {profile.display_name_zh}
- description: {profile.description}
- fallback_topic: {fallback_topic.topic} / {fallback_topic.topic_zh}

Paper:
Title: {paper.title}
Authors: {", ".join(paper.authors)}
Primary category: {paper.primary_category or ""}
Categories: {", ".join(paper.categories)}
Abstract: {paper.abstract}
""".strip()
