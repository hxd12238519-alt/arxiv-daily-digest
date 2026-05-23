from __future__ import annotations

import json

from arxiv_digest.config import ProfileConfig
from arxiv_digest.llm.schemas import PaperAnalysis
from arxiv_digest.models import Paper

QAH_FOCUS = [
    "quantum anomalous Hall effect",
    "Chern insulator",
    "topological insulator",
    "topological semimetal",
    "topological superconductor",
    "Berry curvature",
    "chiral edge state",
    "surface state",
    "quantum transport",
    "magnetic topological material",
    "moiré material",
    "strongly correlated topological phase",
    "fractional quantum Hall",
    "fractional Chern insulator",
]


def build_analysis_messages(
    paper: Paper,
    *,
    profile_name: str,
    profile: ProfileConfig,
) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You are a careful physics research assistant helping a physics student "
                "read arXiv papers. Analyze only from the supplied title, abstract, "
                "authors, and arXiv categories. Return strict JSON only."
            ),
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
    schema = json.dumps(PaperAnalysis.model_json_schema(), ensure_ascii=False)
    topics = "\n".join(f"- {item.topic}: {item.topic_zh}" for item in profile.topics)
    qah_focus = ""
    if profile_name == "condensed_matter_topology_qah":
        qah_focus = "\nSpecial focus:\n" + "\n".join(f"- {item}" for item in QAH_FOCUS)
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
- quantum anomalous Hall effect 翻译为“量子反常霍尔效应”
- chiral edge state 翻译为“手性边缘态”
- topological insulator 翻译为“拓扑绝缘体”
- Weyl semimetal 翻译为“外尔半金属”
- Dirac semimetal 翻译为“狄拉克半金属”
{qah_focus}

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
