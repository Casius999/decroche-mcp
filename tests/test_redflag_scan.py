"""Tests for ats.redflag_scan — red-flag taxonomy.

TDD: written before implementation.
"""
from __future__ import annotations


from decroche.models import JSONResume, Basics, Work


# ── helpers ───────────────────────────────────────────────────────────────────

def _jr(**kwargs) -> JSONResume:
    """Minimal JSONResume factory."""
    from decroche.models import Meta
    defaults = dict(
        basics=Basics(name="Jane Doe", email="jane.doe@example.com"),
        work=[],
        education=[],
        skills=[],
        meta=Meta(market="fr"),
    )
    defaults.update(kwargs)
    return JSONResume(**defaults)


def _flag_ids(flags) -> list[str]:
    return [f.flag_id for f in flags]


# ── Tests ─────────────────────────────────────────────────────────────────

def test_passive_voice_flagged() -> None:
    """Bullet in passive voice → passive_voice flag."""
    from decroche.ats.redflag_scan import redflag_scan

    jr = _jr(work=[Work(highlights=["Was responsible for the deployment of services"])])
    raw = "Was responsible for the deployment of services"
    flags = redflag_scan(jr, raw)
    ids = _flag_ids(flags)
    assert "passive_voice" in ids or "duty_bullets" in ids


def test_duty_bullet_no_metric_no_strong_verb() -> None:
    """Bullet with only a responsibility and no metric/strong verb → duty_bullets."""
    from decroche.ats.redflag_scan import redflag_scan

    jr = _jr(work=[Work(highlights=["Responsible for managing the team calendar"])])
    raw = "Responsible for managing the team calendar"
    flags = redflag_scan(jr, raw)
    ids = _flag_ids(flags)
    assert "duty_bullets" in ids


def test_strong_verb_clears_duty_flag() -> None:
    """Bullet starting with strong verb + metric → no duty_bullets flag."""
    from decroche.ats.redflag_scan import redflag_scan

    jr = _jr(work=[Work(highlights=["Led migration of 12 services to Kubernetes, reducing latency 38%"])])
    raw = "Led migration of 12 services to Kubernetes, reducing latency 38%"
    flags = redflag_scan(jr, raw)
    ids = _flag_ids(flags)
    assert "duty_bullets" not in ids


def test_banned_word_flagged() -> None:
    """Banned word in text → banned_word flag."""
    from decroche.ats.redflag_scan import redflag_scan

    jr = _jr(work=[Work(highlights=["I am a team player and motivated individual"])])
    raw = "I am a team player and motivated individual"
    flags = redflag_scan(jr, raw)
    ids = _flag_ids(flags)
    assert "banned_word" in ids


def test_banned_word_fr_flagged() -> None:
    """French banned word (dynamique) → banned_word flag."""
    from decroche.ats.redflag_scan import redflag_scan

    jr = _jr(work=[Work(highlights=["Profil dynamique et motivé avec rigueur"])])
    raw = "Profil dynamique et motivé avec rigueur"
    flags = redflag_scan(jr, raw)
    ids = _flag_ids(flags)
    assert "banned_word" in ids


def test_employment_gap_flagged() -> None:
    """Gap > 3 months between work entries → gap_unlabeled flag."""
    from decroche.ats.redflag_scan import redflag_scan

    jr = _jr(work=[
        Work(startDate="2020-01", endDate="2021-01", name="Company A"),
        Work(startDate="2022-06", endDate="2023-01", name="Company B"),  # ~17 month gap
    ])
    raw = "Senior engineer at Company A and Company B"
    flags = redflag_scan(jr, raw)
    ids = _flag_ids(flags)
    assert "gap_unlabeled" in ids


def test_no_gap_no_flag() -> None:
    """Continuous employment → no gap_unlabeled flag."""
    from decroche.ats.redflag_scan import redflag_scan

    jr = _jr(work=[
        Work(startDate="2020-01", endDate="2021-01", name="Company A"),
        Work(startDate="2021-02", endDate="2022-01", name="Company B"),  # 1 month gap OK
    ])
    raw = "Continuous employment"
    flags = redflag_scan(jr, raw)
    ids = _flag_ids(flags)
    assert "gap_unlabeled" not in ids


def test_job_hopping_flagged() -> None:
    """At least 3 stints < 12 months → job_hopping flag."""
    from decroche.ats.redflag_scan import redflag_scan

    jr = _jr(work=[
        Work(startDate="2020-01", endDate="2020-06", name="A"),   # 5 months
        Work(startDate="2020-07", endDate="2021-01", name="B"),   # 6 months
        Work(startDate="2021-02", endDate="2021-08", name="C"),   # 6 months
    ])
    raw = "Short stints"
    flags = redflag_scan(jr, raw)
    ids = _flag_ids(flags)
    assert "job_hopping" in ids


def test_no_job_hopping_stable() -> None:
    """Long stints → no job_hopping flag."""
    from decroche.ats.redflag_scan import redflag_scan

    jr = _jr(work=[
        Work(startDate="2018-01", endDate="2020-01", name="A"),
        Work(startDate="2020-02", endDate="2023-01", name="B"),
    ])
    raw = "Stable career"
    flags = redflag_scan(jr, raw)
    ids = _flag_ids(flags)
    assert "job_hopping" not in ids


def test_years_only_dates_flagged() -> None:
    """Work entry with only year date (e.g. '2020') → years_only_dates flag."""
    from decroche.ats.redflag_scan import redflag_scan

    jr = _jr(work=[Work(startDate="2020", endDate="2021", name="Company")])
    raw = "2020 - 2021"
    flags = redflag_scan(jr, raw)
    ids = _flag_ids(flags)
    assert "years_only_dates" in ids


def test_unprofessional_email_flagged() -> None:
    """Email like 'xXx_gamer99@hotmail.com' → email_unprofessional flag."""
    from decroche.ats.redflag_scan import redflag_scan

    jr = _jr(basics=Basics(name="Jane Doe", email="xXx_gamer99@hotmail.com"))
    raw = "xXx_gamer99@hotmail.com"
    flags = redflag_scan(jr, raw)
    ids = _flag_ids(flags)
    assert "email_unprofessional" in ids


def test_professional_email_not_flagged() -> None:
    """Professional email → no email_unprofessional flag."""
    from decroche.ats.redflag_scan import redflag_scan

    jr = _jr(basics=Basics(name="Jane Doe", email="jane.doe@gmail.com"))
    raw = "jane.doe@gmail.com"
    flags = redflag_scan(jr, raw)
    ids = _flag_ids(flags)
    assert "email_unprofessional" not in ids


def test_wrong_photo_us_market() -> None:
    """Photo field present + US market → wrong_photo_market CRITICAL flag."""
    from decroche.ats.redflag_scan import redflag_scan
    from decroche.models import Meta

    jr = _jr(meta=Meta(market="us"))
    raw = "Photo included in CV"
    # We encode photo presence via raw_text containing photo indicator
    flags = redflag_scan(jr, raw + " [photo]", market_id="us", has_photo=True)
    ids = _flag_ids(flags)
    assert "wrong_photo_market" in ids


def test_no_photo_fr_market_ok() -> None:
    """No photo in FR market → no wrong_photo_market flag."""
    from decroche.ats.redflag_scan import redflag_scan

    jr = _jr()
    raw = "No photo here"
    flags = redflag_scan(jr, raw, market_id="fr", has_photo=False)
    ids = _flag_ids(flags)
    assert "wrong_photo_market" not in ids


def test_ai_generic_phrasing_flagged() -> None:
    """'responsible for' phrasing → ai_generic_phrasing flag."""
    from decroche.ats.redflag_scan import redflag_scan

    jr = _jr(work=[Work(highlights=["Was responsible for the delivery pipeline"])])
    raw = "Was responsible for the delivery pipeline"
    flags = redflag_scan(jr, raw)
    ids = _flag_ids(flags)
    assert "ai_generic_phrasing" in ids or "passive_voice" in ids


def test_redflag_has_required_fields() -> None:
    """Each RedFlag has flag_id, severity, location, evidence, fix."""
    from decroche.ats.redflag_scan import redflag_scan
    from decroche.models import RedFlag

    jr = _jr(work=[Work(highlights=["Was responsible for managing team player dynamics"])])
    raw = "Was responsible for managing team player dynamics"
    flags = redflag_scan(jr, raw)
    assert len(flags) > 0
    for flag in flags:
        assert isinstance(flag, RedFlag)
        assert flag.flag_id
        assert flag.severity in ("CRITICAL", "HIGH", "MEDIUM", "LOW")
        assert flag.location
        assert flag.evidence
        assert flag.fix


def test_no_flags_clean_cv() -> None:
    """Clean CV with strong bullets → minimal/no high-severity flags."""
    from decroche.ats.redflag_scan import redflag_scan

    jr = _jr(
        basics=Basics(name="Jane Doe", email="jane.doe@example.com"),
        work=[Work(
            startDate="2022-01",
            endDate="2024-01",
            name="Acme",
            highlights=[
                "Led migration of 12 services to Kubernetes, reducing latency 38%",
                "Built automated CI/CD pipeline, saving 4 hours/week",
            ],
        )],
    )
    raw = "Led migration of 12 services to Kubernetes, reducing latency 38%\nBuilt automated CI/CD pipeline, saving 4 hours/week"
    flags = redflag_scan(jr, raw)
    critical_and_high = [f for f in flags if f.severity in ("CRITICAL", "HIGH")]
    assert len(critical_and_high) == 0
