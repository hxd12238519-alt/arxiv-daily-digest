from __future__ import annotations

import re

_EXISTING_MATH_RE = re.compile(r"(?s)(\$\$.*?\$\$|\$[^$\n]+\$|\\\(.*?\\\)|\\\[.*?\\\])")
_MATH_INDEX = r"[A-Za-z0-9Α-ω\\{}\[\]\(\)]+"
_MATH_LHS = r"""
    (?:\\[A-Za-z]+|[A-Za-zΑ-ω])
    [A-Za-z0-9Α-ω\\{}\[\]\(\)]*
    [_^]
    [A-Za-z0-9Α-ω\\{}\[\]\(\)]*
"""
_MATH_TERM = rf"""
    (?:
      \\[A-Za-z]+
      |[A-Za-z]{{1,3}}(?:[_^]{_MATH_INDEX})+
      |[Α-ω]+(?:[_^]{_MATH_INDEX})*
      |(?<![A-Za-z])[A-Za-z]{{1,2}}(?![A-Za-z])
      |[0-9]+
      |[{{}}\[\]\(\)_^+\-*/]+
    )
"""
_COMPACT_EQUATION_RE = re.compile(
    rf"""
    (?<![$\\A-Za-z0-9_])
    (?P<formula>
      {_MATH_LHS}
      \s*=\s*
      {_MATH_TERM}(?:\s*{_MATH_TERM})*
    )
    (?![$A-Za-z0-9_])
    """,
    re.VERBOSE,
)
_TRAILING_CONNECTOR_RE = re.compile(
    r"\s+(?:a|an|and|are|as|by|for|from|in|is|of|on|or|the|to|where|with)$",
    re.IGNORECASE,
)
_GREEK_REPLACEMENTS = {
    "α": r"\alpha",
    "β": r"\beta",
    "γ": r"\gamma",
    "δ": r"\delta",
    "ε": r"\epsilon",
    "θ": r"\theta",
    "κ": r"\kappa",
    "λ": r"\lambda",
    "μ": r"\mu",
    "ν": r"\nu",
    "π": r"\pi",
    "ρ": r"\rho",
    "σ": r"\sigma",
    "τ": r"\tau",
    "φ": r"\phi",
    "χ": r"\chi",
    "ψ": r"\psi",
    "ω": r"\omega",
    "Γ": r"\Gamma",
    "Δ": r"\Delta",
    "Θ": r"\Theta",
    "Λ": r"\Lambda",
    "Π": r"\Pi",
    "Σ": r"\Sigma",
    "Φ": r"\Phi",
    "Ψ": r"\Psi",
    "Ω": r"\Omega",
}


def normalize_math_text(text: str) -> str:
    """Wrap obvious raw inline formula fragments so MathJax can render them."""
    if not text:
        return text

    protected: list[str] = []

    def protect(match: re.Match[str]) -> str:
        protected.append(match.group(0))
        return f"\ue000MATH{len(protected) - 1}\ue001"

    normalized = _EXISTING_MATH_RE.sub(protect, text)
    normalized = _COMPACT_EQUATION_RE.sub(_wrap_formula, normalized)

    for index, value in enumerate(protected):
        normalized = normalized.replace(f"\ue000MATH{index}\ue001", value)
    return normalized


def normalize_math_texts(values: list[str]) -> list[str]:
    return [normalize_math_text(value) for value in values]


def _wrap_formula(match: re.Match[str]) -> str:
    formula = _normalize_formula(_trim_trailing_connectors(match.group("formula").strip()))
    return f"${formula}$"


def _normalize_formula(formula: str) -> str:
    normalized = formula
    for source, replacement in _GREEK_REPLACEMENTS.items():
        normalized = normalized.replace(source, replacement)
    normalized = re.sub(r"(?<!\\)\bTr(?=_|\b)", r"\\mathrm{Tr}", normalized)
    return normalized


def _trim_trailing_connectors(formula: str) -> str:
    normalized = formula
    while True:
        trimmed = _TRAILING_CONNECTOR_RE.sub("", normalized)
        if trimmed == normalized:
            return normalized
        normalized = trimmed
