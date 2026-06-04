"""Tests for match.company_intel — pure deterministic synthesiser, no network."""
from __future__ import annotations

from decroche.match.company_intel import company_intel
from decroche.models import CompanyIntel, JobPosting


def _make_job(
    *,
    source_id: str = "j1",
    company: str = "Acme Corp",
    location: str | None = "Paris",
    remote: bool | None = None,
    tags: list[str] | None = None,
) -> JobPosting:
    return JobPosting(
        source="test",
        source_id=source_id,
        title="Engineer",
        company=company,
        location=location,
        remote=remote,
        url="https://example.com/job",
        description="A job.",
        tags=tags or [],
    )


class TestCompanyIntelReturnType:
    def test_returns_company_intel_instance(self):
        result = company_intel("Acme Corp")
        assert isinstance(result, CompanyIntel)

    def test_company_field_set(self):
        result = company_intel("Acme Corp")
        assert result.company == "Acme Corp"

    def test_research_checklist_not_empty(self):
        result = company_intel("Acme Corp")
        assert len(result.research_checklist) > 0

    def test_all_checklist_items_to_research(self):
        result = company_intel("Acme Corp")
        for item in result.research_checklist:
            assert item["status"] == "to_research"


class TestCompanyIntelDerivedFacts:
    def test_open_roles_count_correct(self):
        jobs = [_make_job(source_id="j1"), _make_job(source_id="j2"), _make_job(source_id="j3")]
        result = company_intel("Acme Corp", jobs=jobs)
        assert result.derived["open_roles_count"] == 3

    def test_locations_unique(self):
        jobs = [
            _make_job(source_id="j1", location="Paris"),
            _make_job(source_id="j2", location="Lyon"),
            _make_job(source_id="j3", location="Paris"),
        ]
        result = company_intel("Acme Corp", jobs=jobs)
        assert result.derived["locations"] == ["Paris", "Lyon"]

    def test_remote_ratio_all_remote(self):
        jobs = [_make_job(source_id="j1", remote=True), _make_job(source_id="j2", remote=True)]
        result = company_intel("Acme Corp", jobs=jobs)
        assert result.derived["remote_ratio"] == 1.0

    def test_remote_ratio_none_remote(self):
        jobs = [_make_job(source_id="j1", remote=False), _make_job(source_id="j2", remote=False)]
        result = company_intel("Acme Corp", jobs=jobs)
        assert result.derived["remote_ratio"] == 0.0

    def test_remote_ratio_mixed(self):
        jobs = [
            _make_job(source_id="j1", remote=True),
            _make_job(source_id="j2", remote=False),
            _make_job(source_id="j3", remote=True),
            _make_job(source_id="j4", remote=False),
        ]
        result = company_intel("Acme Corp", jobs=jobs)
        assert abs(result.derived["remote_ratio"] - 0.5) < 0.001

    def test_tech_tags_frequency(self):
        jobs = [
            _make_job(source_id="j1", tags=["Python", "FastAPI"]),
            _make_job(source_id="j2", tags=["Python", "Docker"]),
            _make_job(source_id="j3", tags=["Python"]),
        ]
        result = company_intel("Acme Corp", jobs=jobs)
        assert result.derived["tech_tags"]["Python"] == 3
        assert result.derived["tech_tags"]["FastAPI"] == 1

    def test_no_jobs_empty_derived(self):
        result = company_intel("Acme Corp", jobs=[])
        assert result.derived == {}
        assert len(result.notes) > 0

    def test_no_jobs_note_explains(self):
        result = company_intel("Acme Corp", jobs=None)
        assert any("No job postings" in n for n in result.notes)


class TestCompanyIntelHonesty:
    def test_no_glassdoor_rating_in_derived(self):
        jobs = [_make_job()]
        result = company_intel("Acme Corp", jobs=jobs)
        derived_keys = set(result.derived.keys())
        assert "glassdoor_rating" not in derived_keys
        assert "rating" not in derived_keys

    def test_no_funding_in_derived(self):
        jobs = [_make_job()]
        result = company_intel("Acme Corp", jobs=jobs)
        assert "funding" not in result.derived
        assert "last_funding_round" not in result.derived

    def test_no_layoff_signal_in_derived(self):
        jobs = [_make_job()]
        result = company_intel("Acme Corp", jobs=jobs)
        assert "layoffs" not in result.derived

    def test_glassdoor_in_research_checklist(self):
        result = company_intel("Acme Corp")
        items_text = " ".join(item.get("item", "") for item in result.research_checklist)
        assert "Glassdoor" in items_text or "glassdoor" in items_text.lower()

    def test_layoffs_in_research_checklist(self):
        result = company_intel("Acme Corp")
        items_text = " ".join(item.get("item", "") for item in result.research_checklist)
        assert "ayoff" in items_text

    def test_visa_in_research_checklist(self):
        result = company_intel("Acme Corp")
        items_text = " ".join(item.get("item", "") for item in result.research_checklist)
        assert "isa" in items_text or "sponsorship" in items_text.lower()


class TestCompanyIntelEdgeCases:
    def test_remote_unknown_not_in_derived(self):
        jobs = [_make_job(source_id="j1", remote=None), _make_job(source_id="j2", remote=None)]
        result = company_intel("Acme Corp", jobs=jobs)
        assert "remote_ratio" not in result.derived
        assert any("remote_ratio" in n for n in result.notes)

    def test_no_tags_no_tech_tags_key(self):
        jobs = [_make_job(source_id="j1", tags=[]), _make_job(source_id="j2", tags=[])]
        result = company_intel("Acme Corp", jobs=jobs)
        assert "tech_tags" not in result.derived

    def test_date_range_derived_when_dates_present(self):
        jobs = [
            JobPosting(source="test", source_id="j1", title="Dev", company="Acme Corp",
                       url="https://x.com", description="x", date_posted="2026-05-01"),
            JobPosting(source="test", source_id="j2", title="Dev2", company="Acme Corp",
                       url="https://x.com", description="x", date_posted="2026-06-01"),
        ]
        result = company_intel("Acme Corp", jobs=jobs)
        assert result.derived.get("earliest_posting") == "2026-05-01"
        assert result.derived.get("latest_posting") == "2026-06-01"
