"""Tests for analytics.crm — SQLite-backed Application CRM (deterministic)."""

from __future__ import annotations

import pytest

from decroche.analytics.crm import get, list_apps, track, update_stage
from decroche.models import Application


def _app(app_id: str = "app-001", stage: str = "saved") -> Application:
    return Application(id=app_id, company="Acme Corp", role_title="Senior Python Dev", source_channel="cold_apply", url="https://acme.com/jobs/1", apply_url="https://acme.com/apply/1", stage=stage, tags=["python", "remote"])


def test_track_insert_and_get_roundtrip(tmp_path):
    db = str(tmp_path / "crm.db")
    app = _app()
    saved = track(app, db)
    assert saved.id == app.id
    fetched = get(app.id, db)
    assert fetched is not None and fetched.company == "Acme Corp" and fetched.tags == ["python", "remote"]

def test_track_update_existing(tmp_path):
    db = str(tmp_path / "crm.db")
    app = _app()
    track(app, db)
    track(app.model_copy(update={"role_title": "Lead Python Dev"}), db)
    assert get(app.id, db).role_title == "Lead Python Dev"

def test_track_returns_application_object(tmp_path):
    assert isinstance(track(_app(), str(tmp_path / "crm.db")), Application)

def test_track_preserves_all_fields(tmp_path):
    db = str(tmp_path / "crm.db")
    app = Application(id="app-full", job_id="job-42", company="NovaCorp", role_title="ML Engineer", source_channel="referral", url="https://nova.com/jobs/42", apply_url="https://nova.com/apply/42", stage="applied", resume_version_id="rv-1", cover_letter_id="cl-1", contact_ids=["c1", "c2"], notes=["Talked to recruiter"], thank_you_sent=True, follow_up_sent=False, tags=["ml", "python"])
    track(app, db)
    fetched = get("app-full", db)
    assert fetched.job_id == "job-42" and fetched.source_channel == "referral" and fetched.contact_ids == ["c1", "c2"] and fetched.thank_you_sent is True

def test_get_missing_returns_none(tmp_path):
    assert get("nonexistent", str(tmp_path / "crm.db")) is None

def test_get_from_empty_db(tmp_path):
    assert get("app-001", str(tmp_path / "crm.db")) is None

def test_update_stage_changes_stage(tmp_path):
    db = str(tmp_path / "crm.db")
    track(_app("app-002", stage="saved"), db)
    assert update_stage("app-002", "applied", db).stage == "applied"

def test_update_stage_appends_history(tmp_path):
    db = str(tmp_path / "crm.db")
    track(_app("app-003", stage="saved"), db)
    update_stage("app-003", "applied", db)
    update_stage("app-003", "screen", db)
    fetched = get("app-003", db)
    assert len(fetched.stage_history) == 2
    assert [h["stage"] for h in fetched.stage_history] == ["applied", "screen"]

def test_update_stage_history_has_timestamp(tmp_path):
    db = str(tmp_path / "crm.db")
    track(_app("app-004"), db)
    update_stage("app-004", "applied", db)
    assert "at" in get("app-004", db).stage_history[0]

def test_update_stage_with_note(tmp_path):
    db = str(tmp_path / "crm.db")
    track(_app("app-005"), db)
    update_stage("app-005", "screen", db, note="Phone screen booked")
    assert get("app-005", db).stage_history[0].get("note") == "Phone screen booked"

def test_update_stage_raises_on_missing(tmp_path):
    with pytest.raises(KeyError):
        update_stage("does-not-exist", "applied", str(tmp_path / "crm.db"))

def test_update_stage_persisted_after_get(tmp_path):
    db = str(tmp_path / "crm.db")
    track(_app("app-006", stage="saved"), db)
    update_stage("app-006", "applied", db)
    assert get("app-006", db).stage == "applied"

def test_list_apps_empty(tmp_path):
    assert list_apps(str(tmp_path / "crm.db")) == []

def test_list_apps_all(tmp_path):
    db = str(tmp_path / "crm.db")
    for aid, stage in [("a1", "saved"), ("a2", "applied"), ("a3", "screen")]:
        track(_app(aid, stage), db)
    assert len(list_apps(db)) == 3

def test_list_apps_filter_by_stage(tmp_path):
    db = str(tmp_path / "crm.db")
    track(_app("b1", "saved"), db); track(_app("b2", "applied"), db); track(_app("b3", "applied"), db)
    results = list_apps(db, stage="applied")
    assert len(results) == 2 and all(a.stage == "applied" for a in results)

def test_list_apps_filter_no_match(tmp_path):
    db = str(tmp_path / "crm.db")
    track(_app("c1", "saved"), db)
    assert list_apps(db, stage="rejected") == []

def test_list_apps_returns_application_objects(tmp_path):
    db = str(tmp_path / "crm.db")
    track(_app("d1"), db)
    assert all(isinstance(a, Application) for a in list_apps(db))
