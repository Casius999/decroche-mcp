"""Tests for source MCP tools — HTTP mocked via monkeypatch."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from decroche.models import JobPosting, SourceResult
from decroche.source import source_server
from decroche.source.providers import (
    arbeitnow, ashby, greenhouse, lever, recruitee,
    remoteok, remotive, smartrecruiters, workable,
)

_FIXTURES = Path(__file__).parent / "fixtures" / "source"


def _load(name: str):
    return json.loads((_FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


async def _call_tool(name: str, **kwargs):
    tool = await source_server.get_tool(name)
    assert tool is not None, f"Tool '{name}' not found"
    return await tool.fn(**kwargs)


@pytest.mark.asyncio
async def test_greenhouse_tool_returns_source_result(monkeypatch):
    monkeypatch.setattr(greenhouse, "fetch", AsyncMock(return_value=_load("greenhouse")))
    result = await _call_tool("greenhouse", board_token="acmecorp")
    assert isinstance(result, SourceResult)
    assert result.provider == "greenhouse"
    assert result.count == 3
    assert result.warnings == []


@pytest.mark.asyncio
async def test_greenhouse_tool_network_error_returns_warning(monkeypatch):
    import httpx
    monkeypatch.setattr(greenhouse, "fetch", AsyncMock(side_effect=httpx.RequestError("timeout")))
    result = await _call_tool("greenhouse", board_token="bad-token")
    assert result.count == 0
    assert len(result.warnings) > 0


@pytest.mark.asyncio
async def test_lever_tool_returns_source_result(monkeypatch):
    monkeypatch.setattr(lever, "fetch", AsyncMock(return_value=_load("lever")))
    result = await _call_tool("lever", company="techstart")
    assert isinstance(result, SourceResult)
    assert result.count == 2
    assert result.warnings == []


@pytest.mark.asyncio
async def test_ashby_tool_returns_source_result(monkeypatch):
    monkeypatch.setattr(ashby, "fetch", AsyncMock(return_value=_load("ashby")))
    result = await _call_tool("ashby", job_board_name="novacorp")
    assert isinstance(result, SourceResult)
    assert result.count == 2


@pytest.mark.asyncio
async def test_recruitee_tool_returns_source_result(monkeypatch):
    monkeypatch.setattr(recruitee, "fetch", AsyncMock(return_value=_load("recruitee")))
    result = await _call_tool("recruitee", company="recruitee-demo")
    assert isinstance(result, SourceResult)
    assert result.count == 2


@pytest.mark.asyncio
async def test_workable_tool_returns_source_result(monkeypatch):
    monkeypatch.setattr(workable, "fetch", AsyncMock(return_value=_load("workable")))
    result = await _call_tool("workable", account="megacorp")
    assert isinstance(result, SourceResult)
    assert result.count == 2


@pytest.mark.asyncio
async def test_smartrecruiters_tool_returns_source_result(monkeypatch):
    monkeypatch.setattr(smartrecruiters, "fetch", AsyncMock(return_value=_load("smartrecruiters")))
    result = await _call_tool("smartrecruiters", company_id="SmartCoSA")
    assert isinstance(result, SourceResult)
    assert result.count == 2


@pytest.mark.asyncio
async def test_remoteok_tool_returns_source_result(monkeypatch):
    monkeypatch.setattr(remoteok, "fetch", AsyncMock(return_value=_load("remoteok")))
    result = await _call_tool("remoteok")
    assert isinstance(result, SourceResult)
    assert result.count == 2


@pytest.mark.asyncio
async def test_remotive_tool_no_search(monkeypatch):
    monkeypatch.setattr(remotive, "fetch", AsyncMock(return_value=_load("remotive")))
    result = await _call_tool("remotive", search="")
    assert isinstance(result, SourceResult)
    assert result.count == 2
    assert result.query is None


@pytest.mark.asyncio
async def test_arbeitnow_tool_returns_source_result(monkeypatch):
    monkeypatch.setattr(arbeitnow, "fetch", AsyncMock(return_value=_load("arbeitnow")))
    result = await _call_tool("arbeitnow")
    assert isinstance(result, SourceResult)
    assert result.count == 3


@pytest.mark.asyncio
async def test_search_all_aggregates_multiple_providers(monkeypatch):
    monkeypatch.setattr(greenhouse, "fetch", AsyncMock(return_value=_load("greenhouse")))
    monkeypatch.setattr(lever, "fetch", AsyncMock(return_value=_load("lever")))
    from decroche.source.aggregate import search_all as _agg
    jobs, warnings = await _agg(greenhouse_tokens=["acmecorp"], lever_companies=["techstart"])
    assert len(jobs) == 5
    assert warnings == []


@pytest.mark.asyncio
async def test_search_all_captures_per_provider_error(monkeypatch):
    import httpx
    monkeypatch.setattr(greenhouse, "fetch", AsyncMock(side_effect=httpx.RequestError("timeout")))
    monkeypatch.setattr(lever, "fetch", AsyncMock(return_value=_load("lever")))
    from decroche.source.aggregate import search_all as _agg
    jobs, warnings = await _agg(greenhouse_tokens=["bad"], lever_companies=["techstart"])
    assert len(jobs) == 2
    assert len(warnings) == 1


@pytest.mark.asyncio
async def test_search_all_empty_specs_returns_empty():
    from decroche.source.aggregate import search_all as _agg
    jobs, warnings = await _agg()
    assert jobs == [] and warnings == []


def test_env_key_returns_dict_when_all_set(monkeypatch):
    monkeypatch.setenv("MY_API_KEY", "abc123")
    from decroche.source.http import env_key
    assert env_key("MY_API_KEY") == {"MY_API_KEY": "abc123"}


def test_env_key_returns_none_when_missing(monkeypatch):
    monkeypatch.delenv("MISSING_KEY", raising=False)
    from decroche.source.http import env_key
    assert env_key("MISSING_KEY") is None


@pytest.mark.asyncio
async def test_source_server_has_expected_tools():
    tools = [t.name for t in await source_server.list_tools()]
    for name in ["greenhouse", "lever", "ashby", "recruitee", "workable",
                 "smartrecruiters", "remoteok", "remotive", "arbeitnow", "search_all"]:
        assert name in tools
