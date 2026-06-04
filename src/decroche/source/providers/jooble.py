"""Jooble job aggregator provider.

Auth: API key embedded in the POST URL.
Env:  JOOBLE_KEY

Docs: https://jooble.org/api/about
"""

from __future__ import annotations

from decroche.models import JobPosting
from decroche.source.http import fetch_json, require_env

_BASE = "https://jooble.org/api/{key}"


async def fetch(query: str, location: str = "") -> dict:
    """Fetch jobs from Jooble.

    Raises:
        MissingKeyError: if JOOBLE_KEY not set.
    """
    keys = require_env("JOOBLE_KEY")
    url = _BASE.format(key=keys["JOOBLE_KEY"])
    body: dict[str, str] = {"keywords": query}
    if location:
        body["location"] = location
    return await fetch_json(url, method="POST", json_body=body, provider="jooble")


def normalize(raw: dict | list) -> list[JobPosting]:
    """Normalise Jooble response → list[JobPosting]."""
    if isinstance(raw, dict):
        items: list[dict] = raw.get("jobs", [])
    else:
        items = list(raw)

    results: list[JobPosting] = []
    for item in items:
        if not isinstance(item, dict):
            continue

        job_id = str(item.get("id", ""))
        title = item.get("title") or ""
        company = item.get("company")
        location = item.get("location")

        remote_raw = str(item.get("location") or "").lower()
        remote = True if "remote" in remote_raw else None

        url = item.get("link") or ""
        date_posted = item.get("updated")
        description = item.get("snippet") or ""

        salary = item.get("salary") or None

        results.append(
            JobPosting(
                source="jooble",
                source_id=job_id,
                title=title,
                company=company,
                location=location,
                remote=remote,
                url=url,
                apply_url=None,
                date_posted=str(date_posted) if date_posted else None,
                description=description,
                salary=str(salary) if salary else None,
                tags=[],
                raw=item,
            )
        )
    return results
