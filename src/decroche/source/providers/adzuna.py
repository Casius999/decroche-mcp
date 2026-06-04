"""Adzuna job search API provider.

Auth: app_id + app_key as query params.
Env:  ADZUNA_APP_ID, ADZUNA_APP_KEY

Docs: https://developer.adzuna.com/docs/search
"""

from __future__ import annotations

from decroche.models import JobPosting
from decroche.source.http import fetch_json, require_env

_BASE = "https://api.adzuna.com/v1/api/jobs/{country}/search/1"


async def fetch(query: str, country: str = "fr") -> dict:
    """Fetch jobs from Adzuna for the given country.

    Raises:
        MissingKeyError: if ADZUNA_APP_ID or ADZUNA_APP_KEY not set.
    """
    keys = require_env("ADZUNA_APP_ID", "ADZUNA_APP_KEY")
    url = _BASE.format(country=country)
    return await fetch_json(
        url,
        params={
            "app_id": keys["ADZUNA_APP_ID"],
            "app_key": keys["ADZUNA_APP_KEY"],
            "what": query,
            "results_per_page": 50,
        },
        provider="adzuna",
    )


def normalize(raw: dict | list) -> list[JobPosting]:
    """Normalise Adzuna search response → list[JobPosting]."""
    if isinstance(raw, dict):
        items: list[dict] = raw.get("results", [])
    else:
        items = list(raw)

    results: list[JobPosting] = []
    for item in items:
        if not isinstance(item, dict):
            continue

        job_id = str(item.get("id", ""))
        title = item.get("title") or ""

        company_data = item.get("company") or {}
        company = company_data.get("display_name") if isinstance(company_data, dict) else None

        location_data = item.get("location") or {}
        location: str | None = None
        if isinstance(location_data, dict):
            display = location_data.get("display_name")
            location = display if display else None

        url = item.get("redirect_url") or ""
        date_posted = item.get("created")
        description = item.get("description") or ""

        salary_min = item.get("salary_min")
        salary_max = item.get("salary_max")
        salary: str | None = None
        if salary_min is not None or salary_max is not None:
            salary = f"{salary_min or '?'}–{salary_max or '?'}"

        category_data = item.get("category") or {}
        tags: list[str] = []
        if isinstance(category_data, dict) and category_data.get("label"):
            tags.append(category_data["label"])

        results.append(
            JobPosting(
                source="adzuna",
                source_id=job_id,
                title=title,
                company=company,
                location=location,
                remote=None,
                url=url,
                apply_url=None,
                date_posted=str(date_posted) if date_posted else None,
                description=description,
                salary=salary,
                tags=tags,
                raw=item,
            )
        )
    return results
