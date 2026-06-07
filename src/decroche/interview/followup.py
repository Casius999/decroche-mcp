"""interview.followup — Post-interview follow-up message scaffolds.

PURE functions — no network, no LLM, deterministic.
The host LLM personalises the placeholders; these functions provide the
structure and locale-aware register.
"""

from __future__ import annotations

_FR_THANK_YOU = """\
Objet : {subject}

Bonjour {interviewer},

Je souhaitais vous remercier pour le temps que vous m'avez accordé lors de notre entretien concernant le poste de {role}.

L'échange a confirmé mon intérêt pour ce poste et pour [CE QUI VOUS A MARQUÉ — à personnaliser]. \
Je suis enthousiaste à l'idée de rejoindre votre équipe et de contribuer à [OBJECTIF MENTIONNÉ EN ENTRETIEN].

N'hésitez pas à me contacter si vous avez besoin d'informations complémentaires.

Cordialement,
[Votre prénom et nom]
"""

_EN_THANK_YOU = """\
Subject: {subject}

Hi {interviewer},

Thank you for taking the time to speak with me about the {role} position.

Our conversation confirmed my enthusiasm for this opportunity and particularly for \
[WHAT RESONATED — personalize]. I am excited about the prospect of joining your team \
and contributing to [GOAL MENTIONED IN INTERVIEW].

Please don't hesitate to reach out if you need any additional information.

Best regards,
[Your name]
"""

_FR_DEBRIEF = """\
# Compte-rendu d'entretien — {role}

## Informations clés
- Entreprise : [À compléter]
- Interlocuteur(s) : [À compléter]
- Date / Heure : [À compléter]
- Durée : [À compléter]

## Ce qui s'est bien passé
- [Point fort 1]
- [Point fort 2]

## Questions posées
1. [Question 1 — et ma réponse résumée]
2. [Question 2 — et ma réponse résumée]
3. [Question 3 — et ma réponse résumée]

## Signaux positifs / négatifs perçus
- [Signal positif]
- [Point d'attention]

## Prochaines étapes annoncées
- [Délai de réponse mentionné]
- [Prochaine étape du processus]

## Actions à mener
- [ ] Envoyer le message de remerciement
- [ ] Relancer si pas de retour d'ici [DATE]
- [ ] Mettre à jour le CRM
"""

_EN_DEBRIEF = """\
# Interview Debrief — {role}

## Key Info
- Company: [Fill in]
- Interviewer(s): [Fill in]
- Date / Time: [Fill in]
- Duration: [Fill in]

## What went well
- [Strength 1]
- [Strength 2]

## Questions asked
1. [Question 1 — and my summary answer]
2. [Question 2 — and my summary answer]
3. [Question 3 — and my summary answer]

## Positive / negative signals perceived
- [Positive signal]
- [Watch point]

## Next steps mentioned
- [Timeline for decision]
- [Next process step]

## Actions
- [ ] Send thank-you message
- [ ] Follow up if no reply by [DATE]
- [ ] Update CRM
"""


def thank_you(
    interviewer: str,
    role: str,
    lang: str = "fr",
) -> str:
    """Generate a thank-you message scaffold.

    Args:
        interviewer: The interviewer's first name or full name.
        role:        The job title / role name.
        lang:        ``"fr"`` (default) or ``"en"``.

    Returns:
        A locale-appropriate thank-you message scaffold with [PLACEHOLDERS]
        for personalisation by the host LLM.
    """
    lang_lower = lang.lower().strip()
    if lang_lower == "fr":
        subject = f"Suite à notre entretien — {role}"
        template = _FR_THANK_YOU
    else:
        subject = f"Thank you — {role} interview"
        template = _EN_THANK_YOU

    return template.format(interviewer=interviewer, role=role, subject=subject).strip()


def debrief_template(role: str, lang: str = "fr") -> str:
    """Generate a post-interview debrief template.

    Args:
        role: The job title / role name.
        lang: ``"fr"`` (default) or ``"en"``.

    Returns:
        A markdown-formatted debrief scaffold.
    """
    lang_lower = lang.lower().strip()
    if lang_lower == "fr":
        return _FR_DEBRIEF.format(role=role).strip()
    return _EN_DEBRIEF.format(role=role).strip()
