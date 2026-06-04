"""Ashby Job Board API provider (no auth required).

API:  https://api.ashbyhq.com/posting-api/job-board/{name}?includeCompensation=true
Docs: https://developers.ashbyhq.com/reference/jobpostinglist
"""
from __future__ import annotations

from typing import Any

from decroche.models import JobPosting
from decroche.source.http import fetch_json

_BASE = "https://api.ashbyhq.com/posting-api/job-board/{name}"


async def fetch(job_board_name: str) -> dict:
    """Fetch all listed jobs for *job_board_name* from Ashby Posting API."""
    url = _BASE.format(name=job_board_name)
    return await fetch_json(url, params={"includeCompensation": "true"})


def normalize(raw: dict | list, *, company: str | None = None) -> list[JobPosting]:
    """Normalise an Ashby posting-api response → list[JobPosting]."""
    if isinstance(raw, dict):
        items: list[dict[str, Any]] = raw.get("jobs", [])
    else:
        items = list(raw)

    results: list[JobPosting] = []
    for item in items:
        if not isinstance(item, dict):
            continue

        job_id = item.get("id") or ""
        title = item.get("title") or ""
        is_remote: Any = item.get("isRemote")
        remote: bool | None = bool(is_remote) if is_remote is not None else None
        location: str | None = item.get("location") or None
        url = item.get("jobUrl") or ""
        apply_url = item.get("applyUrl")
        description = item.get("descriptionPlain") or item.get("descriptionHtml") or ""
        date_posted: str | None = item.get("publishedDate")

        # Compensation
        salary: str | None = None
        compensation = item.get("compensation")
        if isinstance(compensation, dict):
            components = compensation.get("summaryComponents") or []
            parts = [c.get("value") for c in components if isinstance(c, dict) and c.get("value")]
            if parts:
                salary = " / ".join(str(p) for p in parts)

        results.append(
            JobPosting(
                source="ashby",
                source_id=str(job_id),
                title=title,
                company=company,
                location=location,
                remote=remote,
                url=url,
                apply_url=apply_url,
                date_posted=date_posted,
                description=description,
                salary=salary,
                tags=[],
                raw=item,
            )
        )
    return results
