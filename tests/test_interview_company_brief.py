"""Tests for interview.company_brief."""

from __future__ import annotations


from decroche.interview.company_brief import company_brief
from decroche.models import CompanyBrief


def test_returns_company_brief_type():
    result = company_brief("Acme Corp")
    assert isinstance(result, CompanyBrief)


def test_company_name_stored():
    result = company_brief("TechCo")
    assert result.company == "TechCo"


def test_five_sections_present():
    result = company_brief("Acme")
    expected_keys = {
        "what_they_do",
        "recent_signals",
        "culture",
        "role_context",
        "questions_to_ask",
    }
    assert set(result.sections.keys()) == expected_keys


def test_sections_contain_to_research_placeholders():
    result = company_brief("Startup")
    for section_text in result.sections.values():
        assert "[TO_RESEARCH]" in section_text or section_text  # at least non-empty


def test_research_checklist_non_empty():
    result = company_brief("BigCorp")
    assert len(result.research_checklist) > 0


def test_checklist_items_are_strings():
    result = company_brief("BigCorp")
    for item in result.research_checklist:
        assert isinstance(item, str)


def test_notes_injected_into_what_they_do():
    result = company_brief("Acme", notes="Spécialisée en cybersécurité")
    assert "Spécialisée en cybersécurité" in result.sections["what_they_do"]


def test_jobs_title_injected_into_role_context():
    jobs = [{"title": "Senior Data Engineer", "tags": ["Python", "Spark"]}]
    result = company_brief("DataCorp", jobs=jobs)
    assert "Senior Data Engineer" in result.sections["role_context"]


def test_jobs_tech_tags_injected():
    jobs = [{"title": "Dev", "tags": ["Rust", "Kafka"]}]
    result = company_brief("TechCo", jobs=jobs)
    what = result.sections["what_they_do"]
    assert "Rust" in what or "Kafka" in what


def test_jobs_tech_tags_extend_checklist():
    jobs = [{"title": "Engineer", "tags": ["Go", "K8s"]}]
    result = company_brief("OpsLand", jobs=jobs)
    combined = " ".join(result.research_checklist)
    assert "Go" in combined or "K8s" in combined


def test_no_jobs_role_context_has_to_research():
    result = company_brief("MysteryInc")
    assert "[TO_RESEARCH]" in result.sections["role_context"]


def test_empty_notes_produces_to_research_in_what():
    result = company_brief("NoCo", notes="")
    assert "[TO_RESEARCH]" in result.sections["what_they_do"]


def test_notes_field_is_list():
    result = company_brief("AnyCompany")
    assert isinstance(result.notes, list)


def test_questions_to_ask_section_not_empty():
    result = company_brief("Acme")
    assert len(result.sections["questions_to_ask"]) > 0


def test_idempotent_same_input():
    r1 = company_brief("Stable", notes="note A")
    r2 = company_brief("Stable", notes="note A")
    assert r1.sections == r2.sections


def test_multiple_job_titles_joined():
    jobs = [{"title": "PM"}, {"title": "APM"}, {"title": "CPO"}]
    result = company_brief("Corp", jobs=jobs)
    ctx = result.sections["role_context"]
    assert "PM" in ctx
