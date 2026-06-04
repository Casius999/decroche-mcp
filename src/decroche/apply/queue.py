"""apply.queue — Pure JSON-backed batch-apply queue.

All functions accept a ``path`` parameter (JSON file) so tests can use tmp_path.
The store is a JSON object keyed by job_id for O(1) lookup and deduplication.
"""

from __future__ import annotations

import json
from pathlib import Path

from decroche.models import QueueItem


def _load(path: str) -> dict[str, dict]:
    """Load the queue store from disk; return empty dict if file absent."""
    p = Path(path)
    if not p.exists():
        return {}
    with p.open(encoding="utf-8") as fh:
        data = json.load(fh)
    return data if isinstance(data, dict) else {}


def _save(store: dict[str, dict], path: str) -> None:
    """Persist the queue store to disk."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as fh:
        json.dump(store, fh, ensure_ascii=False, indent=2)


def _item_to_dict(item: QueueItem) -> dict:
    return json.loads(item.model_dump_json())


def _dict_to_item(d: dict) -> QueueItem:
    return QueueItem.model_validate(d)


# ── public API ─────────────────────────────────────────────────────────────────


def queue_add(item: QueueItem, path: str) -> None:
    """Add or replace a QueueItem in the queue store.

    If an item with the same ``job_id`` already exists it is replaced.

    Args:
        item: The QueueItem to add.
        path: Absolute path to the JSON queue file.
    """
    store = _load(path)
    store[item.job_id] = _item_to_dict(item)
    _save(store, path)


def queue_review(path: str) -> list[QueueItem]:
    """Return all items currently in the queue.

    Args:
        path: Absolute path to the JSON queue file.

    Returns:
        List of QueueItem objects (all statuses).
    """
    store = _load(path)
    return [_dict_to_item(v) for v in store.values()]


def queue_approve(job_ids: list[str], path: str) -> int:
    """Flip status from "prepared" → "approved" for the listed job_ids.

    Args:
        job_ids: List of job_id strings to approve.
        path:    Absolute path to the JSON queue file.

    Returns:
        Number of items actually changed.
    """
    store = _load(path)
    count = 0
    for jid in job_ids:
        if jid in store and store[jid].get("status") == "prepared":
            store[jid]["status"] = "approved"
            count += 1
    _save(store, path)
    return count


def queue_mark_sent(job_id: str, path: str) -> None:
    """Mark a queue item as sent (regardless of current status).

    Silently ignores unknown job_ids.

    Args:
        job_id: The job_id to mark as sent.
        path:   Absolute path to the JSON queue file.
    """
    store = _load(path)
    if job_id in store:
        store[job_id]["status"] = "sent"
        _save(store, path)
