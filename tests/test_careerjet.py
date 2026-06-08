"""Tests for source/providers/careerjet.py — normalizer + fetch.

All network calls are mocked.  The normalizer tests are synchronous.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from decroche.models import JobPosting
from decroche.source.providers import careerjet

_FIXTURE = Path(__file__).parent / "fixtures" / "source" / "careerjet.json"


def _load_fixture() -> dict:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


# ── TestCareerjetNormalizer ────────────────────────────────────────────────────


class TestCareerjetNormalizer:
    def test_returns_list(self):
        raw = _load_fixture()
        result = careerjet.normalize(raw)
        assert isinstance(result, list)

    def test_count_matches_fixture(self):
        raw = _load_fixture()
        result = careerjet.normalize(raw)
        # Fixture has 3 jobs
        assert len(result) == 3

    def test_all_job_postings(self):
        result = careerjet.normalize(_load_fixture())
        assert all(isinstance(j, JobPosting) for j in result)

    def test_source_is_careerjet(self):
        result = careerjet.normalize(_load_fixture())
        assert all(j.source == "careerjet" for j in result)

    def test_first_job_title(self):
        result = careerjet.normalize(_load_fixture())
        assert result[0].title == "Développeur Python"

    def test_first_job_company(self):
        result = careerjet.normalize(_load_fixture())
        assert result[0].company == "DataSolutions SAS"

    def test_first_job_location(self):
        result = careerjet.normalize(_load_fixture())
        assert result[0].location == "Paris, Île-de-France"

    def test_first_job_url(self):
        result = careerjet.normalize(_load_fixture())
        assert result[0].url == "https://www.careerjet.fr/emploi/a7b8c9d0e1f2"

    def test_first_job_date_posted(self):
        result = careerjet.normalize(_load_fixture())
        assert result[0].date_posted == "il y a 2 jours"

    def test_second_job_title(self):
        result = careerjet.normalize(_load_fixture())
        assert result[1].title == "Ingénieur Machine Learning"

    def test_third_job_null_company(self):
        """Null company in fixture → None in model."""
        result = careerjet.normalize(_load_fixture())
        assert result[2].company is None

    def test_third_job_null_location(self):
        result = careerjet.normalize(_load_fixture())
        assert result[2].location is None

    def test_third_job_null_date(self):
        result = careerjet.normalize(_load_fixture())
        assert result[2].date_posted is None

    def test_source_id_from_url(self):
        """source_id is last URL segment."""
        result = careerjet.normalize(_load_fixture())
        assert result[0].source_id == "a7b8c9d0e1f2"

    def test_bare_list_input(self):
        """normalize() also accepts a plain list (not dict envelope)."""
        raw = _load_fixture()
        jobs_list = raw["jobs"]
        result = careerjet.normalize(jobs_list)
        assert len(result) == 3


# ── TestCareerjetFetch ────────────────────────────────────────────────────────


class TestCareerjetFetch:
    @pytest.mark.asyncio
    async def test_fetch_returns_dict(self):
        raw = _load_fixture()
        with patch(
            "decroche.source.providers.careerjet.fetch_json",
            new=AsyncMock(return_value=raw),
        ):
            result = await careerjet.fetch("python developer", "Paris")
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_fetch_passes_keywords(self):
        raw = _load_fixture()
        mock = AsyncMock(return_value=raw)
        with patch("decroche.source.providers.careerjet.fetch_json", new=mock):
            await careerjet.fetch("data engineer")
        _url, call_kwargs = mock.call_args[0][0], mock.call_args[1]
        params = call_kwargs.get("params", {})
        assert params.get("keywords") == "data engineer"

    @pytest.mark.asyncio
    async def test_fetch_default_locale(self):
        raw = _load_fixture()
        mock = AsyncMock(return_value=raw)
        with patch("decroche.source.providers.careerjet.fetch_json", new=mock):
            await careerjet.fetch("python")
        params = mock.call_args[1].get("params", {})
        assert params.get("locale_code") == "fr_FR"

    @pytest.mark.asyncio
    async def test_fetch_uses_affid_env(self, monkeypatch):
        monkeypatch.setenv("CAREERJET_AFFID", "test_affid_123")
        raw = _load_fixture()
        mock = AsyncMock(return_value=raw)
        with patch("decroche.source.providers.careerjet.fetch_json", new=mock):
            await careerjet.fetch("python")
        params = mock.call_args[1].get("params", {})
        assert params.get("affid") == "test_affid_123"
