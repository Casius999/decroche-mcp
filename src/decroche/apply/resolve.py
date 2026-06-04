"""apply.resolve — Resolve the true apply URL and channel from a JobPosting.

Pure function, no network. Implements the apply-at-source principle:
candidates should always apply at the employer's own ATS, never via
LinkedIn/Indeed/Glassdoor aggregator pages.
"""

from __future__ import annotations

from urllib.parse import urlparse

from decroche.models import JobPosting

# Known aggregator/platform hostnames where applying via the platform is
# disallowed per apply-at-source principle.
_AGGREGATOR_HOSTS: frozenset[str] = frozenset(
    {
        "linkedin.com",
        "www.linkedin.com",
        "fr.linkedin.com",
        "uk.linkedin.com",
        "de.linkedin.com",
        "indeed.com",
        "www.indeed.com",
        "fr.indeed.com",
        "uk.indeed.com",
        "glassdoor.com",
        "www.glassdoor.com",
        "fr.glassdoor.com",
        "uk.glassdoor.com",
    }
)

_NOTE_AGGREGATOR = (
    "Apply directly at the employer ATS, not the aggregator platform. "
    "LinkedIn/Indeed/Glassdoor only serve for discovery."
)
_NOTE_DIRECT = "Apply URL resolved to employer ATS directly."
_NOTE_FALLBACK = "No dedicated apply URL found; using job listing URL."


def _host(url: str) -> str:
    """Return the lower-cased netloc of a URL."""
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


def _is_aggregator(url: str) -> bool:
    host = _host(url)
    # Match exact host or any subdomain of aggregator hosts
    if host in _AGGREGATOR_HOSTS:
        return True
    # e.g. "us.linkedin.com" → ends with ".linkedin.com"
    for agg in ("linkedin.com", "indeed.com", "glassdoor.com"):
        if host == agg or host.endswith(f".{agg}"):
            return True
    return False


def resolve_source(job: JobPosting) -> dict:
    """Resolve the best apply URL and channel for a job posting.

    Priority:
    1. ``job.apply_url`` if set → use directly (employer ATS URL, manual=False).
    2. ``job.url`` if it is an aggregator host → manual=True + note.
    3. ``job.url`` otherwise → use as apply_url, manual=False.

    Args:
        job: A normalised JobPosting.

    Returns:
        Dict with keys:
        - ``apply_url`` (str): URL to apply at.
        - ``channel`` (str): "direct" | "ats" | "aggregator".
        - ``manual`` (bool): True if human must manually find the employer ATS.
        - ``note`` (str): Human-readable explanation.
    """
    if job.apply_url:
        # Employer ATS URL provided — best case
        return {
            "apply_url": job.apply_url,
            "channel": "ats",
            "manual": False,
            "note": _NOTE_DIRECT,
        }

    # No apply_url — fall back to job.url
    if _is_aggregator(job.url):
        return {
            "apply_url": job.url,
            "channel": "aggregator",
            "manual": True,
            "note": _NOTE_AGGREGATOR,
        }

    # Direct / ATS-hosted job page
    return {
        "apply_url": job.url,
        "channel": "direct",
        "manual": False,
        "note": _NOTE_FALLBACK,
    }
