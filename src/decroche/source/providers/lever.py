"""Lever Posting API provider (no auth required).

API:  https://api.lever.co/v0/postings/{company}?mode=json
Docs: https://hire.lever.co/developer/postings
"""

from __future__ import annotations

from typing import Any

from decroche.models import JobPosting
from decroche.source.http import fetch_json

_BASE = "https://api.lever.co/v0/postings/{company}"


async def fetch(company: str) -> list:
    """Fetch all published postings for *company* from the Lever public API."""
    url = _BASE.format(company=company)
    return await fetch_json(url, params={"mode": "json"})


def normalize(raw: dict | list, *, company: str | None = None) -> list[JobPosting]:
    """Normalise a Lever postings response → list[JobPosting].

    Accepts both the list form (``mode=json``) or a dict envelope.
    """
    if isinstance(raw, dict):
        items: list[dict[str, Any]] = raw.get("data", [])
    else:
        items = list(raw)

    results: list[JobPosting] = []
    for item in items:
        if not isinstance(item, dict):
            continue

        cats = item.get("categories") or {}
        location: str | None = cats.get("location") if isinstance(cats, dict) else None
        workplace_type: str | None = item.get("workplaceType")
        remote: bool | None = (workplace_type == "remote") if workplace_type else None

        job_id = item.get("id") or ""
        title = item.get("text") or ""
        url = item.get("hostedUrl") or ""
        apply_url = item.get("applyUrl")
        description = item.get("descriptionPlain") or item.get("description") or ""

        # epoch ms → ISO string
        created_at = item.get("createdAt")
        date_posted = _epoch_to_iso(created_at)

        results.append(
            JobPosting(
                source="lever",
                source_id=str(job_id),
                title=title,
                company=company,
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


def _epoch_to_iso(ms: Any) -> str | None:
    """Convert epoch milliseconds to ISO-8601 date string (best-effort)."""
    if ms is None:
        return None
    try:
        import datetime

        return datetime.datetime.fromtimestamp(int(ms) / 1000, tz=datetime.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
    except Exception:
        return str(ms)
