"""Tests for source/market_search.py — breadth orchestrator.

All provider calls are mocked.  No network.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from decroche.models import JobPosting
from decroche.source.market_search import _matches_query, _sort_key, search_market

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


# ── unit: _matches_query ───────────────────────────────────────────────────────


class TestQueryFiltering:
    def test_empty_terms_match_all(self):
        job = _job(title="Anything")
        assert _matches_query(job, []) is True

    def test_term_in_title_matches(self):
        job = _job(title="Python Developer")
        assert _matches_query(job, ["python"]) is True

    def test_term_in_description_matches(self):
        job = _job(title="Dev", description="Kubernetes experience required")
        assert _matches_query(job, ["kubernetes"]) is True

    def test_no_match_returns_false(self):
        job = _job(title="Java Developer", description="Spring Boot")
        assert _matches_query(job, ["python"]) is False

    def test_or_logic_any_term_matches(self):
        job = _job(title="Python Developer")
        assert _matches_query(job, ["python", "rust", "go"]) is True

    def test_case_insensitive(self):
        job = _job(title="PYTHON Developer")
        assert _matches_query(job, ["python"]) is True


# ── unit: _sort_key ────────────────────────────────────────────────────────────


class TestSortOrder:
    def test_dated_sorts_before_none(self):
        dated = _job(date_posted="2026-05-01")
        undated = _job(date_posted=None)
        assert _sort_key(dated) > _sort_key(undated)

    def test_newer_sorts_before_older(self):
        newer = _job(date_posted="2026-06-01")
        older = _job(date_posted="2026-01-01")
        assert _sort_key(newer) > _sort_key(older)

    def test_none_sorts_last_in_sorted(self):
        jobs = [
            _job(source_id="a", date_posted=None),
            _job(source_id="b", date_posted="2026-01-01"),
            _job(source_id="c", date_posted="2026-06-01"),
        ]
        sorted_jobs = sorted(jobs, key=_sort_key, reverse=True)
        assert sorted_jobs[-1].date_posted is None


# ── unit: deduplication ────────────────────────────────────────────────────────


class TestDeduplication:
    @pytest.mark.asyncio
    async def test_duplicate_jobs_removed(self):
        boards = [{"provider": "greenhouse", "token": "stripe", "company": "Stripe"}]
        fixture = _load("greenhouse")
        mock_fetch = AsyncMock(return_value=fixture)

        with (
            patch("decroche.source.market_search._fan_out_keyless") as mock_fanout,
            patch("decroche.source.market_search.dedupe") as mock_dedupe,
        ):
            jobs = [
                _job(source="greenhouse", source_id="1", title="Dev"),
                _job(source="greenhouse", source_id="1", title="Dev"),  # duplicate
            ]
            mock_fanout.return_value = (jobs, [])
            mock_dedupe.return_value = [jobs[0]]  # deduped to 1

            result = await search_market("", boards=boards, use_keyed=False)

        mock_dedupe.assert_called_once()
        assert len(result) == 1


# ── integration: keyed provider skip when no env vars ─────────────────────────


class TestKeyedProviders:
    @pytest.mark.asyncio
    async def test_keyed_providers_skipped_when_no_env(self, monkeypatch):
        monkeypatch.delenv("FRANCE_TRAVAIL_ID", raising=False)
        monkeypatch.delenv("FRANCE_TRAVAIL_SECRET", raising=False)
        monkeypatch.delenv("ADZUNA_APP_ID", raising=False)
        monkeypatch.delenv("ADZUNA_APP_KEY", raising=False)
        monkeypatch.delenv("JSEARCH_RAPIDAPI_KEY", raising=False)

        with patch("decroche.source.market_search._fan_out_keyless") as mock_fanout:
            mock_fanout.return_value = ([], [])
            jobs, warnings = await search_market(
                "", boards=[], use_keyed=True, _return_warnings=True
            )

        # All three keyed providers should be in warnings as 'skipped'
        warning_text = " ".join(warnings)
        assert "france_travail" in warning_text
        assert "adzuna" in warning_text
        assert "jsearch" in warning_text

    @pytest.mark.asyncio
    async def test_keyed_false_skips_all_keyed(self, monkeypatch):
        monkeypatch.setenv("FRANCE_TRAVAIL_ID", "x")
        monkeypatch.setenv("FRANCE_TRAVAIL_SECRET", "y")

        with (
            patch("decroche.source.market_search._fan_out_keyless") as mock_fanout,
            patch("decroche.source.market_search._run_france_travail") as mock_ft,
        ):
            mock_fanout.return_value = ([], [])
            jobs = await search_market("", boards=[], use_keyed=False)

        mock_ft.assert_not_called()


# ── error resilience ──────────────────────────────────────────────────────────


class TestErrorResilience:
    @pytest.mark.asyncio
    async def test_fan_out_error_produces_warning_not_exception(self):
        with patch("decroche.source.market_search._fan_out_keyless") as mock_fanout:
            mock_fanout.return_value = ([], ["greenhouse:err-co: RuntimeError: network down"])
            jobs, warnings = await search_market(
                "", boards=[], use_keyed=False, _return_warnings=True
            )

        assert jobs == []
        assert len(warnings) == 1
        assert "RuntimeError" in warnings[0]

    @pytest.mark.asyncio
    async def test_keyed_error_appended_to_warnings(self, monkeypatch):
        monkeypatch.setenv("FRANCE_TRAVAIL_ID", "x")
        monkeypatch.setenv("FRANCE_TRAVAIL_SECRET", "y")
        monkeypatch.delenv("ADZUNA_APP_ID", raising=False)
        monkeypatch.delenv("ADZUNA_APP_KEY", raising=False)
        monkeypatch.delenv("JSEARCH_RAPIDAPI_KEY", raising=False)

        with (
            patch("decroche.source.market_search._fan_out_keyless") as mock_fanout,
            patch(
                "decroche.source.market_search._run_france_travail",
                AsyncMock(return_value=([], ["france_travail: API error"])),
            ),
        ):
            mock_fanout.return_value = ([], [])
            jobs, warnings = await search_market(
                "", boards=[], use_keyed=True, _return_warnings=True
            )

        assert "france_travail" in " ".join(warnings)


# ── boards injection ──────────────────────────────────────────────────────────


class TestBoardsInjection:
    @pytest.mark.asyncio
    async def test_custom_boards_used_instead_of_yaml(self):
        custom_boards = [{"provider": "greenhouse", "token": "custom-co", "company": "Custom"}]

        with (
            patch("decroche.source.market_search._load_known_boards") as mock_load,
            patch("decroche.source.market_search._fan_out_keyless") as mock_fanout,
        ):
            mock_fanout.return_value = ([], [])
            await search_market("", boards=custom_boards, use_keyed=False)

        mock_load.assert_not_called()
        call_boards = mock_fanout.call_args[0][1]
        assert call_boards == custom_boards

    @pytest.mark.asyncio
    async def test_yaml_loaded_when_boards_none(self):
        with (
            patch(
                "decroche.source.market_search._load_known_boards",
                return_value=[],
            ) as mock_load,
            patch("decroche.source.market_search._fan_out_keyless") as mock_fanout,
        ):
            mock_fanout.return_value = ([], [])
            await search_market("", boards=None, use_keyed=False)

        mock_load.assert_called_once()
