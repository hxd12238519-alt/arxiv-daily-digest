from __future__ import annotations

from arxiv_digest.math_text import normalize_math_text


def test_normalize_math_text_wraps_raw_compact_equations() -> None:
    text = "The entropy starts from Z_n[A]=Tr_Aρ_A^n and q_m=(2m+1)π/n."

    normalized = normalize_math_text(text)

    assert r"$Z_n[A]=\mathrm{Tr}_A\rho_A^n$" in normalized
    assert r"$q_m=(2m+1)\pi/n$" in normalized


def test_normalize_math_text_preserves_existing_math_delimiters() -> None:
    text = "We keep $n$ and \\(q_m=(2m+1)\\pi/n\\) unchanged."

    normalized = normalize_math_text(text)

    assert normalized == text
