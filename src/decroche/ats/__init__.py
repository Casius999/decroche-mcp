"""ATS sub-server — double-reader diagnostic tools.

Mounts as namespace "ats" in the main decroche-mcp server.
All tools are deterministic (no LLM, no network, no secrets).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from decroche.ats.parse_sim import parse_sim as _parse_sim
from decroche.ats.redflag_scan import redflag_scan as _redflag_scan
from decroche.ats.screener_brief import screener_brief as _screener_brief
from decroche.ats.score_report import score_report as _score_report
from decroche.models import (
    AtsParseResult,
    JSONResume,
    RedFlag,
    ScreenerKit,
    ScoreReport,
)

ats_server = FastMCP("ats")


@ats_server.tool()
def parse_sim(path: str, ats_id: str, fmt: str | None = None) -> AtsParseResult:
    """Simulate how an ATS parses the CV file.

    Analyses the raw file structure (columns, tables, header/footer contact,
    file size, text density) and applies the target ATS's quirks rules to
    compute a parsability score (0–100) and a list of breakages with fixes.

    Args:
        path: Absolute path to the CV file (PDF, DOCX, TXT, or MD).
        ats_id: Target ATS identifier. Valid values:
            workday, greenhouse, lever, taleo_oracle, icims, smartrecruiters,
            ashby, bamboohr, recruitee, generic.
        fmt: Optional format override ("pdf", "docx", "txt", "md").

    Returns:
        AtsParseResult with parsability_score, breakages, fields_extracted,
        and fields_lost.
    """
    return _parse_sim(Path(path), ats_id, fmt=fmt)


@ats_server.tool()
def redflag_scan(
    json_resume: dict[str, Any],
    raw_text: str,
    market_id: str = "fr",
    has_photo: bool = False,
) -> list[RedFlag]:
    """Scan a parsed CV for content red flags.

    Implements all red-flag checks from data/redflags.yaml:
    passive voice, duty bullets without metric/strong verb, employment gaps,
    job-hopping, banned buzzwords, year-only dates, unprofessional email,
    wrong photo for market, AI-generic phrasing, no quantification.

    Args:
        json_resume: JSONResume-compatible dict (output of cv.parse).
        raw_text: Raw text of the CV as extracted from the file.
        market_id: Target market (fr, us, uk, ca, ca-en, ca-fr).
        has_photo: Whether the CV contains a photo.

    Returns:
        List of RedFlag objects with flag_id, severity, location, evidence, fix.
    """
    jr = JSONResume.model_validate(json_resume)
    return _redflag_scan(jr, raw_text, market_id=market_id, has_photo=has_photo)


@ats_server.tool()
def screener_brief(
    json_resume: dict[str, Any],
    offer_text: str,
    ats_id: str,
) -> ScreenerKit:
    """Build a screener simulation kit for Claude.

    Produces the plain text the machine sees after ATS parsing, a fixed
    scoring rubric, and deterministic keyword requirements extracted from
    the offer. Claude then plays the AI screener on this exact text.

    Args:
        json_resume: JSONResume-compatible dict (output of cv.parse).
        offer_text: Raw job offer text or job description.
        ats_id: Target ATS identifier.

    Returns:
        ScreenerKit with machine_view_text, rubric, requirements, ats_id.
    """
    jr = JSONResume.model_validate(json_resume)
    return _screener_brief(jr, offer_text, ats_id)


@ats_server.tool()
def score_report(
    before: dict[str, Any],
    after: dict[str, Any] | None = None,
    match: float | None = None,
    redflag_count: int = 0,
) -> ScoreReport:
    """Generate a before/after score report.

    Combines the parsability score, optional match score, and redflag count
    into a ScoreReport with screener_readiness tier and optional delta.

    Args:
        before: AtsParseResult dict (before optimisation).
        after: Optional AtsParseResult dict (after optimisation) for delta.
        match: Optional keyword match score 0–100.
        redflag_count: Number of red flags detected by redflag_scan.

    Returns:
        ScoreReport with parsability, match, screener_readiness, redflag_count,
        and delta (if after is provided).
    """
    before_model = AtsParseResult.model_validate(before)
    after_model = AtsParseResult.model_validate(after) if after is not None else None
    return _score_report(before_model, after=after_model, match=match, redflag_count=redflag_count)
