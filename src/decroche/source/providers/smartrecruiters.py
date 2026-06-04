"""SmartRecruiters Posting API provider (no auth required for public postings).

API:  https://api.smartrecruiters.com/v1/companies/{company_id}/postings
Docs: https://developers.smartrecruiters.com/reference/postings-get
"""

from __future__ import annotations

from typing import Any

from decroche.models import JobPosting
from decroche.source.http import fetch_json

_BASE = "https://api.smartrecruiters.com/v1/companies/{company_id}/postings"


async def fetch(company_id: str) -> dict:
    """Fetch all public postings for *company_id* from SmartRecruiters Posting API."""
    url = _BASE.format(company_id=company_id)
    return await fetch_json(url)


def normalize(raw: dict | list, *, company: str | None = None) -> list[JobPosting]:
    """Normalise a SmartRecruiters postings response → list[JobPosting]."""
    if isinstance(raw, dict):
        items: list[dict[str, Any]] = raw.get("content", [])
    else:
        items = list(raw)

    results: list[JobPosting] = []
    for item in items:
        if not isinstance(item, dict):
            continue

        job_id = item.get("id") or ""
        title = item.get("name") or ""
        apply_url: str | None = item.get("applyUrl")
        url: str = apply_url or f"https://jobs.smartrecruiters.com/{job_id}"
        date_posted: str | None = item.get("releasedDate")

        # Company name from item or from caller
        company_data = item.get("company") or {}
        company_name: str | None = None
        if isinstance(company_data, dict):
            company_name = company_data.get("name")
        resolved_company = company_name or company

        loc_data = item.get("location") or {}
        location: str | None = None
        remote: bool | None = None
        if isinstance(loc_data, dict):
            city: str | None = loc_data.get("city")
            region: str | None = loc_data.get("region")
            country: str | None = loc_data.get("country")
            loc_parts = [p for p in [city, region, country] if p]
            location = ", ".join(loc_parts) if loc_parts else None
            remote_data = loc_data.get("remote")
            if isinstance(remote_data, dict):
                remote = bool(remote_data.get("enabled", False))

        # Description from jobAd sections
        description = ""
        job_ad = item.get("jobAd") or {}
        if isinstance(job_ad, dict):
            sections = job_ad.get("sections") or {}
            if isinstance(sections, dict):
                job_desc = sections.get("jobDescription") or {}
                if isinstance(job_desc, dict):
                    description = job_desc.get("text") or ""

        results.append(
            JobPosting(
                source="smartrecruiters",
                source_id=str(job_id),
                title=title,
                company=resolved_company,
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
