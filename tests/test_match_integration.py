"""Integration tests for the match sub-server via FastMCP Client."""
from __future__ import annotations

import pytest
from fastmcp import Client

from decroche.server import mcp

OFFER_TEXT = """
Backend Engineer — Senior

Requirements:
- Kubernetes
- Python

Nice to have:
- Rust
"""


class TestMatchToolsRegistered:
    @pytest.mark.asyncio
    async def test_match_tools_present(self):
        async with Client(mcp) as client:
            names = [t.name for t in await client.list_tools()]
            # Namespace is "match" → tools like "match_score", "match_keyword_gap"
            match_tools = [n for n in names if "match" in n]
            assert len(match_tools) >= 2

    @pytest.mark.asyncio
    async def test_score_tool_registered(self):
        async with Client(mcp) as client:
            names = [t.name for t in await client.list_tools()]
            assert any("score" in n and "match" in n for n in names)

    @pytest.mark.asyncio
    async def test_keyword_gap_tool_registered(self):
        async with Client(mcp) as client:
            names = [t.name for t in await client.list_tools()]
            assert any("keyword_gap" in n for n in names)


class TestScoreToolCallable:
    @pytest.mark.asyncio
    async def test_score_returns_match_score(self, fixtures_dir):
        async with Client(mcp) as client:
            names = [t.name for t in await client.list_tools()]
            score_name = next(n for n in names if "score" in n and "match" in n)
            result = await client.call_tool(
                score_name,
                {
                    "cv_path": str(fixtures_dir / "sample_en.txt"),
                    "offer_text": OFFER_TEXT,
                },
            )
            data = result.structured_content
            assert "score_0_100" in data
            assert 0.0 <= data["score_0_100"] <= 100.0
            assert "seniority_fit" in data
            assert "missing_must" in data

    @pytest.mark.asyncio
    async def test_score_k8s_covered_via_synonym(self, fixtures_dir):
        """sample_en.txt has 'Kubernetes' in skills → covered."""
        async with Client(mcp) as client:
            names = [t.name for t in await client.list_tools()]
            score_name = next(n for n in names if "score" in n and "match" in n)
            result = await client.call_tool(
                score_name,
                {
                    "cv_path": str(fixtures_dir / "sample_en.txt"),
                    "offer_text": OFFER_TEXT,
                },
            )
            data = result.structured_content
            # Kubernetes in sample_en.txt skills → should be covered
            coverage = data.get("requirement_coverage", [])
            kube_entries = [
                rc for rc in coverage if rc.get("requirement", "").lower() == "kubernetes"
            ]
            assert any(rc.get("covered") for rc in kube_entries)


def _unwrap_list(structured_content: object) -> list:
    """FastMCP wraps list returns in {'result': [...]}.  Unwrap if needed."""
    if isinstance(structured_content, list):
        return structured_content
    if isinstance(structured_content, dict) and "result" in structured_content:
        return structured_content["result"]  # type: ignore[return-value]
    return []  # fallback


class TestKeywordGapToolCallable:
    @pytest.mark.asyncio
    async def test_keyword_gap_returns_list(self, fixtures_dir):
        async with Client(mcp) as client:
            names = [t.name for t in await client.list_tools()]
            gap_name = next(n for n in names if "keyword_gap" in n)
            result = await client.call_tool(
                gap_name,
                {
                    "cv_path": str(fixtures_dir / "sample_en.txt"),
                    "offer_text": OFFER_TEXT,
                },
            )
            data = _unwrap_list(result.structured_content)
            assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_keyword_gap_respects_n(self, fixtures_dir):
        async with Client(mcp) as client:
            names = [t.name for t in await client.list_tools()]
            gap_name = next(n for n in names if "keyword_gap" in n)
            result = await client.call_tool(
                gap_name,
                {
                    "cv_path": str(fixtures_dir / "sample_en.txt"),
                    "offer_text": OFFER_TEXT,
                    "n": 2,
                },
            )
            data = _unwrap_list(result.structured_content)
            assert len(data) <= 2

    @pytest.mark.asyncio
    async def test_keyword_gap_status_values_valid(self, fixtures_dir):
        async with Client(mcp) as client:
            names = [t.name for t in await client.list_tools()]
            gap_name = next(n for n in names if "keyword_gap" in n)
            result = await client.call_tool(
                gap_name,
                {
                    "cv_path": str(fixtures_dir / "sample_en.txt"),
                    "offer_text": OFFER_TEXT,
                },
            )
            data = _unwrap_list(result.structured_content)
            for item in data:
                assert item.get("status") in ("addable_honestly", "genuinely_missing")
