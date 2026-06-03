"""Tests for ats.screener_brief — deterministic kit for screener simulation.

TDD: written before implementation.
"""
from __future__ import annotations


from decroche.models import JSONResume, Basics, Work, Skill, ScreenerKit


SAMPLE_OFFER = """
Senior Backend Engineer — Python & Kubernetes

We are looking for an experienced backend engineer to join our platform team.

Requirements:
- 5+ years of experience in Python backend development
- Strong knowledge of Kubernetes and container orchestration
- Experience with PostgreSQL, Redis, and distributed systems
- Familiarity with CI/CD pipelines (GitHub Actions, Jenkins)
- Knowledge of microservices architecture
- Experience with REST APIs and GraphQL
- Good communication skills
"""

SAMPLE_RESUME_TEXT = """
Jane Doe
jane.doe@example.com

Experience
Led migration of 12 services to Kubernetes, reducing latency 38%
Built automated CI/CD pipeline using GitHub Actions, saving 4 hours/week
Designed PostgreSQL schema for high-throughput data ingestion

Skills
Python, Go, Kubernetes, PostgreSQL, Redis, GitHub Actions
"""


def _jr() -> JSONResume:
    from decroche.models import Meta
    return JSONResume(
        basics=Basics(name="Jane Doe", email="jane.doe@example.com"),
        work=[Work(
            name="Acme",
            highlights=[
                "Led migration of 12 services to Kubernetes, reducing latency 38%",
                "Built automated CI/CD pipeline using GitHub Actions",
            ],
        )],
        skills=[Skill(name=s) for s in ["Python", "Go", "Kubernetes", "PostgreSQL", "Redis"]],
        meta=Meta(market="fr"),
    )


def test_screener_brief_returns_kit() -> None:
    """screener_brief returns a ScreenerKit."""
    from decroche.ats.screener_brief import screener_brief

    jr = _jr()
    kit = screener_brief(jr, SAMPLE_OFFER, "workday")
    assert isinstance(kit, ScreenerKit)


def test_machine_view_text_non_empty() -> None:
    """machine_view_text is non-empty."""
    from decroche.ats.screener_brief import screener_brief

    jr = _jr()
    kit = screener_brief(jr, SAMPLE_OFFER, "workday")
    assert len(kit.machine_view_text.strip()) > 0


def test_rubric_non_empty() -> None:
    """rubric contains at least one criterion string."""
    from decroche.ats.screener_brief import screener_brief

    jr = _jr()
    kit = screener_brief(jr, SAMPLE_OFFER, "workday")
    assert len(kit.rubric) >= 1
    for r in kit.rubric:
        assert isinstance(r, str)
        assert len(r) > 0


def test_requirements_extracted() -> None:
    """Requirements extracted from offer_text contain known keywords."""
    from decroche.ats.screener_brief import screener_brief

    jr = _jr()
    kit = screener_brief(jr, SAMPLE_OFFER, "workday")
    assert len(kit.requirements) >= 1
    # Should contain at least some key terms from the offer
    all_reqs = " ".join(kit.requirements).lower()
    # At least one of these should appear
    found = any(kw in all_reqs for kw in ["python", "kubernetes", "postgresql", "backend"])
    assert found, f"Expected technical keywords in requirements, got: {kit.requirements}"


def test_ats_id_preserved() -> None:
    """ats_id is preserved in the ScreenerKit."""
    from decroche.ats.screener_brief import screener_brief

    jr = _jr()
    kit = screener_brief(jr, SAMPLE_OFFER, "greenhouse")
    assert kit.ats_id == "greenhouse"


def test_machine_view_text_contains_name() -> None:
    """machine_view_text includes the candidate name from JSON Resume."""
    from decroche.ats.screener_brief import screener_brief

    jr = _jr()
    kit = screener_brief(jr, SAMPLE_OFFER, "workday")
    assert "Jane Doe" in kit.machine_view_text


def test_machine_view_text_contains_skills() -> None:
    """machine_view_text includes skills."""
    from decroche.ats.screener_brief import screener_brief

    jr = _jr()
    kit = screener_brief(jr, SAMPLE_OFFER, "lever")
    assert "Python" in kit.machine_view_text or "Kubernetes" in kit.machine_view_text


def test_requirements_deterministic() -> None:
    """Same inputs → same requirements (no randomness)."""
    from decroche.ats.screener_brief import screener_brief

    jr = _jr()
    kit1 = screener_brief(jr, SAMPLE_OFFER, "workday")
    kit2 = screener_brief(jr, SAMPLE_OFFER, "workday")
    assert kit1.requirements == kit2.requirements


def test_empty_offer_returns_empty_requirements() -> None:
    """Empty offer text → empty requirements list."""
    from decroche.ats.screener_brief import screener_brief

    jr = _jr()
    kit = screener_brief(jr, "", "workday")
    assert kit.requirements == []


def test_rubric_criteria_are_meaningful() -> None:
    """Rubric strings describe actual screening criteria."""
    from decroche.ats.screener_brief import screener_brief

    jr = _jr()
    kit = screener_brief(jr, SAMPLE_OFFER, "workday")
    # Each rubric item should be > 10 chars (not degenerate)
    for r in kit.rubric:
        assert len(r) > 10, f"Rubric item too short: {r!r}"
