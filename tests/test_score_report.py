"""Tests for ats.score_report — ScoreReport generation.

TDD: written before implementation.
"""
from __future__ import annotations


from decroche.models import AtsParseResult, Breakage, ScoreReport


def _make_result(parsability: float, breakages=None, fields_lost=None) -> AtsParseResult:
    return AtsParseResult(
        ats_id="workday",
        fmt="pdf",
        parsability_score=parsability,
        fields_extracted={"contact": True, "experience": True, "education": True, "skills": True},
        fields_lost=fields_lost or [],
        breakages=breakages or [],
    )


def test_score_report_returns_model() -> None:
    """score_report returns a ScoreReport."""
    from decroche.ats.score_report import score_report

    before = _make_result(85.0)
    report = score_report(before)
    assert isinstance(report, ScoreReport)


def test_parsability_preserved() -> None:
    """parsability field equals before.parsability_score."""
    from decroche.ats.score_report import score_report

    before = _make_result(75.5)
    report = score_report(before)
    assert report.parsability == 75.5


def test_screener_readiness_high() -> None:
    """High parsability + no red flags → high screener_readiness."""
    from decroche.ats.score_report import score_report

    before = _make_result(90.0)
    report = score_report(before, redflag_count=0)
    assert report.screener_readiness == "high"


def test_screener_readiness_low() -> None:
    """Low parsability → low screener_readiness."""
    from decroche.ats.score_report import score_report

    before = _make_result(35.0)
    report = score_report(before, redflag_count=5)
    assert report.screener_readiness == "low"


def test_screener_readiness_medium() -> None:
    """Medium parsability → medium screener_readiness."""
    from decroche.ats.score_report import score_report

    before = _make_result(65.0)
    report = score_report(before, redflag_count=2)
    assert report.screener_readiness == "medium"


def test_no_after_no_delta() -> None:
    """Without after, delta is None."""
    from decroche.ats.score_report import score_report

    before = _make_result(70.0)
    report = score_report(before)
    assert report.delta is None


def test_delta_computed_with_after() -> None:
    """With after, delta contains parsability_before, parsability_after, breakage_delta."""
    from decroche.ats.score_report import score_report

    before = _make_result(
        60.0,
        breakages=[Breakage(type="two_column", location="body", severity="HIGH", fix="Use single column")],
    )
    after = _make_result(90.0, breakages=[])
    report = score_report(before, after=after)
    assert report.delta is not None
    assert report.delta["parsability_before"] == 60.0
    assert report.delta["parsability_after"] == 90.0
    assert report.delta["breakage_delta"] == -1  # 0 - 1 = -1 (improvement)


def test_match_preserved_when_given() -> None:
    """match field is set when provided."""
    from decroche.ats.score_report import score_report

    before = _make_result(80.0)
    report = score_report(before, match=72.5)
    assert report.match == 72.5


def test_match_none_by_default() -> None:
    """match is None when not provided."""
    from decroche.ats.score_report import score_report

    before = _make_result(80.0)
    report = score_report(before)
    assert report.match is None


def test_redflag_count_preserved() -> None:
    """redflag_count is set in the report."""
    from decroche.ats.score_report import score_report

    before = _make_result(80.0)
    report = score_report(before, redflag_count=3)
    assert report.redflag_count == 3
