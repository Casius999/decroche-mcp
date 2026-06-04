"""Tests for match.dedupe — deterministic deduplication, pure functions only."""
from __future__ import annotations

from datetime import date

import pytest

from decroche.match.dedupe import (
    _are_duplicates,
    _blocking_key,
    _city_from_location,
    _completeness,
    _normalize_token,
    _parse_date,
    _within_14_days,
    dedupe,
)
from decroche.models import JobPosting


def _job(
    title: str = "Software Engineer",
    company: str | None = "Acme Corp",
    location: str | None = "Paris, France",
    date_posted: str | None = "2026-05-20",
    source: str = "greenhouse",
    source_id: str = "1",
    description: str = "A job.",
    remote: bool | None = None,
    apply_url: str | None = None,
    salary: str | None = None,
    tags: list[str] | None = None,
) -> JobPosting:
    return JobPosting(
        source=source,
        source_id=source_id,
        title=title,
        company=company,
        location=location,
        date_posted=date_posted,
        url=f"https://example.com/jobs/{source_id}",
        description=description,
        remote=remote,
        apply_url=apply_url,
        salary=salary,
        tags=tags or [],
        raw={},
    )


class TestNormalizeToken:
    def test_lowercases(self):
        assert _normalize_token("ACME") == "acme"

    def test_strips_accents(self):
        assert _normalize_token("Société") == "societe"

    def test_removes_noise_tokens(self):
        assert "inc" not in _normalize_token("Acme Inc")
        assert "ltd" not in _normalize_token("Global Ltd")

    def test_collapses_whitespace(self):
        assert _normalize_token("  Hello   World  ") == "hello world"

    def test_empty_string(self):
        assert _normalize_token("") == ""

    def test_none(self):
        assert _normalize_token(None) == ""

    def test_all_noise(self):
        assert _normalize_token("Inc Ltd") == ""

    def test_sarl_removed(self):
        result = _normalize_token("TechCo SARL")
        assert "sarl" not in result
        assert "techco" in result


class TestCityFromLocation:
    def test_first_comma_token(self):
        assert _city_from_location("Paris, France") == "Paris"

    def test_no_comma(self):
        assert _city_from_location("Berlin") == "Berlin"

    def test_none(self):
        assert _city_from_location(None) == ""

    def test_empty(self):
        assert _city_from_location("") == ""

    def test_strips_whitespace(self):
        assert _city_from_location("  Lyon , France") == "Lyon"


class TestBlockingKey:
    def test_same_job_same_key(self):
        job = _job()
        assert _blocking_key(job) == _blocking_key(job)

    def test_different_source_same_canonical_same_key(self):
        job_a = _job(source="greenhouse", source_id="g1")
        job_b = _job(source="lever", source_id="l1")
        assert _blocking_key(job_a) == _blocking_key(job_b)

    def test_different_company_different_key(self):
        assert _blocking_key(_job(company="Alpha")) != _blocking_key(_job(company="Beta"))

    def test_noise_token_ignored_in_company(self):
        assert _blocking_key(_job(company="Acme Inc")) == _blocking_key(_job(company="Acme"))

    def test_accent_normalised(self):
        assert _blocking_key(_job(company="Société")) == _blocking_key(_job(company="Societe"))

    def test_none_company_handled(self):
        key = _blocking_key(_job(company=None))
        assert isinstance(key, str)
        assert len(key) == 64


class TestParseDate:
    def test_iso_date(self):
        assert _parse_date("2026-05-20") == date(2026, 5, 20)

    def test_iso_datetime(self):
        assert _parse_date("2026-05-20T10:00:00Z") == date(2026, 5, 20)

    def test_none_returns_none(self):
        assert _parse_date(None) is None

    def test_unparseable_returns_none(self):
        assert _parse_date("not-a-date") is None

    def test_empty_string(self):
        assert _parse_date("") is None


class TestWithin14Days:
    def test_same_date(self):
        assert _within_14_days("2026-05-20", "2026-05-20") is True

    def test_13_days_apart(self):
        assert _within_14_days("2026-05-01", "2026-05-14") is True

    def test_14_days_apart(self):
        assert _within_14_days("2026-05-01", "2026-05-15") is True

    def test_15_days_apart(self):
        assert _within_14_days("2026-05-01", "2026-05-16") is False

    def test_none_date_a_returns_true(self):
        assert _within_14_days(None, "2026-05-20") is True

    def test_none_date_b_returns_true(self):
        assert _within_14_days("2026-05-20", None) is True

    def test_both_none_returns_true(self):
        assert _within_14_days(None, None) is True


class TestCompleteness:
    def test_more_fields_higher_score(self):
        sparse = _job(salary=None, remote=None, apply_url=None)
        rich = _job(salary="100k", remote=True, apply_url="https://apply.example.com")
        assert _completeness(rich) > _completeness(sparse)

    def test_tags_contribute_to_score(self):
        assert _completeness(_job(tags=["python", "backend"])) > _completeness(_job())


class TestAreDuplicates:
    def test_identical_titles_same_date(self):
        assert _are_duplicates(_job(title="Software Engineer", date_posted="2026-05-20"),
                               _job(title="Software Engineer", date_posted="2026-05-20")) is True

    def test_very_different_titles(self):
        assert _are_duplicates(_job(title="Backend Engineer"), _job(title="Marketing Manager")) is False

    def test_same_title_dates_far_apart(self):
        assert _are_duplicates(_job(title="Backend Engineer", date_posted="2026-01-01"),
                               _job(title="Backend Engineer", date_posted="2026-02-01")) is False

    def test_same_title_missing_date(self):
        assert _are_duplicates(_job(title="Backend Engineer", date_posted=None),
                               _job(title="Backend Engineer", date_posted="2026-05-20")) is True


class TestDedupe:
    def test_empty_list(self):
        assert dedupe([]) == []

    def test_no_duplicates(self):
        jobs = [
            _job(title="Backend Engineer", company="Alpha", location="Paris", source_id="1"),
            _job(title="Data Scientist", company="Beta", location="Lyon", source_id="2"),
        ]
        assert len(dedupe(jobs)) == 2

    def test_identical_jobs_deduped(self):
        job_a = _job(source="greenhouse", source_id="g1", date_posted="2026-05-20")
        job_b = _job(source="lever", source_id="l1", date_posted="2026-05-20")
        assert len(dedupe([job_a, job_b])) == 1

    def test_cross_provider_dedup(self):
        job_gh = _job(source="greenhouse", source_id="g42", title="Senior Software Engineer",
                      company="Acme Corp", location="Paris, France", date_posted="2026-05-20")
        job_lv = _job(source="lever", source_id="l99", title="Senior Software Engineer",
                      company="Acme Corp", location="Paris, France", date_posted="2026-05-22")
        assert len(dedupe([job_gh, job_lv])) == 1

    def test_distinct_companies_not_deduped(self):
        assert len(dedupe([_job(company="Alpha Inc", source_id="a1"),
                           _job(company="Beta Ltd", source_id="b1")])) == 2

    def test_dates_too_far_not_deduped(self):
        assert len(dedupe([_job(date_posted="2026-01-01", source_id="a1"),
                           _job(date_posted="2026-02-15", source_id="b1")])) == 2

    def test_keeps_most_complete(self):
        sparse = _job(source="greenhouse", source_id="g1", salary=None, remote=None)
        rich = _job(source="lever", source_id="l1", salary="€70k–€90k", remote=True,
                    apply_url="https://apply.example.com", date_posted="2026-05-20")
        result = dedupe([sparse, rich])
        assert len(result) == 1
        assert result[0].salary == "€70k–€90k"

    def test_deterministic_same_input_same_output(self):
        jobs = [
            _job(source="greenhouse", source_id="g1", title="Engineer", date_posted="2026-05-20"),
            _job(source="lever", source_id="l1", title="Engineer", date_posted="2026-05-21"),
            _job(source="ashby", source_id="a1", title="Backend Dev", company="Beta",
                 location="Lyon", date_posted="2026-05-18"),
        ]
        assert [j.source_id for j in dedupe(jobs)] == [j.source_id for j in dedupe(jobs)]

    def test_large_batch_no_false_dedup(self):
        jobs = [_job(title=f"Role {i}", company=f"Company {i}", location=f"City {i}, Country",
                     source_id=str(i), date_posted="2026-05-20") for i in range(20)]
        assert len(dedupe(jobs)) == 20

    def test_noise_in_company_name_same_block(self):
        job_a = _job(company="Acme Inc", title="Engineer", source_id="a1", date_posted="2026-05-20")
        job_b = _job(company="Acme", title="Engineer", source_id="b1", date_posted="2026-05-20")
        assert len(dedupe([job_a, job_b])) == 1

    def test_three_way_cluster(self):
        jobs = [
            _job(source="greenhouse", source_id="g1", date_posted="2026-05-18"),
            _job(source="lever", source_id="l1", date_posted="2026-05-19"),
            _job(source="ashby", source_id="a1", date_posted="2026-05-20"),
        ]
        assert len(dedupe(jobs)) == 1

    def test_missing_date_does_not_prevent_dedup(self):
        job_a = _job(source="greenhouse", source_id="g1", date_posted=None)
        job_b = _job(source="lever", source_id="l1", date_posted="2026-05-20")
        assert len(dedupe([job_a, job_b])) == 1

    def test_none_company_handled(self):
        assert isinstance(dedupe([_job(company=None, source_id="a1"),
                                   _job(company=None, source_id="b1")]), list)

    def test_none_location_handled(self):
        assert isinstance(dedupe([_job(location=None, source_id="a1"),
                                   _job(location=None, source_id="b1")]), list)


class TestDedupeViaTool:
    @pytest.mark.asyncio
    async def test_dedupe_tool_registered(self):
        from decroche.match import match_server
        tool_names = [t.name for t in await match_server.list_tools()]
        assert "dedupe" in tool_names

    def test_dedupe_tool_reduces_duplicates(self):
        from decroche.match.dedupe import dedupe as pure_dedupe
        jobs = [_job(source="greenhouse", source_id="g1"), _job(source="lever", source_id="l1")]
        assert len(pure_dedupe(jobs)) == 1

    @pytest.mark.asyncio
    async def test_dedupe_tool_fn_callable(self):
        from decroche.match import match_server
        tool = await match_server.get_tool("dedupe")
        assert tool is not None
        assert callable(tool.fn)
