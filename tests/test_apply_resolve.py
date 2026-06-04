"""Tests for apply.resolve — pure deterministic source resolution (no network)."""

from __future__ import annotations

import pytest

from decroche.apply.resolve import resolve_source
from decroche.models import JobPosting


def _job(url: str = "https://acme.com/jobs/1", apply_url: str | None = None) -> JobPosting:
    return JobPosting(source="greenhouse", source_id="1", title="Senior Dev", company="Acme", url=url, apply_url=apply_url, description="A job")


def test_resolve_prefers_apply_url():
    job = _job(url="https://linkedin.com/jobs/view/123", apply_url="https://acme.com/apply/1")
    assert resolve_source(job)["apply_url"] == "https://acme.com/apply/1"

def test_resolve_apply_url_not_manual():
    job = _job(url="https://linkedin.com/jobs/view/123", apply_url="https://acme.com/apply/1")
    assert resolve_source(job)["manual"] is False

def test_resolve_apply_url_channel():
    job = _job(url="https://indeed.com/viewjob?jk=abc", apply_url="https://employer.com/apply/7")
    assert resolve_source(job)["channel"] in ("direct", "ats")

def test_resolve_fallback_to_url_when_no_apply_url():
    job = _job(url="https://company.com/jobs/dev", apply_url=None)
    assert resolve_source(job)["apply_url"] == "https://company.com/jobs/dev"

def test_resolve_fallback_non_aggregator_not_manual():
    job = _job(url="https://company.com/jobs/dev", apply_url=None)
    assert resolve_source(job)["manual"] is False

@pytest.mark.parametrize("url", [
    "https://www.linkedin.com/jobs/view/3945890123",
    "https://linkedin.com/jobs/view/1234",
    "https://fr.linkedin.com/jobs/view/789",
    "https://www.indeed.com/viewjob?jk=abc123",
    "https://indeed.com/viewjob?jk=xyz",
    "https://fr.indeed.com/viewjob?jk=xyz",
    "https://www.glassdoor.com/job-listing/python-engineer-acme-JV_123.htm",
    "https://glassdoor.com/job-listing/python-engineer-acme-JV_123.htm",
])
def test_resolve_aggregator_url_sets_manual(url: str):
    assert resolve_source(_job(url=url, apply_url=None))["manual"] is True

@pytest.mark.parametrize("url", [
    "https://www.linkedin.com/jobs/view/123",
    "https://indeed.com/viewjob?jk=abc",
    "https://glassdoor.com/job-listing/xyz",
])
def test_resolve_aggregator_note_mentions_employer_ats(url: str):
    note = resolve_source(_job(url=url, apply_url=None))["note"].lower()
    assert "employer" in note or "ats" in note or "source" in note

@pytest.mark.parametrize("url", [
    "https://boards.greenhouse.io/acme/jobs/1234567",
    "https://jobs.lever.co/acme/job-id",
    "https://job.ashbyhq.com/acme/12345",
    "https://acme.recruitee.com/o/senior-dev",
    "https://acme.com/careers/senior-dev",
])
def test_resolve_non_aggregator_not_manual(url: str):
    assert resolve_source(_job(url=url, apply_url=None))["manual"] is False

def test_resolve_returns_dict_with_required_keys():
    result = resolve_source(_job())
    for k in ("apply_url", "channel", "manual", "note"):
        assert k in result

def test_resolve_note_is_string():
    assert isinstance(resolve_source(_job())["note"], str)

def test_resolve_channel_is_string():
    assert isinstance(resolve_source(_job())["channel"], str)

def test_resolve_manual_is_bool():
    assert isinstance(resolve_source(_job())["manual"], bool)
