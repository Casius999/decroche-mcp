"""apply.followup — Pure deterministic follow-up message template.

Generates a polite follow-up template string. Actual sending is always
human-confirmed (Phase 4b browser). This function is a pure scaffold.
"""

from __future__ import annotations

from decroche.models import Application

_TEMPLATE_FR = """\
Objet : Candidature — {role_title}{company_part}

Bonjour,

Je me permets de vous recontacter au sujet de ma candidature pour le poste de \
{role_title}{company_part}, déposée il y a quelques semaines.

Je reste très intéressé(e) par cette opportunité et souhaite vous confirmer ma \
motivation. N'hésitez pas à me contacter si vous avez besoin d'informations complémentaires.

Dans l'attente de votre retour, je vous adresse mes cordiales salutations.
"""

_TEMPLATE_EN = """\
Subject: Application Follow-Up — {role_title}{company_part}

Dear Hiring Team,

I am writing to follow up on my application for the {role_title} position\
{company_part_long}, submitted a few weeks ago.

I remain very interested in this opportunity and would be happy to provide any \
additional information you might need.

Thank you for your time, and I look forward to hearing from you.

Kind regards,
"""


def draft_followup(app: Application, lang: str = "fr") -> str:
    """Draft a polite follow-up message for a job application.

    This function is a pure template scaffold. Sending is always
    human-confirmed (Phase 4b). No network calls are made.

    Args:
        app:  The Application being followed up.
        lang: Language code — ``"fr"`` (default) or ``"en"``.

    Returns:
        A formatted follow-up message string.
    """
    role = app.role_title or "poste"
    company = app.company

    if lang == "fr":
        company_part = f" chez {company}" if company else ""
        return _TEMPLATE_FR.format(
            role_title=role,
            company_part=company_part,
        ).strip()
    else:
        company_part = f" at {company}" if company else ""
        company_part_long = f" at {company}" if company else ""
        return _TEMPLATE_EN.format(
            role_title=role,
            company_part=company_part,
            company_part_long=company_part_long,
        ).strip()
