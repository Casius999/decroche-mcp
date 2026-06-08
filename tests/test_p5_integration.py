"""Phase 5 integration tests — interview + negotiate tools registered and callable."""

from __future__ import annotations

import asyncio

import pytest

from decroche.interview import interview_server
from decroche.negotiate import negotiate_server
from decroche.server import mcp


# ── Tool registration ────────────────────────────────────────────────────────────


def _tool_names(server) -> set[str]:
    """Return the set of tool names registered on a FastMCP server (async)."""
    tools = asyncio.run(server.list_tools())
    return {t.name for t in tools}


def test_interview_server_has_company_brief():
    assert "company_brief" in _tool_names(interview_server)


def test_interview_server_has_story_add():
    assert "story_add" in _tool_names(interview_server)


def test_interview_server_has_story_suggest():
    assert "story_suggest" in _tool_names(interview_server)


def test_interview_server_has_question_bank():
    assert "question_bank" in _tool_names(interview_server)


def test_interview_server_has_mock_evaluate():
    assert "mock_evaluate" in _tool_names(interview_server)


def test_interview_server_has_thank_you():
    assert "thank_you" in _tool_names(interview_server)


def test_interview_server_has_debrief():
    assert "debrief" in _tool_names(interview_server)


def test_negotiate_server_has_benchmark_range():
    assert "benchmark_range" in _tool_names(negotiate_server)


def test_negotiate_server_has_counter_offer_template():
    assert "counter_offer_template" in _tool_names(negotiate_server)


def test_negotiate_server_has_total_comp():
    assert "total_comp" in _tool_names(negotiate_server)


def test_negotiate_server_has_competing_offer_script():
    assert "competing_offer_script" in _tool_names(negotiate_server)


# ── Main server mounts ────────────────────────────────────────────────────────────


def _mcp_tool_names() -> set[str]:
    """Return all tools visible from the top-level mcp server."""
    tools = asyncio.run(mcp.list_tools())
    return {t.name for t in tools}


def test_mcp_has_interview_namespace_tools():
    names = _mcp_tool_names()
    interview_tools = {
        n for n in names if "company_brief" in n or "mock_evaluate" in n or "question_bank" in n
    }
    assert len(interview_tools) > 0, f"No interview tools found in: {sorted(names)[:30]}"


def test_mcp_has_negotiate_namespace_tools():
    names = _mcp_tool_names()
    neg_tools = {
        n for n in names if "benchmark_range" in n or "counter_offer" in n or "total_comp" in n
    }
    assert len(neg_tools) > 0, f"No negotiate tools found in: {sorted(names)[:30]}"


# ── Callable end-to-end ────────────────────────────────────────────────────────────


def test_interview_company_brief_callable():
    from decroche.interview.company_brief import company_brief

    result = company_brief("Acme")
    assert result.company == "Acme"
    assert len(result.sections) == 5


def test_interview_question_bank_callable():
    from decroche.interview.questions import question_bank

    result = question_bank("software", "behavioral")
    assert len(result) > 0


def test_interview_mock_evaluate_callable():
    from decroche.interview.mock import mock_evaluate

    result = mock_evaluate("I solved a big problem and we got 20% improvement.")
    assert result.score_0_100 >= 0
    assert result.score_band in ("low", "med", "high")


def test_interview_thank_you_callable():
    from decroche.interview.followup import thank_you

    result = thank_you("Sophie", "PM Senior", lang="fr")
    assert "Sophie" in result


def test_negotiate_benchmark_callable():
    from decroche.negotiate.benchmark import benchmark_range

    result = benchmark_range("software", "mid", "fr")
    assert result.p50 > 0


def test_negotiate_total_comp_callable():
    from decroche.negotiate.counter import total_comp

    # base=60000, variable=6000 (10%), signing=2500 (10000/4yr), equity=0
    # total = 60000 + 6000 + 2500 = 68500
    result = total_comp(base=60000, variable_pct=0.10, signing=10000, years=4)
    assert result.total == pytest.approx(68500.0)


def test_negotiate_counter_offer_callable():
    from decroche.negotiate.counter import counter_offer_template

    offer = {
        "company": "CorpX",
        "role": "Dev",
        "amount": 50000,
        "currency": "EUR",
        "hiring_manager": "Alice",
    }
    target = {
        "base": 60000,
        "role_family": "software",
        "seniority": "mid",
        "region": "fr",
        "p50": 55000,
        "p75": 65000,
        "source": "APEC 2024",
    }
    result = counter_offer_template(offer, target, market_id="fr")
    assert "CorpX" in result.body
    assert result.target == 60000.0
