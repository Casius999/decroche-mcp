"""Recruitee Offers API provider (no auth required).

API:  https://{company}.recruitee.com/api/offers/
Docs: https://developer.recruitee.com/docs/public-api
"""

from __future__ import annotations

from typing import Any

from decroche.models import JobPosting
from decroche.source.http import fetch_json

_BASE = "https://{company}.recruitee.com/api/offers/"


async def fetch(company: str) -> dict:
    """Fetch all open offers for *company* from Recruitee public API."""
    url = _BASE.format(company=company)
    return await fetch_json(url)


def normalize(raw: dict | list, *, company: str | None = None) -> list[JobPosting]:
    """Normalise a Recruitee offers response → list[JobPosting]."""
    if isinstance(raw, dict):
        items: list[dict[str, Any]] = raw.get("offers", [])
    else:
        items = list(raw)

    results: list[JobPosting] = []
    for item in items:
        if not isinstance(item, dict):
            continue

        job_id = str(item.get("id", ""))
        title = item.get("title") or ""

        city: str | None = item.get("city")
        country: str | None = item.get("country")
        location_parts = [p for p in [city, country] if p]
        location: str | None = ", ".join(location_parts) if location_parts else None

        remote_val: Any = item.get("remote")
        remote: bool | None = bool(remote_val) if remote_val is not None else None

        url = item.get("careers_url") or item.get("url") or ""
        description = item.get("description") or ""
        date_posted: str | None = item.get("created_at")

        # Salary
        salary_from = item.get("salary_from")
        salary_to = item.get("salary_to")
        salary_currency = item.get("salary_currency")
        salary: str | None = None
        if salary_from or salary_to:
            parts = []
            if salary_from:
                parts.append(str(salary_from))
            if salary_to:
                parts.append(str(salary_to))
            base = " – ".join(parts)
            if salary_currency:
                salary = f"{base} {salary_currency}"
            else:
                salary = base

        results.append(
            JobPosting(
                source="recruitee",
                source_id=job_id,
                title=title,
                company=company,
                location=location,
                remote=remote,
                url=url,
                apply_url=None,
                date_posted=date_posted,
                description=description,
                salary=salary,
                tags=[],
                raw=item,
            )
        )
    return results
