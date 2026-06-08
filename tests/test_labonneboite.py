"""Tests for source/providers/labonneboite.py — normalizer + fetch.

All network calls are mocked.  The normalizer tests are synchronous.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from decroche.models import JobPosting
from decroche.source.providers import labonneboite

_FIXTURE = Path(__file__).parent / "fixtures" / "source" / "labonneboite.json"


def _load_fixture() -> dict:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


# ── TestLabonneBoiteNormalizer ─────────────────────────────────────────────────


class TestLabonneBoiteNormalizer:
    def test_returns_list(self):
        result = labonneboite.normalize(_load_fixture())
        assert isinstance(result, list)

    def test_count_matches_fixture(self):
        result = labonneboite.normalize(_load_fixture())
        assert len(result) == 2

    def test_all_job_postings(self):
        result = labonneboite.normalize(_load_fixture())
        assert all(isinstance(j, JobPosting) for j in result)

    def test_source_is_labonneboite(self):
        result = labonneboite.normalize(_load_fixture())
        assert all(j.source == "labonneboite" for j in result)

    def test_title_has_hidden_market_prefix(self):
        result = labonneboite.normalize(_load_fixture())
        assert all(j.title.startswith("(marché caché)") for j in result)

    def test_first_company_name(self):
        result = labonneboite.normalize(_load_fixture())
        assert result[0].company == "Startup Tech Lyon"

    def test_first_location(self):
        result = labonneboite.normalize(_load_fixture())
        assert result[0].location == "Lyon, 69002"

    def test_first_url_present(self):
        result = labonneboite.normalize(_load_fixture())
        assert result[0].url == "https://labonneboite.francetravail.fr/entreprise/12345678901234"

    def test_source_id_is_siret(self):
        result = labonneboite.normalize(_load_fixture())
        assert result[0].source_id == "12345678901234"

    def test_second_url_null_fallback(self):
        """Second fixture item has url=null → fallback to SIRET URL."""
        result = labonneboite.normalize(_load_fixture())
        assert "98765432100001" in result[1].url

    def test_description_contains_naf_text(self):
        result = labonneboite.normalize(_load_fixture())
        assert "Programmation informatique" in result[0].description

    def test_bare_list_input(self):
        raw = _load_fixture()
        companies = raw["companies"]
        result = labonneboite.normalize(companies)
        assert len(result) == 2


# ── TestLabonneBoiteFetch ─────────────────────────────────────────────────────


class TestLabonneBoiteFetch:
    @pytest.mark.asyncio
    async def test_raises_missing_key_without_env(self, monkeypatch):
        monkeypatch.delenv("FRANCE_TRAVAIL_ID", raising=False)
        monkeypatch.delenv("FRANCE_TRAVAIL_SECRET", raising=False)
        from decroche.source.http import MissingKeyError

        with pytest.raises((MissingKeyError, Exception)):
            await labonneboite.fetch("M1805", "69123")

    @pytest.mark.asyncio
    async def test_fetch_calls_api_with_params(self, monkeypatch):
        monkeypatch.setenv("FRANCE_TRAVAIL_ID", "test_id")
        monkeypatch.setenv("FRANCE_TRAVAIL_SECRET", "test_secret")

        fixture = _load_fixture()
        mock_token = AsyncMock(return_value="fake_token")
        mock_fetch_json = AsyncMock(return_value=fixture)

        with (
            patch.object(labonneboite, "_get_token", mock_token),
            patch("decroche.source.providers.labonneboite.fetch_json", mock_fetch_json),
        ):
            result = await labonneboite.fetch("M1805", "69123", distance=5)

        assert isinstance(result, dict)
        call_kwargs = mock_fetch_json.call_args[1]
        params = call_kwargs.get("params", {})
        assert params.get("rome_codes") == "M1805"
        assert params.get("commune_id") == "69123"
        assert params.get("distance") == 5
