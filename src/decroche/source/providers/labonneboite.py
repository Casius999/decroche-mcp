"""La Bonne Boîte (France Travail) provider — hidden job market.

La Bonne Boîte surfaces companies that are *likely to hire* in a given ROME
code + commune, even when they have published no formal job offer.  Results
are normalised as JobPosting with a "(marché caché)" title prefix so callers
can distinguish them from explicit postings.

Auth:      OAuth2 client_credentials — reuses the France Travail token helper.
Env:       FRANCE_TRAVAIL_ID, FRANCE_TRAVAIL_SECRET
Scope:     api_labonneboitev1 (preferred) — if rejected by the token endpoint,
           fall back to the offres scope used by france_travail.py.
           NOTE: scope acceptance requires the partner to have subscribed to
           the La Bonne Boîte product in the France Travail developer portal.
           See live-verification note in the project report.

Endpoint family:
    GET https://api.francetravail.io/partenaire/labonneboite/v1/company/
        ?rome_codes=<ROME>&commune_id=<INSEE>&distance=<km>

Reference:
    https://francetravail.io/produits-services/api/la-bonne-boite
"""

from __future__ import annotations

from typing import Any

import httpx

from decroche.models import JobPosting
from decroche.source.http import ToolError, fetch_json, require_env

_TOKEN_URL = "https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=%2Fpartenaire"
_SEARCH_URL = "https://api.francetravail.io/partenaire/labonneboite/v1/company/"

# Preferred scope for La Bonne Boîte; the token endpoint may reject it if the
# partner account has not subscribed — in that case the caller will receive an
# HTTP 400/401.  Live verification required.
_SCOPE = "api_labonneboitev1"


async def _get_token(client_id: str, client_secret: str) -> str:
    """Obtain a Bearer token via client_credentials grant (LBB scope)."""
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(
            _TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
                "scope": _SCOPE,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()
        data = resp.json()
    token = data.get("access_token")
    if not token:
        raise ToolError("La Bonne Boîte: token response missing 'access_token'")
    return str(token)


async def fetch(
    rome: str,
    commune: str,
    *,
    distance: int = 10,
) -> dict:
    """Fetch companies likely to hire from La Bonne Boîte API.

    Args:
        rome:     ROME occupation code (e.g. ``"M1805"``).
        commune:  INSEE commune code (e.g. ``"69123"`` for Lyon).
        distance: Radius in km around the commune (default 10).

    Returns:
        Raw API response dict.

    Raises:
        MissingKeyError: if FRANCE_TRAVAIL_ID or FRANCE_TRAVAIL_SECRET not set.
        ToolError:       on HTTP or network errors.
    """
    keys = require_env("FRANCE_TRAVAIL_ID", "FRANCE_TRAVAIL_SECRET")
    token = await _get_token(keys["FRANCE_TRAVAIL_ID"], keys["FRANCE_TRAVAIL_SECRET"])

    params: dict[str, Any] = {
        "rome_codes": rome,
        "commune_id": commune,
        "distance": distance,
    }

    return await fetch_json(
        _SEARCH_URL,
        params=params,
        headers={"Authorization": f"Bearer {token}"},
        provider="labonneboite",
    )


def normalize(raw: dict | list) -> list[JobPosting]:
    """Normalise a La Bonne Boîte API response → list[JobPosting].

    Each company is mapped as a JobPosting with:
    - title = "(marché caché) <company name>"
    - url   = company LBB page (or fallback search URL if absent)

    Accepts either the full envelope ``{"companies": [...]}`` or a bare list.
    """
    if isinstance(raw, dict):
        items: list[dict[str, Any]] = raw.get("companies", [])
    else:
        items = list(raw)

    results: list[JobPosting] = []
    for item in items:
        if not isinstance(item, dict):
            continue

        siret = str(item.get("siret", ""))
        name = item.get("name") or ""
        title = f"(marché caché) {name}".strip()

        city = item.get("city") or ""
        zipcode = item.get("zipcode") or ""
        location_parts = [p for p in [city, zipcode] if p]
        location: str | None = ", ".join(location_parts) if location_parts else None

        raw_url = item.get("url")
        if raw_url:
            url = str(raw_url)
        else:
            # Fallback: La Bonne Boîte search URL with SIRET
            url = (
                f"https://labonneboite.francetravail.fr/entreprise/{siret}"
                if siret
                else ("https://labonneboite.francetravail.fr/")
            )

        # Build a brief description from available metadata
        naf_text = item.get("naf_text") or ""
        headcount = item.get("headcount_text") or ""
        desc_parts = [p for p in [naf_text, headcount] if p]
        description = " — ".join(desc_parts)

        results.append(
            JobPosting(
                source="labonneboite",
                source_id=siret,
                title=title,
                company=name or None,
                location=location,
                remote=None,
                url=url,
                apply_url=None,
                date_posted=None,
                description=description,
                salary=None,
                tags=[],
                raw=item,
            )
        )
    return results
