"""source.monitor — career-page/board monitoring via snapshot + diff.

No firecrawl dependency. Uses the keyless provider fetch + normalize functions
to take snapshots and detect new postings between runs.

Tools registered on source_server:
- monitor_snapshot(provider, key, out_path) → dict
- monitor_diff(provider, key, prev_path)    → MonitorDiff
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from decroche.models import JobPosting, MonitorDiff

# Registry of keyless providers (provider_id → (fetch_coro_factory, normalize_fn))
# We import lazily to avoid circular imports and keep the module testable.


def _get_provider(provider: str):
    """Return (async fetch callable, normalize fn) for the given keyless provider id.

    Raises:
        ValueError: if the provider is unknown or not supported for monitoring.
    """
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

    _registry: dict[str, Any] = {
        "greenhouse": (greenhouse.fetch, greenhouse.normalize),
        "lever": (lever.fetch, lever.normalize),
        "ashby": (ashby.fetch, ashby.normalize),
        "recruitee": (recruitee.fetch, recruitee.normalize),
        "workable": (workable.fetch, workable.normalize),
        "smartrecruiters": (smartrecruiters.fetch, smartrecruiters.normalize),
        "remoteok": (remoteok.fetch, remoteok.normalize),
        "remotive": (remotive.fetch, remotive.normalize),
        "arbeitnow": (arbeitnow.fetch, arbeitnow.normalize),
    }

    if provider not in _registry:
        raise ValueError(
            f"Unknown monitor provider '{provider}'. Supported: {', '.join(sorted(_registry))}"
        )
    return _registry[provider]


async def monitor_snapshot(
    provider: str,
    key: str,
    out_path: str,
) -> dict:
    """Fetch current postings for a keyless provider and write a snapshot to disk.

    The snapshot stores the list of source_ids only (not full postings) so diffs
    can detect new additions without storing PII-heavy full descriptions.

    Args:
        provider: Provider id (e.g. ``"greenhouse"``).
        key:      Provider-specific key whose meaning depends on the provider:
                  - ``greenhouse`` / ``ashby`` / ``workable``: board token or slug
                  - ``lever`` / ``recruitee`` / ``smartrecruiters``: company slug
                  - ``remotive``: **search string** (e.g. ``"python backend"``;
                    pass ``""`` for all jobs) — must use the same string in
                    both ``monitor_snapshot`` and ``monitor_diff``
                  - ``remoteok`` / ``arbeitnow``: ignored (pass ``""``)
        out_path: Absolute path where the JSON snapshot will be written.

    Returns:
        A summary dict: {provider, key, job_count, snapshot_path}.
    """
    fetch_fn, normalize_fn = _get_provider(provider)

    # Providers that take no argument
    _no_arg = {"remoteok", "arbeitnow"}
    if provider in _no_arg:
        raw = await fetch_fn()
    else:
        raw = await fetch_fn(key)

    jobs: list[JobPosting] = normalize_fn(raw)

    # Build snapshot: store source_ids list only
    snapshot = {
        "provider": provider,
        "key": key,
        "job_ids": [j.source_id for j in jobs],
    }

    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "provider": provider,
        "key": key,
        "job_count": len(jobs),
        "snapshot_path": str(path),
    }


async def monitor_diff(
    provider: str,
    key: str,
    prev_path: str,
) -> MonitorDiff:
    """Compare current provider fetch against a stored snapshot; return new postings.

    Args:
        provider:  Provider id (e.g. ``"greenhouse"``).
        key:       Provider-specific key.  Must match the ``key`` used when
                   ``monitor_snapshot`` was called so that the same result set
                   is fetched.  For ``remotive`` this is the search string.
        prev_path: Absolute path to the previously written snapshot JSON.

    Returns:
        MonitorDiff with new_jobs, new_count, total_count.

    Raises:
        FileNotFoundError: if prev_path does not exist.
    """
    fetch_fn, normalize_fn = _get_provider(provider)

    # Load previous snapshot
    prev_snapshot = json.loads(Path(prev_path).read_text(encoding="utf-8"))
    prev_ids: set[str] = set(prev_snapshot.get("job_ids", []))

    # Fetch current
    _no_arg = {"remoteok", "arbeitnow"}
    if provider in _no_arg:
        raw = await fetch_fn()
    else:
        raw = await fetch_fn(key)

    current_jobs: list[JobPosting] = normalize_fn(raw)

    new_jobs = [j for j in current_jobs if j.source_id not in prev_ids]

    return MonitorDiff(
        provider=provider,
        key=key,
        new_jobs=new_jobs,
        new_count=len(new_jobs),
        total_count=len(current_jobs),
    )
