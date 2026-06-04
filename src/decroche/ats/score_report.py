"""Score report builder.

Combines AtsParseResult (before/after) with optional match score and
redflag count to produce a ScoreReport.
Pure deterministic logic — no LLM, no network.
"""

from __future__ import annotations

from decroche.models import AtsParseResult, ScoreReport

# ── Screener-readiness thresholds ────────────────────────────────────────────────────────
# parsability + redflag adjustments → tier

_HIGH_PARSABILITY = 75.0
_LOW_PARSABILITY = 50.0
_HIGH_REDFLAG_COUNT = 4
_MEDIUM_REDFLAG_COUNT = 2


def _screener_readiness(parsability: float, redflag_count: int) -> str:
    """Classify screener readiness from parsability + redflags."""
    # Effective score: parsability penalised by severe red flags
    penalty = redflag_count * 5  # 5 points per red flag
    effective = parsability - penalty

    if effective >= _HIGH_PARSABILITY:
        return "high"
    if effective <= _LOW_PARSABILITY:
        return "low"
    return "medium"


# ── Entry point ─────────────────────────────────────────────────────────────────────────────


def score_report(
    before: AtsParseResult,
    after: AtsParseResult | None = None,
    match: float | None = None,
    redflag_count: int = 0,
) -> ScoreReport:
    """Build a ScoreReport.

    Args:
        before: AtsParseResult from the original CV.
        after: Optional AtsParseResult after optimisation (for delta computation).
        match: Optional keyword match score 0-100.
        redflag_count: Number of red flags detected.

    Returns:
        ScoreReport.
    """
    parsability = before.parsability_score
    readiness = _screener_readiness(parsability, redflag_count)

    delta: dict | None = None
    if after is not None:
        delta = {
            "parsability_before": parsability,
            "parsability_after": after.parsability_score,
            "breakage_delta": len(after.breakages) - len(before.breakages),
        }

    return ScoreReport(
        parsability=parsability,
        match=match,
        screener_readiness=readiness,
        redflag_count=redflag_count,
        delta=delta,
    )
