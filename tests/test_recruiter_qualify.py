"""Tests for recruiter.qualify — deterministic fit scoring."""

from __future__ import annotations


from decroche.models import Recruiter
from decroche.recruiter.qualify import qualify

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def make_inhouse(company: str = "Acme Corp", title: str = "Technical Recruiter") -> Recruiter:
    return Recruiter(name="Alice Dupont", title=title, company=company, kind="in_house")


def make_agency(title: str = "Talent Acquisition Manager") -> Recruiter:
    return Recruiter(name="Bob Martin", title=title, company="Hays", kind="agency")


def make_unknown() -> Recruiter:
    return Recruiter(name="Carol Petit", title=None, company=None, kind="unknown")


TARGET_TECH_SENIOR = {
    "company": "Acme Corp",
    "sector": "tech",
    "role": "Senior Backend Engineer",
    "seniority": "senior",
}

TARGET_GENERIC = {
    "company": "OtherCorp",
}

TARGET_JUNIOR = {
    "company": "Acme Corp",
    "role": "Junior Developer",
    "seniority": "junior",
}


# ---------------------------------------------------------------------------
# Basic structure
# ---------------------------------------------------------------------------


class TestReturnStructure:
    def test_returns_qualification(self):
        q = qualify(make_inhouse(), TARGET_TECH_SENIOR)
        assert hasattr(q, "fit_score")
        assert hasattr(q, "recommend")
        assert hasattr(q, "reasons")

    def test_reasons_is_list(self):
        q = qualify(make_inhouse(), TARGET_TECH_SENIOR)
        assert isinstance(q.reasons, list)
        assert len(q.reasons) >= 1

    def test_score_within_bounds(self):
        for recruiter in [make_inhouse(), make_agency(), make_unknown()]:
            q = qualify(recruiter, TARGET_TECH_SENIOR)
            assert 0.0 <= q.fit_score <= 1.0


# ---------------------------------------------------------------------------
# Kind scoring hierarchy
# ---------------------------------------------------------------------------


class TestKindScoring:
    def test_inhouse_exact_match_scores_higher_than_agency(self):
        q_inhouse = qualify(make_inhouse("Acme Corp"), {"company": "Acme Corp"})
        q_agency = qualify(make_agency(), {"company": "Acme Corp"})
        assert q_inhouse.fit_score > q_agency.fit_score

    def test_agency_scores_higher_than_unknown(self):
        q_agency = qualify(make_agency(), TARGET_GENERIC)
        q_unknown = qualify(make_unknown(), TARGET_GENERIC)
        assert q_agency.fit_score > q_unknown.fit_score

    def test_inhouse_exact_match_recommends(self):
        q = qualify(make_inhouse("Acme Corp"), {"company": "Acme Corp"})
        assert q.recommend is True

    def test_unknown_does_not_recommend(self):
        q = qualify(make_unknown(), TARGET_GENERIC)
        assert q.recommend is False


# ---------------------------------------------------------------------------
# Title relevance
# ---------------------------------------------------------------------------


class TestTitleScoring:
    def test_tech_recruiter_scores_higher_than_generic_hr(self):
        tech = make_inhouse(title="Technical Recruiter")
        hr = make_inhouse(title="HR Generalist")
        q_tech = qualify(tech, TARGET_TECH_SENIOR)
        q_hr = qualify(hr, TARGET_TECH_SENIOR)
        assert q_tech.fit_score >= q_hr.fit_score

    def test_talent_acquisition_title_detected(self):
        r = make_inhouse(title="Talent Acquisition Specialist")
        q = qualify(r, TARGET_TECH_SENIOR)
        assert any("talent" in reason.lower() or "titre" in reason.lower() for reason in q.reasons)


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_same_input_same_output(self):
        r = make_inhouse("Acme Corp")
        target = {"company": "Acme Corp", "role": "Backend Engineer", "seniority": "senior"}
        q1 = qualify(r, target)
        q2 = qualify(r, target)
        assert q1.fit_score == q2.fit_score
        assert q1.recommend == q2.recommend
        assert q1.reasons == q2.reasons


# ---------------------------------------------------------------------------
# Role keyword overlap
# ---------------------------------------------------------------------------


class TestRoleOverlap:
    def test_role_keywords_generate_reason(self):
        r = make_inhouse(title="Senior Backend Recruiter")
        q = qualify(r, {"role": "Senior Backend Engineer", "company": "Acme"})
        # Should see overlap on "senior" or "backend"
        reasons_text = " ".join(q.reasons).lower()
        assert "overlap" in reasons_text or "backend" in reasons_text or "senior" in reasons_text
