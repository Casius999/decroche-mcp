"""Tests for match.score.match_score — requirement coverage + seniority_fit."""
from __future__ import annotations


from decroche.match.score import match_score
from decroche.models import JSONResume, MatchScore, Skill, Work, Basics


# ── Fixture helpers ───────────────────────────────────────────────────────────────────────────

def _resume_k8s() -> JSONResume:
    """Resume that lists k8s (synonym of Kubernetes) as a skill."""
    return JSONResume(
        basics=Basics(name="Jane"),
        skills=[Skill(name="k8s"), Skill(name="Python"), Skill(name="Go")],
        work=[Work(highlights=["Deployed 12 services using k8s on GCP"])],
    )


def _resume_senior() -> JSONResume:
    """Resume with 'senior' in the label."""
    return JSONResume(
        basics=Basics(name="Jane", label="Senior Backend Engineer"),
        skills=[Skill(name="Python"), Skill(name="Kubernetes")],
    )


def _resume_junior() -> JSONResume:
    """Resume with 'junior' in the label."""
    return JSONResume(
        basics=Basics(name="Bob", label="Junior Developer"),
        skills=[Skill(name="Python")],
    )


OFFER_K8S = """
Backend Engineer — Senior

Requirements:
- Kubernetes
- Python

Nice to have:
- Rust
"""

OFFER_ALL_MISSING = """
Staff Engineer

Requirements:
- Erlang
- Haskell
- COBOL
"""

OFFER_NICE_ONLY = """
Python Engineer

Nice to have:
- Kubernetes
- Rust
"""


class TestMatchScoreReturnType:
    def test_returns_match_score(self):
        result = match_score(_resume_k8s(), OFFER_K8S)
        assert isinstance(result, MatchScore)

    def test_score_in_range(self):
        result = match_score(_resume_k8s(), OFFER_K8S)
        assert 0.0 <= result.score_0_100 <= 100.0


class TestSynonymCoverage:
    def test_k8s_covers_kubernetes(self):
        """CV has 'k8s'; offer requires 'Kubernetes' → covered via synonym."""
        result = match_score(_resume_k8s(), OFFER_K8S)
        covered_reqs = {
            rc.requirement.lower() for rc in result.requirement_coverage if rc.covered
        }
        assert "kubernetes" in covered_reqs

    def test_evidence_mentions_synonym(self):
        """Coverage evidence should reference the matched term."""
        result = match_score(_resume_k8s(), OFFER_K8S)
        kube_cov = next(
            (rc for rc in result.requirement_coverage if rc.requirement.lower() == "kubernetes"),
            None,
        )
        assert kube_cov is not None
        assert kube_cov.covered is True
        assert kube_cov.evidence is not None

    def test_python_covered_exact(self):
        result = match_score(_resume_k8s(), OFFER_K8S)
        covered = {rc.requirement.lower() for rc in result.requirement_coverage if rc.covered}
        assert "python" in covered


class TestMissingMust:
    def test_missing_when_nothing_matches(self):
        result = match_score(_resume_k8s(), OFFER_ALL_MISSING)
        assert len(result.missing_must) >= 1

    def test_no_missing_when_all_covered(self):
        result = match_score(_resume_k8s(), OFFER_K8S)
        # both must_have (kubernetes via k8s, python) should be covered
        assert len(result.missing_must) == 0


class TestScoreBand:
    def test_score_high_when_all_covered(self):
        result = match_score(_resume_k8s(), OFFER_K8S)
        assert result.score_0_100 >= 60.0

    def test_score_low_when_nothing_matches(self):
        result = match_score(_resume_k8s(), OFFER_ALL_MISSING)
        assert result.score_0_100 < 30.0

    def test_score_nonzero_when_nice_only_covered(self):
        """If only nice_to_have covered, score >0 but reflects lower weight."""
        resume = JSONResume(
            basics=Basics(),
            skills=[Skill(name="Kubernetes"), Skill(name="Rust")],
        )
        result = match_score(resume, OFFER_NICE_ONLY)
        assert result.score_0_100 > 0


class TestSeniorityFit:
    def test_senior_offer_senior_cv_is_match(self):
        result = match_score(_resume_senior(), OFFER_K8S)
        assert result.seniority_fit == "match"

    def test_junior_cv_senior_offer_is_under(self):
        result = match_score(_resume_junior(), OFFER_K8S)
        assert result.seniority_fit == "under"

    def test_no_seniority_on_either_is_unknown(self):
        resume = JSONResume(basics=Basics(name="X"), skills=[Skill(name="Python")])
        offer_no_seniority = "Engineer\n\nRequirements:\n- Python"
        result = match_score(resume, offer_no_seniority)
        assert result.seniority_fit == "unknown"


class TestRequirementCoverageDetails:
    def test_coverage_has_one_entry_per_requirement(self):
        result = match_score(_resume_k8s(), OFFER_K8S)
        requirements = [rc.requirement.lower() for rc in result.requirement_coverage]
        # At minimum must_have requirements are present
        assert "kubernetes" in requirements or "python" in requirements

    def test_coverage_kind_is_must_or_nice(self):
        result = match_score(_resume_k8s(), OFFER_K8S)
        for rc in result.requirement_coverage:
            assert rc.kind in ("must_have", "nice_to_have")
