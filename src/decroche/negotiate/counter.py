"""negotiate.counter — Salary negotiation scaffolds.

All functions are PURE — deterministic, no network, no LLM.
The host LLM personalises the [PLACEHOLDER] sections.
"""

from __future__ import annotations

from decroche.models import CounterOffer, TotalComp

# ── FR counter-offer template ───────────────────────────────────────────────────────────────────
_FR_COUNTER = """\
Objet : {subject}

Bonjour {hiring_manager},

Je vous remercie pour votre offre relative au poste de {role}. \
Je suis très enthousiaste à l'idée de rejoindre {company} et de \
contribuer à [VALEUR SPÉCIFIQUE QUE VOUS APPORTEZ].

À la suite de mes recherches sur les niveaux de rémunération actuels \
pour ce type de profil ({role_family}, niveau {seniority}, région {region}), \
les données de marché (source : {source}) indiquent une médiane de {p50} {currency} \
avec un P75 à {p75} {currency}.

Compte tenu de [VOTRE EXPÉRIENCE / COMPÉTENCES CLÉS / RÉALISATIONS], \
je souhaiterais vous proposer une rémunération de base de {target} {currency}.

Je reste bien entendu ouvert·e à la discussion sur l'ensemble du package \
(variable, avantages, remote, formation) afin de trouver un accord \
mutuellement bénéfique.

Dans l'attente de votre retour, je reste à votre disposition.

Cordialement,
[Votre prénom et nom]
"""

# ── EN counter-offer template ───────────────────────────────────────────────────────────────────
_EN_COUNTER = """\
Subject: {subject}

Hi {hiring_manager},

Thank you for extending an offer for the {role} position. \
I'm very excited about the opportunity to join {company} and \
contribute to [SPECIFIC VALUE YOU BRING].

Based on my research into current compensation for this profile \
({role_family}, {seniority} level, {region} market), \
market data (source: {source}) shows a median of {p50} {currency} \
with a P75 at {p75} {currency}.

Given [YOUR EXPERIENCE / KEY SKILLS / ACHIEVEMENTS], \
I would like to propose a base salary of {target} {currency}.

I'm happy to discuss the full package (bonus, benefits, remote policy, \
learning budget) to reach a mutually beneficial agreement.

Looking forward to your response.

Best regards,
[Your name]
"""

# ── Competing offer script ──────────────────────────────────────────────────────────────────────
_FR_COMPETING = """\
Script — offre concurrente (FR)

Contexte : Vous avez reçu une offre de {competitor} à {competing_amount} {currency}. \
Vous préférez rejoindre {company} mais souhaitez aligner les conditions.

Phrase d'ouverture :
« J'ai reçu une autre offre de {competing_amount} {currency} \
de la part de {competitor} pour un poste de {competing_role}. \
Je tiens à être transparent·e car ma préférence reste {company}. \
Seriez-vous en mesure de revoir le package pour qu'on puisse avancer ensemble ? »

Points à valoriser (à personnaliser) :
- [Pourquoi vous préférez {company}]
- [Ce que vous apportez de spécifique]
- [Ce sur quoi vous êtes flexible]

À ne pas dire :
- Ne bluffez pas sur une offre inexistante.
- N'utilisez pas l'offre comme ultimatum ; restez collaboratif·ve.
"""

_EN_COMPETING = """\
Script — competing offer (EN)

Context: You have received an offer from {competitor} at {competing_amount} {currency}. \
You prefer {company} but want to align compensation.

Opening line:
"I've received another offer from {competitor} for a {competing_role} role \
at {competing_amount} {currency}. I want to be transparent because my first \
choice is {company}. Is there any flexibility in the package so we can move forward together?"

Points to highlight (customise):
- [Why you prefer {company}]
- [What you uniquely bring]
- [Where you're flexible]

Do not:
- Bluff about an offer that doesn't exist.
- Use it as an ultimatum — stay collaborative.
"""


def counter_offer_template(
    offer: dict,
    target: dict,
    market_id: str = "fr",
) -> CounterOffer:
    """Build a counter-offer message scaffold.

    Args:
        offer: Dict with keys: ``company``, ``role``, ``amount`` (current offer),
               ``currency`` (e.g. ``"EUR"``), ``hiring_manager`` (name).
        target: Dict with keys: ``base`` (target salary), ``role_family``,
                ``seniority``, ``region``, ``p50``, ``p75``, ``source``.
        market_id: ``"fr"`` (default) or ``"en"`` — determines the email register.

    Returns:
        CounterOffer with subject, body, lang, target base, and rationale.
    """
    lang = "fr" if market_id.lower().strip() == "fr" else "en"
    currency = offer.get("currency", "EUR")
    company = offer.get("company", "[Entreprise]")
    role = offer.get("role", "[Poste]")
    hiring_manager = offer.get("hiring_manager", "[Responsable RH]")
    target_base = float(target.get("base", 0))
    p50 = target.get("p50", 0)
    p75 = target.get("p75", 0)
    role_family = target.get("role_family", "")
    seniority = target.get("seniority", "")
    region = target.get("region", "")
    source = target.get("source", "données de marché")

    rationale = (
        f"Médiane marché : {p50} {currency} (P75 : {p75} {currency}) "
        f"— source : {source} — cible : {target_base} {currency} "
        f"({'+' if target_base >= p50 else ''}{((target_base / p50 - 1) * 100):.1f}% vs P50)."
        if lang == "fr"
        else (
            f"Market median: {p50} {currency} (P75: {p75} {currency}) "
            f"— source: {source} — target: {target_base} {currency} "
            f"({'+' if target_base >= p50 else ''}{((target_base / p50 - 1) * 100):.1f}% vs P50)."
        )
    )

    if lang == "fr":
        subject = f"Proposition de rémunération — {role}"
        body = _FR_COUNTER.format(
            subject=subject,
            hiring_manager=hiring_manager,
            role=role,
            company=company,
            role_family=role_family,
            seniority=seniority,
            region=region,
            source=source,
            p50=p50,
            p75=p75,
            target=int(target_base),
            currency=currency,
        ).strip()
    else:
        subject = f"Compensation discussion — {role}"
        body = _EN_COUNTER.format(
            subject=subject,
            hiring_manager=hiring_manager,
            role=role,
            company=company,
            role_family=role_family,
            seniority=seniority,
            region=region,
            source=source,
            p50=p50,
            p75=p75,
            target=int(target_base),
            currency=currency,
        ).strip()

    return CounterOffer(
        subject=subject,
        body=body,
        lang=lang,
        target=target_base,
        rationale=rationale,
    )


def total_comp(
    base: float,
    variable_pct: float = 0.0,
    signing: float = 0.0,
    equity_total: float = 0.0,
    years: int = 4,
    currency: str = "EUR",
) -> TotalComp:
    """Compute annualised total compensation breakdown.

    Args:
        base:          Annual base salary.
        variable_pct:  Variable as a fraction of base (e.g. ``0.15`` = 15 %).
        signing:       One-time signing bonus (annualised over ``years``).
        equity_total:  Total equity grant value (annualised over ``years``).
        years:         Vesting / amortisation period (default 4).
        currency:      Currency code (default ``"EUR"``).

    Returns:
        TotalComp with all components and total.
    """
    variable_amount = base * variable_pct
    signing_annual = signing / max(1, years)
    equity_annual = equity_total / max(1, years)
    total = base + variable_amount + signing_annual + equity_annual

    return TotalComp(
        base=round(base, 2),
        variable=round(variable_amount, 2),
        signing=round(signing_annual, 2),
        equity_annualized=round(equity_annual, 2),
        total=round(total, 2),
        currency=currency,
    )


def competing_offer_script(
    company: str,
    competitor: str,
    competing_amount: float,
    competing_role: str,
    currency: str = "EUR",
    lang: str = "fr",
) -> str:
    """Generate a competing-offer negotiation script.

    Args:
        company:          The preferred company (the one you're negotiating with).
        competitor:       The competing company making the other offer.
        competing_amount: The competing offer base salary.
        competing_role:   Job title at the competing company.
        currency:         Currency code.
        lang:             ``"fr"`` (default) or ``"en"``.

    Returns:
        A text script with opening line and coaching notes.
    """
    lang_lower = lang.lower().strip()
    template = _FR_COMPETING if lang_lower == "fr" else _EN_COMPETING
    return template.format(
        company=company,
        competitor=competitor,
        competing_amount=int(competing_amount),
        competing_role=competing_role,
        currency=currency,
    ).strip()
