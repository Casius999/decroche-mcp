"""match sub-package — FastMCP sub-server exposing score, keyword_gap, and Phase-2b tools.

Tools (mounted under namespace "match" in the main server):
- score                : compute skill-coverage score between CV file and offer text
- keyword_gap          : top-N uncovered offer keywords with addable/missing status
- dedupe               : remove duplicate job postings
- success_probability  : deterministic success-probability estimate for a job posting
- company_intel        : derive company facts from postings + research checklist

All tools are thin wrappers. No LLM, no network.  Deterministic.
"""
from __future__ import annotations

from fastmcp import FastMCP

from decroche.cv.parse import parse_cv
from decroche.match.company_intel import company_intel as _company_intel
from decroche.match.dedupe import dedupe as _dedupe
from decroche.match.keyword_gap import keyword_gap as _keyword_gap
from decroche.match.score import match_score as _match_score
from decroche.match.success_probability import success_probability as _success_probability
from decroche.models import CompanyIntel, JobPosting, KeywordGap, MatchScore, SuccessProbability

match_server = FastMCP("match")


@match_server.tool
def score(cv_path: str, offer_text: str) -> MatchScore:
    """Compute a skill-coverage match score between a CV file and a job offer.

    Args:
        cv_path: Path to the CV file (PDF/DOCX/MD/TXT).
        offer_text: Raw job-offer/job-description text.

    Returns:
        MatchScore with score_0_100, per-requirement coverage, seniority_fit,
        and missing_must list.
    """
    cv_parse = parse_cv(cv_path)
    return _match_score(cv_parse.json_resume, offer_text)


@match_server.tool
def dedupe(jobs: list[JobPosting]) -> list[JobPosting]:
    """Remove duplicate job postings from a list.

    Uses SHA-256 blocking on normalised company|city|title, then within each
    block merges postings where ``token_set_ratio(title) ≥ 85`` AND dates are
    within ±14 calendar days (or absent).  Keeps the most-complete posting.

    Args:
        jobs: List of JobPosting objects (may contain duplicates across providers).

    Returns:
        Deduplicated list preserving the most-complete posting per cluster.
    """
    return _dedupe(jobs)


@match_server.tool
def keyword_gap(cv_path: str, offer_text: str, n: int = 5) -> list[KeywordGap]:
    """Return the top-N offer keywords not covered by the CV, ranked by salience.

    Each gap is classified as:
    - "addable_honestly": term or synonym appears anywhere in CV text.
    - "genuinely_missing": no trace in the CV at all.

    Args:
        cv_path: Path to the CV file (PDF/DOCX/MD/TXT).
        offer_text: Raw job-offer/job-description text.
        n: Maximum number of gaps to return (default 5).

    Returns:
        List of KeywordGap sorted by salience descending, length ≤ n.
    """
    cv_parse = parse_cv(cv_path)
    return _keyword_gap(cv_parse.json_resume, offer_text, n=n)


@match_server.tool
def success_probability(
    job: JobPosting,
    fit_score: float,
    network_proximity: float | None = None,
    applicants: int | None = None,
) -> SuccessProbability:
    """Estimate application success probability deterministically.

    Combines fit_score with recency, competition proxy, optional network proximity,
    and optional applicant count into a single 0–100 score with per-factor breakdown.

    Unknown signals default to neutral and are flagged in ``notes`` — never fabricated.

    Args:
        job:               Target job posting.
        fit_score:         Match score 0–100 (from match.score).
        network_proximity: Optional 0–1 float (closeness to hiring team).
        applicants:        Optional known applicant count.

    Returns:
        SuccessProbability with score_0_100, factors dict, confidence, and notes.
    """
    return _success_probability(
        job,
        fit_score,
        network_proximity=network_proximity,
        applicants=applicants,
    )


@match_server.tool
def company_intel(
    company: str,
    jobs: list[JobPosting] | None = None,
) -> CompanyIntel:
    """Derive company intelligence from job postings + produce research checklist.

    Only asserts facts derivable from the provided postings (open_roles_count,
    locations, remote_ratio, tech_tags).  Everything else (Glassdoor rating,
    funding, layoff signals, visa sponsorship) is placed in a research_checklist
    with status ``"to_research"`` — never fabricated.

    Args:
        company: Company name.
        jobs:    Optional list of JobPosting objects for this company.

    Returns:
        CompanyIntel with derived dict, research_checklist, and notes.
    """
    return _company_intel(company, jobs=jobs)
