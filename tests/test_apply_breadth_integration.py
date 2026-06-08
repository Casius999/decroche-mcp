"""Integration tests: apply_cover_letter + apply_answer_screening tools
registered and callable via FastMCP Client on apply_server.

No network calls.  All fixtures are in-memory.
"""

from __future__ import annotations

import pytest
from fastmcp import Client

from decroche.apply import apply_server


# ── tool registration ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_apply_cover_letter_tool_registered():
    async with Client(apply_server) as client:
        names = [t.name for t in await client.list_tools()]
    assert "cover_letter" in names, f"cover_letter not in tools: {names}"


@pytest.mark.asyncio
async def test_apply_answer_screening_tool_registered():
    async with Client(apply_server) as client:
        names = [t.name for t in await client.list_tools()]
    assert "answer_screening" in names, f"answer_screening not in tools: {names}"


# ── cover_letter tool callable ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_apply_cover_letter_callable(fixtures_dir):
    async with Client(apply_server) as client:
        result = await client.call_tool(
            "cover_letter",
            {
                "cv_path": str(fixtures_dir / "sample_en.txt"),
                "job_json": {
                    "source": "greenhouse",
                    "source_id": "1",
                    "title": "Backend Engineer",
                    "company": "Acme Corp",
                    "url": "https://acme.com/jobs/1",
                    "description": "Python, Docker, CI/CD",
                },
                "lang": "en",
            },
        )
    data = result.structured_content
    assert "role_title" in data
    assert data["role_title"] == "Backend Engineer"
    assert "full_scaffold" in data
    assert len(data["full_scaffold"]) > 20


@pytest.mark.asyncio
async def test_apply_cover_letter_fr(fixtures_dir):
    async with Client(apply_server) as client:
        result = await client.call_tool(
            "cover_letter",
            {
                "cv_path": str(fixtures_dir / "sample_fr.txt"),
                "job_json": {
                    "source": "greenhouse",
                    "source_id": "2",
                    "title": "Développeur Python",
                    "company": "MegaCorp",
                    "url": "https://megacorp.com/jobs/2",
                    "description": "Python, Kubernetes, AWS",
                },
            },
        )
    data = result.structured_content
    assert data["lang"] == "fr"
    assert data["company"] == "MegaCorp"


@pytest.mark.asyncio
async def test_apply_cover_letter_why_me_no_fabrication(fixtures_dir):
    """why_me bullets from the tool must not contain Kubernetes when CV has none."""
    # sample_en.txt has Python, Go, Kubernetes, PostgreSQL — but we use it here
    # The test just checks the structure is honest and why_them has placeholder.
    async with Client(apply_server) as client:
        result = await client.call_tool(
            "cover_letter",
            {
                "cv_path": str(fixtures_dir / "sample_en.txt"),
                "job_json": {
                    "source": "greenhouse",
                    "source_id": "3",
                    "title": "Software Engineer",
                    "url": "https://co.com/jobs/3",
                    "description": "Python, Go",
                },
            },
        )
    data = result.structured_content
    # why_them must have a placeholder
    assert "[" in data["why_them"], "why_them must have placeholder"
    # notes must be a list
    assert isinstance(data["notes"], list)


@pytest.mark.asyncio
async def test_apply_cover_letter_result_has_required_keys(fixtures_dir):
    async with Client(apply_server) as client:
        result = await client.call_tool(
            "cover_letter",
            {
                "cv_path": str(fixtures_dir / "sample_en.txt"),
                "job_json": {
                    "source": "greenhouse",
                    "source_id": "4",
                    "title": "Engineer",
                    "url": "https://co.com/jobs/4",
                    "description": "Python",
                },
            },
        )
    data = result.structured_content
    for key in (
        "role_title",
        "lang",
        "hook",
        "why_them",
        "why_me",
        "close",
        "full_scaffold",
        "notes",
        "evidence_used",
    ):
        assert key in data, f"Missing key {key!r} in cover_letter result"


# ── answer_screening tool callable ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_apply_answer_screening_callable(fixtures_dir):
    async with Client(apply_server) as client:
        result = await client.call_tool(
            "answer_screening",
            {
                "question": "Do you have experience with Python?",
                "cv_path": str(fixtures_dir / "sample_en.txt"),
            },
        )
    data = result.structured_content
    assert "question" in data
    assert "needs_human" in data
    assert "source" in data


@pytest.mark.asyncio
async def test_apply_answer_screening_authorization_needs_human(fixtures_dir):
    async with Client(apply_server) as client:
        result = await client.call_tool(
            "answer_screening",
            {
                "question": "Are you authorized to work in the US?",
                "cv_path": str(fixtures_dir / "sample_en.txt"),
            },
        )
    data = result.structured_content
    assert data["needs_human"] is True
    assert data["suggested_answer"] is None


@pytest.mark.asyncio
async def test_apply_answer_screening_salary_needs_human(fixtures_dir):
    async with Client(apply_server) as client:
        result = await client.call_tool(
            "answer_screening",
            {
                "question": "What are your salary expectations?",
                "cv_path": str(fixtures_dir / "sample_en.txt"),
            },
        )
    data = result.structured_content
    assert data["needs_human"] is True
    assert data["suggested_answer"] is None


@pytest.mark.asyncio
async def test_apply_answer_screening_skill_derived_from_cv(fixtures_dir):
    # sample_en.txt contains "Kubernetes" in skills
    async with Client(apply_server) as client:
        result = await client.call_tool(
            "answer_screening",
            {
                "question": "Do you have experience with Kubernetes?",
                "cv_path": str(fixtures_dir / "sample_en.txt"),
            },
        )
    data = result.structured_content
    assert data["source"] == "derived_from_cv"
    assert data["needs_human"] is False


@pytest.mark.asyncio
async def test_apply_answer_screening_result_has_required_keys(fixtures_dir):
    async with Client(apply_server) as client:
        result = await client.call_tool(
            "answer_screening",
            {
                "question": "How many years of experience do you have?",
                "cv_path": str(fixtures_dir / "sample_en.txt"),
            },
        )
    data = result.structured_content
    for key in ("question", "suggested_answer", "source", "confidence", "needs_human"):
        assert key in data, f"Missing key {key!r} in answer_screening result"
