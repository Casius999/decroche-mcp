"""Tests for ats.redflag_scan — red-flag taxonomy.

TDD: written before implementation.
"""
from __future__ import annotations


from decroche.models import JSONResume, Basics, Work


# ── helpers ───────────────────────────────────────────────────────────────────────

def _jr(**kwargs) -> JSONResume:
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


# ── Tests ───────────────────────────────────────────────────────────────────────

def test_passive_voice_flagged() -> None:
    from decroche.ats.redflag_scan import redflag_scan

    jr = _jr(work=[Work(highlights=["Was responsible for the deployment of services"])])
    raw = "Was responsible for the deployment of services"
    flags = redflag_scan(jr, raw)
    ids = _flag_ids(flags)
    assert "passive_voice" in ids or "duty_bullets" in ids


def test_duty_bullet_no_metric_no_strong_verb() -> None:
    from decroche.ats.redflag_scan import redflag_scan

    jr = _jr(work=[Work(highlights=["Responsible for managing the team calendar"])])
    raw = "Responsible for managing the team calendar"
    flags = redflag_scan(jr, raw)
    ids = _flag_ids(flags)
    assert "duty_bullets" in ids


def test_strong_verb_clears_duty_flag() -> None:
    from decroche.ats.redflag_scan import redflag_scan

    jr = _jr(work=[Work(highlights=["Led migration of 12 services to Kubernetes, reducing latency 38%"])])
    raw = "Led migration of 12 services to Kubernetes, reducing latency 38%"
    flags = redflag_scan(jr, raw)
    ids = _flag_ids(flags)
    assert "duty_bullets" not in ids


def test_banned_word_flagged() -> None:
    from decroche.ats.redflag_scan import redflag_scan

    jr = _jr(work=[Work(highlights=["I am a team player and motivated individual"])])
    raw = "I am a team player and motivated individual"
    flags = redflag_scan(jr, raw)
    ids = _flag_ids(flags)
    assert "banned_word" in ids


def test_banned_word_fr_flagged() -> None:
    from decroche.ats.redflag_scan import redflag_scan

    jr = _jr(work=[Work(highlights=["Profil dynamique et motivé avec rigueur"])])
    raw = "Profil dynamique et motivé avec rigueur"
    flags = redflag_scan(jr, raw)
    ids = _flag_ids(flags)
    assert "banned_word" in ids


def test_employment_gap_flagged() -> None:
    from decroche.ats.redflag_scan import redflag_scan

    jr = _jr(work=[
        Work(startDate="2020-01", endDate="2021-01", name="Company A"),
        Work(startDate="2022-06", endDate="2023-01", name="Company B"),
    ])
    raw = "Senior engineer at Company A and Company B"
    flags = redflag_scan(jr, raw)
    ids = _flag_ids(flags)
    assert "gap_unlabeled" in ids


def test_no_gap_no_flag() -> None:
    from decroche.ats.redflag_scan import redflag_scan

    jr = _jr(work=[
        Work(startDate="2020-01", endDate="2021-01", name="Company A"),
        Work(startDate="2021-02", endDate="2022-01", name="Company B"),
    ])
    raw = "Continuous employment"
    flags = redflag_scan(jr, raw)
    ids = _flag_ids(flags)
    assert "gap_unlabeled" not in ids


def test_job_hopping_flagged() -> None:
    from decroche.ats.redflag_scan import redflag_scan

    jr = _jr(work=[
        Work(startDate="2020-01", endDate="2020-06", name="A"),
        Work(startDate="2020-07", endDate="2021-01", name="B"),
        Work(startDate="2021-02", endDate="2021-08", name="C"),
    ])
    raw = "Short stints"
    flags = redflag_scan(jr, raw)
    ids = _flag_ids(flags)
    assert "job_hopping" in ids


def test_no_job_hopping_stable() -> None:
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
    from decroche.ats.redflag_scan import redflag_scan

    jr = _jr(work=[Work(startDate="2020", endDate="2021", name="Company")])
    raw = "2020 - 2021"
    flags = redflag_scan(jr, raw)
    ids = _flag_ids(flags)
    assert "years_only_dates" in ids


def test_unprofessional_email_flagged() -> None:
    from decroche.ats.redflag_scan import redflag_scan

    jr = _jr(basics=Basics(name="Jane Doe", email="xXx_gamer99@hotmail.com"))
    raw = "xXx_gamer99@hotmail.com"
    flags = redflag_scan(jr, raw)
    ids = _flag_ids(flags)
    assert "email_unprofessional" in ids


def test_professional_email_not_flagged() -> None:
    from decroche.ats.redflag_scan import redflag_scan

    jr = _jr(basics=Basics(name="Jane Doe", email="jane.doe@gmail.com"))
    raw = "jane.doe@gmail.com"
    flags = redflag_scan(jr, raw)
    ids = _flag_ids(flags)
    assert "email_unprofessional" not in ids


def test_wrong_photo_us_market() -> None:
    from decroche.ats.redflag_scan import redflag_scan
    from decroche.models import Meta

    jr = _jr(meta=Meta(market="us"))
    raw = "Photo included in CV"
    flags = redflag_scan(jr, raw + " [photo]", market_id="us", has_photo=True)
    ids = _flag_ids(flags)
    assert "wrong_photo_market" in ids


def test_no_photo_fr_market_ok() -> None:
    from decroche.ats.redflag_scan import redflag_scan

    jr = _jr()
    raw = "No photo here"
    flags = redflag_scan(jr, raw, market_id="fr", has_photo=False)
    ids = _flag_ids(flags)
    assert "wrong_photo_market" not in ids


def test_ai_generic_phrasing_flagged() -> None:
    from decroche.ats.redflag_scan import redflag_scan

    jr = _jr(work=[Work(highlights=["Was responsible for the delivery pipeline"])])
    raw = "Was responsible for the delivery pipeline"
    flags = redflag_scan(jr, raw)
    ids = _flag_ids(flags)
    assert "ai_generic_phrasing" in ids or "passive_voice" in ids


def test_redflag_has_required_fields() -> None:
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


# ── FIX 1: wrong_personal_info, length_violation, typo_risk ───────────────────────

def test_wrong_personal_info_us_market_dob_in_text() -> None:
    from decroche.ats.redflag_scan import redflag_scan

    jr = _jr()
    raw = "Jane Doe\njane@example.com\nDate de naissance: 12/03/1990\nIngénieure logicielle"
    flags = redflag_scan(jr, raw, market_id="us")
    ids = _flag_ids(flags)
    assert "wrong_personal_info" in ids


def test_wrong_personal_info_flag_is_critical() -> None:
    from decroche.ats.redflag_scan import redflag_scan

    jr = _jr()
    raw = "Date de naissance: 12/03/1990\nnationalité: française"
    flags = redflag_scan(jr, raw, market_id="us")
    pi_flags = [f for f in flags if f.flag_id == "wrong_personal_info"]
    assert len(pi_flags) >= 1
    assert pi_flags[0].severity == "CRITICAL"


def test_wrong_personal_info_fr_market_not_flagged() -> None:
    from decroche.ats.redflag_scan import redflag_scan

    jr = _jr()
    raw = "Jane Doe\njane@example.com\nIngénieure logicielle avec 5 ans d'expérience."
    flags = redflag_scan(jr, raw, market_id="fr")
    ids = _flag_ids(flags)
    assert "wrong_personal_info" not in ids


def test_length_violation_long_cv() -> None:
    from decroche.ats.redflag_scan import redflag_scan

    long_text = ("Senior Software Engineer. " * 200 +
                 "Led migration of 12 services.\n" * 100 +
                 "Built CI/CD pipelines saving 4h/week.\n" * 100)
    assert len(long_text) > 8000
    jr = _jr()
    flags = redflag_scan(jr, long_text, market_id="us")
    ids = _flag_ids(flags)
    assert "length_violation" in ids


def test_length_violation_short_cv_not_flagged() -> None:
    from decroche.ats.redflag_scan import redflag_scan

    short_text = "Jane Doe\njane@example.com\nLed migration of 12 services to Kubernetes."
    jr = _jr()
    flags = redflag_scan(jr, short_text, market_id="us")
    ids = _flag_ids(flags)
    assert "length_violation" not in ids


def test_typo_risk_doubled_word() -> None:
    from decroche.ats.redflag_scan import redflag_scan

    jr = _jr()
    raw = "Led the the deployment of containerized services on Kubernetes."
    flags = redflag_scan(jr, raw, market_id="fr")
    ids = _flag_ids(flags)
    assert "typo_risk" in ids


def test_typo_risk_doubled_word_fr() -> None:
    from decroche.ats.redflag_scan import redflag_scan

    jr = _jr()
    raw = "Géré le le déploiement de services sur Kubernetes."
    flags = redflag_scan(jr, raw, market_id="fr")
    ids = _flag_ids(flags)
    assert "typo_risk" in ids


def test_typo_risk_triple_letter() -> None:
    from decroche.ats.redflag_scan import redflag_scan

    jr = _jr()
    raw = "Produced excelllent results across all projects."
    flags = redflag_scan(jr, raw, market_id="fr")
    ids = _flag_ids(flags)
    assert "typo_risk" in ids


def test_typo_risk_clean_cv_no_false_positive() -> None:
    from decroche.ats.redflag_scan import redflag_scan

    jr = _jr()
    raw = ("Marie Dupont\nmarie.dupont@example.com\n"
           "Ingénieure logicielle senior avec 8 ans d'expérience.\n"
           "Led migration of 12 services to Kubernetes, reducing latency 38%.\n"
           "Built automated CI/CD pipeline, saving 4 hours/week.")
    flags = redflag_scan(jr, raw, market_id="fr")
    ids = _flag_ids(flags)
    assert "typo_risk" not in ids
