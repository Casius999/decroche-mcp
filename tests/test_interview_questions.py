"""Tests for interview.questions (question_bank)."""

from __future__ import annotations

import pytest

from decroche.interview.questions import question_bank
from decroche.models import Question


def test_returns_list():
    result = question_bank("software", "behavioral")
    assert isinstance(result, list)


def test_returns_question_objects():
    result = question_bank("software", "behavioral")
    assert all(isinstance(q, Question) for q in result)


def test_software_behavioral_non_empty():
    result = question_bank("software", "behavioral")
    assert len(result) > 0


def test_software_technical_non_empty():
    result = question_bank("software", "technical")
    assert len(result) > 0


def test_software_case_non_empty():
    result = question_bank("software", "case")
    assert len(result) > 0


def test_data_behavioral_non_empty():
    result = question_bank("data", "behavioral")
    assert len(result) > 0


def test_product_behavioral_non_empty():
    result = question_bank("product", "behavioral")
    assert len(result) > 0


def test_sales_behavioral_non_empty():
    result = question_bank("sales", "behavioral")
    assert len(result) > 0


def test_generic_behavioral_non_empty():
    result = question_bank("generic", "behavioral")
    assert len(result) > 0


def test_kind_stored_correctly():
    result = question_bank("software", "technical")
    for q in result:
        assert q.kind == "technical"


def test_text_non_empty():
    result = question_bank("software", "behavioral")
    for q in result:
        assert len(q.text) > 0


def test_rationale_is_string():
    result = question_bank("data", "behavioral")
    for q in result:
        assert isinstance(q.rationale, str)


def test_case_insensitive_family():
    result = question_bank("SOFTWARE", "behavioral")
    assert len(result) > 0


def test_case_insensitive_kind():
    result = question_bank("software", "BEHAVIORAL")
    assert len(result) > 0


def test_unknown_family_returns_empty():
    result = question_bank("nonexistent_role", "behavioral")
    assert result == []


def test_invalid_kind_raises_value_error():
    with pytest.raises(ValueError, match="Invalid kind"):
        question_bank("software", "wrongkind")


def test_default_kind_is_behavioral():
    result = question_bank("software")
    for q in result:
        assert q.kind == "behavioral"


def test_generic_case_non_empty():
    result = question_bank("generic", "case")
    assert len(result) > 0


def test_product_case_non_empty():
    result = question_bank("product", "case")
    assert len(result) > 0
