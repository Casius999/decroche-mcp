"""Careerjet public API provider.

Careerjet is an international job-search engine.  Their public JSON API
requires only an affiliate ID (``affid``) which can be empty for some locales
— functionality may be reduced without a valid affiliate ID.

Env (optional):
    CAREERJET_AFFID — affiliate ID issued by Careerjet.  If absent the
                      parameter is sent as an empty string with a NOTE logged.

API endpoint (HTTP, not HTTPS — Careerjet public API as documented):
    http://public.api.careerjet.net/search
    Params: keywords, location, locale_code, affid, sort, start_num, pagesize

Reference:
    https://www.careerjet.com/partners/api/
"""

from __future__ import annotations

import os
from typing import Any

from decroche.models import JobPosting
from decroche.source.http import fetch_json

_API_URL = "http://public.api.careerjet.net/search"


async def fetch(
    keywords: str,
    location: str = "",
    *,
    locale: str = "fr_FR",
    page_size: int = 99,
) -> dict:
    """Fetch job listings from Careerjet public API.

    Args:
        keywords:   Search keywords (e.g. ``"python developer"``).
        location:   Location string (e.g. ``"Paris"``).  Empty string = all.
        locale:     Careerjet locale code, default ``"fr_FR"``.
        page_size:  Max results per call, default 99 (API limit).

    Returns:
        Raw API response dict.
    """
    affid = os.environ.get("CAREERJET_AFFID", "")

    params: dict[str, Any] = {
        "keywords": keywords,
        "location": location,
        "locale_code": locale,
        "affid": affid,
        "sort": "date",
        "start_num": 1,
        "pagesize": page_size,
    }

    return await fetch_json(_API_URL, params=params, provider="careerjet")


def normalize(raw: dict | list) -> list[JobPosting]:
    """Normalise a Careerjet API response → list[JobPosting].

    Accepts either the full envelope ``{"jobs": [...]}`` or a bare list.
    """
    if isinstance(raw, dict):
        items: list[dict[str, Any]] = raw.get("jobs", [])
    else:
        items = list(raw)

    results: list[JobPosting] = []
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            continue

        url = item.get("url") or ""
        # Use URL path fragment as source_id (unique within Careerjet)
        source_id = url.rstrip("/").split("/")[-1] if url else str(i)

        title = item.get("title") or ""
        company: str | None = item.get("company") or None
        location: str | None = item.get("locations") or None
        description: str = item.get("description") or ""
        date_posted: str | None = item.get("date") or None

        results.append(
            JobPosting(
                source="careerjet",
                source_id=source_id,
                title=title,
                company=company,
                location=location,
                remote=None,
                url=url,
                apply_url=None,
                date_posted=date_posted,
                description=description,
                salary=None,
                tags=[],
                raw=item,
            )
        )
    return results
