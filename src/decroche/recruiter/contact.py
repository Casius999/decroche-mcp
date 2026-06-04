"""recruiter.contact — find or guess a recruiter's email address.

Two modes:
1. DROPCONTACT_KEY env set → call Dropcontact CNIL-audited enrichment API.
   Status is "verified" only on a confirmed hit.
2. No key → deterministic email pattern guess (firstname.lastname@domain).
   Status is always "guessed_unverified". Never claimed as verified.

COMPLIANCE:
- "verified" status is ONLY set when a live API confirms the address.
- No scraping, no DB lookups, no LinkedIn traversal.
- Secrets read from env vars only; key never logged (sanitized errors via source.http).
"""

from __future__ import annotations

import re
import unicodedata

from decroche.models import Contact
from decroche.source.http import ToolError, env_key, fetch_json

_DROPCONTACT_URL = "https://api.dropcontact.com/v1/enrich/all"


def _normalize_name_part(part: str) -> str:
    """Lowercase, strip accents, remove non-alpha chars."""
    nfkd = unicodedata.normalize("NFKD", part)
    ascii_part = nfkd.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z]", "", ascii_part.lower())


def _guess_email(name: str, domain: str) -> str:
    """Generate firstname.lastname@domain from a full name."""
    parts = name.strip().split()
    if len(parts) >= 2:
        first = _normalize_name_part(parts[0])
        last = _normalize_name_part(parts[-1])
        local = f"{first}.{last}" if first and last else _normalize_name_part(name)
    else:
        local = _normalize_name_part(name)
    return f"{local}@{domain.lstrip('@').lower()}"


async def find_contact(
    name: str,
    company: str | None,
    domain: str | None = None,
) -> Contact:
    """Find or guess a recruiter's email address.

    Priority:
    1. If ``DROPCONTACT_KEY`` is set → call Dropcontact API (CNIL-audited).
       Returns status="verified" on hit, "not_found" if not enriched.
    2. If ``domain`` provided but no API key → guess pattern, status="guessed_unverified".
    3. Neither → status="not_found".

    Args:
        name:    Full name of the recruiter.
        company: Company name (used for Dropcontact request).
        domain:  Email domain (e.g. "acme.com"). Required for guessing.

    Returns:
        :class:`Contact` with honest status. "verified" is ONLY set when
        Dropcontact confirms an address.
    """
    keys = env_key("DROPCONTACT_KEY")
    if keys:
        return await _find_via_dropcontact(name, company, domain, keys["DROPCONTACT_KEY"])

    if domain:
        guessed = _guess_email(name, domain)
        return Contact(
            name=name,
            email=guessed,
            status="guessed_unverified",
            source="pattern_guess",
            company=company,
        )

    return Contact(
        name=name,
        email=None,
        status="not_found",
        source="no_source",
        company=company,
    )


async def _find_via_dropcontact(
    name: str,
    company: str | None,
    domain: str | None,
    api_key: str,
) -> Contact:
    """Call Dropcontact v1/enrich/all and map the response to Contact."""
    parts = name.strip().split(maxsplit=1)
    first_name = parts[0] if parts else name
    last_name = parts[1] if len(parts) > 1 else ""

    payload: dict = {
        "data": [
            {
                "first_name": first_name,
                "last_name": last_name,
                **({{"company": company}} if company else {}),
                **({{"email_domain": domain}} if domain else {}),
            }
        ]
    }

    try:
        resp = await fetch_json(
            _DROPCONTACT_URL,
            method="POST",
            json_body=payload,
            headers={"X-Access-Token": api_key, "Content-Type": "application/json"},
            provider="dropcontact",
        )
    except ToolError:
        # Re-raise — caller decides how to handle (error already sanitized)
        raise

    # Parse response — Dropcontact returns {"data": [{...}], ...}
    data_list = resp.get("data", [])
    if not data_list:
        return Contact(
            name=name,
            email=None,
            status="not_found",
            source="dropcontact",
            company=company,
        )

    record = data_list[0]
    emails = record.get("email", [])
    if isinstance(emails, list) and emails:
        best = emails[0]
        email_str = best.get("email") if isinstance(best, dict) else str(best)
        return Contact(
            name=name,
            email=email_str,
            status="verified",
            source="dropcontact",
            company=company,
        )

    # No email found in enrichment
    return Contact(
        name=name,
        email=None,
        status="not_found",
        source="dropcontact",
        company=company,
    )
