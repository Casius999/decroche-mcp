"""recruiter.qualify — score a recruiter's fit for a target job/company.

Pure deterministic logic. No network, no LLM.
"""

from __future__ import annotations

import re

from decroche.models import Recruiter, RecruiterQualification

# Tech/talent recruiter title signals → higher relevance
_TECH_RECRUITER_RE = re.compile(
    r"\b("
    r"tech(nical)?\s+(recruiter|talent|sourcer)"
    r"|ingénieur\s+recrutement"
    r"|talent\s+acquisition"
    r"|sourcing\s+specialist"
    r"|dev\s+recruiter"
    r")\b",
    re.IGNORECASE,
)

_GENERIC_HR_RE = re.compile(
    r"\b(hr\s+generalist|responsable\s+rh|drh|rrh|people\s+ops)\b",
    re.IGNORECASE,
)

# Seniority keywords
_SENIOR_TITLE_RE = re.compile(
    r"\b(lead|senior|sr\.?|head\s+of|principal|manager|director|vp|chief)\b",
    re.IGNORECASE,
)


def qualify(recruiter: Recruiter, target: dict) -> RecruiterQualification:
    """Score a recruiter's fit against a target job/company context.

    Args:
        recruiter: A :class:`Recruiter` (from ``identify()`` or manually constructed).
        target:    Dict describing the target. Expected keys (all optional):
                   - ``company``: target company name (str)
                   - ``sector``: sector/industry (str)
                   - ``role``: job title / role sought (str)
                   - ``seniority``: "junior"|"senior"|"lead"|"executive" (str)

    Returns:
        :class:`RecruiterQualification` with fit_score (0–1), recommend (bool),
        and a list of human-readable reasons.
    """
    reasons: list[str] = []
    score = 0.0

    target_company = target.get("company", "")
    target_role = target.get("role", "")
    target_seniority = target.get("seniority", "")

    # ── Kind scoring (most impactful) ─────────────────────────────────────────
    if recruiter.kind == "in_house":
        # In-house recruiter for the exact target company → strongest signal
        if target_company and recruiter.company:
            if recruiter.company.lower().strip() == target_company.lower().strip():
                score += 0.45
                reasons.append(f"Recruteur interne chez {recruiter.company} — cible directe.")
            else:
                score += 0.20
                reasons.append("Recruteur interne (entreprise différente de la cible).")
        else:
            score += 0.30
            reasons.append("Recruteur interne (entreprise cible non précisée).")
    elif recruiter.kind == "agency":
        score += 0.10
        reasons.append("Recruteur en cabinet — pertinence dépend du mandat.")
    else:
        score += 0.05
        reasons.append("Type de recruteur inconnu — pertinence incertaine.")

    # ── Title relevance ────────────────────────────────────────────────────────
    title = recruiter.title or ""
    if _TECH_RECRUITER_RE.search(title):
        score += 0.25
        reasons.append("Titre spécialisé tech/talent — forte pertinence rôle.")
    elif _GENERIC_HR_RE.search(title):
        score += 0.05
        reasons.append("Titre RH généraliste — pertinence rôle technique modérée.")
    elif title:
        score += 0.15
        reasons.append(f"Titre reconnu: {title}.")
    else:
        reasons.append("Titre inconnu — estimation de pertinence réduite.")

    # ── Seniority alignment ───────────────────────────────────────────────
    if target_seniority and title:
        target_is_senior = target_seniority.lower() in {"senior", "lead", "executive", "principal"}
        recruiter_is_senior = bool(_SENIOR_TITLE_RE.search(title))
        if target_is_senior and recruiter_is_senior:
            score += 0.10
            reasons.append("Séniorité du recruteur alignée avec le niveau cible.")
        elif not target_is_senior and not recruiter_is_senior:
            score += 0.10
            reasons.append("Niveau junio r/confirmé cohérent avec la cible.")

    # ── Role alignment (keyword overlap) ───────────────────────────────────
    if target_role and title:
        role_words = set(re.findall(r"\w+", target_role.lower()))
        title_words = set(re.findall(r"\w+", title.lower()))
        overlap = role_words & title_words - {"de", "du", "la", "le", "of", "the", "and", "et"}
        if overlap:
            score += min(0.10, 0.05 * len(overlap))
            reasons.append(f"Overlap mots-clés rôle/titre: {', '.join(sorted(overlap))}.")

    # ── Cap and recommend ──────────────────────────────────────────────────
    score = min(1.0, round(score, 3))
    recommend = score >= 0.40

    if not reasons:
        reasons.append("Données insuffisantes pour une qualification fine.")

    return RecruiterQualification(fit_score=score, recommend=recommend, reasons=reasons)
