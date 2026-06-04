"""Greenhouse Boards API provider (no auth required).

API:  https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true
Docs: https://developers.greenhouse.io/job-board.html
"""
from __future__ import annotations

from typing import Any

from decroche.models import JobPosting
from decroche.source.http import fetch_json

_BASE = "https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs"


async def fetch(board_token: str) -> dict:
    """Fetch all live jobs for *board_token* from Greenhouse Boards API."""
    url = _BASE.format(board_token=board_token)
    return await fetch_json(url, params={"content": "true"})


def normalize(raw: dict | list, *, company: str | None = None) -> list[JobPosting]:
    """Normalise a Greenhouse boards API response → list[JobPosting].

    Accepts either the full envelope (``{"jobs": [...]}`` dict) or a bare list.
    """
    if isinstance(raw, dict):
        items: list[dict[str, Any]] = raw.get("jobs", [])
    else:
        items = list(raw)

    results: list[JobPosting] = []
    for item in items:
        if not isinstance(item, dict):
            continue

        loc_data = item.get("location") or {}
        location: str | None = loc_data.get("name") if isinstance(loc_data, dict) else None

        job_id = str(item.get("id", ""))
        title = item.get("title") or ""
        url = item.get("absolute_url") or ""
        description = item.get("content") or ""
        date_posted = _parse_date(item.get("updated_at"))

        # Company comes from the board token context; not in the item itself
        results.append(
            JobPosting(
                source="greenhouse",
                source_id=job_id,
                title=title,
                company=company,
                location=location,
                remote=None,
                url=url,
                apply_url=None,
                date_posted=date_posted,
                description=description,
                salary=None,
                tags=[],
                raw=item,
            )
        )
    return results


def _parse_date(value: Any) -> str | None:
    if not value:
        return None
    return str(value)
