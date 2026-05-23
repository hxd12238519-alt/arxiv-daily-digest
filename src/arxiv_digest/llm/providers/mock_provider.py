from __future__ import annotations

import hashlib
import re

from arxiv_digest.llm.base import LLMProvider
from arxiv_digest.llm.schemas import PaperAnalysis
from arxiv_digest.models import Paper

PHYSICS_RULES = [
    (
        "Mott Physics / Hubbard Models",
        "莫特物理 / Hubbard 模型",
        ["hubbard", "mott", "t-j model", "tJ model"],
    ),
    (
        "Unconventional Superconductivity",
        "非常规超导",
        ["superconduct", "pairing", "cooper", "cuprate", "pair-density wave"],
    ),
    (
        "Strongly Correlated Systems",
        "强关联体系",
        ["strongly correlated", "correlation", "many-body", "electron-electron"],
    ),
    (
        "Quantum Magnetism",
        "量子磁性",
        ["magnet", "magnon", "antiferromagnet", "ferromagnet", "spin"],
    ),
    (
        "Charge / Spin / Orbital Order",
        "电荷 / 自旋 / 轨道有序",
        ["charge order", "spin order", "orbital order", "density wave", "stripe"],
    ),
    (
        "Frustrated Magnets / Spin Liquids",
        "阻挫磁性 / 自旋液体",
        ["frustrated", "spin liquid", "kitaev"],
    ),
    ("Heavy Fermions / Kondo Physics", "重费米子 / 近藤物理", ["heavy fermion", "kondo"]),
    (
        "Moiré Correlated Materials",
        "莫尔强关联材料",
        ["moire", "moiré", "twisted bilayer", "magic angle"],
    ),
    (
        "Correlated Topological Phases",
        "强关联拓扑相",
        ["topological", "chern", "berry", "edge state", "surface state"],
    ),
    (
        "Numerical Many-Body Methods",
        "多体数值方法",
        ["dmrg", "monte carlo", "exact diagonalization", "tensor network"],
    ),
]

SPT_ANOMALY_RULES = [
    (
        "Symmetry-Protected Topological Phases / SPT",
        "对称性保护拓扑相 / SPT",
        ["symmetry-protected topological", "symmetry protected topological", "spt phase"],
    ),
    (
        "Quantum Anomalies / Anomaly Matching",
        "量子反常 / 反常匹配",
        ["quantum anomaly", "quantum anomalies", "anomaly matching", "t hooft anomaly"],
    ),
    (
        "Generalized Global Symmetries",
        "广义全局对称性",
        ["generalized symmetry", "generalized symmetries", "generalized global symmetry"],
    ),
    (
        "Higher-Form Symmetries",
        "高形式对称性",
        [
            "higher-form symmetry",
            "higher-form symmetries",
            "higher form symmetry",
            "higher form symmetries",
            "1-form symmetry",
            "one-form symmetry",
        ],
    ),
    (
        "Non-Invertible / Categorical Symmetries",
        "非可逆 / 范畴对称性",
        [
            "non-invertible symmetry",
            "non-invertible symmetries",
            "noninvertible symmetry",
            "categorical symmetry",
            "categorical symmetries",
        ],
    ),
    (
        "Symmetry-Enriched Topological Order",
        "对称性富集拓扑序",
        ["symmetry enriched topological", "symmetry fractionalization", "set phase"],
    ),
    ("Topological Field Theory / Cobordism", "拓扑场论 / 配边理论", ["cobordism", "tqft"]),
    (
        "Boundary Anomaly / Anomaly Inflow",
        "边界反常 / 反常流入",
        ["anomaly inflow", "boundary anomaly", "gapless boundary"],
    ),
]


class MockProvider(LLMProvider):
    def analyze_paper(self, paper: Paper) -> PaperAnalysis:
        topic, topic_zh = self._topic_for(paper)
        score = self._score_for(paper, topic)
        priority = "high" if score >= 80 else "medium" if score >= 60 else "low"
        concepts_en, concepts_zh = self._concepts_for(paper)
        method_type = self._method_type_for(paper)
        keyword_hits = paper.keyword_hits or self._keywords_for(paper)
        return PaperAnalysis(
            topic=topic,
            topic_zh=topic_zh,
            title_zh=f"Mock 中文标题：{paper.title}",
            abstract_zh=f"Mock 摘要翻译：{paper.abstract[:260]}",
            physics_problem_en=(
                "Mock physics problem: identify the physical mechanism and phase "
                "behavior described in the abstract."
            ),
            physics_problem_zh="Mock 研究问题：理解摘要中涉及的物理机制、物态或相变行为。",
            physical_system_en=self._physical_system_en(paper),
            physical_system_zh=self._physical_system_zh(paper),
            key_concepts_en=concepts_en,
            key_concepts_zh=concepts_zh,
            method_type=method_type,
            method_en=self._method_en(method_type),
            method_zh=self._method_zh(method_type),
            main_results_en=(
                f"Mock main result: the abstract suggests a physics result relevant to {topic}."
            ),
            main_results_zh=(
                f"Mock 主要结果：摘要显示该工作与“{topic_zh}”相关，值得进一步阅读原文。"
            ),
            experiments_or_calculations_en="Not specified in the abstract.",
            experiments_or_calculations_zh="摘要中未明确说明。",
            limitations_en="Not specified in the abstract.",
            limitations_zh="摘要中未明确说明。",
            why_relevant_en=f"It matches the active profile {self.profile.display_name}.",
            why_relevant_zh=f"它命中了当前方向“{self.profile.display_name_zh}”的关键词和主题。",
            suggested_reading_priority=priority,
            relevance_score=score,
            keywords_en=keyword_hits[:5] or ["physics"],
            keywords_zh=concepts_zh[:5] or ["物理"],
            recommended_reason_zh=f"Mock 推荐理由：主题匹配“{topic_zh}”，阅读优先级为 {priority}。",
        )

    def _topic_for(self, paper: Paper) -> tuple[str, str]:
        text = self._text(paper)
        rules = (
            SPT_ANOMALY_RULES
            if self.profile_name == "spt_anomaly_generalized_symmetry"
            else PHYSICS_RULES
        )
        for topic, topic_zh, terms in rules:
            if any(term in text for term in terms):
                return topic, topic_zh
        fallback = self.profile.fallback_topic
        return fallback.topic, fallback.topic_zh

    def _score_for(self, paper: Paper, topic: str) -> int:
        seed = f"{self.profile_name}|{paper.arxiv_id}|{paper.title}|{topic}".encode()
        digest = hashlib.sha256(seed).hexdigest()
        score = 45 + int(digest[:2], 16) % 41
        if topic != self.profile.fallback_topic.topic:
            score += 10
        if paper.keyword_hits:
            score += min(10, len(paper.keyword_hits) * 2)
        return max(0, min(100, score))

    def _concepts_for(self, paper: Paper) -> tuple[list[str], list[str]]:
        text = self._text(paper)
        concepts: list[tuple[str, str]] = []
        concept_map = [
            ("symmetry-protected topological phase", "对称性保护拓扑相"),
            ("quantum anomaly", "量子反常"),
            ("anomaly matching", "反常匹配"),
            ("generalized global symmetry", "广义全局对称性"),
            ("higher-form symmetry", "高形式对称性"),
            ("non-invertible symmetry", "非可逆对称性"),
            ("anomaly inflow", "反常流入"),
            ("cobordism", "配边理论"),
            ("Chern insulator", "陈绝缘体"),
            ("Berry curvature", "贝里曲率"),
            ("topological insulator", "拓扑绝缘体"),
            ("chiral edge state", "手性边缘态"),
            ("superconductivity", "超导"),
            ("strong correlation", "强关联"),
            ("cold atoms", "冷原子"),
            ("quantum transport", "量子输运"),
            ("moiré material", "莫尔材料"),
        ]
        for concept_en, concept_zh in concept_map:
            if concept_en.lower() in text:
                concepts.append((concept_en, concept_zh))
        if not concepts:
            concepts.append(("physics mechanism", "物理机制"))
        return [item[0] for item in concepts[:5]], [item[1] for item in concepts[:5]]

    def _method_type_for(self, paper: Paper) -> str:
        text = self._text(paper)
        if any(term in text for term in ["transport", "conductance", "hall measurement"]):
            return "quantum_transport"
        if any(term in text for term in ["spectroscopy", "arpes", "raman"]):
            return "spectroscopy"
        if any(term in text for term in ["synthesis", "growth", "fabrication"]):
            return "materials_synthesis"
        if any(term in text for term in ["experiment", "measured", "measurement"]):
            return "experiment"
        if any(term in text for term in ["simulation", "numerical", "monte carlo", "dmrg"]):
            return "numerical"
        if any(term in text for term in ["cold atom", "optical lattice"]):
            return "cold_atoms"
        if "review" in text:
            return "review"
        if any(term in text for term in ["model", "theory", "hamiltonian"]):
            return "theory"
        return "unknown"

    def _keywords_for(self, paper: Paper) -> list[str]:
        text = self._text(paper)
        matched = [keyword for keyword in self.profile.arxiv.keywords if keyword.lower() in text]
        if matched:
            return matched[:5]
        words = re.findall(r"[a-zA-Z][a-zA-Z\-]{3,}", paper.title.lower())
        return (words[:3] or ["physics"])[:5]

    def _physical_system_en(self, paper: Paper) -> str:
        text = self._text(paper)
        if "graphene" in text:
            return "graphene or graphene-based moiré material"
        if "mnbi2te4" in text:
            return "MnBi2Te4 magnetic topological material"
        if "cold atom" in text or "optical lattice" in text:
            return "cold atoms in an optical lattice"
        if "superconduct" in text:
            return "superconducting system"
        return "Not specified in the abstract."

    def _physical_system_zh(self, paper: Paper) -> str:
        text = self._text(paper)
        if "graphene" in text:
            return "石墨烯或石墨烯相关莫尔材料。"
        if "mnbi2te4" in text:
            return "MnBi2Te4 磁性拓扑材料。"
        if "cold atom" in text or "optical lattice" in text:
            return "光晶格中的冷原子体系。"
        if "superconduct" in text:
            return "超导体系。"
        return "摘要中未明确说明。"

    def _method_en(self, method_type: str) -> str:
        return {
            "theory": "The abstract suggests a theoretical model or analytical argument.",
            "numerical": "The abstract suggests numerical calculations or simulations.",
            "experiment": "The abstract suggests an experimental study.",
            "materials_synthesis": "The abstract suggests materials synthesis or fabrication.",
            "quantum_transport": "The abstract suggests quantum transport measurements.",
            "spectroscopy": "The abstract suggests spectroscopy measurements.",
            "cold_atoms": "The abstract suggests a cold-atom experiment or simulation.",
            "review": "The abstract suggests a review-style paper.",
            "unknown": "Not specified in the abstract.",
        }[method_type]

    def _method_zh(self, method_type: str) -> str:
        return {
            "theory": "摘要显示该工作偏理论模型或解析论证。",
            "numerical": "摘要显示该工作包含数值计算或模拟。",
            "experiment": "摘要显示该工作偏实验研究。",
            "materials_synthesis": "摘要显示该工作涉及材料制备或器件加工。",
            "quantum_transport": "摘要显示该工作涉及量子输运测量。",
            "spectroscopy": "摘要显示该工作涉及光谱实验。",
            "cold_atoms": "摘要显示该工作涉及冷原子实验或量子模拟。",
            "review": "摘要显示该论文可能是综述。",
            "unknown": "摘要中未明确说明。",
        }[method_type]

    def _text(self, paper: Paper) -> str:
        return f"{paper.title} {paper.abstract} {' '.join(paper.categories)}".lower()
