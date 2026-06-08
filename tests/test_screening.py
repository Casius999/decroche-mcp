"""Tests for apply.screening — honest, deterministic screening-question answerer.

Key invariants:
1. Work authorization / visa / sponsorship → needs_human=True, suggested_answer=None.
2. Salary expectation → needs_human=True, suggested_answer=None.
3. Relocation / notice period / start date / availability → needs_human=True.
4. "Why do you want to work here" → needs_human=True.
5. Experience years derived from CV work dates → source="derived_from_cv".
6. Skill presence/absence from CV → source="derived_from_cv", honest yes/no.
7. Unknown question → needs_human=True.
8. NEVER fabricates eligibility/authorization/availability.
"""

from __future__ import annotations

import pytest

from decroche.apply.screening import answer_screening
from decroche.models import Basics, JSONResume, ScreeningAnswer, Skill, Work


# ── fixtures ───────────────────────────────────────────────────────────────────


def _resume_python_k8s() -> JSONResume:
    """Resume with Python (5 years) and Kubernetes."""
    basics = Basics(name="Jane Doe", email="jane@example.com")
    work = [
        Work(
            name="CloudCo",
            position="Senior Dev",
            startDate="2018-01",
            endDate="2023-01",
            highlights=["Built Kubernetes clusters", "Developed Python microservices"],
        ),
        Work(
            name="StartupAB",
            position="Developer",
            startDate="2016-06",
            endDate="2018-01",
            highlights=["Python backend development"],
        ),
    ]
    skills = [
        Skill(name="Python", keywords=["FastAPI"]),
        Skill(name="Kubernetes", keywords=["k8s", "Helm"]),
    ]
    return JSONResume(basics=basics, work=work, skills=skills)


def _resume_no_k8s() -> JSONResume:
    """Resume with Python but NO Kubernetes."""
    basics = Basics(name="Bob Smith", email="bob@example.com")
    work = [
        Work(
            name="DevShop",
            position="Dev",
            startDate="2020-01",
            endDate="2023-01",
            highlights=["Python scripts"],
        )
    ]
    skills = [Skill(name="Python")]
    return JSONResume(basics=basics, work=work, skills=skills)


def _resume_empty() -> JSONResume:
    return JSONResume(basics=Basics(name="Empty"))


# ── return type ────────────────────────────────────────────────────────────────


def test_answer_screening_returns_model():
    result = answer_screening("How many years of Python?", _resume_python_k8s())
    assert isinstance(result, ScreeningAnswer)


# ── CRITICAL: eligibility / authorization ALWAYS needs_human ──────────────────


@pytest.mark.parametrize(
    "question",
    [
        "Are you authorized to work in the US?",
        "Do you require visa sponsorship?",
        "Will you need sponsorship?",
        "Are you eligible to work in the EU?",
        "Do you have the right to work in France?",
        "Avez-vous le droit de travailler en France ?",
        "Êtes-vous autorisé à travailler en Europe ?",
        "Do you have work authorization?",
        "Can you legally work in this country?",
    ],
)
def test_work_authorization_always_needs_human(question: str):
    """Work authorization MUST NEVER be answered from CV — always needs_human."""
    result = answer_screening(question, _resume_python_k8s())
    assert result.needs_human is True, (
        f"Work authorization question must be needs_human. Question: {question!r}"
    )
    assert result.suggested_answer is None, (
        f"suggested_answer must be None for authorization question. Got: {result.suggested_answer!r}"
    )


# ── salary expectation ALWAYS needs_human ─────────────────────────────────────


@pytest.mark.parametrize(
    "question",
    [
        "What are your salary expectations?",
        "Salary expectation?",
        "What do you expect to be paid?",
        "Quelles sont vos prétentions salariales ?",
        "Quel salaire souhaitez-vous ?",
        "Expected salary?",
        "What compensation are you looking for?",
    ],
)
def test_salary_expectation_always_needs_human(question: str):
    result = answer_screening(question, _resume_python_k8s())
    assert result.needs_human is True
    assert result.suggested_answer is None


# ── relocation / notice / start date ALWAYS needs_human ───────────────────────


@pytest.mark.parametrize(
    "question",
    [
        "Are you willing to relocate?",
        "Êtes-vous mobile ?",
        "What is your notice period?",
        "What is your availability?",
        "When can you start?",
        "Quelle est votre disponibilité ?",
        "What is your start date?",
        "Quand pouvez-vous commencer ?",
    ],
)
def test_relocation_notice_availability_needs_human(question: str):
    result = answer_screening(question, _resume_python_k8s())
    assert result.needs_human is True
    assert result.suggested_answer is None


# ── "why work here" ALWAYS needs_human ────────────────────────────────────────


@pytest.mark.parametrize(
    "question",
    [
        "Why do you want to work here?",
        "Pourquoi voulez-vous travailler chez nous ?",
        "Why are you interested in this role?",
        "Why this company?",
    ],
)
def test_why_work_here_needs_human(question: str):
    result = answer_screening(question, _resume_python_k8s())
    assert result.needs_human is True
    assert result.suggested_answer is None


# ── experience years derived from CV ──────────────────────────────────────────


def test_years_of_experience_derived_from_cv():
    result = answer_screening("How many years of experience do you have?", _resume_python_k8s())
    assert result.source == "derived_from_cv"
    assert result.needs_human is False
    assert result.suggested_answer is not None
    # Should mention some number
    assert any(c.isdigit() for c in result.suggested_answer), (
        f"Expected year count in answer, got: {result.suggested_answer!r}"
    )


def test_years_of_python_derived_from_cv():
    result = answer_screening(
        "How many years of Python experience do you have?",
        _resume_python_k8s(),
    )
    assert result.source == "derived_from_cv"
    assert result.needs_human is False
    assert result.suggested_answer is not None


def test_years_fr_question():
    result = answer_screening(
        "Combien d'années d'expérience avez-vous ?",
        _resume_python_k8s(),
    )
    assert result.source == "derived_from_cv"
    assert result.needs_human is False
    assert result.suggested_answer is not None


# ── skill presence/absence from CV ────────────────────────────────────────────


def test_skill_present_in_cv_answered_yes():
    result = answer_screening(
        "Do you have experience with Kubernetes?",
        _resume_python_k8s(),
    )
    assert result.source == "derived_from_cv"
    assert result.needs_human is False
    assert result.suggested_answer is not None
    assert (
        "yes" in result.suggested_answer.lower()
        or "oui" in result.suggested_answer.lower()
        or "kubernetes" in result.suggested_answer.lower()
        or "k8s" in result.suggested_answer.lower()
    ), f"Expected affirmative/evidence answer for Kubernetes, got: {result.suggested_answer!r}"


def test_skill_present_in_cv_high_or_medium_confidence():
    result = answer_screening(
        "Do you have experience with Kubernetes?",
        _resume_python_k8s(),
    )
    assert result.confidence in ("high", "medium")


def test_skill_absent_from_cv_answered_honestly():
    """When a skill is NOT in the CV, must say 'no' or 'not listed' — never fabricate."""
    result = answer_screening(
        "Do you have experience with Kubernetes?",
        _resume_no_k8s(),
    )
    assert result.source == "derived_from_cv"
    assert result.needs_human is False
    assert result.suggested_answer is not None
    answer_lower = result.suggested_answer.lower()
    # Must NOT claim to have Kubernetes experience
    assert (
        "no" in answer_lower
        or "not" in answer_lower
        or "non" in answer_lower
        or "pas" in answer_lower
    ), f"Must say no/not listed for absent skill. Got: {result.suggested_answer!r}"


def test_skill_absent_never_fabricates():
    """Kubernetes must NOT be claimed when CV has no Kubernetes."""
    result = answer_screening(
        "Do you have experience with Kubernetes?",
        _resume_no_k8s(),
    )
    # The answer must not positively claim kubernetes experience
    if result.suggested_answer:
        answer_lower = result.suggested_answer.lower()
        # If it says 'yes' + kubernetes, that would be fabrication
        assert not (
            "yes" in answer_lower and "kubernetes" in answer_lower and "no" not in answer_lower
        ), f"Fabricated Kubernetes claim: {result.suggested_answer!r}"


def test_skill_question_fr():
    result = answer_screening(
        "Avez-vous de l'expérience avec Python ?",
        _resume_python_k8s(),
    )
    assert result.source == "derived_from_cv"
    assert result.needs_human is False


# ── unknown question → needs_human ────────────────────────────────────────────


def test_unknown_question_needs_human():
    result = answer_screening(
        "What is your spirit animal?",
        _resume_python_k8s(),
    )
    assert result.needs_human is True


def test_completely_arbitrary_question_needs_human():
    result = answer_screening(
        "Please describe your management philosophy.",
        _resume_python_k8s(),
    )
    assert result.needs_human is True
    assert result.suggested_answer is None


# ── needs_human → suggested_answer always None ────────────────────────────────


def test_needs_human_implies_suggested_answer_none():
    """When needs_human=True, suggested_answer MUST be None (no partial fabrication)."""
    questions = [
        "Are you authorized to work in the US?",
        "What is your salary expectation?",
        "Are you willing to relocate?",
        "Why do you want to work here?",
        "What is your notice period?",
    ]
    for q in questions:
        result = answer_screening(q, _resume_python_k8s())
        if result.needs_human:
            assert result.suggested_answer is None, (
                f"needs_human=True but suggested_answer={result.suggested_answer!r} for: {q!r}"
            )


# ── source field values ────────────────────────────────────────────────────────


def test_source_is_valid_value():
    valid_sources = {"derived_from_cv", "needs_human", "benchmark"}
    questions = [
        "How many years of experience do you have?",
        "Do you have experience with Python?",
        "Are you authorized to work in the US?",
        "What is your salary expectation?",
    ]
    for q in questions:
        result = answer_screening(q, _resume_python_k8s())
        assert result.source in valid_sources, (
            f"source={result.source!r} not in {valid_sources} for {q!r}"
        )


# ── confidence field ───────────────────────────────────────────────────────────


def test_confidence_is_valid_value():
    valid_confidence = {"high", "medium", "low", "none"}
    result = answer_screening("How many years of experience?", _resume_python_k8s())
    assert result.confidence in valid_confidence


def test_confidence_none_for_needs_human():
    result = answer_screening("Are you authorized to work in the US?", _resume_python_k8s())
    assert result.confidence == "none"


# ── question stored ────────────────────────────────────────────────────────────


def test_question_stored_in_result():
    q = "Do you have experience with Kubernetes?"
    result = answer_screening(q, _resume_python_k8s())
    assert result.question == q


# ── deterministic ─────────────────────────────────────────────────────────────


def test_answer_screening_is_deterministic():
    q = "Do you have experience with Kubernetes?"
    resume = _resume_python_k8s()
    r1 = answer_screening(q, resume)
    r2 = answer_screening(q, resume)
    assert r1.suggested_answer == r2.suggested_answer
    assert r1.needs_human == r2.needs_human
    assert r1.source == r2.source
