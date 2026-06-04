"""Tests for cv.verify_claims — pure deterministic claim verification.

TDD order:
  RED  (this file first, before implementation)
  GREEN (implement verify_claims.py to pass)
"""
from __future__ import annotations

from decroche.cv.verify_claims import verify_claims
from decroche.models import Claim, JSONResume, Work


# ── helpers ─────────────────────────────────────────────────────────────────────────


def _make_resume_with_highlights(*highlights: str) -> JSONResume:
    return JSONResume(work=[Work(name="Acme", highlights=list(highlights))])


# ── quantified achievements need evidence ─────────────────────────────────────────────


class TestQuantifiedAchievements:
    def test_pct_needs_evidence(self):
        jr = _make_resume_with_highlights("Reduced latency 38% by adding caching")
        claims = verify_claims(jr)
        flagged = [c for c in claims if c.needs_evidence]
        assert len(flagged) >= 1

    def test_pct_location_correct(self):
        jr = _make_resume_with_highlights("Reduced latency 38% by adding caching")
        claims = verify_claims(jr)
        flagged = [c for c in claims if c.needs_evidence]
        locs = [c.location for c in flagged]
        assert any("work[0]" in loc for loc in locs)

    def test_euro_needs_evidence(self):
        jr = _make_resume_with_highlights("Generated €2M revenue")
        claims = verify_claims(jr)
        flagged = [c for c in claims if c.needs_evidence]
        assert len(flagged) >= 1

    def test_dollar_needs_evidence(self):
        jr = _make_resume_with_highlights("Saved $500k in operational costs")
        claims = verify_claims(jr)
        flagged = [c for c in claims if c.needs_evidence]
        assert len(flagged) >= 1

    def test_multiplier_needs_evidence(self):
        jr = _make_resume_with_highlights("Doubled throughput 2x")
        claims = verify_claims(jr)
        flagged = [c for c in claims if c.needs_evidence]
        assert len(flagged) >= 1

    def test_suggested_artifact_metric_type(self):
        jr = _make_resume_with_highlights("Reduced latency 38% by adding caching")
        claims = verify_claims(jr)
        flagged = [c for c in claims if c.needs_evidence]
        assert len(flagged) >= 1
        artifact = flagged[0].suggested_artifact.lower()
        assert any(kw in artifact for kw in ("dashboard", "report", "reference", "link"))


class TestLeadershipClaims:
    def test_led_team_needs_evidence(self):
        jr = _make_resume_with_highlights("Led a team of 8 engineers to deliver the platform")
        claims = verify_claims(jr)
        flagged = [c for c in claims if c.needs_evidence]
        assert len(flagged) >= 1

    def test_managed_team_needs_evidence(self):
        jr = _make_resume_with_highlights("Managed team of 5 developers")
        claims = verify_claims(jr)
        flagged = [c for c in claims if c.needs_evidence]
        assert len(flagged) >= 1

    def test_led_with_count_suggests_reference(self):
        jr = _make_resume_with_highlights("Led a team of 8 engineers to deliver the platform")
        claims = verify_claims(jr)
        flagged = [c for c in claims if c.needs_evidence]
        assert len(flagged) >= 1
        artifact = flagged[0].suggested_artifact.lower()
        assert any(kw in artifact for kw in ("reference", "contact", "linkedin", "link"))


class TestDutyBullets:
    def test_plain_duty_not_flagged(self):
        jr = _make_resume_with_highlights("Responsible for database maintenance")
        claims = verify_claims(jr)
        flagged = [c for c in claims if c.needs_evidence]
        assert len(flagged) == 0

    def test_plain_worked_on_not_flagged(self):
        jr = _make_resume_with_highlights("Worked on backend infrastructure")
        claims = verify_claims(jr)
        flagged = [c for c in claims if c.needs_evidence]
        assert len(flagged) == 0

    def test_helped_not_flagged(self):
        jr = _make_resume_with_highlights("Helped the team with deployments")
        claims = verify_claims(jr)
        flagged = [c for c in claims if c.needs_evidence]
        assert len(flagged) == 0


class TestProjectOutcomes:
    def test_named_project_needs_evidence(self):
        jr = _make_resume_with_highlights("Launched PaymentGateway v2 serving 1M users")
        claims = verify_claims(jr)
        flagged = [c for c in claims if c.needs_evidence]
        assert len(flagged) >= 1

    def test_project_suggests_repo_or_portfolio(self):
        jr = _make_resume_with_highlights("Built and launched DataPipeline processing 500k events/day")
        claims = verify_claims(jr)
        flagged = [c for c in claims if c.needs_evidence]
        assert len(flagged) >= 1
        artifact = flagged[0].suggested_artifact.lower()
        assert any(kw in artifact for kw in ("repo", "portfolio", "url", "link", "project"))


class TestLocationAccuracy:
    def test_location_first_work_first_highlight(self):
        jr = _make_resume_with_highlights("Reduced costs 25%", "Responsible for teams")
        claims = verify_claims(jr)
        flagged = [c for c in claims if c.needs_evidence]
        assert any("work[0].highlights[0]" in c.location for c in flagged)

    def test_location_second_highlight(self):
        jr = _make_resume_with_highlights("Responsible for teams", "Saved $100k annually")
        claims = verify_claims(jr)
        flagged = [c for c in claims if c.needs_evidence]
        assert any("highlights[1]" in c.location for c in flagged)

    def test_multiple_work_entries_correct_index(self):
        jr = JSONResume(
            work=[
                Work(name="Co1", highlights=["Responsible for database"]),
                Work(name="Co2", highlights=["Generated €1M revenue"]),
            ]
        )
        claims = verify_claims(jr)
        flagged = [c for c in claims if c.needs_evidence]
        assert any("work[1]" in c.location for c in flagged)


class TestReturnType:
    def test_returns_list(self):
        jr = _make_resume_with_highlights("Reduced latency 38%")
        result = verify_claims(jr)
        assert isinstance(result, list)

    def test_all_entries_are_claims(self):
        jr = _make_resume_with_highlights("Reduced latency 38%", "Responsible for db")
        result = verify_claims(jr)
        assert all(isinstance(c, Claim) for c in result)

    def test_empty_resume_returns_empty_list(self):
        jr = JSONResume(work=[Work(name="Co", highlights=[])])
        result = verify_claims(jr)
        assert result == []

    def test_text_populated(self):
        jr = _make_resume_with_highlights("Reduced latency 38% by caching")
        claims = verify_claims(jr)
        flagged = [c for c in claims if c.needs_evidence]
        assert len(flagged) >= 1
        assert flagged[0].text != ""


class TestCertificationAndAward:
    def test_certification_mention_needs_evidence(self):
        jr = _make_resume_with_highlights("Obtained AWS certification after 6-month training")
        claims = verify_claims(jr)
        flagged = [c for c in claims if c.needs_evidence]
        assert len(flagged) >= 1

    def test_certification_suggests_credential(self):
        jr = _make_resume_with_highlights("Received certification in cloud architecture")
        claims = verify_claims(jr)
        flagged = [c for c in claims if c.needs_evidence]
        assert len(flagged) >= 1
        artifact = flagged[0].suggested_artifact.lower()
        assert any(kw in artifact for kw in ("credential", "credly", "url", "certification"))

    def test_award_needs_evidence(self):
        jr = _make_resume_with_highlights("Won best engineer award at company hackathon")
        claims = verify_claims(jr)
        flagged = [c for c in claims if c.needs_evidence]
        assert len(flagged) >= 1

    def test_award_suggests_announcement(self):
        jr = _make_resume_with_highlights("Received top performer prize from VP Engineering")
        claims = verify_claims(jr)
        flagged = [c for c in claims if c.needs_evidence]
        assert len(flagged) >= 1
        artifact = flagged[0].suggested_artifact.lower()
        assert any(kw in artifact for kw in ("announcement", "certificate", "mention", "press", "scan"))

    def test_named_project_camelcase_artifact_is_repo(self):
        jr = _make_resume_with_highlights("Launched DataMigrationTool used by entire team")
        claims = verify_claims(jr)
        flagged = [c for c in claims if c.needs_evidence]
        assert len(flagged) >= 1
        artifact = flagged[0].suggested_artifact.lower()
        assert any(kw in artifact for kw in ("repo", "portfolio", "url", "link", "product"))
