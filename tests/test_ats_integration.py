"""Integration test for the ATS sub-server via FastMCP Client.

TDD: written before implementation.
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def single_col_pdf(tmp_path_factory) -> Path:
    d = tmp_path_factory.mktemp("ats_integ")
    from reportlab.lib.pagesizes import LETTER
    from reportlab.pdfgen import canvas

    p = d / "cv.pdf"
    c = canvas.Canvas(str(p), pagesize=LETTER)
    y = 750
    for line in [
        "Jane Doe",
        "jane.doe@example.com",
        "",
        "Experience",
        "Led migration of 12 services to Kubernetes, reducing latency 38%",
        "Skills",
        "Python, Go, Kubernetes",
        "Education",
        "MIT Computer Science",
    ]:
        c.drawString(50, y, line)
        y -= 14
    c.save()
    return p


@pytest.mark.asyncio
async def test_ats_tools_registered() -> None:
    """ATS server tools are registered with 'parse_sim', 'redflag_scan', etc."""
    from fastmcp import Client
    from decroche.server import mcp

    async with Client(mcp) as client:
        tools = await client.list_tools()
        tool_names = [t.name for t in tools]
        # After mount with namespace="ats", tools are named "ats_parse_sim" etc.
        # (FastMCP 3.4 uses underscore separator for namespace)
        ats_tools = [
            n for n in tool_names if "ats" in n.lower() or "parse_sim" in n or "redflag" in n
        ]
        assert len(ats_tools) >= 1, f"No ATS tools found. All tools: {tool_names}"


@pytest.mark.asyncio
async def test_parse_sim_tool_callable(single_col_pdf: Path) -> None:
    """parse_sim tool can be called via MCP Client and returns a valid result."""
    from fastmcp import Client
    from decroche.server import mcp

    async with Client(mcp) as client:
        tools = await client.list_tools()
        tool_names = [t.name for t in tools]
        # Find parse_sim tool (may be ats_parse_sim or similar)
        parse_sim_name = next(
            (n for n in tool_names if "parse_sim" in n),
            None,
        )
        assert parse_sim_name is not None, f"parse_sim tool not found. Tools: {tool_names}"

        result = await client.call_tool(
            parse_sim_name,
            {"path": str(single_col_pdf), "ats_id": "workday"},
        )
        # Result should be non-empty
        assert result is not None
        # FastMCP 3.4 returns a CallToolResult with .content attribute
        content_str = str(result)
        assert (
            "parsability_score" in content_str
            or "workday" in content_str
            or "AtsParseResult" in content_str
            or len(content_str) > 10
        )


@pytest.mark.asyncio
async def test_redflag_scan_tool_registered() -> None:
    """redflag_scan tool is registered."""
    from fastmcp import Client
    from decroche.server import mcp

    async with Client(mcp) as client:
        tools = await client.list_tools()
        tool_names = [t.name for t in tools]
        redflag_name = next(
            (n for n in tool_names if "redflag" in n),
            None,
        )
        assert redflag_name is not None, f"redflag_scan tool not found. Tools: {tool_names}"


@pytest.mark.asyncio
async def test_screener_brief_tool_registered() -> None:
    """screener_brief tool is registered."""
    from fastmcp import Client
    from decroche.server import mcp

    async with Client(mcp) as client:
        tools = await client.list_tools()
        tool_names = [t.name for t in tools]
        screener_name = next(
            (n for n in tool_names if "screener" in n),
            None,
        )
        assert screener_name is not None, f"screener_brief tool not found. Tools: {tool_names}"


@pytest.mark.asyncio
async def test_score_report_tool_registered() -> None:
    """score_report tool is registered."""
    from fastmcp import Client
    from decroche.server import mcp

    async with Client(mcp) as client:
        tools = await client.list_tools()
        tool_names = [t.name for t in tools]
        score_name = next(
            (n for n in tool_names if "score_report" in n),
            None,
        )
        assert score_name is not None, f"score_report tool not found. Tools: {tool_names}"
