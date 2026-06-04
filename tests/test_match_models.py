"""Tests for Tranche-3 model additions: RequirementCoverage, Offer, MatchScore, KeywordGap."""
from __future__ import annotations


from decroche.models import KeywordGap, MatchScore, Offer, RequirementCoverage


class TestRequirementCoverage:
    def test_minimal_construction(self):
        rc = RequirementCoverage(requirement="python", kind="must_have", covered=True)
        assert rc.requirement == "python"
        assert rc.covered is True
        assert rc.evidence is None

    def test_with_evidence(self):
        rc = RequirementCoverage(
            requirement="kubernetes", kind="nice_to_have", covered=True, evidence="via k8s"
        )
        assert rc.evidence == "via k8s"


class TestOffer:
    def test_defaults(self):
        o = Offer(raw="some offer text")
        assert o.must_have == []
        assert o.nice_to_have == []
        assert o.title is None
        assert o.seniority is None
        assert o.hard_requirements == []

    def test_full(self):
        o = Offer(
            title="Backend Engineer",
            must_have=["python", "kubernetes"],
            nice_to_have=["rust"],
            seniority="senior",
            hard_requirements=["5+ years"],
            raw="raw text",
        )
        assert o.title == "Backend Engineer"
        assert "kubernetes" in o.must_have
        assert o.seniority == "senior"


class TestMatchScore:
    def test_construction(self):
        ms = MatchScore(
            score_0_100=75.0,
            requirement_coverage=[
                RequirementCoverage(requirement="python", kind="must_have", covered=True)
            ],
            seniority_fit="match",
            missing_must=[],
        )
        assert ms.score_0_100 == 75.0
        assert ms.seniority_fit == "match"

    def test_score_with_missing(self):
        ms = MatchScore(
            score_0_100=50.0,
            requirement_coverage=[],
            seniority_fit="under",
            missing_must=["rust", "go"],
        )
        assert len(ms.missing_must) == 2


class TestKeywordGap:
    def test_addable(self):
        kg = KeywordGap(term="docker", salience=0.8, status="addable_honestly")
        assert kg.status == "addable_honestly"
        assert kg.evidence is None

    def test_missing(self):
        kg = KeywordGap(term="rust", salience=0.5, status="genuinely_missing")
        assert kg.status == "genuinely_missing"

    def test_with_evidence(self):
        kg = KeywordGap(
            term="kubernetes", salience=0.9, status="addable_honestly", evidence="mentions k8s"
        )
        assert kg.evidence == "mentions k8s"
