"""network.paths — warm introduction path finder and intro request drafter.

COMPLIANCE:
- Operates ONLY on user-provided connection lists (each item is a dict the
  user supplies). NO LinkedIn traversal, NO automated profile lookup.
- Connections must be provided explicitly by the user.

Each connection dict is expected to have:
  - name        : str — connector's full name
  - company     : str — current company
  - relationship: str — e.g. "former colleague", "university friend", "mentor"

Optional keys:
  - note        : str — extra context the user adds
"""

from __future__ import annotations


from decroche.models import IntroRequest, NetworkPath

# Relationship strength hierarchy for scoring
_RELATIONSHIP_SCORE: dict[str, float] = {
    # Strong
    "friend": 1.0,
    "ami": 1.0,
    "amie": 1.0,
    "former manager": 0.95,
    "ancien manager": 0.95,
    "mentor": 0.95,
    "mentee": 0.90,
    # Medium-strong
    "former colleague": 0.75,
    "ancien collègue": 0.75,
    "ancien collegue": 0.75,
    "colleague": 0.70,
    "collègue": 0.70,
    "collegue": 0.70,
    "university friend": 0.70,
    "camarade de promo": 0.70,
    "school friend": 0.65,
    # Medium
    "acquaintance": 0.40,
    "connaissance": 0.40,
    "linkedin connection": 0.25,
    "connexion linkedin": 0.25,
    "contact": 0.30,
}


def _relationship_weight(relationship: str) -> float:
    """Map a relationship string to a 0–1 weight (lower-bound 0.15)."""
    key = relationship.strip().lower()
    if key in _RELATIONSHIP_SCORE:
        return _RELATIONSHIP_SCORE[key]
    # Partial match
    for pattern, weight in _RELATIONSHIP_SCORE.items():
        if pattern in key or key in pattern:
            return weight
    return 0.20  # unknown relationship, weak signal


def _company_match(conn_company: str, target_company: str) -> bool:
    """True if connection's company matches (or contains) target_company."""
    return target_company.lower().strip() in conn_company.lower().strip() or (
        conn_company.lower().strip() in target_company.lower().strip()
    )


def find_warm_path(
    target_company: str,
    connections: list[dict],
) -> list[NetworkPath]:
    """Find warm introduction paths to a target company from user-provided connections.

    COMPLIANCE: only the ``connections`` list the user provides is used.
    No LinkedIn traversal, no external lookups.

    Args:
        target_company: Name of the company the user wants to approach.
        connections:    List of connection dicts; each must have:
                        ``name`` (str), ``company`` (str), ``relationship`` (str).
                        Optional: ``note`` (str).

    Returns:
        List of :class:`NetworkPath` sorted by intro value (highest first).
        Empty list if no connections match the target company.
    """
    paths: list[NetworkPath] = []
    for conn in connections:
        conn_company = conn.get("company", "")
        if not conn_company:
            continue
        if not _company_match(conn_company, target_company):
            continue
        name = conn.get("name", "Unknown")
        relationship = conn.get("relationship", "contact")
        note = conn.get("note") or None
        paths.append(
            NetworkPath(
                target_company=target_company,
                connector=name,
                relationship=relationship,
                hops=1,
                note=note,
            )
        )

    # Sort by intro value descending
    paths.sort(key=lambda p: score_intro_value(p), reverse=True)
    return paths


def score_intro_value(path: NetworkPath) -> float:
    """Score the intro value of a :class:`NetworkPath` (0–1).

    Factors:
    - Relationship strength (primary).
    - Hops: direct (hops=1) is full weight; hops=2 is halved, etc.
    - Company match is implicit (only matched paths reach this function).

    Args:
        path: A :class:`NetworkPath`.

    Returns:
        Float 0–1 representing intro value.
    """
    rel_weight = _relationship_weight(path.relationship)
    hop_discount = 1.0 / path.hops  # hops=1 → 1.0, hops=2 → 0.5, etc.
    return round(min(1.0, rel_weight * hop_discount), 3)


_OPTOUT_FR = (
    "Si tu ne souhaites pas faciliter cette mise en relation, "
    "dis-le moi et je ne t'en parlerai plus."
)

_OPTOUT_EN = "If you'd rather not make this intro, no worries at all — just let me know."

_SUBJECT_FR = "Mise en relation — {target_company}"
_SUBJECT_EN = "Introduction request — {target_company}"

_BODY_FR = """\
Bonjour {connector},

J'espère que tu vas bien. Je me permets de te contacter car je suis très intéressé(e) \
par une opportunité chez {target_company} ({context}).

Sais-tu s'il y a des postes ouverts ou pourrais-tu me mettre en relation \
avec quelqu'un de l'équipe recrutement ?

Merci d'avance pour ton aide !

À bientôt,
[Ton prénom]

---
{optout}"""

_BODY_EN = """\
Hi {connector},

Hope you're doing well! I'm exploring opportunities at {target_company} \
({context}) and would love an introduction.

Would you be comfortable connecting me with someone on their recruiting team, \
or letting me know if you're aware of any open roles?

Thanks so much!

Best,
[Your name]

---
{optout}"""


def draft_intro_request(
    path: NetworkPath,
    context: str = "",
    lang: str = "fr",
) -> IntroRequest:
    """Draft an intro request message scaffold.

    COMPLIANCE: French drafts include an opt-out line.

    Args:
        path:    A :class:`NetworkPath` (from ``find_warm_path``).
        context: Brief context (e.g. role sought, reason for interest).
        lang:    "fr" (default) or "en".

    Returns:
        :class:`IntroRequest` with to, subject, body, lang.
    """
    connector_first = path.connector.strip().split()[0]
    ctx = context or "poste ouvert"

    if lang == "en":
        subject = _SUBJECT_EN.format(target_company=path.target_company)
        body = _BODY_EN.format(
            connector=connector_first,
            target_company=path.target_company,
            context=ctx,
            optout=_OPTOUT_EN,
        )
    else:
        subject = _SUBJECT_FR.format(target_company=path.target_company)
        body = _BODY_FR.format(
            connector=connector_first,
            target_company=path.target_company,
            context=ctx,
            optout=_OPTOUT_FR,
        )

    return IntroRequest(
        to=path.connector,
        subject=subject,
        body=body,
        lang=lang if lang in {"fr", "en"} else "fr",
    )
