"""Integration tests: apply_server + analytics_server tools registered + callable."""

from __future__ import annotations

import pytest
from fastmcp import Client

from decroche.analytics import analytics_server
from decroche.apply import apply_server
from decroche.models import Application


# ── apply server ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_apply_tools_registered():
    async with Client(apply_server) as client:
        names = [t.name for t in await client.list_tools()]
    assert "resolve_source" in names
    assert "prefill" in names
    assert "queue_add" in names
    assert "queue_review" in names
    assert "queue_approve" in names
    assert "followup" in names


@pytest.mark.asyncio
async def test_apply_resolve_source_callable():
    async with Client(apply_server) as client:
        result = await client.call_tool(
            "resolve_source",
            {
                "job": {
                    "source": "greenhouse",
                    "source_id": "1",
                    "title": "Dev",
                    "url": "https://boards.greenhouse.io/acme/jobs/1",
                    "description": "A job",
                }
            },
        )
    data = result.structured_content
    assert data["manual"] is False
    assert "apply_url" in data


@pytest.mark.asyncio
async def test_apply_resolve_aggregator_manual():
    async with Client(apply_server) as client:
        result = await client.call_tool(
            "resolve_source",
            {
                "job": {
                    "source": "jsearch",
                    "source_id": "1",
                    "title": "Dev",
                    "url": "https://www.linkedin.com/jobs/view/123",
                    "description": "A job",
                }
            },
        )
    data = result.structured_content
    assert data["manual"] is True


@pytest.mark.asyncio
async def test_apply_prefill_callable():
    async with Client(apply_server) as client:
        result = await client.call_tool(
            "prefill",
            {
                "job": {
                    "source": "greenhouse",
                    "source_id": "1",
                    "title": "Dev",
                    "url": "https://acme.com/jobs/1",
                    "apply_url": "https://acme.com/apply/1",
                    "description": "A job",
                },
                "json_resume": {
                    "basics": {
                        "name": "Jane Doe",
                        "email": "jane@example.com",
                        "phone": "+33612345678",
                    }
                },
            },
        )
    data = result.structured_content
    assert data["fields"]["full_name"] == "Jane Doe"
    assert "password" not in data["fields"]


@pytest.mark.asyncio
async def test_apply_prefill_never_exposes_sensitive():
    """Ensure the tool-level prefill also excludes sensitive fields."""
    async with Client(apply_server) as client:
        result = await client.call_tool(
            "prefill",
            {
                "job": {
                    "source": "lever",
                    "source_id": "2",
                    "title": "Engineer",
                    "url": "https://jobs.lever.co/co/1",
                    "description": "job",
                },
                "json_resume": {"basics": {"name": "Bob", "email": "bob@b.com"}},
            },
        )
    data = result.structured_content
    sensitive = {"password", "mot_de_passe", "card_number", "cvv", "ssn", "iban", "dob"}
    for s in sensitive:
        assert s not in data["fields"], f"Sensitive field {s!r} must not be in fields"


@pytest.mark.asyncio
async def test_apply_followup_callable(tmp_path):
    async with Client(apply_server) as client:
        result = await client.call_tool(
            "followup",
            {
                "app": {
                    "id": "app-001",
                    "company": "Acme",
                    "role_title": "Dev",
                    "stage": "applied",
                }
            },
        )
    data = result.structured_content
    if isinstance(data, dict):
        text = data.get("result", "")
    else:
        text = data
    assert isinstance(text, str)
    assert len(text) > 20


# ── analytics server ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_analytics_tools_registered():
    async with Client(analytics_server) as client:
        names = [t.name for t in await client.list_tools()]
    assert "track" in names
    assert "update_stage" in names
    assert "list_apps" in names
    assert "funnel" in names


@pytest.mark.asyncio
async def test_analytics_track_callable(tmp_path):
    db = str(tmp_path / "crm.db")
    async with Client(analytics_server) as client:
        result = await client.call_tool(
            "track",
            {
                "app": {
                    "id": "app-int-001",
                    "company": "Acme",
                    "role_title": "Dev",
                    "stage": "saved",
                },
                "db_path": db,
            },
        )
    data = result.structured_content
    assert data["id"] == "app-int-001"


@pytest.mark.asyncio
async def test_analytics_list_apps_callable(tmp_path):
    db = str(tmp_path / "crm.db")
    from decroche.analytics.crm import track

    track(Application(id="a1", company="Co", stage="applied"), db)
    track(Application(id="a2", company="Co", stage="saved"), db)
    async with Client(analytics_server) as client:
        result = await client.call_tool("list_apps", {"db_path": db})
    data = result.structured_content
    if isinstance(data, dict):
        data = data.get("result", data)
    assert isinstance(data, list)
    assert len(data) == 2


@pytest.mark.asyncio
async def test_analytics_funnel_callable():
    apps = [
        {"id": "f1", "company": "Co", "stage": "applied"},
        {"id": "f2", "company": "Co", "stage": "applied"},
        {"id": "f3", "company": "Co", "stage": "screen"},
    ]
    async with Client(analytics_server) as client:
        result = await client.call_tool("funnel", {"apps": apps})
    data = result.structured_content
    assert data["counts"]["applied"] == 2
    assert data["counts"]["screen"] == 1


# ── full server mount ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_apply_and_analytics_mounted_in_main_server():
    from decroche.server import mcp

    async with Client(mcp) as client:
        names = [t.name for t in await client.list_tools()]
    assert any("apply" in n for n in names)
    assert any("analytics" in n for n in names)
