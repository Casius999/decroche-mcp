"""Breadth orchestrator — fan-out across known job boards + keyed providers.

``search_market`` is the primary entry point.  It:

1. Loads ``known_boards.yaml`` (or uses the caller-supplied ``boards`` list).
2. Fans out keyless provider fetches (greenhouse/lever/ashby/recruitee) across
   all board tokens concurrently.
3. Optionally runs keyed providers (france_travail/adzuna/jsearch) when their
   env vars are present and ``use_keyed=True``.
4. Merges all results, runs ``match.dedupe``, filters by query terms, and
   sorts descending by ``date_posted`` (None last).

Design for testability
----------------------
The three inner async helpers are module-level functions so tests can
monkeypatch them individually without touching the real providers:

- ``_fan_out_keyless(query, boards, per_provider_limit)``  → (jobs, warnings)
- ``_run_france_travail(query, region)``                   → (jobs, warnings)
- ``_run_adzuna(query, region)``                           → (jobs, warnings)
- ``_run_jsearch(query)``                                  → (jobs, warnings)
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import yaml

from decroche.match.dedupe import dedupe
from decroche.models import JobPosting
from decroche.source.http import env_key
from decroche.source.providers import ashby, greenhouse, lever, recruitee

_KNOWN_BOARDS_PATH = Path(__file__).parent.parent / "data" / "known_boards.yaml"


def _load_known_boards() -> list[dict]:
    """Load and return rows from known_boards.yaml."""
    with open(_KNOWN_BOARDS_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or []


def _matches_query(job: JobPosting, terms: list[str]) -> bool:
    """Return True if all query terms appear in the job title or description (OR logic).

    Empty terms list → match everything.
    Uses OR: any single term match is sufficient (maximises breadth).
    """
    if not terms:
        return True
    text = f"{job.title} {job.description}".lower()
    return any(t in text for t in terms)


def _sort_key(job: JobPosting) -> tuple:
    """Sort key for descending date_posted order (None sorts last).

    With ``reverse=True`` in sorted(), highest key comes first.
    - Dated postings get ``(True, date_str)`` — True > False, and within
      dated postings ISO strings compare correctly (newer = higher).
    - None-dated postings get ``(False, "")`` — always last after reverse.
    """
    if job.date_posted is None:
        return (False, "")
    return (True, job.date_posted)


async def _fan_out_keyless(
    query: str,
    boards: list[dict],
    per_provider_limit: int,
) -> tuple[list[JobPosting], list[str]]:
    """Fan out keyless provider fetches across all ``boards`` concurrently.

    Each board row: ``{provider, token, company, ...}``
    Returns ``(all_jobs, warnings)``.
    """
    tasks: list[tuple[str, Any]] = []  # (label, coroutine)

    for row in boards:
        provider_name = row.get("provider", "")
        token = row.get("token", "")
        if not token:
            continue

        if provider_name == "greenhouse":
            tasks.append((f"greenhouse:{token}", greenhouse.fetch(token)))
        elif provider_name == "lever":
            tasks.append((f"lever:{token}", lever.fetch(token)))
        elif provider_name == "ashby":
            tasks.append((f"ashby:{token}", ashby.fetch(token)))
        elif provider_name == "recruitee":
            tasks.append((f"recruitee:{token}", recruitee.fetch(token)))

    if not tasks:
        return [], []

    labels = [label for label, _ in tasks]
    coros = [coro for _, coro in tasks]

    raw_results = await asyncio.gather(*coros, return_exceptions=True)

    all_jobs: list[JobPosting] = []
    warnings: list[str] = []

    for label, result in zip(labels, raw_results):
        if isinstance(result, BaseException):
            warnings.append(f"{label}: {type(result).__name__}: {result}")
            continue

        provider_name = label.split(":")[0]
        company_hint: str | None = label.split(":", 1)[1] if ":" in label else None

        try:
            if provider_name == "greenhouse":
                jobs = greenhouse.normalize(result, company=company_hint)
            elif provider_name == "lever":
                jobs = lever.normalize(result, company=company_hint)
            elif provider_name == "ashby":
                jobs = ashby.normalize(result, company=company_hint)
            elif provider_name == "recruitee":
                jobs = recruitee.normalize(result, company=company_hint)
            else:
                warnings.append(f"{label}: unknown provider — skipped")
                continue
            all_jobs.extend(jobs[:per_provider_limit])
        except Exception as exc:
            warnings.append(f"{label} normalize error: {type(exc).__name__}: {exc}")

    return all_jobs, warnings


async def _run_france_travail(query: str, region: str) -> tuple[list[JobPosting], list[str]]:
    """Run France Travail if env vars are present.  Returns (jobs, warnings)."""
    from decroche.source.providers import france_travail

    try:
        raw = await france_travail.fetch(query, location=region)
        jobs = france_travail.normalize(raw)
        return jobs, []
    except Exception as exc:
        return [], [f"france_travail: {type(exc).__name__}: {exc}"]


async def _run_adzuna(query: str, region: str) -> tuple[list[JobPosting], list[str]]:
    """Run Adzuna if env vars are present.  Returns (jobs, warnings)."""
    from decroche.source.providers import adzuna

    country = region[:2].lower() if region else "fr"
    try:
        raw = await adzuna.fetch(query, country=country)
        jobs = adzuna.normalize(raw)
        return jobs, []
    except Exception as exc:
        return [], [f"adzuna: {type(exc).__name__}: {exc}"]


async def _run_jsearch(query: str) -> tuple[list[JobPosting], list[str]]:
    """Run JSearch if env vars are present.  Returns (jobs, warnings)."""
    from decroche.source.providers import jsearch

    try:
        raw = await jsearch.fetch(query)
        jobs = jsearch.normalize(raw)
        return jobs, []
    except Exception as exc:
        return [], [f"jsearch: {type(exc).__name__}: {exc}"]


async def search_market(
    query: str,
    *,
    region: str = "fr",
    boards: list[dict] | None = None,
    use_keyed: bool = True,
    per_provider_limit: int = 50,
    # Internal: set True to return (jobs, warnings) tuple instead of just jobs
    _return_warnings: bool = False,
) -> list[JobPosting] | tuple[list[JobPosting], list[str]]:
    """Search across the maximum number of job sources for a given query.

    Args:
        query:               Search terms.  Empty string → return all.
        region:              Two-letter country code or broader region hint.
                             Used as a country parameter for keyed providers.
        boards:              Override the known_boards.yaml list.  Pass ``None``
                             to load from YAML automatically.
        use_keyed:           Whether to also call keyed providers when their env
                             vars are present.  Default True.
        per_provider_limit:  Max postings per individual board / provider call.
        _return_warnings:    Internal flag for tests — returns ``(jobs, warnings)``
                             instead of just ``jobs``.

    Returns:
        Deduplicated, query-filtered, date-sorted list of JobPosting objects.
    """
    effective_boards = boards if boards is not None else _load_known_boards()
    terms = [t.lower() for t in query.split() if t] if query else []

    all_jobs: list[JobPosting] = []
    all_warnings: list[str] = []

    # ── keyless fan-out ───────────────────────────────────────────────────────────────────
    keyless_jobs, keyless_warnings = await _fan_out_keyless(
        query, effective_boards, per_provider_limit
    )
    all_jobs.extend(keyless_jobs)
    all_warnings.extend(keyless_warnings)

    # ── keyed providers ──────────────────────────────────────────────────────────────────
    if use_keyed:
        keyed_coros: list[tuple[str, Any]] = []

        # France Travail
        if env_key("FRANCE_TRAVAIL_ID", "FRANCE_TRAVAIL_SECRET"):
            keyed_coros.append(("france_travail", _run_france_travail(query, region)))
        else:
            all_warnings.append(
                "france_travail: skipped — FRANCE_TRAVAIL_ID/FRANCE_TRAVAIL_SECRET not set"
            )

        # Adzuna
        if env_key("ADZUNA_APP_ID", "ADZUNA_APP_KEY"):
            keyed_coros.append(("adzuna", _run_adzuna(query, region)))
        else:
            all_warnings.append("adzuna: skipped — ADZUNA_APP_ID/ADZUNA_APP_KEY not set")

        # JSearch
        if env_key("JSEARCH_RAPIDAPI_KEY"):
            keyed_coros.append(("jsearch", _run_jsearch(query)))
        else:
            all_warnings.append("jsearch: skipped — JSEARCH_RAPIDAPI_KEY not set")

        if keyed_coros:
            keyed_results = await asyncio.gather(
                *[coro for _, coro in keyed_coros], return_exceptions=True
            )
            for (label, _), result in zip(keyed_coros, keyed_results):
                if isinstance(result, BaseException):
                    all_warnings.append(f"{label}: {type(result).__name__}: {result}")
                else:
                    jobs_k, warns_k = result
                    all_jobs.extend(jobs_k)
                    all_warnings.extend(warns_k)

    # ── deduplicate ───────────────────────────────────────────────────────────────────────
    deduped = dedupe(all_jobs)

    # ── filter by query ────────────────────────────────────────────────────────────────────
    filtered = [j for j in deduped if _matches_query(j, terms)]

    # ── sort date desc, None last ──────────────────────────────────────────────────────────
    # Reverse=True + (False, date) / (True, "") → newest first, None last.
    sorted_jobs = sorted(filtered, key=_sort_key, reverse=True)

    if _return_warnings:
        return sorted_jobs, all_warnings
    return sorted_jobs
