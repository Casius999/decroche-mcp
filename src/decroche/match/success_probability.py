"""match.success_probability — deterministic success probability estimator.

``success_probability(job, fit_score, *, network_proximity, applicants) -> SuccessProbability``

All factors are 0–1 floats.  Unknown signals default to neutral (0.5) and are
flagged in the notes list — they are NEVER fabricated.

Factor weights:
    fit             : 0.40  (from fit_score/100)
    recency         : 0.20  (fresher posting → higher; unknown → neutral 0.5)
    competition     : 0.20  (proxy: remote + low seniority → more competition)
    hiring_signal   : 0.10  (neutral 0.5 unless network_proximity or applicants given)
    network         : 0.10  (network_proximity or 0.0)

Confidence:
    high  → 4–5 signals known
    med   → 2–3 signals known
    low   → 0–1 signals known

No LLM, no network.  Deterministic.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from decroche.models import JobPosting, SuccessProbability

# Factor weights (must sum to 1.0)
_W_FIT = 0.40
_W_RECENCY = 0.20
_W_COMPETITION = 0.20
_W_HIRING_SIGNAL = 0.10
_W_NETWORK = 0.10

# Seniority keywords that indicate low seniority (more competition)
_LOW_SENIORITY = re.compile(r"\b(junior|stagiaire|stage|entry|intern|graduate)\b", re.IGNORECASE)
# Keywords indicating senior/specialist (less competition)
_HIGH_SENIORITY = re.compile(r"\b(senior|lead|principal|staff|architect|director|vp|head)\b", re.IGNORECASE)

_RECENCY_HALF_LIFE_DAYS = 7  # days; posting age beyond which recency drops to ~0.5


def _recency_factor(date_posted: str | None) -> tuple[float, bool]:
    """Return (recency_factor 0–1, known: bool).

    Fresher postings → higher score.  Uses an exponential decay with half-life of
    ``_RECENCY_HALF_LIFE_DAYS``.  Unknown date → neutral 0.5.
    """
    if not date_posted:
        return 0.5, False

    # Try to parse ISO-8601 or date-only
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(date_posted[:19], fmt)
            break
        except ValueError:
            continue
    else:
        return 0.5, False

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    age_days = max(0.0, (now - parsed).total_seconds() / 86400)
    # Exponential decay: factor = exp(-ln(2) * age / half_life)
    import math
    factor = math.exp(-math.log(2) * age_days / _RECENCY_HALF_LIFE_DAYS)
    return min(1.0, max(0.0, factor)), True


def _competition_factor(job: JobPosting) -> tuple[float, bool]:
    """Return (competition_factor 0–1, known: bool).

    Higher score = less competition (better for candidate).
    Heuristic: remote jobs + low seniority signals → more competition → lower score.
    We can only derive from title + tags + remote flag.
    """
    signals_found = 0
    penalty = 0.0

    text = f"{job.title} {' '.join(job.tags)}".lower()

    if job.remote is True:
        # Remote roles attract more applicants globally
        penalty += 0.15
        signals_found += 1
    elif job.remote is False:
        # On-site reduces competition slightly
        penalty -= 0.05
        signals_found += 1

    if _LOW_SENIORITY.search(text):
        # Entry-level → more competition
        penalty += 0.20
        signals_found += 1
    elif _HIGH_SENIORITY.search(text):
        # Senior → less competition
        penalty -= 0.15
        signals_found += 1

    if signals_found == 0:
        return 0.5, False

    raw = 0.5 - penalty
    return min(1.0, max(0.0, raw)), True


def _hiring_signal_factor(
    applicants: int | None,
) -> tuple[float, bool]:
    """Return (hiring_signal 0–1, known: bool).

    Fewer applicants → higher signal (better odds).
    Without data → neutral 0.5.
    """
    if applicants is None:
        return 0.5, False

    # Heuristic bands:
    #   < 10 applicants  → 0.85 (very good odds)
    #   10–50            → 0.65
    #   50–200           → 0.45
    #   200+             → 0.20
    if applicants < 10:
        return 0.85, True
    if applicants < 50:
        return 0.65, True
    if applicants < 200:
        return 0.45, True
    return 0.20, True


def success_probability(
    job: JobPosting,
    fit_score: float,
    *,
    network_proximity: float | None = None,
    applicants: int | None = None,
) -> SuccessProbability:
    """Estimate application success probability deterministically.

    Args:
        job:               The target job posting.
        fit_score:         Match score 0–100 (from match.score).
        network_proximity: Optional 0–1 float indicating network closeness to hiring team.
        applicants:        Optional known applicant count (from LinkedIn/provider).

    Returns:
        SuccessProbability with score_0_100, factors dict, confidence, and notes.
    """
    notes: list[str] = []
    signals_known = 0

    # ── fit ───────────────────────────────────────────────────────────────────────────
    fit = min(1.0, max(0.0, fit_score / 100.0))
    signals_known += 1  # fit is always provided

    # ── recency ────────────────────────────────────────────────────────────────────────
    recency, recency_known = _recency_factor(job.date_posted)
    if recency_known:
        signals_known += 1
    else:
        notes.append("recency: date_posted unknown — using neutral 0.5")

    # ── competition ──────────────────────────────────────────────────────────────────────
    competition, competition_known = _competition_factor(job)
    if competition_known:
        signals_known += 1
    else:
        notes.append("competition: no remote/seniority signals in posting — using neutral 0.5")

    # ── hiring_signal ──────────────────────────────────────────────────────────────────────
    hiring_signal, hs_known = _hiring_signal_factor(applicants)
    if hs_known:
        signals_known += 1
    else:
        notes.append("hiring_signal: applicant count not provided — using neutral 0.5")

    # ── network ─────────────────────────────────────────────────────────────────────────
    if network_proximity is not None:
        network = min(1.0, max(0.0, network_proximity))
        signals_known += 1
    else:
        network = 0.0
        notes.append("network: network_proximity not provided — using 0.0 (no network boost)")

    # ── weighted score ─────────────────────────────────────────────────────────────────────
    raw_score = (
        _W_FIT * fit
        + _W_RECENCY * recency
        + _W_COMPETITION * competition
        + _W_HIRING_SIGNAL * hiring_signal
        + _W_NETWORK * network
    )
    score = round(min(100.0, max(0.0, raw_score * 100.0)), 2)

    # ── confidence ───────────────────────────────────────────────────────────────────────
    if signals_known >= 4:
        confidence = "high"
    elif signals_known >= 2:
        confidence = "med"
    else:
        confidence = "low"

    factors = {
        "fit": round(fit, 4),
        "recency": round(recency, 4),
        "competition": round(competition, 4),
        "hiring_signal": round(hiring_signal, 4),
        "network": round(network, 4),
    }

    return SuccessProbability(
        score_0_100=score,
        factors=factors,
        confidence=confidence,
        notes=notes,
    )
