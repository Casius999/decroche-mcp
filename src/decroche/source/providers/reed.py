"""Reed.co.uk job board provider (UK).

Auth: HTTP Basic — API key as username, empty password.
Env:  REED_KEY

Docs: https://www.reed.co.uk/developers/jobseeker
"""
from __future__ import annotations

import base64

from decroche.models import JobPosting
from decroche.source.http import fetch_json, require_env

_BASE = "https://www.reed.co.uk/api/1.0/search"


async def fetch(query: str) -> dict:
    """Fetch jobs from Reed.co.uk.

    Raises:
        MissingKeyError: if REED_KEY not set.
    """
    keys = require_env("REED_KEY")
    # HTTP Basic: key as username, empty password
    credentials = base64.b64encode(f"{keys['REED_KEY']}:".encode()).decode()
    return await fetch_json(
        _BASE,
        params={"keywords": query},
        headers={"Authorization": f"Basic {credentials}"},
    )


def normalize(raw: dict | list) -> list[JobPosting]:
    """Normalise Reed search response → list[JobPosting]."""
    if isinstance(raw, dict):
        items: list[dict] = raw.get("results", [])
    else:
        items = list(raw)

    results: list[JobPosting] = []
    for item in items:
        if not isinstance(item, dict):
            continue

        job_id = str(item.get("jobId", ""))
        title = item.get("jobTitle") or ""
        company = item.get("employerName")
        location = item.get("locationName")

        remote_raw = item.get("locationName", "")
        remote = True if isinstance(remote_raw, str) and "remote" in remote_raw.lower() else None

        url = item.get("jobUrl") or f"https://www.reed.co.uk/jobs/{job_id}"
        apply_url = item.get("jobUrl")
        date_posted = item.get("date") or item.get("expirationDate")
        description = item.get("jobDescription") or item.get("snippet") or ""

        min_s = item.get("minimumSalary")
        max_s = item.get("maximumSalary")
        salary: str | None = None
        if min_s is not None or max_s is not None:
            currency = item.get("currency", "GBP")
            salary = f"{min_s or '?'}–{max_s or '?'} {currency}".strip()

        results.append(
            JobPosting(
                source="reed",
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
                tags=[],
                raw=item,
            )
        )
    return results
