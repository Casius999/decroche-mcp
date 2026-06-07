"""analytics.extras — Pure deterministic analytics extras (P5).

All functions are pure — no network, no database.
"""

from __future__ import annotations

from decroche.models import Application, SalaryRange, Story

_INTERVIEW_STAGES = frozenset({"interview", "offer", "accepted", "rejected_late"})
_OFFER_STAGES = frozenset({"offer", "accepted"})
_AT_BAND_PCT = 3.0  # ±3 % = "at"


def channel_roi(apps: list[Application]) -> dict:
    """Compute interview and offer rates by source_channel.

    Args:
        apps: List of Application objects.

    Returns:
        Dict keyed by source_channel with ``{count, interview_rate, offer_rate}``.
    """
    channels: dict[str, dict[str, int]] = {}
    for app in apps:
        ch = app.source_channel if app.source_channel else "unknown"
        if ch not in channels:
            channels[ch] = {"count": 0, "interviews": 0, "offers": 0}
        channels[ch]["count"] += 1
        if app.stage in _INTERVIEW_STAGES:
            channels[ch]["interviews"] += 1
        if app.stage in _OFFER_STAGES:
            channels[ch]["offers"] += 1

    result: dict[str, dict] = {}
    for ch, d in channels.items():
        n = d["count"]
        result[ch] = {
            "count": n,
            "interview_rate": round(d["interviews"] / n, 4) if n else 0.0,
            "offer_rate": round(d["offers"] / n, 4) if n else 0.0,
        }
    return result


def story_coverage(stories: list[Story], target_competencies: list[str]) -> dict:
    """Report competency coverage from a story bank.

    Args:
        stories:              List of Story objects.
        target_competencies:  Competencies to check coverage for.

    Returns:
        Dict with ``covered`` (list), ``gaps`` (list), ``coverage_pct`` (float).
    """
    covered_set: set[str] = set()
    for s in stories:
        for c in s.competencies:
            covered_set.add(c.lower().strip())

    covered: list[str] = []
    gaps: list[str] = []
    for comp in target_competencies:
        key = comp.lower().strip()
        is_covered = any(key in c or c in key for c in covered_set)
        if is_covered:
            covered.append(comp)
        else:
            gaps.append(comp)

    total = len(target_competencies)
    pct = round(len(covered) / total, 4) if total else 0.0

    return {
        "covered": covered,
        "gaps": gaps,
        "coverage_pct": pct,
    }


def salary_delta(offer: dict, benchmark: SalaryRange) -> dict:
    """Compare an offer amount to benchmark P50 and P75.

    Args:
        offer:     Dict with ``base`` (numeric) and optionally ``currency``.
        benchmark: SalaryRange from ``negotiate.benchmark_range``.

    Returns:
        Dict with ``offer_base``, ``p50``, ``p75``, ``delta_p50``,
        ``delta_p75``, ``delta_p50_pct``, ``delta_p75_pct``,
        ``vs_p50`` (``"above"`` / ``"at"`` / ``"below"``), ``currency``.
    """
    base = float(offer.get("base", 0))
    p50 = benchmark.p50
    p75 = benchmark.p75

    delta_p50 = base - p50
    delta_p75 = base - p75
    delta_p50_pct = round((delta_p50 / p50) * 100, 2) if p50 else 0.0
    delta_p75_pct = round((delta_p75 / p75) * 100, 2) if p75 else 0.0

    if abs(delta_p50_pct) <= _AT_BAND_PCT:
        vs_p50 = "at"
    elif base > p50:
        vs_p50 = "above"
    else:
        vs_p50 = "below"

    return {
        "offer_base": base,
        "p50": p50,
        "p75": p75,
        "delta_p50": round(delta_p50, 2),
        "delta_p75": round(delta_p75, 2),
        "delta_p50_pct": delta_p50_pct,
        "delta_p75_pct": delta_p75_pct,
        "vs_p50": vs_p50,
        "currency": benchmark.currency,
    }
