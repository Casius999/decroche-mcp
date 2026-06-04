"""recruiter.message — draft a tasteful outreach scaffold.

Pure deterministic function. No LLM, no network.

COMPLIANCE (RGPD/CNIL):
- Every French-language draft MUST contain an opt-out sentence.
  Standard wording: "Si vous ne souhaitez pas être recontacté(e), dites-le moi et
  je supprimerai vos coordonnées."
- The host LLM is expected to personalise the scaffold; this function produces only
  the structural skeleton.
"""

from __future__ import annotations

from decroche.models import IntroRequest, Recruiter

_OPTOUT_FR = (
    "Si vous ne souhaitez pas être recontacté(e), dites-le moi et je supprimerai vos coordonnées."
)

_OPTOUT_EN = (
    "If you'd prefer not to hear from me, just let me know "
    "and I'll remove your details from my list."
)

_SUBJECT_FR = "Candidature — {offer_title}"
_SUBJECT_EN = "Application — {offer_title}"

_BODY_FR = """\
Bonjour {recruiter_name},

Je me permets de vous contacter au sujet du poste de {offer_title}.

{candidate_summary}

Je serais ravi(e) d'échanger avec vous sur cette opportunité et de vous présenter \
mon parcours plus en détail.

Cordialement,
[Votre prénom et nom]

---
{optout}"""

_BODY_EN = """\
Hi {recruiter_name},

I'm reaching out regarding the {offer_title} position.

{candidate_summary}

I'd love to connect and share more about my background.

Best regards,
[Your name]

---
{optout}"""


def draft_message(
    recruiter: Recruiter,
    candidate_summary: str,
    offer_title: str,
    lang: str = "fr",
) -> IntroRequest:
    """Draft an outreach message scaffold for a recruiter.

    COMPLIANCE: French drafts always include the RGPD opt-out line.

    Args:
        recruiter:          Target recruiter (:class:`Recruiter`).
        candidate_summary:  Short (1–3 sentence) summary of the candidate.
        offer_title:        Job title / offer name.
        lang:               "fr" (default) or "en".

    Returns:
        :class:`IntroRequest` with to, subject, body (opt-out included for FR),
        and lang.
    """
    name_parts = recruiter.name.strip().split()
    first_name = name_parts[0] if name_parts else recruiter.name

    if lang == "en":
        subject = _SUBJECT_EN.format(offer_title=offer_title)
        body = _BODY_EN.format(
            recruiter_name=first_name,
            offer_title=offer_title,
            candidate_summary=candidate_summary,
            optout=_OPTOUT_EN,
        )
    else:
        # Default to French for any non-"en" lang value
        subject = _SUBJECT_FR.format(offer_title=offer_title)
        body = _BODY_FR.format(
            recruiter_name=first_name,
            offer_title=offer_title,
            candidate_summary=candidate_summary,
            optout=_OPTOUT_FR,
        )

    return IntroRequest(
        to=recruiter.name,
        subject=subject,
        body=body,
        lang=lang if lang in {"fr", "en"} else "fr",
    )
