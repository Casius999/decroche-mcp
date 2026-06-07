"""interview.company_brief — Pure scaffold for company research before an interview.

No network calls, no LLM invocations.  Returns a structured skeleton the host
LLM fills in using its own knowledge / web-search results.

HONESTY: sections carry [TO_RESEARCH] placeholders when facts are unknown.
The research_checklist tells the user what to verify before the interview.
"""

from __future__ import annotations

from decroche.models import CompanyBrief

_CHECKLIST_BASE = [
    "Vérifier les dernières actualités de l'entreprise (press releases, LinkedIn)",
    "Lire le rapport annuel ou la page 'À propos' sur le site officiel",
    "Identifier le/la DG et les dirigeants clés",
    "Rechercher des articles récents (6 mois) sur Glassdoor/Indeed pour la culture",
    "Repérer les valeurs affichées et exemples concrets de mise en pratique",
    "Trouver le nom du/de la responsable de l'équipe cible si possible",
    "Préparer 3 questions pertinentes basées sur les actualités récentes",
]


def company_brief(
    company: str,
    notes: str = "",
    jobs: list[dict] | None = None,
) -> CompanyBrief:
    """Build a structured research scaffold for interview preparation.

    PURE function — no network, no LLM. The host LLM is responsible for
    filling the [TO_RESEARCH] placeholders with real information.

    Args:
        company: The company name.
        notes:   Free-text notes the user has already gathered (optional).
        jobs:    List of JobPosting-like dicts (optional); used to extract
                 role context and infer tech tags.

    Returns:
        CompanyBrief with 5-section skeleton and a research checklist.
    """
    # ── derive context from jobs ────────────────────────────────────────────────────────────────────
    role_context = "[TO_RESEARCH] Rôle(s) ciblé(s) et responsabilités clés"
    tech_tags: list[str] = []
    if jobs:
        titles = [j.get("title", "") for j in jobs if j.get("title")]
        if titles:
            joined = ", ".join(titles[:3])
            role_context = (
                f"Poste(s) identifié(s) : {joined}. [TO_RESEARCH] Responsabilités détaillées"
            )
        for j in jobs:
            for tag in j.get("tags", []):
                if tag and tag not in tech_tags:
                    tech_tags.append(tag)

    tech_hint = (
        f"Tags technologiques repérés dans les offres : {', '.join(tech_tags[:8])}."
        if tech_tags
        else "[TO_RESEARCH] Stack technique"
    )

    # ── notes preamble ────────────────────────────────────────────────────────────────────────
    notes_hint = (
        f"Notes utilisateur : {notes.strip()}"
        if notes.strip()
        else "[TO_RESEARCH] Aucune note fournie"
    )

    sections: dict[str, str] = {
        "what_they_do": (
            f"[TO_RESEARCH] Activité principale, secteur, taille, marchés. "
            f"{notes_hint}. {tech_hint}"
        ),
        "recent_signals": (
            "[TO_RESEARCH] Actualités récentes (levées de fonds, partenariats, "
            "recrutements, produits lancés, articles de presse 6 derniers mois)"
        ),
        "culture": (
            "[TO_RESEARCH] Valeurs affichées, avis Glassdoor/Indeed, style de management, "
            "remote policy, diversité & inclusion"
        ),
        "role_context": role_context,
        "questions_to_ask": (
            "[TO_RESEARCH] 3–5 questions préparées basées sur les signaux récents "
            "et la culture pour montrer ton intérêt et ta préparation"
        ),
    }

    # ── research checklist ─────────────────────────────────────────────────────────────────────────
    checklist = list(_CHECKLIST_BASE)
    if tech_tags:
        checklist.append(f"Approfondir les technologies utilisées : {', '.join(tech_tags[:5])}")

    return CompanyBrief(
        company=company,
        sections=sections,
        research_checklist=checklist,
    )
