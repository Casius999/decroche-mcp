"""Tests for negotiate.benchmark (benchmark_range)."""

from __future__ import annotations

import pytest

from decroche.models import SalaryRange
from decroche.negotiate.benchmark import benchmark_range


def test_returns_salary_range():
    result = benchmark_range("software", "mid", "fr")
    assert isinstance(result, SalaryRange)


def test_exact_match_software_mid_fr():
    result = benchmark_range("software", "mid", "fr")
    assert result.role_family == "software"
    assert result.seniority == "mid"
    assert result.region == "fr"
    assert result.currency == "EUR"


def test_exact_match_not_approximate():
    result = benchmark_range("software", "mid", "fr")
    assert result.approximate is False
    assert result.note == ""


def test_p25_lt_p50_lt_p75():
    result = benchmark_range("software", "senior", "fr")
    assert result.p25 < result.p50 < result.p75


def test_fr_software_senior_median_reasonable():
    # APEC 2024: FR software senior median ~72k€ — stored as 72 (thousands)
    result = benchmark_range("software", "senior", "fr")
    # Values are in k (thousands of currency units)
    assert 55 <= result.p50 <= 100


def test_us_software_senior_median_reasonable():
    # Levels.fyi 2024: US software senior median ~195k USD — stored as 195
    result = benchmark_range("software", "senior", "us")
    assert 150 <= result.p50 <= 280
    assert result.currency == "USD"


def test_uk_software_mid_returns_gbp():
    result = benchmark_range("software", "mid", "uk")
    assert result.currency == "GBP"


def test_ca_software_mid_returns_cad():
    result = benchmark_range("software", "mid", "ca")
    assert result.currency == "CAD"


def test_data_mid_fr():
    result = benchmark_range("data", "mid", "fr")
    assert result.role_family == "data"
    assert result.p50 > 0


def test_product_mid_fr():
    result = benchmark_range("product", "mid", "fr")
    assert result.p50 > 0


def test_sales_has_high_variable_pct():
    result = benchmark_range("sales", "mid", "fr")
    assert result.variable_pct >= 0.25


def test_source_non_empty():
    result = benchmark_range("software", "mid", "fr")
    assert len(result.source) > 0


def test_case_insensitive_inputs():
    result = benchmark_range("SOFTWARE", "MID", "FR")
    assert result.role_family == "software"


def test_interpolation_on_missing_seniority():
    # "data" has no "lead" row for UK — should fall back with approximate=True
    result = benchmark_range("data", "lead", "uk")
    assert result.approximate is True
    assert len(result.note) > 0


def test_interpolation_note_mentions_seniority():
    result = benchmark_range("data", "lead", "uk")
    assert "lead" in result.note.lower() or "seniority" in result.note.lower()


def test_unknown_role_family_raises():
    with pytest.raises(LookupError):
        benchmark_range("nonexistent_job", "mid", "fr")


def test_variable_pct_between_0_and_1():
    for rf in ("software", "data", "product", "sales"):
        result = benchmark_range(rf, "mid", "fr")
        assert 0.0 <= result.variable_pct <= 1.0
