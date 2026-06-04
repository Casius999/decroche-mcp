"""Tests for analytics.funnel — pure deterministic conversion funnel."""

from __future__ import annotations

from decroche.analytics.funnel import funnel
from decroche.models import Application, FunnelStats


def _mk(app_id: str, stage: str) -> Application:
    return Application(id=app_id, company="Co", role_title="Dev", stage=stage)

def _sample_apps() -> list[Application]:
    apps = [_mk(f"a{i:02d}", "applied") for i in range(1, 21)]
    apps += [_mk(f"s{i}", "screen") for i in range(1, 4)]
    apps += [_mk(f"i{i}", "interview") for i in range(1, 3)]
    apps += [_mk("o1", "offer"), _mk("acc1", "accepted"), _mk("rej1", "rejected"), _mk("ghost1", "ghosted"), _mk("sav1", "saved")]
    return apps


def test_funnel_counts_all_stages():
    stats = funnel(_sample_apps())
    assert stats.counts["applied"] == 20 and stats.counts["screen"] == 3
    assert stats.counts["interview"] == 2 and stats.counts["offer"] == 1

def test_funnel_empty_list():
    stats = funnel([])
    assert isinstance(stats, FunnelStats) and stats.counts == {} and stats.bottleneck is None

def test_funnel_single_stage():
    assert funnel([_mk("x1", "applied"), _mk("x2", "applied")]).counts["applied"] == 2

def test_funnel_counts_returns_int_values():
    assert all(isinstance(v, int) for v in funnel(_sample_apps()).counts.values())

def test_funnel_rates_applied_to_screen():
    stats = funnel(_sample_apps())
    assert "applied_to_screen" in stats.rates
    assert abs(stats.rates["applied_to_screen"] - 0.15) < 0.001

def test_funnel_rates_screen_to_interview():
    stats = funnel(_sample_apps())
    assert abs(stats.rates["screen_to_interview"] - 2/3) < 0.001

def test_funnel_rates_interview_to_offer():
    assert abs(funnel(_sample_apps()).rates["interview_to_offer"] - 0.5) < 0.001

def test_funnel_rates_offer_to_accepted():
    assert abs(funnel(_sample_apps()).rates["offer_to_accepted"] - 1.0) < 0.001

def test_funnel_rates_zero_when_numerator_stage_absent():
    apps = [_mk("a1", "applied"), _mk("a2", "applied")]
    assert funnel(apps).rates.get("applied_to_screen", 0.0) == 0.0

def test_funnel_rates_missing_when_denominator_zero():
    rate = funnel([_mk("s1", "screen")]).rates.get("applied_to_screen")
    assert rate is None or rate == 0.0

def test_funnel_bottleneck_is_string_or_none():
    b = funnel(_sample_apps()).bottleneck
    assert b is None or isinstance(b, str)

def test_funnel_bottleneck_applied_to_screen_worst_dropout():
    assert funnel(_sample_apps()).bottleneck == "applied_to_screen"

def test_funnel_bottleneck_none_when_no_transitions():
    assert funnel([_mk("a1", "saved")]).bottleneck is None

def test_funnel_vs_benchmark_has_applied_to_screen():
    assert "applied_to_screen" in funnel(_sample_apps()).vs_benchmark

def test_funnel_vs_benchmark_labels_are_valid():
    valid = {"below", "at", "above"}
    assert all(v in valid for v in funnel(_sample_apps()).vs_benchmark.values())

def test_funnel_vs_benchmark_above_applied_to_screen():
    assert funnel(_sample_apps()).vs_benchmark.get("applied_to_screen") == "above"

def test_funnel_notes_is_list():
    assert isinstance(funnel(_sample_apps()).notes, list)

def test_funnel_returns_funnel_stats():
    assert isinstance(funnel(_sample_apps()), FunnelStats)
