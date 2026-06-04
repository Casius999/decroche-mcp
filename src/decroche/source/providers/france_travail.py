"""France Travail (Pôle Emploi) API v2 provider.

Auth: OAuth2 client_credentials (POST token endpoint) → Bearer on search endpoint.
Env:  FRANCE_TRAVAIL_ID, FRANCE_TRAVAIL_SECRET

Docs: https://francetravail.io/produits-services/api/offres-demploi
"""
from __future__ import annotations

from typing import Any

import httpx

from decroche.models import JobPosting
from decroche.source.http import ToolError, fetch_json, require_env

_TOKEN_URL = (
    "https://entreprise.francetravail.fr/connexion/oauth2/access_token"
    "?realm=%2Fpartenaire"
)
_SEARCH_URL = (
    "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"
)
_SCOPE = "api_offresdemploiv2 o2dsoffre"


async def _get_token(client_id: str, client_secret: str) -> str:
    """Obtain a Bearer token via client_credentials grant."""
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
        raise ToolError("France Travail: token response missing 'access_token'")
    return str(token)


async def fetch(query: str, location: str = "") -> dict:
    """Fetch job offers from France Travail search API.

    Raises:
        MissingKeyError: if FRANCE_TRAVAIL_ID or FRANCE_TRAVAIL_SECRET not set.
    """
    keys = require_env("FRANCE_TRAVAIL_ID", "FRANCE_TRAVAIL_SECRET")
    token = await _get_token(keys["FRANCE_TRAVAIL_ID"], keys["FRANCE_TRAVAIL_SECRET"])

    params: dict[str, Any] = {"motsCles": query}
    if location:
        params["commune"] = location

    return await fetch_json(
        _SEARCH_URL,
        params=params,
        headers={"Authorization": f"Bearer {token}"},
    )


def normalize(raw: dict | list) -> list[JobPosting]:
    """Normalise France Travail search response → list[JobPosting]."""
    if isinstance(raw, dict):
        items: list[dict] = raw.get("resultats", [])
    else:
        items = list(raw)

    results: list[JobPosting] = []
    for item in items:
        if not isinstance(item, dict):
            continue

        job_id = str(item.get("id", ""))
        title = item.get("intitule") or ""
        company_data = item.get("entreprise") or {}
        company = company_data.get("nom") if isinstance(company_data, dict) else None

        lieu = item.get("lieuTravail") or {}
        location = lieu.get("libelle") if isinstance(lieu, dict) else None

        # remote flag: France Travail does not have a direct remote field
        remote: bool | None = None

        url_raw = item.get("origineOffre") or {}
        url = url_raw.get("urlOrigine") if isinstance(url_raw, dict) else None
        if not url:
            url = f"https://candidat.francetravail.fr/offres/recherche/detail/{job_id}"

        date_posted = item.get("dateCreation") or item.get("dateActualisation")
        description = item.get("description") or ""
        salary_data = item.get("salaire") or {}
        salary = salary_data.get("libelle") if isinstance(salary_data, dict) else None

        competences = item.get("competences") or []
        tags = [
            c.get("libelle", "")
            for c in competences
            if isinstance(c, dict) and c.get("libelle")
        ]

        results.append(
            JobPosting(
                source="france_travail",
                source_id=job_id,
                title=title,
                company=company,
                location=location,
                remote=remote,
                url=url,
                apply_url=None,
                date_posted=str(date_posted) if date_posted else None,
                description=description,
                salary=salary,
                tags=tags,
                raw=item,
            )
        )
    return results
