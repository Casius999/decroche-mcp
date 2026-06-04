"""recruiter.store — local JSON persistence for recruiter records.

CNIL/RGPD compliance:
- Every stored record carries ``pii: true`` and ``retention_max_years: 3``.
- Callers are responsible for honouring the retention policy (purge after 3 years).
- An optional AIDefence PII gate can be applied by the caller before calling
  ``store_recruiter``; it is NOT performed here to keep this module pure/sync.

Storage format (JSON array written to ``out_path``):
[
  {
    "pii": true,
    "retention_max_years": 3,
    "recruiter": { ... },
    "contact":   { ... }
  },
  ...
]
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from decroche.models import Contact, Recruiter

_PII_FLAG = True
_RETENTION_YEARS = 3


def _make_record(recruiter: Recruiter, contact: Contact) -> dict[str, Any]:
    """Build a single store record dict."""
    return {
        "pii": _PII_FLAG,
        "retention_max_years": _RETENTION_YEARS,
        "recruiter": recruiter.model_dump(),
        "contact": contact.model_dump(),
    }


def load_store(path: str | Path) -> list[dict[str, Any]]:
    """Load an existing recruiter store JSON file.

    Returns an empty list if the file does not exist.

    Args:
        path: Path to the JSON store file.

    Returns:
        List of record dicts (may be empty).
    """
    p = Path(path)
    if not p.exists():
        return []
    return json.loads(p.read_text(encoding="utf-8"))


def store_recruiter(
    recruiter: Recruiter,
    contact: Contact,
    out_path: str | Path,
) -> dict[str, Any]:
    """Append a recruiter+contact record to a local JSON store.

    Creates the file if it does not exist. Appends to existing records.
    Each record carries CNIL compliance metadata (``pii:true``,
    ``retention_max_years:3``).

    Args:
        recruiter: Identified recruiter.
        contact:   Email contact record (may have ``status="not_found"``).
        out_path:  Absolute path to the JSON store file.

    Returns:
        The newly written record dict (including pii and retention metadata).
    """
    p = Path(out_path)
    records = load_store(p)
    record = _make_record(recruiter, contact)
    records.append(record)
    p.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    return record
