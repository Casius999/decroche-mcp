"""Workable SPI v3 Jobs provider (no auth required for public listings).

API:  https://{account}.workable.com/spi/v3/jobs
Docs: https://workable.readme.io/docs/jobs
"""

from __future__ import annotations

from typing import Any

from decroche.models import JobPosting
from decroche.source.http import fetch_json

_BASE = "https://{account}.workable.com/spi/v3/jobs"


async def fetch(account: str) -> dict:
    """Fetch all published jobs for *account* from Workable SPI v3."""
    url = _BASE.format(account=account)
    return await fetch_json(url)


def normalize(raw: dict | list, *, company: str | None = None) -> list[JobPosting]:
    """Normalise a Workable jobs response → list[JobPosting]."""
    if isinstance(raw, dict):
        items: list[dict[str, Any]] = raw.get("jobs", [])
    else:
        items = list(raw)

    results: list[JobPosting] = []
    for item in items:
        if not isinstance(item, dict):
            continue

        job_id = item.get("shortcode") or ""
        title = item.get("full_title") or item.get("title") or ""
        url = item.get("url") or ""
        apply_url = item.get("application_url")
        description = item.get("description") or ""
        date_posted: str | None = item.get("created_at")

        loc_data = item.get("location") or {}
        location: str | None = None
        remote: bool | None = None
        if isinstance(loc_data, dict):
            city: str | None = loc_data.get("city")
            country: str | None = loc_data.get("country")
            loc_parts = [p for p in [city, country] if p]
            location = ", ".join(loc_parts) if loc_parts else None
            telecommuting = loc_data.get("telecommuting")
            if telecommuting is not None:
                remote = bool(telecommuting)

        results.append(
            JobPosting(
                source="workable",
                source_id=str(job_id),
                title=title,
                company=company,
                location=location,
                remote=remote,
                url=url,
                apply_url=apply_url,
                date_posted=date_posted,
                description=description,
                salary=None,
                tags=[],
                raw=item,
            )
        )
    return results
