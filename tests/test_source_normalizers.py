"""Tests for source provider normalizers — pure functions, no network."""
from __future__ import annotations

import json
from pathlib import Path

from decroche.source.providers import (
    arbeitnow, ashby, greenhouse, lever, recruitee,
    remoteok, remotive, smartrecruiters, workable,
)

_FIXTURES = Path(__file__).parent / "fixtures" / "source"


def _load(name: str):
    return json.loads((_FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


class TestGreenhouseNormalizer:
    def test_returns_correct_count(self):
        assert len(greenhouse.normalize(_load("greenhouse"), company="acmecorp")) == 3

    def test_source_field(self):
        assert all(j.source == "greenhouse" for j in greenhouse.normalize(_load("greenhouse"), company="acmecorp"))

    def test_first_job_title(self):
        assert greenhouse.normalize(_load("greenhouse"), company="acmecorp")[0].title == "Senior Software Engineer"

    def test_source_id_is_string(self):
        assert all(isinstance(j.source_id, str) for j in greenhouse.normalize(_load("greenhouse"), company="acmecorp"))

    def test_company_set_from_kwarg(self):
        assert all(j.company == "acmecorp" for j in greenhouse.normalize(_load("greenhouse"), company="acmecorp"))

    def test_url_contains_boards_greenhouse(self):
        assert all("greenhouse.io" in j.url for j in greenhouse.normalize(_load("greenhouse"), company="acmecorp"))

    def test_location_extracted(self):
        assert greenhouse.normalize(_load("greenhouse"), company="acmecorp")[0].location == "Paris, France"

    def test_date_posted_not_none(self):
        assert greenhouse.normalize(_load("greenhouse"), company="acmecorp")[0].date_posted is not None

    def test_description_not_empty(self):
        assert all(j.description for j in greenhouse.normalize(_load("greenhouse"), company="acmecorp"))

    def test_bare_list_input(self):
        raw = _load("greenhouse")
        assert len(greenhouse.normalize(raw["jobs"], company="acmecorp")) == len(greenhouse.normalize(raw, company="acmecorp"))

    def test_empty_input(self):
        assert greenhouse.normalize({"jobs": []}) == []

    def test_skips_non_dict_items(self):
        assert greenhouse.normalize({"jobs": ["bad", None, 42]}) == []


class TestLeverNormalizer:
    def test_returns_correct_count(self):
        assert len(lever.normalize(_load("lever"), company="techstart")) == 2

    def test_first_job_title(self):
        assert lever.normalize(_load("lever"), company="techstart")[0].title == "Staff Backend Engineer"

    def test_source_id_matches_lever_id(self):
        assert lever.normalize(_load("lever"), company="techstart")[0].source_id == "lever-job-abc123"

    def test_apply_url_set(self):
        assert lever.normalize(_load("lever"), company="techstart")[0].apply_url is not None

    def test_remote_detected(self):
        assert lever.normalize(_load("lever"), company="techstart")[1].remote is True

    def test_hybrid_not_remote(self):
        assert lever.normalize(_load("lever"), company="techstart")[0].remote is False

    def test_location_from_categories(self):
        assert lever.normalize(_load("lever"), company="techstart")[0].location == "Paris, France"

    def test_date_posted_parsed(self):
        assert "T" in lever.normalize(_load("lever"), company="techstart")[0].date_posted

    def test_empty_input(self):
        assert lever.normalize([]) == []


class TestAshbyNormalizer:
    def test_returns_correct_count(self):
        assert len(ashby.normalize(_load("ashby"), company="novacorp")) == 2

    def test_first_job_title(self):
        assert ashby.normalize(_load("ashby"), company="novacorp")[0].title == "Engineering Manager"

    def test_remote_false(self):
        assert ashby.normalize(_load("ashby"), company="novacorp")[0].remote is False

    def test_remote_true(self):
        assert ashby.normalize(_load("ashby"), company="novacorp")[1].remote is True

    def test_salary_extracted(self):
        salary = ashby.normalize(_load("ashby"), company="novacorp")[0].salary
        assert salary is not None and "70" in salary

    def test_location_set(self):
        assert ashby.normalize(_load("ashby"), company="novacorp")[0].location == "Bordeaux, France"

    def test_empty_input(self):
        assert ashby.normalize({"jobs": []}) == []


class TestRecruiteeNormalizer:
    def test_returns_correct_count(self):
        assert len(recruitee.normalize(_load("recruitee"), company="recruitee-demo")) == 2

    def test_first_job_title(self):
        assert recruitee.normalize(_load("recruitee"), company="recruitee-demo")[0].title == "Product Manager"

    def test_location_from_city_country(self):
        loc = recruitee.normalize(_load("recruitee"), company="recruitee-demo")[0].location
        assert "Paris" in loc and "France" in loc

    def test_salary_extracted(self):
        salary = recruitee.normalize(_load("recruitee"), company="recruitee-demo")[0].salary
        assert salary is not None and "55000" in salary and "EUR" in salary

    def test_empty_input(self):
        assert recruitee.normalize({"offers": []}) == []


class TestWorkableNormalizer:
    def test_returns_correct_count(self):
        assert len(workable.normalize(_load("workable"), company="megacorp")) == 2

    def test_first_job_title(self):
        assert workable.normalize(_load("workable"), company="megacorp")[0].title == "Backend Developer (Python)"

    def test_source_id_is_shortcode(self):
        assert workable.normalize(_load("workable"), company="megacorp")[0].source_id == "ABC123"

    def test_remote_false(self):
        assert workable.normalize(_load("workable"), company="megacorp")[0].remote is False

    def test_remote_true(self):
        assert workable.normalize(_load("workable"), company="megacorp")[1].remote is True

    def test_empty_input(self):
        assert workable.normalize({"jobs": []}) == []


class TestSmartRecruitersNormalizer:
    def test_returns_correct_count(self):
        assert len(smartrecruiters.normalize(_load("smartrecruiters"))) == 2

    def test_first_job_title(self):
        assert smartrecruiters.normalize(_load("smartrecruiters"))[0].title == "Senior Data Scientist"

    def test_company_name_from_item(self):
        assert smartrecruiters.normalize(_load("smartrecruiters"))[0].company == "SmartCo SA"

    def test_remote_false(self):
        assert smartrecruiters.normalize(_load("smartrecruiters"))[0].remote is False

    def test_remote_true(self):
        assert smartrecruiters.normalize(_load("smartrecruiters"))[1].remote is True

    def test_description_from_job_ad(self):
        assert "recommendation engines" in smartrecruiters.normalize(_load("smartrecruiters"))[0].description

    def test_empty_input(self):
        assert smartrecruiters.normalize({"content": []}) == []


class TestRemoteOKNormalizer:
    def test_skips_metadata_item(self):
        assert len(remoteok.normalize(_load("remoteok"))) == 2

    def test_first_job_title(self):
        assert remoteok.normalize(_load("remoteok"))[0].title == "Remote Python Developer"

    def test_remote_always_true(self):
        assert all(j.remote is True for j in remoteok.normalize(_load("remoteok")))

    def test_tags_populated(self):
        assert "python" in remoteok.normalize(_load("remoteok"))[0].tags

    def test_salary_extracted_from_min_max(self):
        salary = remoteok.normalize(_load("remoteok"))[0].salary
        assert salary is not None and "60000" in salary

    def test_date_posted_from_epoch(self):
        assert "T" in remoteok.normalize(_load("remoteok"))[0].date_posted

    def test_empty_list(self):
        assert remoteok.normalize([]) == []


class TestRemotiveNormalizer:
    def test_returns_correct_count(self):
        assert len(remotive.normalize(_load("remotive"))) == 2

    def test_first_job_title(self):
        assert remotive.normalize(_load("remotive"))[0].title == "Backend Engineer"

    def test_remote_always_true(self):
        assert all(j.remote is True for j in remotive.normalize(_load("remotive")))

    def test_salary_set(self):
        assert remotive.normalize(_load("remotive"))[0].salary == "$80,000 – $110,000"

    def test_empty_input(self):
        assert remotive.normalize({"jobs": []}) == []


class TestArbeitnowNormalizer:
    def test_returns_correct_count(self):
        assert len(arbeitnow.normalize(_load("arbeitnow"))) == 3

    def test_first_job_title(self):
        assert arbeitnow.normalize(_load("arbeitnow"))[0].title == "Backend Developer"

    def test_remote_false(self):
        assert arbeitnow.normalize(_load("arbeitnow"))[0].remote is False

    def test_remote_true(self):
        assert arbeitnow.normalize(_load("arbeitnow"))[1].remote is True

    def test_tags_populated(self):
        assert "golang" in arbeitnow.normalize(_load("arbeitnow"))[0].tags

    def test_date_posted_from_epoch(self):
        assert "T" in arbeitnow.normalize(_load("arbeitnow"))[0].date_posted

    def test_empty_input(self):
        assert arbeitnow.normalize({"data": []}) == []
