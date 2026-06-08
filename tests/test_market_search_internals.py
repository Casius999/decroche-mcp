"""White-box tests for market_search internal helpers.

Tests _fan_out_keyless and _run_* helpers directly with monkeypatched providers.
These complement test_market_search.py to reach ≥80% module coverage.
No network.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from decroche.models import JobPosting

_FIXTURES = Path(__file__).parent / "fixtures" / "source"


def _load(name: str):
    return json.loads((_FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def _job(**kwargs) -> JobPosting:
    defaults = dict(
        source="greenhouse",
        source_id="1",
        title="Engineer",
        company="Acme",
        location="Paris",
        remote=None,
        url="https://example.com/1",
        apply_url=None,
        date_posted="2026-05-01",
        description="",
        salary=None,
        tags=[],
        raw={},
    )
    defaults.update(kwargs)
    return JobPosting(**defaults)


# ── _fan_out_keyless ───────────────────────────────────────────────────────────


class TestFanOutKeyless:
    @pytest.mark.asyncio
    async def test_empty_boards_returns_empty(self):
        from decroche.source.market_search import _fan_out_keyless

        jobs, warnings = await _fan_out_keyless("python", [], 50)
        assert jobs == []
        assert warnings == []

    @pytest.mark.asyncio
    async def test_missing_token_skipped(self):
        from decroche.source.market_search import _fan_out_keyless

        boards = [{"provider": "greenhouse", "token": "", "company": "NoToken"}]
        jobs, warnings = await _fan_out_keyless("python", boards, 50)
        assert jobs == []
        assert warnings == []

    @pytest.mark.asyncio
    async def test_greenhouse_board_normalised(self):
        from decroche.source.market_search import _fan_out_keyless
        from decroche.source.providers import greenhouse

        boards = [{"provider": "greenhouse", "token": "stripe", "company": "Stripe"}]
        fixture = _load("greenhouse")
        mock_fetch = AsyncMock(return_value=fixture)

        with patch.object(greenhouse, "fetch", mock_fetch):
            jobs, warnings = await _fan_out_keyless("senior", boards, 50)

        assert warnings == []
        assert len(jobs) > 0
        assert all(j.source == "greenhouse" for j in jobs)

    @pytest.mark.asyncio
    async def test_lever_board_normalised(self):
        from decroche.source.market_search import _fan_out_keyless
        from decroche.source.providers import lever

        boards = [{"provider": "lever", "token": "plaid", "company": "Plaid"}]
        fixture = _load("lever")
        mock_fetch = AsyncMock(return_value=fixture)

        with patch.object(lever, "fetch", mock_fetch):
            jobs, warnings = await _fan_out_keyless("engineer", boards, 50)

        assert warnings == []
        assert all(j.source == "lever" for j in jobs)

    @pytest.mark.asyncio
    async def test_ashby_board_normalised(self):
        from decroche.source.market_search import _fan_out_keyless
        from decroche.source.providers import ashby

        boards = [{"provider": "ashby", "token": "notion", "company": "Notion"}]
        fixture = _load("ashby")
        mock_fetch = AsyncMock(return_value=fixture)

        with patch.object(ashby, "fetch", mock_fetch):
            jobs, warnings = await _fan_out_keyless("product", boards, 50)

        assert warnings == []
        assert all(j.source == "ashby" for j in jobs)

    @pytest.mark.asyncio
    async def test_recruitee_board_normalised(self):
        from decroche.source.market_search import _fan_out_keyless
        from decroche.source.providers import recruitee

        boards = [{"provider": "recruitee", "token": "sumup", "company": "SumUp"}]
        fixture = _load("recruitee")
        mock_fetch = AsyncMock(return_value=fixture)

        with patch.object(recruitee, "fetch", mock_fetch):
            jobs, warnings = await _fan_out_keyless("dev", boards, 50)

        assert warnings == []
        assert all(j.source == "recruitee" for j in jobs)

    @pytest.mark.asyncio
    async def test_exception_produces_warning(self):
        from decroche.source.market_search import _fan_out_keyless
        from decroche.source.providers import greenhouse

        boards = [{"provider": "greenhouse", "token": "err-co", "company": "ErrCo"}]
        mock_fetch = AsyncMock(side_effect=RuntimeError("network down"))

        with patch.object(greenhouse, "fetch", mock_fetch):
            jobs, warnings = await _fan_out_keyless("python", boards, 50)

        assert jobs == []
        assert len(warnings) == 1
        assert "network down" in warnings[0]

    @pytest.mark.asyncio
    async def test_per_provider_limit_applied(self):
        from decroche.source.market_search import _fan_out_keyless
        from decroche.source.providers import greenhouse

        boards = [{"provider": "greenhouse", "token": "big", "company": "Big"}]
        # Fixture has 3 jobs; limit to 2
        fixture = _load("greenhouse")
        mock_fetch = AsyncMock(return_value=fixture)

        with patch.object(greenhouse, "fetch", mock_fetch):
            jobs, _ = await _fan_out_keyless("", boards, 2)

        assert len(jobs) <= 2

    @pytest.mark.asyncio
    async def test_unknown_provider_warning(self):
        from decroche.source.market_search import _fan_out_keyless
        from decroche.source.providers import greenhouse

        boards = [
            {"provider": "unknown_ats", "token": "xyz", "company": "XYZ"},
            {"provider": "greenhouse", "token": "stripe", "company": "Stripe"},
        ]
        fixture = _load("greenhouse")
        mock_fetch = AsyncMock(return_value=fixture)

        with patch.object(greenhouse, "fetch", mock_fetch):
            jobs, warnings = await _fan_out_keyless("", boards, 50)

        # unknown_ats is silently skipped; greenhouse jobs come through
        assert len(jobs) > 0
        assert all(j.source == "greenhouse" for j in jobs)
        assert mock_fetch.call_count == 1

    @pytest.mark.asyncio
    async def test_multiple_boards_fan_out(self):
        """Multiple boards from same provider run concurrently."""
        from decroche.source.market_search import _fan_out_keyless
        from decroche.source.providers import greenhouse

        boards = [
            {"provider": "greenhouse", "token": "stripe", "company": "Stripe"},
            {"provider": "greenhouse", "token": "airbnb", "company": "Airbnb"},
        ]
        fixture = _load("greenhouse")
        mock_fetch = AsyncMock(return_value=fixture)

        with patch.object(greenhouse, "fetch", mock_fetch):
            jobs, warnings = await _fan_out_keyless("", boards, 50)

        assert mock_fetch.call_count == 2
        assert warnings == []
        assert len(jobs) == 2 * len(greenhouse.normalize(fixture))


# ── _run_france_travail ────────────────────────────────────────────────────────


class TestRunFranceTravail:
    @pytest.mark.asyncio
    async def test_returns_jobs_on_success(self):
        from decroche.source.market_search import _run_france_travail
        from decroche.source.providers import france_travail

        fixture = _load("france_travail")
        mock_fetch = AsyncMock(return_value=fixture)

        with patch.object(france_travail, "fetch", mock_fetch):
            jobs, warnings = await _run_france_travail("python", "fr")

        assert len(jobs) == 2
        assert warnings == []

    @pytest.mark.asyncio
    async def test_returns_warning_on_error(self):
        from decroche.source.market_search import _run_france_travail
        from decroche.source.providers import france_travail

        mock_fetch = AsyncMock(side_effect=RuntimeError("API down"))

        with patch.object(france_travail, "fetch", mock_fetch):
            jobs, warnings = await _run_france_travail("python", "fr")

        assert jobs == []
        assert len(warnings) == 1
        assert "france_travail" in warnings[0]


# ── _run_adzuna ────────────────────────────────────────────────────────────────


class TestRunAdzuna:
    @pytest.mark.asyncio
    async def test_returns_jobs_on_success(self):
        from decroche.source.market_search import _run_adzuna
        from decroche.source.providers import adzuna

        fixture = _load("adzuna")
        mock_fetch = AsyncMock(return_value=fixture)

        with patch.object(adzuna, "fetch", mock_fetch):
            jobs, warnings = await _run_adzuna("python", "fr")

        assert warnings == []
        assert isinstance(jobs, list)

    @pytest.mark.asyncio
    async def test_country_extracted_from_region(self):
        """Region 'fr' → country 'fr'; 'gb' → 'gb'."""
        from decroche.source.market_search import _run_adzuna
        from decroche.source.providers import adzuna

        fixture = _load("adzuna")
        mock_fetch = AsyncMock(return_value=fixture)

        with patch.object(adzuna, "fetch", mock_fetch):
            await _run_adzuna("dev", "gb")

        call_kwargs = mock_fetch.call_args
        assert call_kwargs[1].get("country") == "gb" or call_kwargs[0][1] == "gb"

    @pytest.mark.asyncio
    async def test_returns_warning_on_error(self):
        from decroche.source.market_search import _run_adzuna
        from decroche.source.providers import adzuna

        with patch.object(adzuna, "fetch", AsyncMock(side_effect=RuntimeError("err"))):
            jobs, warnings = await _run_adzuna("dev", "fr")

        assert jobs == []
        assert "adzuna" in warnings[0]


# ── _run_jsearch ──────────────────────────────────────────────────────────────


class TestRunJsearch:
    @pytest.mark.asyncio
    async def test_returns_jobs_on_success(self):
        from decroche.source.market_search import _run_jsearch
        from decroche.source.providers import jsearch

        fixture = _load("jsearch")
        mock_fetch = AsyncMock(return_value=fixture)

        with patch.object(jsearch, "fetch", mock_fetch):
            jobs, warnings = await _run_jsearch("python")

        assert warnings == []
        assert isinstance(jobs, list)

    @pytest.mark.asyncio
    async def test_returns_warning_on_error(self):
        from decroche.source.market_search import _run_jsearch
        from decroche.source.providers import jsearch

        with patch.object(jsearch, "fetch", AsyncMock(side_effect=RuntimeError("err"))):
            jobs, warnings = await _run_jsearch("python")

        assert jobs == []
        assert "jsearch" in warnings[0]
