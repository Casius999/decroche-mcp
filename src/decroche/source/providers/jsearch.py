"""JSearch (RapidAPI) provider — aggregates LinkedIn/Indeed/Glassdoor via licensed feed.

Auth: RapidAPI key in header.
Env:  JSEARCH_RAPIDAPI_KEY

Docs: https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch
"""
from __future__ import annotations

from decroche.models import JobPosting
from decroche.source.http import fetch_json, require_env

_BASE = "https://jsearch.p.rapidapi.com/search"
_HOST = "jsearch.p.rapidapi.com"


async def fetch(query: str) -> dict:
    """Fetch jobs from JSearch RapidAPI.

    Raises:
        MissingKeyError: if JSEARCH_RAPIDAPI_KEY not set.
    """
    keys = require_env("JSEARCH_RAPIDAPI_KEY")
    return await fetch_json(
        _BASE,
        params={"query": query},
        headers={
            "X-RapidAPI-Key": keys["JSEARCH_RAPIDAPI_KEY"],
            "X-RapidAPI-Host": _HOST,
        },
    )


def normalize(raw: dict | list) -> list[JobPosting]:
    """Normalise JSearch response → list[JobPosting]."""
    if isinstance(raw, dict):
        items: list[dict] = raw.get("data", [])
    else:
        items = list(raw)

    results: list[JobPosting] = []
    for item in items:
        if not isinstance(item, dict):
            continue

        job_id = str(item.get("job_id", ""))
        title = item.get("job_title") or ""
        company = item.get("employer_name")
        location_parts = [
            item.get("job_city"),
            item.get("job_state"),
            item.get("job_country"),
        ]
        location = ", ".join(p for p in location_parts if p) or None

        remote_raw = item.get("job_is_remote")
        remote: bool | None = bool(remote_raw) if remote_raw is not None else None

        url = item.get("job_apply_link") or item.get("job_google_link") or ""
        apply_url = item.get("job_apply_link")
        date_posted = item.get("job_posted_at_datetime_utc") or item.get("job_posted_at_timestamp")
        description = item.get("job_description") or ""

        min_salary = item.get("job_min_salary")
        max_salary = item.get("job_max_salary")
        salary: str | None = None
        if min_salary is not None or max_salary is not None:
            salary = f"{min_salary or '?'}–{max_salary or '?'}"

        highlights = item.get("job_highlights") or {}
        tags: list[str] = []
        if isinstance(highlights, dict):
            for section_items in highlights.values():
                if isinstance(section_items, list):
                    tags.extend(str(t) for t in section_items[:3])

        results.append(
            JobPosting(
                source="jsearch",
                source_id=job_id,
                title=title,
                company=company,
                location=location,
                remote=remote,
                url=url,
                apply_url=apply_url,
                date_posted=str(date_posted) if date_posted else None,
                description=description,
                salary=salary,
                tags=tags,
                raw=item,
            )
        )
    return results
