"""Integration tests: recruiter_* and network_* tools registered and callable via FastMCP Client."""

from __future__ import annotations

import pytest
from fastmcp import Client

from decroche.server import mcp


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recruiter_tools_registered():
    async with Client(mcp) as client:
        names = [t.name for t in await client.list_tools()]
        recruiter_tools = [n for n in names if n.startswith("recruiter_")]
        assert len(recruiter_tools) >= 4, f"Expected ≥4 recruiter tools, got: {recruiter_tools}"


@pytest.mark.asyncio
async def test_network_tools_registered():
    async with Client(mcp) as client:
        names = [t.name for t in await client.list_tools()]
        network_tools = [n for n in names if n.startswith("network_")]
        assert len(network_tools) >= 2, f"Expected ≥2 network tools, got: {network_tools}"


# ---------------------------------------------------------------------------
# recruiter_identify callable
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recruiter_identify_callable():
    pasted = """Sophie Martin
Technical Recruiter
Acme Corp
"""
    async with Client(mcp) as client:
        names = [t.name for t in await client.list_tools()]
        identify_name = next((n for n in names if "recruiter" in n and "identify" in n), None)
        assert identify_name is not None, "recruiter_identify tool not found"
        res = await client.call_tool(identify_name, {"text": pasted})
        data = res.structured_content
        assert data["source"] == "pasted"
        assert data["name"]  # non-empty


# ---------------------------------------------------------------------------
# recruiter_qualify callable
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recruiter_qualify_callable():
    recruiter_dict = {
        "name": "Alice Dupont",
        "title": "Technical Recruiter",
        "company": "Acme Corp",
        "kind": "in_house",
        "source": "pasted",
    }
    target = {"company": "Acme Corp", "role": "Backend Engineer", "seniority": "senior"}

    async with Client(mcp) as client:
        names = [t.name for t in await client.list_tools()]
        qualify_name = next((n for n in names if "recruiter" in n and "qualify" in n), None)
        assert qualify_name is not None, "recruiter_qualify tool not found"
        res = await client.call_tool(qualify_name, {"recruiter": recruiter_dict, "target": target})
        data = res.structured_content
        assert "fit_score" in data
        assert "recommend" in data


# ---------------------------------------------------------------------------
# network_find_warm_path callable
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_network_find_warm_path_callable():
    connections = [
        {"name": "Bob Martin", "company": "Acme Corp", "relationship": "former colleague"},
        {"name": "Carol Smith", "company": "OtherCo", "relationship": "friend"},
    ]
    async with Client(mcp) as client:
        names = [t.name for t in await client.list_tools()]
        path_name = next((n for n in names if "network" in n and "find_warm_path" in n), None)
        assert path_name is not None, "network_find_warm_path tool not found"
        res = await client.call_tool(
            path_name,
            {"target_company": "Acme Corp", "connections": connections},
        )
        raw = res.structured_content
        # FastMCP may wrap list results in {"result": [...]}
        data = raw.get("result", raw) if isinstance(raw, dict) else raw
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["connector"] == "Bob Martin"


# ---------------------------------------------------------------------------
# network_draft_intro_request callable
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_network_draft_intro_request_callable():
    path_dict = {
        "target_company": "Acme Corp",
        "connector": "Bob Martin",
        "relationship": "former colleague",
        "hops": 1,
    }
    async with Client(mcp) as client:
        names = [t.name for t in await client.list_tools()]
        draft_name = next((n for n in names if "network" in n and "draft_intro" in n), None)
        assert draft_name is not None, "network_draft_intro_request tool not found"
        res = await client.call_tool(
            draft_name,
            {"path": path_dict, "context": "poste backend senior", "lang": "fr"},
        )
        data = res.structured_content
        assert "body" in data
        body = data["body"]
        # FR opt-out must be present
        assert "ne souhait" in body.lower() or "supprimerai" in body.lower()
