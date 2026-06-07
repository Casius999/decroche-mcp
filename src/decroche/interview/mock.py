"""interview.mock — Deterministic evaluation of a mock interview answer.

PURE function — no network, no LLM, no randomness.
Evaluates a free-text interview answer against STAR structure,
quantification presence, I/we balance, duration, and returns
a scored MockEval with actionable feedback.
"""

from __future__ import annotations

import re

from decroche.models import MockEval

# ── STAR keyword dictionaries (FR + EN) ────────────────────────────────────────────────

_STAR_PATTERNS: dict[str, list[str]] = {
    "situation": [
        # FR
        r"\b(contexte|context|situation|cadre|époque|moment|à l['’]époque|au moment où)\b",
        # EN
        r"\b(context|situation|background|at the time|when I was)\b",
    ],
    "task": [
        r"\b(mission|objectif|tâche|défi|challenge|responsabilité|chargé de|devais|needed to|had to|my role|my goal|tasked)\b",
    ],
    "action": [
        r"\b(j['’]ai|j['’]avais|nous avons|on a|j['’]ai décidé|j['’]ai mis en place|j['’]ai créé|j['’]ai proposé)\b",
        r"\b(I (decided|implemented|built|created|proposed|designed|led|developed|wrote|set up|coordinated|reached out))\b",
        r"\b(I (did|made|took|drove|launched|initiated|delivered|managed|owned|handled))\b",
    ],
    "result": [
        r"\b(résultat|résultats|impact|bilan|outcome|en conséquence|as a result|which resulted|led to|achieved|delivered)\b",
        r"\b(succès|réussi|gagné|atteint|succeeded|we (reduced|increased|saved|improved|grew|cut|boosted|hit|reached))\b",
    ],
}

# ── Quantification detection ────────────────────────────────────────────────────────────
# Matches numbers (with or without %) or money amounts
_QUANTIFIED_RE = re.compile(
    r"""
    (
        \d+\s*[%€$£k]        # 20%, 50€, 2k
      | \d[\d\s]*[\.,]\d+    # 2.5, 1,000
      | \b\d{2,}\b            # bare numbers ≥10 (10, 150 …)
      | \b(twice|double|triple|x\d+|\dx)\b   # multipliers
    )
    """,
    re.VERBOSE | re.IGNORECASE,
)

# ── I vs we tokens ──────────────────────────────────────────────────────────────────────
_I_RE = re.compile(r"\b(je|j['’]|i\b)", re.IGNORECASE)
_WE_RE = re.compile(r"\b(nous|on\b|we\b)", re.IGNORECASE)

# ── Score thresholds ────────────────────────────────────────────────────────────────────
_BAND_HIGH = 70.0
_BAND_LOW = 40.0

# ── WPM for duration estimate ──────────────────────────────────────────────────────────────────
_WPM = 130


def _check_star(text: str) -> tuple[bool, dict[str, bool]]:
    """Return (has_all_star, {component: found}) for the four STAR components."""
    found: dict[str, bool] = {}
    for component, patterns in _STAR_PATTERNS.items():
        combined = "|".join(f"(?:{p})" for p in patterns)
        found[component] = bool(re.search(combined, text, re.IGNORECASE))
    has_all = all(found.values())
    return has_all, found


def mock_evaluate(answer_text: str) -> MockEval:
    """Evaluate a mock interview answer deterministically.

    Checks:
    - STAR structure (situation, task, action, result)
    - Quantification presence (numbers, %, currency, multipliers)
    - I/we ratio (self-attribution balance)
    - Estimated duration at ~130 wpm
    - Score band: ``low`` / ``med`` / ``high``

    Args:
        answer_text: The candidate's free-text answer.

    Returns:
        MockEval with all fields populated.
    """
    text = answer_text.strip()

    # ── STAR detection ────────────────────────────────────────────────────────────────────
    has_star, star_parts = _check_star(text)

    # ── Quantification ──────────────────────────────────────────────────────────────────────
    quantified = bool(_QUANTIFIED_RE.search(text))

    # ── I / we ratio ────────────────────────────────────────────────────────────────────────
    i_count = len(_I_RE.findall(text))
    we_count = len(_WE_RE.findall(text))
    i_we_ratio = i_count / max(1, we_count)

    # ── Word count & duration ─────────────────────────────────────────────────────────────────
    words = text.split()
    word_count = len(words)
    est_seconds = round((word_count / _WPM) * 60)

    # ── Score (0–100) ─────────────────────────────────────────────────────────────────────
    score = 0.0
    score += 40.0 if has_star else sum(10.0 for v in star_parts.values() if v)
    score += 20.0 if quantified else 0.0
    # Duration sweet-spot: 90–180 seconds (≈ 2–3 minutes)
    if 90 <= est_seconds <= 180:
        score += 20.0
    elif 60 <= est_seconds < 90 or 180 < est_seconds <= 240:
        score += 10.0
    # I/we balance: slightly above 1 means good (owns contribution without
    # erasing the team). Penalise if i_we_ratio is extreme in either direction.
    if 0.5 <= i_we_ratio <= 5.0:
        score += 20.0
    elif 0.2 <= i_we_ratio < 0.5 or 5.0 < i_we_ratio <= 10.0:
        score += 10.0
    score = min(100.0, score)

    # ── Band ────────────────────────────────────────────────────────────────────────────────
    if score >= _BAND_HIGH:
        band = "high"
    elif score >= _BAND_LOW:
        band = "med"
    else:
        band = "low"

    # ── Feedback ──────────────────────────────────────────────────────────────────────────
    feedback: list[str] = []
    if not has_star:
        missing = [k for k, v in star_parts.items() if not v]
        feedback.append(
            f"Structure STAR incomplète — composantes manquantes détectées : {', '.join(missing)}. "
            "Structurez votre réponse avec Situation → Tâche → Action → Résultat."
        )
    else:
        feedback.append("Structure STAR détectée.")

    if not quantified:
        feedback.append(
            "Aucune donnée chiffrée détectée. Ajoutez des métriques concrètes "
            "(%, €, délais, volume, gain) pour renforcer l'impact."
        )
    else:
        feedback.append("Données quantifiées présentes — bon point.")

    if est_seconds < 60:
        feedback.append(
            f"Réponse très courte ({est_seconds}s estimées). "
            "Visez 2–3 minutes pour un entretien comportemental."
        )
    elif est_seconds > 240:
        feedback.append(
            f"Réponse longue ({est_seconds}s estimées). "
            "Restez sous 3 minutes et faites des pauses pour l'échangeur."
        )
    else:
        feedback.append(f"Durée estimée : {est_seconds}s — dans la plage cible.")

    if i_we_ratio < 0.2:
        feedback.append(
            "Ratio Je/Nous très faible — montrez votre contribution personnelle "
            "sans effacer le collectif."
        )
    elif i_we_ratio > 10.0:
        feedback.append("Ratio Je/Nous élevé — pensez à mentionner la contribution de l'équipe.")

    return MockEval(
        has_star=has_star,
        quantified=quantified,
        i_we_ratio=round(i_we_ratio, 3),
        est_seconds=est_seconds,
        word_count=word_count,
        score_0_100=round(score, 1),
        score_band=band,
        feedback=feedback,
    )
