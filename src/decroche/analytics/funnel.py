"""analytics.funnel — Pure deterministic conversion funnel statistics.

Benchmarks (2026, CareerPlug / LinkedIn Talent Insights):
- applied → screen:    ~3 %   (CareerPlug 2026, broad market)
- screen → interview:  ~33 %  (1 in 3 screened get interviewed)
- interview → offer:   ~20 %  (CareerPlug 2026)
- offer → accepted:    ~80 %  (most offers get accepted)
"""

from __future__ import annotations

from decroche.models import Application, FunnelStats

# 2026 industry benchmarks (rate as a decimal 0–1)
_BENCHMARKS: dict[str, float] = {
    "applied_to_screen": 0.03,
    "screen_to_interview": 0.33,
    "interview_to_offer": 0.20,
    "offer_to_accepted": 0.80,
}

# (from_stage, to_stage) → rate_key
_TRANSITIONS: list[tuple[str, str, str]] = [
    ("applied", "screen", "applied_to_screen"),
    ("screen", "interview", "screen_to_interview"),
    ("interview", "offer", "interview_to_offer"),
    ("offer", "accepted", "offer_to_accepted"),
]

_AT_THRESHOLD = 0.05  # ±5 % of benchmark counts as "at"


def funnel(apps: list[Application]) -> FunnelStats:
    """Compute conversion funnel statistics over a list of Applications.

    Args:
        apps: List of Application objects (any stages, any mix).

    Returns:
        FunnelStats with per-stage counts, conversion rates, bottleneck,
        benchmark comparison labels, and descriptive notes.
    """
    if not apps:
        return FunnelStats()

    # ── counts ─────────────────────────────────────────────────────────────────
    counts: dict[str, int] = {}
    for app in apps:
        counts[app.stage] = counts.get(app.stage, 0) + 1

    # ── rates ──────────────────────────────────────────────────────────────────
    rates: dict[str, float] = {}
    for from_stage, to_stage, key in _TRANSITIONS:
        denom = counts.get(from_stage, 0)
        numer = counts.get(to_stage, 0)
        if denom > 0:
            rates[key] = numer / denom
        elif numer > 0:
            # numerator exists but no denominator → can't compute (skip)
            pass
        else:
            rates[key] = 0.0

    # ── bottleneck ─────────────────────────────────────────────────────────────
    # Worst relative dropout = transition with the highest dropout percentage
    # (1 - rate). Only consider transitions where the denominator stage exists.
    bottleneck: str | None = None
    worst_dropout = -1.0
    for from_stage, _to_stage, key in _TRANSITIONS:
        if counts.get(from_stage, 0) > 0 and key in rates:
            dropout = 1.0 - rates[key]
            if dropout > worst_dropout:
                worst_dropout = dropout
                bottleneck = key

    # ── vs_benchmark ───────────────────────────────────────────────────────────
    vs_benchmark: dict[str, str] = {}
    for key, bench in _BENCHMARKS.items():
        if key not in rates:
            continue
        actual = rates[key]
        delta = bench * _AT_THRESHOLD
        if actual >= bench - delta and actual <= bench + delta:
            vs_benchmark[key] = "at"
        elif actual > bench + delta:
            vs_benchmark[key] = "above"
        else:
            vs_benchmark[key] = "below"

    # ── notes ──────────────────────────────────────────────────────────────────
    notes: list[str] = []
    total = len(apps)
    notes.append(f"Total applications tracked: {total}")

    if bottleneck:
        actual_rate = rates.get(bottleneck, 0.0)
        bench_rate = _BENCHMARKS.get(bottleneck, 0.0)
        label = vs_benchmark.get(bottleneck, "unknown")
        notes.append(
            f"Bottleneck: {bottleneck} ({actual_rate:.1%} actual vs {bench_rate:.1%} benchmark → {label})"
        )

    return FunnelStats(
        counts=counts,
        rates=rates,
        bottleneck=bottleneck,
        vs_benchmark=vs_benchmark,
        notes=notes,
    )
