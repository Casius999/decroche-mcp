"""RemoteOK API provider (no auth required; attribution required).

API:  https://remoteok.com/api
Docs: https://remoteok.com/api

Attribution required: "Jobs by RemoteOK.com"
First element in the array is a legal notice dict (skip it).
"""

from __future__ import annotations

import datetime
from datetime import timezone
from typing import Any

from decroche.models import JobPosting
from decroche.source.http import fetch_json

_URL = "https://remoteok.com/api"


async def fetch() -> list:
    """Fetch all remote jobs from RemoteOK API."""
    return await fetch_json(_URL, headers={"User-Agent": "decroche-mcp/1.0"})


def normalize(raw: dict | list) -> list[JobPosting]:
    """Normalise a RemoteOK API response → list[JobPosting].

    The first element is a metadata/legal notice dict — skip it.
    """
    if isinstance(raw, dict):
        items: list[Any] = raw.get("jobs", [])
    else:
        items = list(raw)

    results: list[JobPosting] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        # Skip the legal/metadata notice (has "legal" key, no "id" or position)
        if "position" not in item and "id" not in item:
            continue

        job_id = str(item.get("id") or "")
        title = item.get("position") or ""
        url = item.get("url") or ""
        apply_url = item.get("apply_url") or None
        description = item.get("description") or ""
        company = item.get("company") or None
        location = item.get("location") or None

        tags_raw = item.get("tags") or []
        tags = [str(t) for t in tags_raw if t]

        # epoch seconds → ISO date
        epoch = item.get("epoch")
        date_posted: str | None = None
        if epoch:
            try:
                date_posted = datetime.datetime.fromtimestamp(int(epoch), tz=timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                )
            except Exception:
                date_posted = item.get("date")
        else:
            date_posted = item.get("date")

        # Salary
        salary_min = item.get("salary_min")
        salary_max = item.get("salary_max")
        salary: str | None = None
        if salary_min or salary_max:
            parts = [str(p) for p in [salary_min, salary_max] if p is not None]
            salary = " – ".join(parts)

        results.append(
            JobPosting(
                source="remoteok",
                source_id=job_id,
                title=title,
                company=company,
                location=location,
                remote=True,
                url=url,
                apply_url=apply_url,
                date_posted=date_posted,
                description=description,
                salary=salary,
                tags=tags,
                raw=item,
            )
        )
    return results
