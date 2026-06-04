"""Tests for match.success_probability — pure deterministic scorer, no network."""
from __future__ import annotations

from decroche.match.success_probability import success_probability
from decroche.models import JobPosting, SuccessProbability


def _make_job(
    *,
    source_id: str = "test-001",
    title: str = "Software Engineer",
    remote: bool | None = None,
    date_posted: str | None = None,
    tags: list[str] | None = None,
) -> JobPosting:
    return JobPosting(
        source="test",
        source_id=source_id,
        title=title,
        company="Test Corp",
        location="Paris",
        remote=remote,
        url="https://example.com/job/001",
        description="A test job posting.",
        date_posted=date_posted,
        tags=tags or [],
    )


class TestSuccessProbabilityReturnType:
    def test_returns_success_probability_instance(self):
        result = success_probability(_make_job(), 70.0)
        assert isinstance(result, SuccessProbability)

    def test_score_in_range(self):
        result = success_probability(_make_job(), 80.0)
        assert 0.0 <= result.score_0_100 <= 100.0

    def test_factors_has_all_keys(self):
        result = success_probability(_make_job(), 60.0)
        assert set(result.factors.keys()) == {"fit", "recency", "competition", "hiring_signal", "network"}

    def test_factors_all_in_range(self):
        result = success_probability(_make_job(), 50.0)
        for k, v in result.factors.items():
            assert 0.0 <= v <= 1.0

    def test_confidence_valid_values(self):
        result = success_probability(_make_job(), 50.0)
        assert result.confidence in ("low", "med", "high")


class TestSuccessProbabilityFitFactor:
    def test_high_fit_score_increases_overall(self):
        low = success_probability(_make_job(), 10.0)
        high = success_probability(_make_job(), 90.0)
        assert high.score_0_100 > low.score_0_100

    def test_fit_factor_equals_fit_score_over_100(self):
        result = success_probability(_make_job(), 75.0)
        assert abs(result.factors["fit"] - 0.75) < 0.001

    def test_fit_clamped_at_100(self):
        result = success_probability(_make_job(), 110.0)
        assert result.factors["fit"] == 1.0

    def test_fit_clamped_at_0(self):
        result = success_probability(_make_job(), -5.0)
        assert result.factors["fit"] == 0.0


class TestSuccessProbabilityRecency:
    def test_unknown_date_neutral_recency(self):
        result = success_probability(_make_job(date_posted=None), 50.0)
        assert result.factors["recency"] == 0.5
        assert any("recency" in n for n in result.notes)

    def test_fresh_date_high_recency(self):
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        result = success_probability(_make_job(date_posted=today), 50.0)
        assert result.factors["recency"] > 0.8

    def test_old_date_low_recency(self):
        old = success_probability(_make_job(date_posted="2020-01-01T00:00:00Z"), 50.0)
        new = success_probability(_make_job(date_posted="2026-06-03T12:00:00Z"), 50.0)
        assert new.factors["recency"] > old.factors["recency"]


class TestSuccessProbabilityCompetition:
    def test_remote_senior_role_no_penalty(self):
        result = success_probability(_make_job(title="Senior Software Engineer", remote=True), 50.0)
        assert 0.0 <= result.factors["competition"] <= 1.0

    def test_remote_junior_role_more_competition(self):
        r_junior = success_probability(_make_job(title="Junior Developer", remote=True), 50.0)
        r_senior = success_probability(_make_job(title="Senior Lead Engineer", remote=False), 50.0)
        assert r_senior.factors["competition"] > r_junior.factors["competition"]

    def test_unknown_remote_senior_signals_neutral(self):
        result = success_probability(_make_job(title="Engineer", remote=None), 50.0)
        assert 0.0 <= result.factors["competition"] <= 1.0


class TestSuccessProbabilityNetworkAndHiringSignal:
    def test_no_network_uses_zero(self):
        result = success_probability(_make_job(), 50.0, network_proximity=None)
        assert result.factors["network"] == 0.0
        assert any("network" in n for n in result.notes)

    def test_network_proximity_applied(self):
        r_no = success_probability(_make_job(), 50.0, network_proximity=None)
        r_with = success_probability(_make_job(), 50.0, network_proximity=0.8)
        assert r_with.score_0_100 > r_no.score_0_100

    def test_no_applicants_neutral_hiring_signal(self):
        result = success_probability(_make_job(), 50.0, applicants=None)
        assert result.factors["hiring_signal"] == 0.5
        assert any("hiring_signal" in n for n in result.notes)

    def test_few_applicants_higher_hiring_signal(self):
        r_few = success_probability(_make_job(), 50.0, applicants=5)
        r_many = success_probability(_make_job(), 50.0, applicants=500)
        assert r_few.factors["hiring_signal"] > r_many.factors["hiring_signal"]

    def test_all_signals_known_high_confidence(self):
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        result = success_probability(
            _make_job(date_posted=today, remote=True, title="Senior Engineer"),
            80.0, network_proximity=0.6, applicants=20
        )
        assert result.confidence == "high"

    def test_no_optional_signals_low_confidence(self):
        result = success_probability(
            _make_job(date_posted=None, remote=None, title="Engineer"),
            50.0, network_proximity=None, applicants=None
        )
        assert result.confidence in ("low", "med")


class TestSuccessProbabilityDeterminism:
    def test_same_inputs_same_output(self):
        job = _make_job(date_posted="2026-06-01T00:00:00Z", remote=False)
        r1 = success_probability(job, 65.0, network_proximity=0.3, applicants=50)
        r2 = success_probability(job, 65.0, network_proximity=0.3, applicants=50)
        assert r1.score_0_100 == r2.score_0_100
        assert r1.factors == r2.factors
        assert r1.confidence == r2.confidence
