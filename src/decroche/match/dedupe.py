"""Deterministic deduplication of JobPosting lists.

Algorithm
---------
1. **Blocking key** = SHA-256 hex of ``normalized(company) | normalized(city) | normalized(title)``
   where ``normalized(s)`` lowercases, strips accents, collapses whitespace, and
   removes common noise tokens (``inc``, ``ltd``, ``sas``, ``sarl``, ``gmbh``, …).

2. Within each block, two postings are **duplicates** when BOTH:
   - ``rapidfuzz.fuzz.token_set_ratio(title_a, title_b) >= 85``
   - The ``date_posted`` values are within ±14 calendar days of each other
     (or at least one is absent — treated as "could be the same day").

3. Within a duplicate group the **most-complete** posting is kept (most non-None
   fields wins; ties resolved by the first posting seen — deterministic order).

The function is **pure and deterministic**: same input → same output.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import date

from rapidfuzz.fuzz import token_set_ratio

from decroche.models import JobPosting

# ── Noise tokens stripped before blocking key ─────────────────────────────────────────────
_NOISE = frozenset(
    [
        "inc", "ltd", "llc", "corp", "corporation", "co", "company",
        "sas", "sarl", "sa", "sasu", "gmbh", "bv", "nv", "ag",
        "the", "and", "or", "de", "du", "la", "le", "les",
    ]
)

_WHITESPACE_RE = re.compile(r"\s+")


def _normalize_token(s: str | None) -> str:
    """Lowercase, strip accents, collapse spaces, drop noise tokens."""
    if not s:
        return ""
    # NFD decomposition to strip combining marks (accents)
    nfd = unicodedata.normalize("NFD", s)
    ascii_approx = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    lower = ascii_approx.lower()
    tokens = _WHITESPACE_RE.split(lower.strip())
    clean = [t for t in tokens if t and t not in _NOISE]
    return " ".join(clean)


def _city_from_location(location: str | None) -> str:
    """Extract the city part from a location string (first comma-separated token)."""
    if not location:
        return ""
    return location.split(",")[0].strip()


def _blocking_key(job: JobPosting) -> str:
    """SHA-256 of ``norm(company)|norm(city)|norm(title)``."""
    company_norm = _normalize_token(job.company)
    city_norm = _normalize_token(_city_from_location(job.location))
    title_norm = _normalize_token(job.title)
    payload = f"{company_norm}|{city_norm}|{title_norm}"
    return hashlib.sha256(payload.encode()).hexdigest()


def _parse_date(value: str | None) -> date | None:
    """Parse an ISO-8601-ish date string → ``datetime.date``, or None."""
    if not value:
        return None
    # Try ISO date or ISO datetime (first 10 chars)
    clean = value[:10]
    try:
        return date.fromisoformat(clean)
    except ValueError:
        return None


def _within_14_days(date_a: str | None, date_b: str | None) -> bool:
    """True if both dates parse and are within ±14 days, OR if either is absent."""
    d_a = _parse_date(date_a)
    d_b = _parse_date(date_b)
    if d_a is None or d_b is None:
        return True  # unknown date → treat as potentially same
    return abs((d_a - d_b).days) <= 14


def _completeness(job: JobPosting) -> int:
    """Count of non-None fields (higher = more complete)."""
    fields = [
        job.company, job.location, job.remote, job.apply_url,
        job.date_posted, job.salary, job.description,
    ]
    return sum(1 for f in fields if f is not None) + len(job.tags)


def _are_duplicates(a: JobPosting, b: JobPosting) -> bool:
    """True if a and b are considered duplicates (same block assumed)."""
    ratio = token_set_ratio(a.title, b.title)
    if ratio < 85:
        return False
    return _within_14_days(a.date_posted, b.date_posted)


def dedupe(jobs: list[JobPosting]) -> list[JobPosting]:
    """Return a deduplicated list of JobPosting objects.

    Deterministic: input order determines which posting is kept when completeness
    is equal (first one wins).
    """
    # Build blocks
    blocks: dict[str, list[JobPosting]] = {}
    for job in jobs:
        key = _blocking_key(job)
        blocks.setdefault(key, []).append(job)

    result: list[JobPosting] = []

    for block_jobs in blocks.values():
        # Within a block, greedily cluster duplicates
        kept: list[JobPosting] = []  # one representative per cluster
        used: list[bool] = [False] * len(block_jobs)

        for i, job_i in enumerate(block_jobs):
            if used[i]:
                continue
            # Start a new cluster
            cluster = [job_i]
            used[i] = True
            for j in range(i + 1, len(block_jobs)):
                if not used[j] and _are_duplicates(job_i, block_jobs[j]):
                    cluster.append(block_jobs[j])
                    used[j] = True
            # Keep most-complete posting in the cluster
            best = max(cluster, key=_completeness)
            kept.append(best)

        result.extend(kept)

    return result
