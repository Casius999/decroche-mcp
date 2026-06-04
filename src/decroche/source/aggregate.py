"""Concurrent aggregation across all keyless source providers.

``search_all`` gathers results from the requested providers in parallel,
flattening them into a single list of JobPosting objects.  Network failures
for individual providers are caught and surfaced as warnings — they do not
abort the entire call.
"""
from __future__ import annotations

import asyncio
from typing import Any

from decroche.models import JobPosting
from decroche.source.providers import (
    arbeitnow,
    ashby,
    greenhouse,
    lever,
    recruitee,
    remoteok,
    remotive,
    smartrecruiters,
    workable,
)


async def search_all(
    *,
    greenhouse_tokens: list[str] | None = None,
    lever_companies: list[str] | None = None,
    ashby_boards: list[str] | None = None,
    recruitee_companies: list[str] | None = None,
    workable_accounts: list[str] | None = None,
    smartrecruiters_companies: list[str] | None = None,
    remotive_query: str | None = None,
    include_remoteok: bool = False,
    include_arbeitnow: bool = False,
) -> tuple[list[JobPosting], list[str]]:
    """Run all requested keyless providers concurrently.

    Returns:
        A tuple of ``(jobs, warnings)`` where *jobs* is the flat list of all
        collected JobPosting objects and *warnings* lists any provider errors.
    """
    tasks: list[tuple[str, Any]] = []  # (label, coroutine)

    for token in greenhouse_tokens or []:
        tasks.append((f"greenhouse:{token}", greenhouse.fetch(token)))

    for co in lever_companies or []:
        tasks.append((f"lever:{co}", lever.fetch(co)))

    for board in ashby_boards or []:
        tasks.append((f"ashby:{board}", ashby.fetch(board)))

    for co in recruitee_companies or []:
        tasks.append((f"recruitee:{co}", recruitee.fetch(co)))

    for acc in workable_accounts or []:
        tasks.append((f"workable:{acc}", workable.fetch(acc)))

    for co in smartrecruiters_companies or []:
        tasks.append((f"smartrecruiters:{co}", smartrecruiters.fetch(co)))

    if remotive_query is not None:
        tasks.append(("remotive", remotive.fetch(remotive_query)))

    if include_remoteok:
        tasks.append(("remoteok", remoteok.fetch()))

    if include_arbeitnow:
        tasks.append(("arbeitnow", arbeitnow.fetch()))

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
        extra_kwarg: dict[str, str | None] = {}

        # pass company context where available
        if ":" in label:
            extra_kwarg["company"] = label.split(":", 1)[1]

        try:
            if provider_name == "greenhouse":
                jobs = greenhouse.normalize(result, **extra_kwarg)
            elif provider_name == "lever":
                jobs = lever.normalize(result, **extra_kwarg)
            elif provider_name == "ashby":
                jobs = ashby.normalize(result, **extra_kwarg)
            elif provider_name == "recruitee":
                jobs = recruitee.normalize(result, **extra_kwarg)
            elif provider_name == "workable":
                jobs = workable.normalize(result, **extra_kwarg)
            elif provider_name == "smartrecruiters":
                jobs = smartrecruiters.normalize(result, **extra_kwarg)
            elif provider_name == "remotive":
                jobs = remotive.normalize(result)
            elif provider_name == "remoteok":
                jobs = remoteok.normalize(result)
            elif provider_name == "arbeitnow":
                jobs = arbeitnow.normalize(result)
            else:
                warnings.append(f"{label}: unknown provider — skipped")
                continue
            all_jobs.extend(jobs)
        except Exception as exc:
            warnings.append(f"{label} normalize error: {type(exc).__name__}: {exc}")

    return all_jobs, warnings
