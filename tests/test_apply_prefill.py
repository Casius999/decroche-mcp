"""Tests for apply.prefill — pure deterministic ATS form pre-fill plan."""

from __future__ import annotations

import pytest

from decroche.apply.prefill import prefill
from decroche.models import Basics, JSONResume, JobPosting, Location, PrefillPlan, Profile


def _resume(
    name: str = "Jane Doe",
    email: str = "jane@example.com",
    phone: str = "+33 6 12 34 56 78",
    label: str = "Software Engineer",
    location: str | None = "Paris, France",
    linkedin: str | None = "https://linkedin.com/in/janedoe",
    company: str | None = "Acme Corp",
) -> JSONResume:
    profiles = []
    if linkedin:
        profiles.append(Profile(network="LinkedIn", url=linkedin))
    loc = Location(city=location) if location else None
    basics = Basics(name=name, email=email, phone=phone, label=label, location=loc, profiles=profiles)
    from decroche.models import Work
    work = [Work(name=company, position=label)] if company else []
    return JSONResume(basics=basics, work=work)


def _job(apply_url: str = "https://acme.com/apply/1") -> JobPosting:
    return JobPosting(source="greenhouse", source_id="1", title="Senior Python Dev", company="Acme", url="https://acme.com/jobs/1", apply_url=apply_url, description="A great job")


def test_prefill_maps_full_name():
    plan = prefill(_job(), _resume())
    assert "full_name" in plan.fields
    assert plan.fields["full_name"] == "Jane Doe"

def test_prefill_maps_email():
    plan = prefill(_job(), _resume())
    assert plan.fields["email"] == "jane@example.com"

def test_prefill_maps_phone():
    plan = prefill(_job(), _resume())
    assert plan.fields["phone"] == "+33 6 12 34 56 78"

def test_prefill_maps_linkedin_url():
    plan = prefill(_job(), _resume())
    assert "linkedin" in plan.fields
    assert "linkedin.com" in plan.fields["linkedin"]

def test_prefill_maps_current_company():
    plan = prefill(_job(), _resume(company="TechCorp"))
    assert plan.fields["current_company"] == "TechCorp"

def test_prefill_maps_current_title():
    plan = prefill(_job(), _resume(label="Lead Engineer"))
    assert plan.fields["current_title"] == "Lead Engineer"

def test_prefill_maps_location():
    plan = prefill(_job(), _resume(location="Lyon, France"))
    assert "location" in plan.fields

def test_prefill_apply_url_matches_job():
    plan = prefill(_job(apply_url="https://acme.com/apply/99"), _resume())
    assert plan.apply_url == "https://acme.com/apply/99"

def test_prefill_returns_prefill_plan():
    assert isinstance(prefill(_job(), _resume()), PrefillPlan)

def test_prefill_cover_letter_included_when_provided():
    plan = prefill(_job(), _resume(), cover_letter="Dear Hiring Manager,\nI am excited...")
    assert "cover_letter" in plan.fields

def test_prefill_cover_letter_absent_when_not_provided():
    assert "cover_letter" not in prefill(_job(), _resume()).fields

def test_prefill_no_linkedin_goes_to_unmapped():
    assert "linkedin" in prefill(_job(), _resume(linkedin=None)).unmapped

def test_prefill_no_phone_goes_to_unmapped():
    resume = JSONResume(basics=Basics(name="No Phone", email="np@example.com"))
    assert "phone" in prefill(_job(), resume).unmapped

def test_prefill_unmapped_is_list():
    assert isinstance(prefill(_job(), _resume()).unmapped, list)

@pytest.mark.parametrize("sensitive_field", [
    "password", "mot_de_passe", "card_number", "carte_bancaire", "cvv", "cvc",
    "ssn", "social_security_number", "iban", "dob", "date_of_birth", "date_naissance",
])
def test_prefill_never_fills_sensitive_field(sensitive_field: str):
    plan = prefill(_job(), _resume())
    assert sensitive_field not in plan.fields

def test_prefill_excluded_sensitive_lists_known_exclusions():
    plan = prefill(_job(), _resume())
    assert isinstance(plan.excluded_sensitive, list)
    assert len(plan.excluded_sensitive) > 0

def test_prefill_excluded_sensitive_has_password():
    excluded = [f.lower() for f in prefill(_job(), _resume()).excluded_sensitive]
    assert any("password" in f or "mot_de_passe" in f for f in excluded)

def test_prefill_excluded_sensitive_has_card():
    excluded = [f.lower() for f in prefill(_job(), _resume()).excluded_sensitive]
    assert any("card" in f or "carte" in f for f in excluded)

def test_prefill_excluded_sensitive_has_iban():
    excluded = [f.lower() for f in prefill(_job(), _resume()).excluded_sensitive]
    assert any("iban" in f for f in excluded)

def test_prefill_warnings_is_list():
    assert isinstance(prefill(_job(), _resume()).warnings, list)

def test_prefill_fields_values_are_strings():
    assert all(isinstance(v, str) for v in prefill(_job(), _resume()).fields.values())
