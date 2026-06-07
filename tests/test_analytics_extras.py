"""Tests for analytics extras: channel_roi, story_coverage, salary_delta."""

from __future__ import annotations

import asyncio

import pytest

from decroche.analytics import (
    analytics_server,
    channel_roi,
    salary_delta,
    story_coverage,
)
from decroche.models import Application, SalaryRange, Story


_APP_COUNTER = 0


def _make_app(**kwargs) -> Application:
    global _APP_COUNTER
    _APP_COUNTER += 1
    defaults = dict(
        id=f"app-{_APP_COUNTER}",
        job_id="job-1",
        company="Corp",
        role_title="Dev",
        stage="applied",
        source_channel="linkedin",
    )
    defaults.update(kwargs)
    return Application(**defaults)


def _make_story(competencies: list[str]) -> Story:
    return Story(
        title="Test",
        situation="S",
        task="T",
        action="A",
        result="R",
        competencies=competencies,
    )


def _make_benchmark(**kwargs) -> SalaryRange:
    defaults = dict(
        role_family="software",
        seniority="mid",
        region="fr",
        currency="EUR",
        p25=48000,
        p50=55000,
        p75=65000,
        variable_pct=0.08,
        source="APEC 2024",
    )
    defaults.update(kwargs)
    return SalaryRange(**defaults)


# ── channel_roi ───────────────────────────────────────────────────────────────


def test_channel_roi_empty():
    result = channel_roi([])
    assert result == {}


def test_channel_roi_returns_dict():
    apps = [_make_app()]
    result = channel_roi(apps)
    assert isinstance(result, dict)


def test_channel_roi_counts_correctly():
    apps = [
        _make_app(source_channel="linkedin"),
        _make_app(source_channel="linkedin"),
        _make_app(source_channel="referral"),
    ]
    result = channel_roi(apps)
    assert result["linkedin"]["count"] == 2
    assert result["referral"]["count"] == 1


def test_channel_roi_interview_rate():
    apps = [
        _make_app(source_channel="linkedin", stage="applied"),
        _make_app(source_channel="linkedin", stage="interview"),
        _make_app(source_channel="linkedin", stage="offer"),
        _make_app(source_channel="linkedin", stage="applied"),
    ]
    result = channel_roi(apps)
    # 2 out of 4 reached interview or above
    assert result["linkedin"]["interview_rate"] == pytest.approx(0.5)


def test_channel_roi_offer_rate():
    apps = [
        _make_app(source_channel="referral", stage="applied"),
        _make_app(source_channel="referral", stage="offer"),
    ]
    result = channel_roi(apps)
    assert result["referral"]["offer_rate"] == pytest.approx(0.5)


def test_channel_roi_default_channel_counted():
    # source_channel defaults to "cold_apply" in Application
    app = _make_app(source_channel="cold_apply")
    result = channel_roi([app])
    assert "cold_apply" in result or len(result) > 0


def test_channel_roi_accepted_counts_as_offer():
    apps = [
        _make_app(source_channel="direct", stage="accepted"),
        _make_app(source_channel="direct", stage="applied"),
    ]
    result = channel_roi(apps)
    assert result["direct"]["offer_rate"] == pytest.approx(0.5)


# ── story_coverage ────────────────────────────────────────────────────────────


def test_story_coverage_empty_stories():
    result = story_coverage([], ["leadership", "communication"])
    assert result["gaps"] == ["leadership", "communication"]
    assert result["covered"] == []
    assert result["coverage_pct"] == 0.0


def test_story_coverage_all_covered():
    stories = [_make_story(["leadership", "communication"])]
    result = story_coverage(stories, ["leadership", "communication"])
    assert result["gaps"] == []
    assert set(result["covered"]) == {"leadership", "communication"}
    assert result["coverage_pct"] == 1.0


def test_story_coverage_partial():
    stories = [_make_story(["leadership"])]
    result = story_coverage(stories, ["leadership", "negotiation"])
    assert "leadership" in result["covered"]
    assert "negotiation" in result["gaps"]
    assert result["coverage_pct"] == pytest.approx(0.5)


def test_story_coverage_case_insensitive():
    stories = [_make_story(["Leadership"])]
    result = story_coverage(stories, ["leadership"])
    assert result["coverage_pct"] == 1.0


def test_story_coverage_empty_targets():
    result = story_coverage([], [])
    assert result["coverage_pct"] == 0.0


def test_story_coverage_returns_dict_keys():
    result = story_coverage([], ["x"])
    assert "covered" in result
    assert "gaps" in result
    assert "coverage_pct" in result


# ── salary_delta ──────────────────────────────────────────────────────────────


def test_salary_delta_above_p50():
    bench = _make_benchmark(p50=55000, p75=65000)
    result = salary_delta({"base": 62000}, bench)
    assert result["vs_p50"] == "above"
    assert result["delta_p50"] == pytest.approx(7000.0)


def test_salary_delta_below_p50():
    bench = _make_benchmark(p50=55000, p75=65000)
    result = salary_delta({"base": 48000}, bench)
    assert result["vs_p50"] == "below"
    assert result["delta_p50"] < 0


def test_salary_delta_at_p50():
    bench = _make_benchmark(p50=55000, p75=65000)
    result = salary_delta({"base": 55000}, bench)
    assert result["vs_p50"] == "at"


def test_salary_delta_delta_p75():
    bench = _make_benchmark(p50=55000, p75=65000)
    result = salary_delta({"base": 70000}, bench)
    assert result["delta_p75"] == pytest.approx(5000.0)


def test_salary_delta_pct_above():
    bench = _make_benchmark(p50=100000, p75=120000)
    result = salary_delta({"base": 110000}, bench)
    assert result["delta_p50_pct"] == pytest.approx(10.0)


def test_salary_delta_currency_matches_benchmark():
    bench = _make_benchmark(currency="USD")
    result = salary_delta({"base": 150000}, bench)
    assert result["currency"] == "USD"


def test_salary_delta_returns_required_keys():
    bench = _make_benchmark()
    result = salary_delta({"base": 60000}, bench)
    for key in (
        "offer_base",
        "p50",
        "p75",
        "delta_p50",
        "delta_p75",
        "delta_p50_pct",
        "delta_p75_pct",
        "vs_p50",
        "currency",
    ):
        assert key in result


# ── analytics_server tool registration ───────────────────────────────────────


def _alist_tools(server) -> list[str]:
    return [t.name for t in asyncio.run(server.list_tools())]


def test_analytics_server_has_channel_roi_tool():
    names = _alist_tools(analytics_server)
    assert any("channel_roi" in n for n in names)


def test_analytics_server_has_story_coverage_tool():
    names = _alist_tools(analytics_server)
    assert any("story_coverage" in n for n in names)


def test_analytics_server_has_salary_delta_tool():
    names = _alist_tools(analytics_server)
    assert any("salary_delta" in n for n in names)
