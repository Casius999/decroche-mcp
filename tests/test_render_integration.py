"""Integration test: cv_render tool registered and callable via FastMCP Client."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastmcp import Client

from decroche.server import mcp


class TestRenderToolRegistered:
    @pytest.mark.asyncio
    async def test_cv_render_registered(self):
        async with Client(mcp) as client:
            names = [t.name for t in await client.list_tools()]
            assert any("render" in n and "cv" in n for n in names), (
                f"No cv render tool found. Tools: {names}"
            )

    @pytest.mark.asyncio
    async def test_existing_cv_tools_still_registered(self):
        """Ensure render didn't accidentally remove existing cv tools."""
        async with Client(mcp) as client:
            names = [t.name for t in await client.list_tools()]
            assert any("parse" in n and "cv" in n for n in names)
            assert any("xyz_scaffold" in n for n in names)
            assert any("verify_claims" in n for n in names)


class TestRenderToolCallable:
    @pytest.mark.asyncio
    async def test_cv_render_callable(self, fixtures_dir, tmp_path):
        """Call cv_render on a fixture CV and verify output structure."""
        async with Client(mcp) as client:
            names = [t.name for t in await client.list_tools()]
            render_name = next(n for n in names if "render" in n and "cv" in n)

            result = await client.call_tool(
                render_name,
                {
                    "cv_path": str(fixtures_dir / "sample_en.txt"),
                    "market_id": "fr",
                    "out_dir": str(tmp_path),
                },
            )
            data = result.structured_content
            assert isinstance(data, dict)
            assert "files" in data
            assert "ats_safe_proof" in data
            assert "warnings" in data

    @pytest.mark.asyncio
    async def test_cv_render_files_are_written(self, fixtures_dir, tmp_path):
        """Files listed in the result must actually exist on disk."""
        async with Client(mcp) as client:
            names = [t.name for t in await client.list_tools()]
            render_name = next(n for n in names if "render" in n and "cv" in n)

            result = await client.call_tool(
                render_name,
                {
                    "cv_path": str(fixtures_dir / "sample_en.txt"),
                    "market_id": "fr",
                    "out_dir": str(tmp_path),
                },
            )
            data = result.structured_content
            files = data.get("files", [])
            assert len(files) >= 3
            for f in files:
                p = Path(f["path"])
                assert p.exists(), f"File {f['path']} does not exist"
                assert p.stat().st_size > 0

    @pytest.mark.asyncio
    async def test_cv_render_ats_proof_populated(self, fixtures_dir, tmp_path):
        """ats_safe_proof must contain at least workday score."""
        async with Client(mcp) as client:
            names = [t.name for t in await client.list_tools()]
            render_name = next(n for n in names if "render" in n and "cv" in n)

            result = await client.call_tool(
                render_name,
                {
                    "cv_path": str(fixtures_dir / "sample_en.txt"),
                    "market_id": "fr",
                    "out_dir": str(tmp_path),
                },
            )
            data = result.structured_content
            proof = data.get("ats_safe_proof", {})
            assert len(proof) >= 1
            assert "workday" in proof or "generic" in proof

    @pytest.mark.asyncio
    async def test_cv_render_default_out_dir(self, fixtures_dir):
        """cv_render with no out_dir should use a temp dir and not crash."""
        async with Client(mcp) as client:
            names = [t.name for t in await client.list_tools()]
            render_name = next(n for n in names if "render" in n and "cv" in n)

            result = await client.call_tool(
                render_name,
                {
                    "cv_path": str(fixtures_dir / "sample_en.txt"),
                    "market_id": "us",
                },
            )
            data = result.structured_content
            assert "files" in data
            assert len(data["files"]) >= 1
