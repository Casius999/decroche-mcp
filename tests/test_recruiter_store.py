"""Tests for recruiter.store — JSON persistence with CNIL metadata."""

from __future__ import annotations

import json


from decroche.models import Contact, Recruiter
from decroche.recruiter.store import load_store, store_recruiter


def make_recruiter() -> Recruiter:
    return Recruiter(
        name="Alice Dupont",
        title="Technical Recruiter",
        company="Acme Corp",
        kind="in_house",
        source="pasted",
    )


def make_contact(status: str = "guessed_unverified") -> Contact:
    return Contact(
        name="Alice Dupont",
        email="alice.dupont@acme.com",
        status=status,
        source="pattern_guess",
        company="Acme Corp",
    )


# ---------------------------------------------------------------------------
# Basic roundtrip
# ---------------------------------------------------------------------------


class TestRoundtrip:
    def test_store_creates_file(self, tmp_path):
        p = tmp_path / "store.json"
        store_recruiter(make_recruiter(), make_contact(), p)
        assert p.exists()

    def test_stored_content_is_valid_json(self, tmp_path):
        p = tmp_path / "store.json"
        store_recruiter(make_recruiter(), make_contact(), p)
        data = json.loads(p.read_text(encoding="utf-8"))
        assert isinstance(data, list)

    def test_roundtrip_name(self, tmp_path):
        p = tmp_path / "store.json"
        store_recruiter(make_recruiter(), make_contact(), p)
        records = load_store(p)
        assert records[0]["recruiter"]["name"] == "Alice Dupont"

    def test_roundtrip_contact_email(self, tmp_path):
        p = tmp_path / "store.json"
        store_recruiter(make_recruiter(), make_contact(), p)
        records = load_store(p)
        assert records[0]["contact"]["email"] == "alice.dupont@acme.com"

    def test_append_multiple(self, tmp_path):
        p = tmp_path / "store.json"
        store_recruiter(make_recruiter(), make_contact(), p)
        r2 = Recruiter(name="Bob Martin", title="HR", company="Beta", kind="agency")
        c2 = Contact(name="Bob Martin", status="not_found", source="no_source")
        store_recruiter(r2, c2, p)
        records = load_store(p)
        assert len(records) == 2


# ---------------------------------------------------------------------------
# CNIL/RGPD compliance metadata
# ---------------------------------------------------------------------------


class TestCnilMetadata:
    def test_pii_flag_present(self, tmp_path):
        p = tmp_path / "store.json"
        record = store_recruiter(make_recruiter(), make_contact(), p)
        assert record["pii"] is True

    def test_retention_max_years_is_3(self, tmp_path):
        p = tmp_path / "store.json"
        record = store_recruiter(make_recruiter(), make_contact(), p)
        assert record["retention_max_years"] == 3

    def test_pii_flag_in_file(self, tmp_path):
        p = tmp_path / "store.json"
        store_recruiter(make_recruiter(), make_contact(), p)
        raw = p.read_text(encoding="utf-8")
        assert '"pii": true' in raw

    def test_retention_metadata_in_file(self, tmp_path):
        p = tmp_path / "store.json"
        store_recruiter(make_recruiter(), make_contact(), p)
        raw = p.read_text(encoding="utf-8")
        assert "retention_max_years" in raw
        assert "3" in raw


# ---------------------------------------------------------------------------
# load_store
# ---------------------------------------------------------------------------


class TestLoadStore:
    def test_load_nonexistent_returns_empty(self, tmp_path):
        records = load_store(tmp_path / "does_not_exist.json")
        assert records == []

    def test_load_returns_list(self, tmp_path):
        p = tmp_path / "store.json"
        store_recruiter(make_recruiter(), make_contact(), p)
        records = load_store(p)
        assert isinstance(records, list)

    def test_load_preserves_recruiter_kind(self, tmp_path):
        p = tmp_path / "store.json"
        store_recruiter(make_recruiter(), make_contact(), p)
        records = load_store(p)
        assert records[0]["recruiter"]["kind"] == "in_house"

    def test_utf8_encoding(self, tmp_path):
        p = tmp_path / "store.json"
        r = Recruiter(name="Élodie Génot", company="Société Générale", kind="in_house")
        store_recruiter(r, make_contact(), p)
        records = load_store(p)
        assert "Élodie" in records[0]["recruiter"]["name"]
