"""Tests for negotiate.counter (counter_offer_template, total_comp, competing_offer_script)."""

from __future__ import annotations

import pytest

from decroche.models import CounterOffer, TotalComp
from decroche.negotiate.counter import (
    competing_offer_script,
    counter_offer_template,
    total_comp,
)


# ── Fixtures ────────────────────────────────────────────────────────────────


def _offer_fr():
    return {
        "company": "DataCorp",
        "role": "Senior Data Engineer",
        "amount": 55000,
        "currency": "EUR",
        "hiring_manager": "Sophie Martin",
    }


def _target_fr():
    return {
        "base": 65000,
        "role_family": "data",
        "seniority": "senior",
        "region": "fr",
        "p50": 62000,
        "p75": 75000,
        "source": "APEC 2024",
    }


def _offer_en():
    return {
        "company": "TechInc",
        "role": "Software Engineer",
        "amount": 140000,
        "currency": "USD",
        "hiring_manager": "John Smith",
    }


def _target_en():
    return {
        "base": 165000,
        "role_family": "software",
        "seniority": "senior",
        "region": "us",
        "p50": 155000,
        "p75": 195000,
        "source": "Levels.fyi 2024",
    }


# ── counter_offer_template tests ───────────────────────────────────────────────


def test_returns_counter_offer():
    result = counter_offer_template(_offer_fr(), _target_fr())
    assert isinstance(result, CounterOffer)


def test_fr_lang_set():
    result = counter_offer_template(_offer_fr(), _target_fr(), market_id="fr")
    assert result.lang == "fr"


def test_en_lang_set():
    result = counter_offer_template(_offer_en(), _target_en(), market_id="en")
    assert result.lang == "en"


def test_fr_body_contains_company():
    result = counter_offer_template(_offer_fr(), _target_fr())
    assert "DataCorp" in result.body


def test_fr_body_contains_role():
    result = counter_offer_template(_offer_fr(), _target_fr())
    assert "Senior Data Engineer" in result.body


def test_fr_body_contains_target():
    result = counter_offer_template(_offer_fr(), _target_fr())
    assert "65" in result.body or "65 000" in result.body or "65000" in result.body


def test_fr_body_contains_p50():
    result = counter_offer_template(_offer_fr(), _target_fr())
    assert "62" in result.body


def test_fr_body_contains_source():
    result = counter_offer_template(_offer_fr(), _target_fr())
    assert "APEC" in result.body


def test_fr_subject_contains_role():
    result = counter_offer_template(_offer_fr(), _target_fr())
    assert "Senior Data Engineer" in result.subject


def test_en_body_contains_company():
    result = counter_offer_template(_offer_en(), _target_en(), market_id="en")
    assert "TechInc" in result.body


def test_en_body_is_english():
    result = counter_offer_template(_offer_en(), _target_en(), market_id="en")
    assert "Thank you" in result.body or "best regards" in result.body.lower()


def test_target_field_set():
    result = counter_offer_template(_offer_fr(), _target_fr())
    assert result.target == 65000.0


def test_rationale_non_empty():
    result = counter_offer_template(_offer_fr(), _target_fr())
    assert len(result.rationale) > 0


def test_rationale_mentions_p50():
    result = counter_offer_template(_offer_fr(), _target_fr())
    assert "P50" in result.rationale or "62" in result.rationale


def test_deterministic():
    r1 = counter_offer_template(_offer_fr(), _target_fr())
    r2 = counter_offer_template(_offer_fr(), _target_fr())
    assert r1.body == r2.body


# ── total_comp tests ────────────────────────────────────────────────────────────────


def test_total_comp_returns_total_comp():
    result = total_comp(base=60000)
    assert isinstance(result, TotalComp)


def test_total_comp_base_only():
    result = total_comp(base=60000)
    assert result.base == 60000.0
    assert result.total == 60000.0


def test_total_comp_with_variable():
    result = total_comp(base=60000, variable_pct=0.10)
    assert result.variable == pytest.approx(6000.0)
    assert result.total == pytest.approx(66000.0)


def test_total_comp_with_signing():
    result = total_comp(base=60000, signing=20000, years=4)
    assert result.signing == pytest.approx(5000.0)
    assert result.total == pytest.approx(65000.0)


def test_total_comp_with_equity():
    result = total_comp(base=60000, equity_total=40000, years=4)
    assert result.equity_annualized == pytest.approx(10000.0)
    assert result.total == pytest.approx(70000.0)


def test_total_comp_full():
    result = total_comp(
        base=100000,
        variable_pct=0.15,
        signing=20000,
        equity_total=80000,
        years=4,
        currency="USD",
    )
    # base=100k, variable=15k, signing=5k, equity=20k → total=140k
    assert result.total == pytest.approx(140000.0)
    assert result.currency == "USD"


def test_total_comp_currency_default_eur():
    result = total_comp(base=50000)
    assert result.currency == "EUR"


def test_total_comp_years_1():
    result = total_comp(base=50000, signing=10000, equity_total=20000, years=1)
    assert result.signing == pytest.approx(10000.0)
    assert result.equity_annualized == pytest.approx(20000.0)


def test_total_comp_zero_base():
    result = total_comp(base=0)
    assert result.total == 0.0


# ── competing_offer_script tests ────────────────────────────────────────────


def test_competing_script_returns_string():
    result = competing_offer_script(
        company="DataCorp",
        competitor="OtherCo",
        competing_amount=70000,
        competing_role="Data Engineer",
    )
    assert isinstance(result, str)


def test_competing_script_fr_contains_company():
    result = competing_offer_script("DataCorp", "OtherCo", 70000, "Data Engineer", lang="fr")
    assert "DataCorp" in result


def test_competing_script_fr_contains_competitor():
    result = competing_offer_script("DataCorp", "OtherCo", 70000, "Data Engineer", lang="fr")
    assert "OtherCo" in result


def test_competing_script_fr_contains_amount():
    result = competing_offer_script("DataCorp", "OtherCo", 70000, "Dev", lang="fr")
    assert "70" in result  # amount shown


def test_competing_script_en_is_english():
    result = competing_offer_script("TechCo", "RivalCo", 150000, "SWE", lang="en")
    assert "received" in result.lower() or "offer" in result.lower()


def test_competing_script_fr_default():
    result = competing_offer_script("X", "Y", 55000, "PM")
    # Default lang=fr
    assert (
        "offre" in result.lower()
        or "transparence" in result.lower()
        or "transparent" in result.lower()
    )


def test_competing_script_deterministic():
    r1 = competing_offer_script("A", "B", 60000, "Dev", lang="fr")
    r2 = competing_offer_script("A", "B", 60000, "Dev", lang="fr")
    assert r1 == r2
