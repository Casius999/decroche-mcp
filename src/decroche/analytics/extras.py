"""analytics.extras — supplementary analytics beyond the core funnel.

All functions are pure: they take lists/dicts and return dicts.
No I/O, no side-effects, no imports from storage or crm.

Added in Phase 5:
- channel_roi   : interview & offer rates by source channel
- story_coverage: which competencies are covered / gap
- salary_delta  : offer vs benchmark P50/P75
"""

from __future__ import annotations

from decroche.models import Application, SalaryRange, Story

# Tolerance band for "at" P50 (±3 %)
_AT_BAND_PCT = 3.0


def channel_roi(apps: list[Application]) -> dict[str, dict]:
    """Compute interview and offer rates per source channel.

    Groups Applications by ``source_channel`` and computes:
    - ``count``          : total apps from that channel
    - ``interview_rate`` : fraction that reached interview stage or beyond
    - ``offer_rate``     : fraction that reached offer stage

    Apps with ``source_channel=None`` are grouped under ``"unknown"``.

    Args:
        apps: List of Application objects (any stage).

    Returns:
        Dict keyed by channel name with ``{count, interview_rate, offer_rate}``.
    """
    _INTERVIEW_STAGES = {"phone_screen", "interview", "final", "offer", "accepted"}
    _OFFER_STAGES = {"offer", "accepted"}

    buckets: dict[str, list[Application]] = {}
    for app in apps:
        ch = app.source_channel or "unknown"
        buckets.setdefault(ch, []).append(app)

    result: dict[str, dict] = {}
    for ch, bucket in buckets.items():
        n = len(bucket)
        interviews = sum(1 for a in bucket if a.stage in _INTERVIEW_STAGES)
        offers = sum(1 for a in bucket if a.stage in _OFFER_STAGES)
        result[ch] = {
            "count": n,
            "interview_rate": round(interviews / n, 4) if n else 0.0,
            "offer_rate": round(offers / n, 4) if n else 0.0,
        }
    return result


def story_coverage(
    stories: list[Story],
    target_competencies: list[str],
) -> dict:
    """Report which competencies have at least one story and which are gaps.

    A competency is considered "covered" if at least one Story has that
    competency in its ``competencies`` list (case-insensitive).

    Args:
        stories:              List of Story objects.
        target_competencies:  Competencies to check coverage for.

    Returns:
        Dict with:
        - ``covered``      : list of covered competency strings
        - ``gaps``         : list of uncovered competency strings
        - ``coverage_pct`` : float 0.0–1.0
    """
    if not target_competencies:
        return {"covered": [], "gaps": [], "coverage_pct": 1.0}

    covered_set: set[str] = set()
    for story in stories:
        for comp in (story.competencies or []):
            covered_set.add(comp.lower())

    covered: list[str] = []
    gaps: list[str] = []
    for tc in target_competencies:
        if tc.lower() in covered_set:
            covered.append(tc)
        else:
            gaps.append(tc)

    pct = len(covered) / len(target_competencies)
    return {
        "covered": covered,
        "gaps": gaps,
        "coverage_pct": round(pct, 4),
    }


def salary_delta(offer: dict, benchmark: SalaryRange) -> dict:
    """Compare an offer amount to benchmark P50 and P75.

    Args:
        offer:     Dict with ``base`` (numeric) and optionally ``currency``.
        benchmark: SalaryRange (from negotiate.benchmark_range).

    Returns:
        Dict with:
        - ``offer_base``    : the raw offer amount
        - ``p50``           : benchmark P50
        - ``p75``           : benchmark P75
        - ``delta_p50``     : offer_base − p50
        - ``delta_p75``     : offer_base − p75
        - ``delta_p50_pct`` : (delta_p50 / p50) * 100, rounded 2dp
        - ``delta_p75_pct`` : (delta_p75 / p75) * 100, rounded 2dp
        - ``vs_p50``        : "above" | "at" | "below" (±3 % band)
        - ``currency``      : from offer dict or benchmark
    """
    base = float(offer.get("base", 0))
    p50 = float(benchmark.p50)
    p75 = float(benchmark.p75)
    currency = offer.get("currency") or benchmark.currency

    delta_p50 = base - p50
    delta_p75 = base - p75

    delta_p50_pct = round((delta_p50 / p50) * 100, 2) if p50 else 0.0
    delta_p75_pct = round((delta_p75 / p75) * 100, 2) if p75 else 0.0

    band = _AT_BAND_PCT
    if delta_p50_pct > band:
        vs_p50 = "above"
    elif delta_p50_pct < -band:
        vs_p50 = "below"
    else:
        vs_p50 = "at"

    return {
        "offer_base": base,
        "p50": p50,
        "p75": p75,
        "delta_p50": round(delta_p50, 2),
        "delta_p75": round(delta_p75, 2),
        "delta_p50_pct": delta_p50_pct,
        "delta_p75_pct": delta_p75_pct,
        "vs_p50": vs_p50,
        "currency": currency,
    }
