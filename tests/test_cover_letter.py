"""Tests for apply.cover_letter — honest, deterministic scaffold.

Key invariants tested here:
1. why_me bullets come ONLY from the candidate's real CV.
2. A skill/experience NOT present in the CV never appears in why_me.
3. [à compléter] placeholder present for why_them (host fills, never invented).
4. Works for both FR and EN lang.
5. No fabricated company facts.
6. full_scaffold assembles all sections.
7. evidence_used is populated from real CV data.
8. notes warn about placeholders and non-invention.
"""

from __future__ import annotations

from decroche.apply.cover_letter import cover_letter
from decroche.models import (
    Basics,
    CoverLetter,
    JobPosting,
    JSONResume,
    Skill,
    Work,
)


# ── fixtures ───────────────────────────────────────────────────────────────────


def _job(
    title: str = "Backend Engineer",
    company: str | None = "Acme Corp",
    description: str = "Python, Docker, CI/CD pipelines",
) -> JobPosting:
    return JobPosting(
        source="greenhouse",
        source_id="1",
        title=title,
        company=company,
        url="https://acme.com/jobs/1",
        description=description,
    )


def _resume_rich() -> JSONResume:
    """A resume with real Python + Docker experience."""
    basics = Basics(name="Jane Dupont", email="jane@example.com")
    work = [
        Work(
            name="TechCorp",
            position="Senior Python Developer",
            startDate="2020-01",
            endDate="2023-06",
            highlights=[
                "Reduced API latency 38% using caching with Redis",
                "Led migration of 12 services to Docker",
                "Built CI/CD pipeline with GitHub Actions",
            ],
        ),
        Work(
            name="StartupXY",
            position="Backend Developer",
            startDate="2018-01",
            endDate="2020-01",
            highlights=["Developed REST APIs with FastAPI"],
        ),
    ]
    skills = [
        Skill(name="Python", keywords=["FastAPI", "Django"]),
        Skill(name="Docker"),
        Skill(name="CI/CD"),
    ]
    return JSONResume(basics=basics, work=work, skills=skills)


def _resume_no_k8s() -> JSONResume:
    """A resume with NO Kubernetes experience at all."""
    basics = Basics(name="Bob Martin", email="bob@example.com")
    work = [
        Work(
            name="SimpleShop",
            position="Developer",
            startDate="2021-01",
            endDate="2023-01",
            highlights=["Maintained PHP monolith", "Added SQL queries for reporting"],
        )
    ]
    skills = [Skill(name="PHP"), Skill(name="SQL")]
    return JSONResume(basics=basics, work=work, skills=skills)


def _resume_empty() -> JSONResume:
    """A resume with no work/skills."""
    basics = Basics(name="Empty User", email="empty@example.com")
    return JSONResume(basics=basics)


# ── return type ────────────────────────────────────────────────────────────────


def test_cover_letter_returns_cover_letter_model():
    result = cover_letter(_job(), _resume_rich())
    assert isinstance(result, CoverLetter)


# ── role_title and company ─────────────────────────────────────────────────────


def test_cover_letter_role_title_from_job():
    result = cover_letter(_job(title="Data Scientist"), _resume_rich())
    assert result.role_title == "Data Scientist"


def test_cover_letter_company_from_job():
    result = cover_letter(_job(company="MegaCorp"), _resume_rich())
    assert result.company == "MegaCorp"


def test_cover_letter_company_none_when_job_has_no_company():
    job = _job(company=None)
    result = cover_letter(job, _resume_rich())
    assert result.company is None


# ── hook ───────────────────────────────────────────────────────────────────────


def test_hook_references_job_title():
    result = cover_letter(_job(title="ML Engineer"), _resume_rich())
    assert "ML Engineer" in result.hook


def test_hook_references_company_when_present():
    result = cover_letter(_job(company="DataCo"), _resume_rich())
    assert "DataCo" in result.hook


# ── why_them placeholder — no fabrication ─────────────────────────────────────


def test_why_them_contains_placeholder():
    result = cover_letter(_job(), _resume_rich())
    assert (
        "[à compléter" in result.why_them
        or "[TO_COMPLETE" in result.why_them.upper()
        or "compléter" in result.why_them
        or "à compléter" in result.why_them.lower()
    )


def test_why_them_does_not_contain_fake_company_fact():
    """why_them must be a placeholder, not invented company data."""
    result = cover_letter(_job(company="FictiveCorp"), _resume_rich())
    # It should NOT contain prose claiming to know the company's strategy/product
    # The placeholder bracket must be present to signal host must fill it
    assert "[" in result.why_them


# ── why_me: only real CV evidence ─────────────────────────────────────────────


def test_why_me_is_non_empty_when_cv_has_highlights():
    result = cover_letter(_job(), _resume_rich())
    assert len(result.why_me) >= 1


def test_why_me_has_at_most_4_bullets():
    result = cover_letter(_job(), _resume_rich())
    assert len(result.why_me) <= 4


def test_why_me_bullets_are_strings():
    result = cover_letter(_job(), _resume_rich())
    assert all(isinstance(b, str) for b in result.why_me)


def test_why_me_no_invented_skill_not_in_cv():
    """Kubernetes MUST NOT appear in why_me when CV has no k8s."""
    result = cover_letter(
        _job(description="Python, Kubernetes, AWS"),
        _resume_no_k8s(),
    )
    for bullet in result.why_me:
        bullet_lower = bullet.lower()
        assert "kubernetes" not in bullet_lower, (
            f"Fabricated skill 'Kubernetes' found in why_me bullet: {bullet!r}"
        )
        assert "k8s" not in bullet_lower, (
            f"Fabricated skill 'k8s' found in why_me bullet: {bullet!r}"
        )


def test_why_me_only_real_skills():
    """Bullets must reference terms actually present in work/skills of the resume."""
    result = cover_letter(_job(), _resume_rich())
    # At least one bullet should mention something from the real CV
    cv_terms = {
        "python",
        "docker",
        "ci",
        "techcorp",
        "redis",
        "fastapi",
        "caching",
        "latency",
        "api",
        "github",
        "pipeline",
        "migration",
        "services",
        "senior",
        "backend",
        "startup",
    }
    for bullet in result.why_me:
        bullet_lower = bullet.lower()
        # Each bullet must contain at least one real CV term
        assert any(term in bullet_lower for term in cv_terms), (
            f"why_me bullet does not reference any real CV term: {bullet!r}"
        )


def test_why_me_empty_when_cv_has_no_work_or_skills():
    """If CV has nothing, why_me should be empty (no fabrication)."""
    result = cover_letter(_job(), _resume_empty())
    assert result.why_me == []


# ── evidence_used tracks provenance ───────────────────────────────────────────


def test_evidence_used_is_list():
    result = cover_letter(_job(), _resume_rich())
    assert isinstance(result.evidence_used, list)


def test_evidence_used_non_empty_when_why_me_non_empty():
    result = cover_letter(_job(), _resume_rich())
    if result.why_me:
        assert len(result.evidence_used) >= 1


# ── close ─────────────────────────────────────────────────────────────────────


def test_close_is_non_empty_string():
    result = cover_letter(_job(), _resume_rich())
    assert isinstance(result.close, str)
    assert len(result.close) > 5


def test_close_fr_is_in_french():
    result = cover_letter(_job(), _resume_rich(), lang="fr")
    # A polite French close typically contains "Cordialement", "salutations", "merci"
    close_lower = result.close.lower()
    assert any(
        w in close_lower
        for w in ["cordialement", "salutations", "merci", "sincèrement", "bonne", "candidature"]
    ), f"Expected French close, got: {result.close!r}"


def test_close_en_is_in_english():
    result = cover_letter(_job(), _resume_rich(), lang="en")
    close_lower = result.close.lower()
    assert any(
        w in close_lower
        for w in ["sincerely", "regards", "thank", "best", "yours", "looking forward"]
    ), f"Expected English close, got: {result.close!r}"


# ── full_scaffold ──────────────────────────────────────────────────────────────


def test_full_scaffold_is_non_empty():
    result = cover_letter(_job(), _resume_rich())
    assert isinstance(result.full_scaffold, str)
    assert len(result.full_scaffold) > 50


def test_full_scaffold_contains_hook():
    result = cover_letter(_job(), _resume_rich())
    # The first part of the hook text should appear in scaffold
    assert result.hook[:20] in result.full_scaffold


def test_full_scaffold_contains_placeholder_for_why_them():
    result = cover_letter(_job(), _resume_rich())
    assert "[" in result.full_scaffold


def test_full_scaffold_contains_close():
    result = cover_letter(_job(), _resume_rich())
    assert result.close[:15] in result.full_scaffold


# ── notes ─────────────────────────────────────────────────────────────────────


def test_notes_is_list():
    result = cover_letter(_job(), _resume_rich())
    assert isinstance(result.notes, list)


def test_notes_non_empty():
    result = cover_letter(_job(), _resume_rich())
    assert len(result.notes) >= 1


def test_notes_warn_about_why_them_placeholder():
    result = cover_letter(_job(), _resume_rich())
    notes_text = " ".join(result.notes).lower()
    # Notes must instruct user NOT to invent company facts
    assert any(
        w in notes_text
        for w in [
            "inventé",
            "inventer",
            "compléter",
            "why_them",
            "completer",
            "invent",
            "company",
            "entreprise",
        ]
    ), f"Notes must warn about placeholders/non-invention. Got: {result.notes!r}"


# ── lang field stored ─────────────────────────────────────────────────────────


def test_lang_stored_fr():
    result = cover_letter(_job(), _resume_rich(), lang="fr")
    assert result.lang == "fr"


def test_lang_stored_en():
    result = cover_letter(_job(), _resume_rich(), lang="en")
    assert result.lang == "en"


# ── deterministic ─────────────────────────────────────────────────────────────


def test_cover_letter_is_deterministic():
    job = _job()
    resume = _resume_rich()
    r1 = cover_letter(job, resume)
    r2 = cover_letter(job, resume)
    assert r1.hook == r2.hook
    assert r1.why_me == r2.why_me
    assert r1.close == r2.close
    assert r1.full_scaffold == r2.full_scaffold
