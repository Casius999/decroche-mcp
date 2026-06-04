"""The Muse job board provider.

Auth: Optional API key (works without but rate-limited).
Env:  THEMUSE_KEY (optional — if absent, call without key)

Docs: https://www.themuse.com/developers/api/v2
"""

from __future__ import annotations

import os

from decroche.models import JobPosting
from decroche.source.http import fetch_json

_BASE = "https://www.themuse.com/api/public/jobs"


async def fetch(category: str = "") -> dict:
    """Fetch jobs from The Muse API.

    The API key is optional. If THEMUSE_KEY is not set, the call is made
    without a key (rate-limited but functional).
    """
    params: dict[str, object] = {"page": 1}
    api_key = os.environ.get("THEMUSE_KEY")
    if api_key:
        params["api_key"] = api_key
    if category:
        params["category"] = category
    return await fetch_json(_BASE, params=params)


def normalize(raw: dict | list) -> list[JobPosting]:
    """Normalise The Muse API response → list[JobPosting]."""
    if isinstance(raw, dict):
        items: list[dict] = raw.get("results", [])
    else:
        items = list(raw)

    results: list[JobPosting] = []
    for item in items:
        if not isinstance(item, dict):
            continue

        job_id = str(item.get("id", ""))
        title = item.get("name") or ""

        company_data = item.get("company") or {}
        company = company_data.get("name") if isinstance(company_data, dict) else None

        locations = item.get("locations") or []
        location: str | None = None
        if isinstance(locations, list) and locations:
            first = locations[0]
            location = first.get("name") if isinstance(first, dict) else None

        refs = item.get("refs") or {}
        url = refs.get("landing_page") if isinstance(refs, dict) else None
        url = url or f"https://www.themuse.com/jobs/{job_id}"

        date_posted = item.get("publication_date")
        contents = item.get("contents") or ""
        # contents may be HTML
        description = str(contents) if contents else ""

        categories = item.get("categories") or []
        tags = [c.get("name", "") for c in categories if isinstance(c, dict) and c.get("name")]

        levels = item.get("levels") or []
        for lvl in levels:
            if isinstance(lvl, dict) and lvl.get("name"):
                tags.append(lvl["name"])

        results.append(
            JobPosting(
                source="themuse",
                source_id=job_id,
                title=title,
                company=company,
                location=location,
                remote=None,
                url=url,
                apply_url=None,
                date_posted=str(date_posted) if date_posted else None,
                description=description,
                salary=None,
                tags=tags,
                raw=item,
            )
        )
    return results
