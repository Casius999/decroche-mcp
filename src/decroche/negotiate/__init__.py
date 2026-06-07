"""negotiate sub-package — FastMCP sub-server for salary negotiation."""

from __future__ import annotations

from fastmcp import FastMCP

from decroche.models import CounterOffer, SalaryRange, TotalComp
from decroche.negotiate.benchmark import benchmark_range as _benchmark_range
from decroche.negotiate.counter import competing_offer_script as _competing_script
from decroche.negotiate.counter import counter_offer_template as _counter_offer
from decroche.negotiate.counter import total_comp as _total_comp

negotiate_server = FastMCP("negotiate")


@negotiate_server.tool
def benchmark_range(
    role_family: str,
    seniority: str,
    region: str,
) -> SalaryRange:
    """Return a sourced salary benchmark for a role/seniority/region.

    Uses the bundled ``salary_benchmarks.yaml`` dataset. Returns the closest
    match with ``approximate=True`` and a note if an exact match is absent.

    Args:
        role_family: e.g. ``"software"``, ``"data"``, ``"product"``, ``"sales"``.
        seniority:   One of ``"junior"``, ``"mid"``, ``"senior"``, ``"lead"``.
        region:      One of ``"fr"``, ``"us"``, ``"uk"``, ``"ca"``.

    Returns:
        SalaryRange with P25/P50/P75, currency, variable_pct, source.

    Raises:
        LookupError: if no match can be found at all.
    """
    return _benchmark_range(role_family=role_family, seniority=seniority, region=region)


@negotiate_server.tool
def counter_offer_template(
    offer: dict,
    target: dict,
    market_id: str = "fr",
) -> CounterOffer:
    """Build a counter-offer message scaffold (FR or EN register).

    Args:
        offer:     Dict with ``company``, ``role``, ``amount``, ``currency``,
                   ``hiring_manager``.
        target:    Dict with ``base``, ``role_family``, ``seniority``,
                   ``region``, ``p50``, ``p75``, ``source``.
        market_id: ``"fr"`` (default) or ``"en"``.

    Returns:
        CounterOffer with subject, body, lang, target salary, and rationale.
    """
    return _counter_offer(offer=offer, target=target, market_id=market_id)


@negotiate_server.tool
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
        variable_pct:  Variable as fraction of base (e.g. 0.15 = 15 %).
        signing:       One-time signing bonus (annualised over ``years``).
        equity_total:  Total equity grant value (annualised over ``years``).
        years:         Vesting/amortisation period (default 4).
        currency:      Currency code (default ``"EUR"``).

    Returns:
        TotalComp with base, variable, signing, equity_annualized, total, currency.
    """
    return _total_comp(
        base=base,
        variable_pct=variable_pct,
        signing=signing,
        equity_total=equity_total,
        years=years,
        currency=currency,
    )


@negotiate_server.tool
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
        company:          The preferred company you're negotiating with.
        competitor:       The company making the competing offer.
        competing_amount: Competing offer base salary (numeric).
        competing_role:   Job title at the competing company.
        currency:         Currency code (default ``"EUR"``).
        lang:             ``"fr"`` (default) or ``"en"``.

    Returns:
        A text script with an opening line and coaching notes.
    """
    return _competing_script(
        company=company,
        competitor=competitor,
        competing_amount=competing_amount,
        competing_role=competing_role,
        currency=currency,
        lang=lang,
    )
