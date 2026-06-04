"""USAJobs federal job board provider.

Auth: Authorization-Key header + User-Agent (email) header.
Env:  USAJOBS_KEY, USAJOBS_EMAIL

Docs: https://developer.usajobs.gov/API-Reference/GET-api-Search
"""

from __future__ import annotations

from decroche.models import JobPosting
from decroche.source.http import fetch_json, require_env

_BASE = "https://data.usajobs.gov/api/search"


async def fetch(query: str) -> dict:
    """Fetch federal jobs from USAJobs.

    Raises:
        MissingKeyError: if USAJOBS_KEY or USAJOBS_EMAIL not set.
    """
    keys = require_env("USAJOBS_KEY", "USAJOBS_EMAIL")
    return await fetch_json(
        _BASE,
        params={"Keyword": query},
        headers={
            "Authorization-Key": keys["USAJOBS_KEY"],
            "User-Agent": keys["USAJOBS_EMAIL"],
            "Host": "data.usajobs.gov",
        },
    )


def normalize(raw: dict | list) -> list[JobPosting]:
    """Normalise USAJobs search response → list[JobPosting]."""
    if isinstance(raw, dict):
        search_result = raw.get("SearchResult") or {}
        items: list[dict] = (
            search_result.get("SearchResultItems", []) if isinstance(search_result, dict) else []
        )
    else:
        items = list(raw)

    results: list[JobPosting] = []
    for item in items:
        if not isinstance(item, dict):
            continue

        matched = item.get("MatchedObjectDescriptor") or {}
        if not isinstance(matched, dict):
            continue

        job_id = str(matched.get("PositionID", ""))
        title = matched.get("PositionTitle") or ""
        company = matched.get("OrganizationName")

        locations_data = matched.get("PositionLocation") or []
        if isinstance(locations_data, list) and locations_data:
            first_loc = locations_data[0]
            location = first_loc.get("LocationName") if isinstance(first_loc, dict) else None
        else:
            location = None

        remote = None
        apply_uri_list = matched.get("ApplyURI")
        _first_apply_uri: str = (
            apply_uri_list[0] if isinstance(apply_uri_list, list) and apply_uri_list else ""
        )
        url = matched.get("PositionURI") or _first_apply_uri or ""
        apply_url = _first_apply_uri or None

        date_posted = matched.get("PublicationStartDate")
        description = matched.get("QualificationSummary") or matched.get("JobSummary") or ""

        remuneration = matched.get("PositionRemuneration") or []
        salary: str | None = None
        if isinstance(remuneration, list) and remuneration:
            rem = remuneration[0]
            if isinstance(rem, dict):
                min_pay = rem.get("MinimumRange")
                max_pay = rem.get("MaximumRange")
                desc = rem.get("RateIntervalCode", "")
                if min_pay or max_pay:
                    salary = f"{min_pay or '?'}–{max_pay or '?'} {desc}".strip()

        job_grades = matched.get("JobGrade") or []
        tags = [g.get("Code", "") for g in job_grades if isinstance(g, dict) and g.get("Code")]

        results.append(
            JobPosting(
                source="usajobs",
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
