"""Tests for keyed source MCP tools — HTTP mocked via monkeypatch, no network."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from decroche.models import SourceResult
from decroche.source import source_server
from decroche.source.http import MissingKeyError, ToolError
from decroche.source.providers import adzuna, france_travail, jooble, jsearch, reed, themuse, usajobs

_FIXTURES = Path(__file__).parent / "fixtures" / "source"


def _load(name: str):
    return json.loads((_FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


async def _call_tool(name: str, **kwargs):
    tool = await source_server.get_tool(name)
    assert tool is not None
    return await tool.fn(**kwargs)


class TestFranceTravailTool:
    @pytest.mark.asyncio
    async def test_returns_source_result(self, monkeypatch):
        monkeypatch.setattr(france_travail, "fetch", AsyncMock(return_value=_load("france_travail")))
        result = await _call_tool("france_travail", query="python", location="")
        assert isinstance(result, SourceResult)
        assert result.count == 2

    @pytest.mark.asyncio
    async def test_missing_key_raises_tool_error(self, monkeypatch):
        monkeypatch.delenv("FRANCE_TRAVAIL_ID", raising=False)
        monkeypatch.delenv("FRANCE_TRAVAIL_SECRET", raising=False)
        with pytest.raises((MissingKeyError, ToolError)):
            await _call_tool("france_travail", query="python", location="")


class TestAdzunaTool:
    @pytest.mark.asyncio
    async def test_returns_source_result(self, monkeypatch):
        monkeypatch.setattr(adzuna, "fetch", AsyncMock(return_value=_load("adzuna")))
        result = await _call_tool("adzuna", query="python", country="fr")
        assert isinstance(result, SourceResult)
        assert result.count == 2

    @pytest.mark.asyncio
    async def test_missing_key_raises_tool_error(self, monkeypatch):
        monkeypatch.delenv("ADZUNA_APP_ID", raising=False)
        monkeypatch.delenv("ADZUNA_APP_KEY", raising=False)
        with pytest.raises((MissingKeyError, ToolError)):
            await _call_tool("adzuna", query="python", country="fr")


class TestJSearchTool:
    @pytest.mark.asyncio
    async def test_returns_source_result(self, monkeypatch):
        monkeypatch.setattr(jsearch, "fetch", AsyncMock(return_value=_load("jsearch")))
        result = await _call_tool("jsearch", query="software engineer")
        assert isinstance(result, SourceResult)
        assert result.count == 2

    @pytest.mark.asyncio
    async def test_missing_key_raises_tool_error(self, monkeypatch):
        monkeypatch.delenv("JSEARCH_RAPIDAPI_KEY", raising=False)
        with pytest.raises((MissingKeyError, ToolError)):
            await _call_tool("jsearch", query="software engineer")


class TestUsajobsTool:
    @pytest.mark.asyncio
    async def test_returns_source_result(self, monkeypatch):
        monkeypatch.setattr(usajobs, "fetch", AsyncMock(return_value=_load("usajobs")))
        result = await _call_tool("usajobs", query="software")
        assert isinstance(result, SourceResult)
        assert result.count == 2

    @pytest.mark.asyncio
    async def test_missing_key_raises_tool_error(self, monkeypatch):
        monkeypatch.delenv("USAJOBS_KEY", raising=False)
        monkeypatch.delenv("USAJOBS_EMAIL", raising=False)
        with pytest.raises((MissingKeyError, ToolError)):
            await _call_tool("usajobs", query="software")


class TestReedTool:
    @pytest.mark.asyncio
    async def test_returns_source_result(self, monkeypatch):
        monkeypatch.setattr(reed, "fetch", AsyncMock(return_value=_load("reed")))
        result = await _call_tool("reed", query="python")
        assert isinstance(result, SourceResult)
        assert result.count == 2

    @pytest.mark.asyncio
    async def test_missing_key_raises_tool_error(self, monkeypatch):
        monkeypatch.delenv("REED_KEY", raising=False)
        with pytest.raises((MissingKeyError, ToolError)):
            await _call_tool("reed", query="python")


class TestTheMuseTool:
    @pytest.mark.asyncio
    async def test_returns_source_result(self, monkeypatch):
        monkeypatch.setattr(themuse, "fetch", AsyncMock(return_value=_load("themuse")))
        result = await _call_tool("themuse", category="")
        assert isinstance(result, SourceResult)
        assert result.count == 2

    @pytest.mark.asyncio
    async def test_works_without_key_env_var(self, monkeypatch):
        monkeypatch.delenv("THEMUSE_KEY", raising=False)
        monkeypatch.setattr(themuse, "fetch", AsyncMock(return_value=_load("themuse")))
        result = await _call_tool("themuse", category="")
        assert result.count == 2


class TestJoobleTool:
    @pytest.mark.asyncio
    async def test_returns_source_result(self, monkeypatch):
        monkeypatch.setattr(jooble, "fetch", AsyncMock(return_value=_load("jooble")))
        result = await _call_tool("jooble", query="java", location="")
        assert isinstance(result, SourceResult)
        assert result.count == 2

    @pytest.mark.asyncio
    async def test_missing_key_raises_tool_error(self, monkeypatch):
        monkeypatch.delenv("JOOBLE_KEY", raising=False)
        with pytest.raises((MissingKeyError, ToolError)):
            await _call_tool("jooble", query="java", location="")
