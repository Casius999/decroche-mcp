"""Remotive API provider (no auth required).

API:  https://remotive.com/api/remote-jobs?search={q}
Docs: https://remotive.com/api/remote-jobs
"""

from __future__ import annotations

from typing import Any

from decroche.models import JobPosting
from decroche.source.http import fetch_json

_URL = "https://remotive.com/api/remote-jobs"


async def fetch(search: str = "") -> dict:
    """Fetch remote jobs from Remotive API, optionally filtered by *search* query."""
    params: dict[str, str] = {}
    if search:
        params["search"] = search
    return await fetch_json(_URL, params=params or None)


def normalize(raw: dict | list) -> list[JobPosting]:
    """Normalise a Remotive API response → list[JobPosting]."""
    if isinstance(raw, dict):
        items: list[dict[str, Any]] = raw.get("jobs", [])
    else:
        items = list(raw)

    results: list[JobPosting] = []
    for item in items:
        if not isinstance(item, dict):
            continue

        job_id = str(item.get("id") or "")
        title = item.get("title") or ""
        url = item.get("url") or ""
        description = item.get("description") or ""
        company = item.get("company_name") or None
        date_posted: str | None = item.get("publication_date")

        tags_raw = item.get("tags") or []
        tags = [str(t) for t in tags_raw if t]

        salary: str | None = item.get("salary") or None

        results.append(
            JobPosting(
                source="remotive",
                source_id=job_id,
                title=title,
                company=company,
                location=None,
                remote=True,
                url=url,
                apply_url=None,
                date_posted=date_posted,
                description=description,
                salary=salary,
                tags=tags,
                raw=item,
            )
        )
    return results
