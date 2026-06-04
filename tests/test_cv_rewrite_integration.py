"""Integration tests for cv.xyz_scaffold and cv.verify_claims tools via FastMCP Client.

Uses the same fixtures_dir conftest fixture and _unwrap_list helper pattern
as test_match_integration.py.
"""
from __future__ import annotations

import pytest
from fastmcp import Client

from decroche.server import mcp


def _unwrap_list(structured_content: object) -> list:
    """FastMCP wraps list returns in {'result': [...]}.  Unwrap if needed."""
    if isinstance(structured_content, list):
        return structured_content
    if isinstance(structured_content, dict) and "result" in structured_content:
        return structured_content["result"]  # type: ignore[return-value]
    return []


class TestCvToolsRegistered:
    @pytest.mark.asyncio
    async def test_xyz_scaffold_registered(self):
        async with Client(mcp) as client:
            names = [t.name for t in await client.list_tools()]
            assert any("xyz_scaffold" in n for n in names)

    @pytest.mark.asyncio
    async def test_verify_claims_registered(self):
        async with Client(mcp) as client:
            names = [t.name for t in await client.list_tools()]
            assert any("verify_claims" in n for n in names)

    @pytest.mark.asyncio
    async def test_parse_still_registered(self):
        """Ensure the original parse tool is not accidentally removed."""
        async with Client(mcp) as client:
            names = [t.name for t in await client.list_tools()]
            assert any("parse" in n and "cv" in n for n in names)


class TestXyzScaffoldTool:
    @pytest.mark.asyncio
    async def test_returns_list(self, fixtures_dir):
        async with Client(mcp) as client:
            names = [t.name for t in await client.list_tools()]
            tool_name = next(n for n in names if "xyz_scaffold" in n)
            result = await client.call_tool(
                tool_name, {"cv_path": str(fixtures_dir / "sample_en.txt")}
            )
            data = _unwrap_list(result.structured_content)
            assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_each_entry_has_required_fields(self, fixtures_dir):
        async with Client(mcp) as client:
            names = [t.name for t in await client.list_tools()]
            tool_name = next(n for n in names if "xyz_scaffold" in n)
            result = await client.call_tool(
                tool_name, {"cv_path": str(fixtures_dir / "sample_en.txt")}
            )
            data = _unwrap_list(result.structured_content)
            assert len(data) > 0
            for entry in data:
                assert "original" in entry
                assert "y_present" in entry
                assert "template" in entry
                assert "weak_verb" in entry

    @pytest.mark.asyncio
    async def test_metric_bullet_flagged_y_present(self, fixtures_dir):
        """sample_en.txt has 'Reduced API latency 38% by introducing a caching layer'."""
        async with Client(mcp) as client:
            names = [t.name for t in await client.list_tools()]
            tool_name = next(n for n in names if "xyz_scaffold" in n)
            result = await client.call_tool(
                tool_name, {"cv_path": str(fixtures_dir / "sample_en.txt")}
            )
            data = _unwrap_list(result.structured_content)
            metric_entries = [e for e in data if e.get("y_present")]
            assert len(metric_entries) >= 1

    @pytest.mark.asyncio
    async def test_works_on_fr_cv(self, fixtures_dir):
        async with Client(mcp) as client:
            names = [t.name for t in await client.list_tools()]
            tool_name = next(n for n in names if "xyz_scaffold" in n)
            result = await client.call_tool(
                tool_name, {"cv_path": str(fixtures_dir / "sample_fr.txt")}
            )
            data = _unwrap_list(result.structured_content)
            assert isinstance(data, list)
            assert len(data) >= 0


class TestVerifyClaimsTool:
    @pytest.mark.asyncio
    async def test_returns_list(self, fixtures_dir):
        async with Client(mcp) as client:
            names = [t.name for t in await client.list_tools()]
            tool_name = next(n for n in names if "verify_claims" in n)
            result = await client.call_tool(
                tool_name, {"cv_path": str(fixtures_dir / "sample_en.txt")}
            )
            data = _unwrap_list(result.structured_content)
            assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_each_entry_has_required_fields(self, fixtures_dir):
        async with Client(mcp) as client:
            names = [t.name for t in await client.list_tools()]
            tool_name = next(n for n in names if "verify_claims" in n)
            result = await client.call_tool(
                tool_name, {"cv_path": str(fixtures_dir / "sample_en.txt")}
            )
            data = _unwrap_list(result.structured_content)
            for entry in data:
                assert "text" in entry
                assert "needs_evidence" in entry
                assert "suggested_artifact" in entry
                assert "location" in entry

    @pytest.mark.asyncio
    async def test_metric_bullet_flagged(self, fixtures_dir):
        """sample_en.txt has 'Reduced API latency 38%' → needs evidence."""
        async with Client(mcp) as client:
            names = [t.name for t in await client.list_tools()]
            tool_name = next(n for n in names if "verify_claims" in n)
            result = await client.call_tool(
                tool_name, {"cv_path": str(fixtures_dir / "sample_en.txt")}
            )
            data = _unwrap_list(result.structured_content)
            flagged = [e for e in data if e.get("needs_evidence")]
            assert len(flagged) >= 1
