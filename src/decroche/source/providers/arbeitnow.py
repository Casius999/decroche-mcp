"""Arbeitnow Job Board API provider (no auth required).

API:  https://www.arbeitnow.com/api/job-board-api
Docs: https://documenter.getpostman.com/view/18545278/UVJbJyTq
"""

from __future__ import annotations

import datetime
from datetime import timezone
from typing import Any

from decroche.models import JobPosting
from decroche.source.http import fetch_json

_URL = "https://www.arbeitnow.com/api/job-board-api"


async def fetch() -> dict:
    """Fetch all jobs from the Arbeitnow public job board API."""
    return await fetch_json(_URL)


def normalize(raw: dict | list) -> list[JobPosting]:
    """Normalise an Arbeitnow API response → list[JobPosting]."""
    if isinstance(raw, dict):
        items: list[dict[str, Any]] = raw.get("data", [])
    else:
        items = list(raw)

    results: list[JobPosting] = []
    for item in items:
        if not isinstance(item, dict):
            continue

        job_id = item.get("slug") or ""
        title = item.get("title") or ""
        url = item.get("url") or ""
        description = item.get("description") or ""
        company = item.get("company_name") or None
        location = item.get("location") or None

        remote_val: Any = item.get("remote")
        remote: bool | None = bool(remote_val) if remote_val is not None else None

        tags_raw = item.get("tags") or []
        tags = [str(t) for t in tags_raw if t]

        # epoch seconds → ISO date
        created_at = item.get("created_at")
        date_posted: str | None = None
        if created_at:
            try:
                date_posted = datetime.datetime.fromtimestamp(
                    int(created_at), tz=timezone.utc
                ).strftime("%Y-%m-%dT%H:%M:%SZ")
            except Exception:
                date_posted = str(created_at)

        results.append(
            JobPosting(
                source="arbeitnow",
                source_id=str(job_id),
                title=title,
                company=company,
                location=location,
                remote=remote,
                url=url,
                apply_url=None,
                date_posted=date_posted,
                description=description,
                salary=None,
                tags=tags,
                raw=item,
            )
        )
    return results
