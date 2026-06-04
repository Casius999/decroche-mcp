"""source sub-package — FastMCP sub-server exposing job-board tools.

Keyless tools:
- greenhouse(board_token)        : Greenhouse Boards API
- lever(company)                 : Lever Postings API
- ashby(job_board_name)          : Ashby Job Board API
- recruitee(company)             : Recruitee Offers API
- workable(account)              : Workable SPI v3
- smartrecruiters(company_id)    : SmartRecruiters Posting API
- remoteok()                     : RemoteOK API (all remote jobs)
- remotive(search)               : Remotive API (optional search filter)
- arbeitnow()                    : Arbeitnow Job Board API
- search_all(...)                : Concurrent aggregation across providers

Keyed tools (require env vars — raise ToolError if absent):
- france_travail(query, location)  : France Travail v2 (FRANCE_TRAVAIL_ID/SECRET)
- adzuna(query, country)           : Adzuna (ADZUNA_APP_ID/APP_KEY)
- jsearch(query)                   : JSearch/RapidAPI (JSEARCH_RAPIDAPI_KEY)
- usajobs(query)                   : USAJobs federal (USAJOBS_KEY/EMAIL)
- reed(query)                      : Reed.co.uk UK (REED_KEY)
- themuse(category)                : The Muse (THEMUSE_KEY optional)
- jooble(query, location)          : Jooble (JOOBLE_KEY)

Network errors per keyless provider are caught and surfaced as ``warnings``.
Keyed providers propagate ToolError (missing key) directly.
"""
from __future__ import annotations

from fastmcp import FastMCP

from decroche.models import JobPosting, MonitorDiff, SourceResult
from decroche.source.aggregate import search_all as _search_all
from decroche.source.monitor import monitor_diff as _monitor_diff
from decroche.source.monitor import monitor_snapshot as _monitor_snapshot
from decroche.source.providers import (
    adzuna as _adzuna,
    arbeitnow as _arbeitnow,
    ashby as _ashby,
    france_travail as _france_travail,
    greenhouse as _greenhouse,
    jooble as _jooble,
    jsearch as _jsearch,
    lever as _lever,
    recruitee as _recruitee,
    reed as _reed,
    remoteok as _remoteok,
    remotive as _remotive,
    smartrecruiters as _smartrecruiters,
    themuse as _themuse,
    usajobs as _usajobs,
    workable as _workable,
)

source_server = FastMCP("source")


# ── helpers ─────────────────────────────────────────────────────────────────────────────

def _wrap_network_error(func):  # type: ignore[return]  (used as decorator factory below)
    """(Not used as a decorator — inline try/except in each tool for clarity.)"""
    pass


async def _safe_fetch_and_normalize(provider: str, coro, normalize_fn, **norm_kwargs) -> SourceResult:
    """Fetch + normalize a single provider; turn any exception into a warning."""
    warnings: list[str] = []
    jobs: list[JobPosting] = []
    try:
        raw = await coro
        jobs = normalize_fn(raw, **norm_kwargs)
    except Exception as exc:
        warnings.append(f"{provider} error: {type(exc).__name__}: {exc}")
    return SourceResult(
        provider=provider,
        query=None,
        count=len(jobs),
        jobs=jobs,
        warnings=warnings,
    )


# ── tools ──────────────────────────────────────────────────────────────────────────────

@source_server.tool
async def greenhouse(board_token: str) -> SourceResult:
    """Fetch all live jobs from a Greenhouse job board (no auth required).

    Args:
        board_token: The board token slug (e.g. ``"acmecorp"``).

    Returns:
        SourceResult with all normalised job postings for this board.
    """
    return await _safe_fetch_and_normalize(
        "greenhouse",
        _greenhouse.fetch(board_token),
        _greenhouse.normalize,
        company=board_token,
    )


@source_server.tool
async def lever(company: str) -> SourceResult:
    """Fetch all published postings from a Lever company page (no auth required).

    Args:
        company: The Lever company slug (e.g. ``"techstart"``).

    Returns:
        SourceResult with all normalised job postings.
    """
    return await _safe_fetch_and_normalize(
        "lever",
        _lever.fetch(company),
        _lever.normalize,
        company=company,
    )


@source_server.tool
async def ashby(job_board_name: str) -> SourceResult:
    """Fetch all listed jobs from an Ashby job board (no auth required).

    Args:
        job_board_name: The Ashby job board name / slug (e.g. ``"novacorp"``).

    Returns:
        SourceResult with all normalised job postings.
    """
    return await _safe_fetch_and_normalize(
        "ashby",
        _ashby.fetch(job_board_name),
        _ashby.normalize,
        company=job_board_name,
    )


@source_server.tool
async def recruitee(company: str) -> SourceResult:
    """Fetch all open offers from a Recruitee company page (no auth required).

    Args:
        company: The Recruitee company subdomain (e.g. ``"recruitee-demo"``).

    Returns:
        SourceResult with all normalised job postings.
    """
    return await _safe_fetch_and_normalize(
        "recruitee",
        _recruitee.fetch(company),
        _recruitee.normalize,
        company=company,
    )


@source_server.tool
async def workable(account: str) -> SourceResult:
    """Fetch all published jobs from a Workable account (no auth required for public listings).

    Args:
        account: The Workable account subdomain (e.g. ``"megacorp"``).

    Returns:
        SourceResult with all normalised job postings.
    """
    return await _safe_fetch_and_normalize(
        "workable",
        _workable.fetch(account),
        _workable.normalize,
        company=account,
    )


@source_server.tool
async def smartrecruiters(company_id: str) -> SourceResult:
    """Fetch all public postings from SmartRecruiters Posting API (no auth required).

    Args:
        company_id: The SmartRecruiters company identifier (e.g. ``"SmartCoSA"``).

    Returns:
        SourceResult with all normalised job postings.
    """
    return await _safe_fetch_and_normalize(
        "smartrecruiters",
        _smartrecruiters.fetch(company_id),
        _smartrecruiters.normalize,
        company=company_id,
    )


@source_server.tool
async def remoteok() -> SourceResult:
    """Fetch all remote jobs from RemoteOK API (no auth required; attribution: remoteok.com).

    Returns:
        SourceResult with all normalised job postings.
    """
    return await _safe_fetch_and_normalize(
        "remoteok",
        _remoteok.fetch(),
        _remoteok.normalize,
    )


@source_server.tool
async def remotive(search: str = "") -> SourceResult:
    """Fetch remote jobs from Remotive API, optionally filtered by search query.

    Args:
        search: Optional keyword search string (e.g. ``"python backend"``).

    Returns:
        SourceResult with matching normalised job postings.
    """
    result = SourceResult(provider="remotive", query=search or None, count=0)
    warnings: list[str] = []
    jobs: list[JobPosting] = []
    try:
        raw = await _remotive.fetch(search)
        jobs = _remotive.normalize(raw)
    except Exception as exc:
        warnings.append(f"remotive error: {type(exc).__name__}: {exc}")
    result = SourceResult(
        provider="remotive",
        query=search or None,
        count=len(jobs),
        jobs=jobs,
        warnings=warnings,
    )
    return result


@source_server.tool
async def arbeitnow() -> SourceResult:
    """Fetch all jobs from the Arbeitnow public job board (no auth required).

    Returns:
        SourceResult with all normalised job postings.
    """
    return await _safe_fetch_and_normalize(
        "arbeitnow",
        _arbeitnow.fetch(),
        _arbeitnow.normalize,
    )


# ── keyed provider tools ──────────────────────────────────────────────────────────────────────

@source_server.tool
async def france_travail(query: str, location: str = "") -> SourceResult:
    """Fetch jobs from France Travail (Pôle Emploi) API v2.

    Requires env: FRANCE_TRAVAIL_ID, FRANCE_TRAVAIL_SECRET

    Args:
        query:    Keywords to search for (e.g. ``"développeur python"``).
        location: Optional commune code or city name.

    Returns:
        SourceResult with normalised job postings.

    Raises:
        ToolError: if required environment variables are not set.
    """
    raw = await _france_travail.fetch(query, location=location)
    jobs = _france_travail.normalize(raw)
    return SourceResult(
        provider="france_travail",
        query=query,
        count=len(jobs),
        jobs=jobs,
    )


@source_server.tool
async def adzuna(query: str, country: str = "fr") -> SourceResult:
    """Fetch jobs from Adzuna (19 countries).

    Requires env: ADZUNA_APP_ID, ADZUNA_APP_KEY

    Args:
        query:   Keywords to search for.
        country: Two-letter country code (default ``"fr"``).

    Returns:
        SourceResult with normalised job postings.

    Raises:
        ToolError: if required environment variables are not set.
    """
    raw = await _adzuna.fetch(query, country=country)
    jobs = _adzuna.normalize(raw)
    return SourceResult(
        provider="adzuna",
        query=query,
        count=len(jobs),
        jobs=jobs,
    )


@source_server.tool
async def jsearch(query: str) -> SourceResult:
    """Fetch jobs from JSearch (RapidAPI) — aggregates LinkedIn/Indeed/Glassdoor legally.

    Requires env: JSEARCH_RAPIDAPI_KEY

    Args:
        query: Search query (e.g. ``"software engineer remote"``).

    Returns:
        SourceResult with normalised job postings.

    Raises:
        ToolError: if required environment variables are not set.
    """
    raw = await _jsearch.fetch(query)
    jobs = _jsearch.normalize(raw)
    return SourceResult(
        provider="jsearch",
        query=query,
        count=len(jobs),
        jobs=jobs,
    )


@source_server.tool
async def usajobs(query: str) -> SourceResult:
    """Fetch US federal jobs from USAJobs.gov.

    Requires env: USAJOBS_KEY, USAJOBS_EMAIL

    Args:
        query: Keywords to search for (e.g. ``"software developer"``).

    Returns:
        SourceResult with normalised job postings.

    Raises:
        ToolError: if required environment variables are not set.
    """
    raw = await _usajobs.fetch(query)
    jobs = _usajobs.normalize(raw)
    return SourceResult(
        provider="usajobs",
        query=query,
        count=len(jobs),
        jobs=jobs,
    )


@source_server.tool
async def reed(query: str) -> SourceResult:
    """Fetch UK jobs from Reed.co.uk.

    Requires env: REED_KEY

    Args:
        query: Keywords to search for (e.g. ``"python developer"``).

    Returns:
        SourceResult with normalised job postings.

    Raises:
        ToolError: if required environment variables are not set.
    """
    raw = await _reed.fetch(query)
    jobs = _reed.normalize(raw)
    return SourceResult(
        provider="reed",
        query=query,
        count=len(jobs),
        jobs=jobs,
    )


@source_server.tool
async def themuse(category: str = "") -> SourceResult:
    """Fetch jobs from The Muse.

    Optional env: THEMUSE_KEY (works without key but rate-limited).

    Args:
        category: Optional job category filter (e.g. ``"Engineering"``).

    Returns:
        SourceResult with normalised job postings.
    """
    raw = await _themuse.fetch(category=category)
    jobs = _themuse.normalize(raw)
    return SourceResult(
        provider="themuse",
        query=category or None,
        count=len(jobs),
        jobs=jobs,
    )


@source_server.tool
async def jooble(query: str, location: str = "") -> SourceResult:
    """Fetch jobs from Jooble international aggregator.

    Requires env: JOOBLE_KEY

    Args:
        query:    Keywords to search for.
        location: Optional location string.

    Returns:
        SourceResult with normalised job postings.

    Raises:
        ToolError: if required environment variables are not set.
    """
    raw = await _jooble.fetch(query, location=location)
    jobs = _jooble.normalize(raw)
    return SourceResult(
        provider="jooble",
        query=query,
        count=len(jobs),
        jobs=jobs,
    )


@source_server.tool
async def search_all(
    greenhouse_tokens: list[str] | None = None,
    lever_companies: list[str] | None = None,
    ashby_boards: list[str] | None = None,
    recruitee_companies: list[str] | None = None,
    workable_accounts: list[str] | None = None,
    smartrecruiters_companies: list[str] | None = None,
    remotive_query: str | None = None,
    include_remoteok: bool = False,
    include_arbeitnow: bool = False,
) -> list[JobPosting]:
    """Fetch and aggregate jobs from multiple keyless providers concurrently.

    Network failures per provider are silently dropped (not raised).

    Returns:
        Flat list of all collected JobPosting objects across all providers.
    """
    jobs, _warnings = await _search_all(
        greenhouse_tokens=greenhouse_tokens,
        lever_companies=lever_companies,
        ashby_boards=ashby_boards,
        recruitee_companies=recruitee_companies,
        workable_accounts=workable_accounts,
        smartrecruiters_companies=smartrecruiters_companies,
        remotive_query=remotive_query,
        include_remoteok=include_remoteok,
        include_arbeitnow=include_arbeitnow,
    )
    return jobs


# ── monitor tools ─────────────────────────────────────────────────────────────────────────────

@source_server.tool
async def monitor_snapshot(provider: str, key: str, out_path: str) -> dict:
    """Take a snapshot of current job postings for a keyless provider.

    Writes a JSON file containing the list of current source_ids to ``out_path``.
    Use ``monitor_diff`` later to detect new postings.

    Args:
        provider: Provider id (e.g. ``"greenhouse"``, ``"lever"``).
        key:      Provider-specific key (board token, company slug, etc.).
                  Pass ``""`` for providers that take no argument (remoteok, arbeitnow).
        out_path: Absolute path where the snapshot JSON will be written.

    Returns:
        Summary dict with provider, key, job_count, snapshot_path.
    """
    return await _monitor_snapshot(provider, key, out_path)


@source_server.tool
async def monitor_diff(provider: str, key: str, prev_path: str) -> MonitorDiff:
    """Detect new job postings since a previous snapshot.

    Fetches current postings for the provider+key and compares source_ids against
    the previously saved snapshot at ``prev_path``.

    Args:
        provider:  Provider id (e.g. ``"greenhouse"``).
        key:       Provider-specific key.
        prev_path: Path to the snapshot file written by ``monitor_snapshot``.

    Returns:
        MonitorDiff with new_jobs list, new_count, and total_count.
    """
    return await _monitor_diff(provider, key, prev_path)
