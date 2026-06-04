"""Tests for keyed provider normalizers — pure functions, no network, no env vars needed."""
from __future__ import annotations

import json
from pathlib import Path

from decroche.source.providers import adzuna, france_travail, jooble, jsearch, reed, themuse, usajobs

_FIXTURES = Path(__file__).parent / "fixtures" / "source"


def _load(name: str):
    return json.loads((_FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


class TestFranceTravailNormalizer:
    def test_returns_correct_count(self):
        assert len(france_travail.normalize(_load("france_travail"))) == 2

    def test_first_job_title(self):
        assert france_travail.normalize(_load("france_travail"))[0].title == "Développeur Python Senior"

    def test_company_extracted(self):
        assert france_travail.normalize(_load("france_travail"))[0].company == "TechParis SAS"

    def test_location_extracted(self):
        assert france_travail.normalize(_load("france_travail"))[0].location == "Paris 8e"

    def test_tags_extracted(self):
        assert "Python" in france_travail.normalize(_load("france_travail"))[0].tags

    def test_salary_extracted(self):
        assert france_travail.normalize(_load("france_travail"))[0].salary is not None

    def test_url_non_empty(self):
        assert all(j.url for j in france_travail.normalize(_load("france_travail")))

    def test_accepts_bare_list(self):
        assert len(france_travail.normalize(_load("france_travail")["resultats"])) == 2


class TestAdzunaNormalizer:
    def test_returns_correct_count(self):
        assert len(adzuna.normalize(_load("adzuna"))) == 2

    def test_first_job_title(self):
        assert adzuna.normalize(_load("adzuna"))[0].title == "Python Backend Engineer"

    def test_company_extracted(self):
        assert adzuna.normalize(_load("adzuna"))[0].company == "Acme Corp"

    def test_location_extracted(self):
        assert adzuna.normalize(_load("adzuna"))[0].location == "Paris, Île-de-France"

    def test_salary_extracted(self):
        salary = adzuna.normalize(_load("adzuna"))[0].salary
        assert salary is not None and "50000" in salary

    def test_tags_from_category(self):
        assert "IT Jobs" in adzuna.normalize(_load("adzuna"))[0].tags


class TestJSearchNormalizer:
    def test_returns_correct_count(self):
        assert len(jsearch.normalize(_load("jsearch"))) == 2

    def test_first_job_title(self):
        assert jsearch.normalize(_load("jsearch"))[0].title == "Software Engineer"

    def test_remote_flag_false(self):
        assert jsearch.normalize(_load("jsearch"))[0].remote is False

    def test_remote_flag_true(self):
        assert jsearch.normalize(_load("jsearch"))[1].remote is True

    def test_salary_extracted(self):
        assert jsearch.normalize(_load("jsearch"))[0].salary is not None

    def test_location_combined(self):
        assert "New York" in jsearch.normalize(_load("jsearch"))[0].location


class TestUsajobsNormalizer:
    def test_returns_correct_count(self):
        assert len(usajobs.normalize(_load("usajobs"))) == 2

    def test_first_job_title(self):
        assert usajobs.normalize(_load("usajobs"))[0].title == "Software Engineer"

    def test_company_extracted(self):
        assert "Veterans" in usajobs.normalize(_load("usajobs"))[0].company

    def test_salary_extracted(self):
        assert usajobs.normalize(_load("usajobs"))[0].salary is not None

    def test_tags_from_job_grade(self):
        assert "GS-12" in usajobs.normalize(_load("usajobs"))[0].tags


class TestReedNormalizer:
    def test_returns_correct_count(self):
        assert len(reed.normalize(_load("reed"))) == 2

    def test_first_job_title(self):
        assert reed.normalize(_load("reed"))[0].title == "Python Developer"

    def test_company_extracted(self):
        assert reed.normalize(_load("reed"))[0].company == "London Tech Ltd"

    def test_salary_extracted(self):
        salary = reed.normalize(_load("reed"))[0].salary
        assert salary is not None and "55000" in salary

    def test_remote_detected_from_location(self):
        assert reed.normalize(_load("reed"))[1].remote is True


class TestTheMuseNormalizer:
    def test_returns_correct_count(self):
        assert len(themuse.normalize(_load("themuse"))) == 2

    def test_first_job_title(self):
        assert themuse.normalize(_load("themuse"))[0].title == "Frontend Engineer"

    def test_company_extracted(self):
        assert themuse.normalize(_load("themuse"))[0].company == "The Muse"

    def test_url_set(self):
        assert "themuse.com" in themuse.normalize(_load("themuse"))[0].url

    def test_tags_from_category(self):
        assert "Engineering" in themuse.normalize(_load("themuse"))[0].tags

    def test_tags_include_level(self):
        assert "Mid Level" in themuse.normalize(_load("themuse"))[0].tags


class TestJoobleNormalizer:
    def test_returns_correct_count(self):
        assert len(jooble.normalize(_load("jooble"))) == 2

    def test_first_job_title(self):
        assert jooble.normalize(_load("jooble"))[0].title == "Java Developer"

    def test_company_extracted(self):
        assert jooble.normalize(_load("jooble"))[0].company == "Enterprise Solutions"

    def test_remote_detected(self):
        assert jooble.normalize(_load("jooble"))[1].remote is True

    def test_salary_extracted(self):
        assert jooble.normalize(_load("jooble"))[0].salary is not None
