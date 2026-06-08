"""Tests for source_search_market FastMCP tool registration and behavior.

Invokes the tool function directly (without spinning up a full MCP server)
so no FastMCP Client is needed.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from decroche.models import JobPosting, SourceResult


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
        description="Python developer",
        salary=None,
        tags=[],
        raw={},
    )
    defaults.update(kwargs)
    return JobPosting(**defaults)


# ── tool registration ─────────────────────────────────────────────────────────


class TestSourceSearchMarketToolRegistration:
    def test_tool_is_registered_on_source_server(self):
        """source_search_market must be registered as a tool on source_server."""
        from decroche.source import source_server

        # FastMCP stores tools in _tool_manager or similar; use the public API
        tool_names = [t.name for t in source_server._tool_manager.list_tools()]
        assert "source_search_market" in tool_names, (
            f"source_search_market not found in: {tool_names}"
        )

    def test_careerjet_tool_registered(self):
        from decroche.source import source_server

        tool_names = [t.name for t in source_server._tool_manager.list_tools()]
        assert "careerjet" in tool_names

    def test_labonneboite_tool_registered(self):
        from decroche.source import source_server

        tool_names = [t.name for t in source_server._tool_manager.list_tools()]
        assert "labonneboite" in tool_names

    @pytest.mark.asyncio
    async def test_tool_returns_source_result(self):
        """Calling the tool fn directly should return a SourceResult."""
        from decroche.source import source_server

        jobs = [_job()]
        warnings = ["adzuna: skipped", "jsearch: skipped", "france_travail: skipped"]

        with patch(
            "decroche.source.market_search.search_market",
            AsyncMock(return_value=(jobs, warnings)),
        ):
            # Get the tool fn from source_server
            tool = next(
                t
                for t in source_server._tool_manager.list_tools()
                if t.name == "source_search_market"
            )
            result = await tool.fn(query="python", region="fr", use_keyed=True, per_provider_limit=50)

        assert isinstance(result, SourceResult)
        assert result.provider == "market_search"
        assert result.count == 1
        assert len(result.jobs) == 1

    @pytest.mark.asyncio
    async def test_tool_passes_warnings_to_result(self):
        """Warnings from search_market must appear in SourceResult.warnings."""
        from decroche.source import source_server

        skipped = ["adzuna: skipped — ADZUNA_APP_ID/ADZUNA_APP_KEY not set"]

        with patch(
            "decroche.source.market_search.search_market",
            AsyncMock(return_value=([], skipped)),
        ):
            tool = next(
                t
                for t in source_server._tool_manager.list_tools()
                if t.name == "source_search_market"
            )
            result = await tool.fn(query="", region="fr", use_keyed=True, per_provider_limit=50)

        assert any("adzuna" in w for w in result.warnings)
