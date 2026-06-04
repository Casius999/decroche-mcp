"""Tests for recruiter.contact — email finding + honest status.

NO network: Dropcontact call is monkeypatched.
"""

from __future__ import annotations


import pytest

from decroche.recruiter.contact import _guess_email, find_contact


# ---------------------------------------------------------------------------
# Unit: _guess_email
# ---------------------------------------------------------------------------


class TestGuessEmail:
    def test_simple_name(self):
        assert _guess_email("Alice Dupont", "acme.com") == "alice.dupont@acme.com"

    def test_accented_name(self):
        assert _guess_email("Élodie Génot", "test.fr") == "elodie.genot@test.fr"

    def test_single_word_name(self):
        result = _guess_email("Madonna", "domain.com")
        assert result.endswith("@domain.com")

    def test_three_word_name_uses_first_last(self):
        result = _guess_email("Jean Pierre Dupont", "co.fr")
        assert result == "jean.dupont@co.fr"

    def test_domain_leading_at_stripped(self):
        assert _guess_email("Bob Smith", "@example.com") == "bob.smith@example.com"

    def test_lowercase_output(self):
        result = _guess_email("JOHN DOE", "DOMAIN.COM")
        assert result == result.lower()


# ---------------------------------------------------------------------------
# Async: no key → guessed_unverified
# ---------------------------------------------------------------------------


class TestNoKey:
    @pytest.mark.asyncio
    async def test_no_key_no_domain_not_found(self, monkeypatch):
        monkeypatch.delenv("DROPCONTACT_KEY", raising=False)
        c = await find_contact("Alice Dupont", "Acme")
        assert c.status == "not_found"
        assert c.email is None

    @pytest.mark.asyncio
    async def test_no_key_with_domain_guessed_unverified(self, monkeypatch):
        monkeypatch.delenv("DROPCONTACT_KEY", raising=False)
        c = await find_contact("Alice Dupont", "Acme", domain="acme.com")
        assert c.status == "guessed_unverified"
        assert c.email is not None
        assert "@acme.com" in c.email

    @pytest.mark.asyncio
    async def test_guessed_is_never_verified(self, monkeypatch):
        monkeypatch.delenv("DROPCONTACT_KEY", raising=False)
        c = await find_contact("Bob Martin", "Corp", domain="corp.io")
        assert c.status != "verified"

    @pytest.mark.asyncio
    async def test_source_is_pattern_guess(self, monkeypatch):
        monkeypatch.delenv("DROPCONTACT_KEY", raising=False)
        c = await find_contact("Carol Petit", "X", domain="x.com")
        assert c.source == "pattern_guess"

    @pytest.mark.asyncio
    async def test_name_preserved(self, monkeypatch):
        monkeypatch.delenv("DROPCONTACT_KEY", raising=False)
        c = await find_contact("Nathalie Girard", "Y", domain="y.fr")
        assert c.name == "Nathalie Girard"


# ---------------------------------------------------------------------------
# Async: DROPCONTACT_KEY set → verified hit (monkeypatched fetch)
# ---------------------------------------------------------------------------


DROPCONTACT_HIT = {
    "data": [
        {
            "email": [{"email": "sophie.martin@hays.fr", "qualifier": "professional"}],
        }
    ]
}

DROPCONTACT_MISS = {"data": [{}]}


class TestWithDropcontact:
    @pytest.mark.asyncio
    async def test_verified_on_hit(self, monkeypatch):
        monkeypatch.setenv("DROPCONTACT_KEY", "test-key-abc")

        async def _fake_fetch_json(url, *, method="GET", json_body=None, headers=None, **kwargs):
            return DROPCONTACT_HIT

        monkeypatch.setattr(
            "decroche.recruiter.contact.fetch_json",
            _fake_fetch_json,
        )

        c = await find_contact("Sophie Martin", "Hays")
        assert c.status == "verified"
        assert c.email == "sophie.martin@hays.fr"
        assert c.source == "dropcontact"

    @pytest.mark.asyncio
    async def test_not_found_on_miss(self, monkeypatch):
        monkeypatch.setenv("DROPCONTACT_KEY", "test-key-abc")

        async def _fake_fetch_json(url, *, method="GET", json_body=None, headers=None, **kwargs):
            return DROPCONTACT_MISS

        monkeypatch.setattr(
            "decroche.recruiter.contact.fetch_json",
            _fake_fetch_json,
        )

        c = await find_contact("Unknown Person", "NoCompany")
        assert c.status == "not_found"
        assert c.email is None

    @pytest.mark.asyncio
    async def test_empty_data_list_not_found(self, monkeypatch):
        monkeypatch.setenv("DROPCONTACT_KEY", "test-key-abc")

        async def _fake_fetch_json(url, **kwargs):
            return {"data": []}

        monkeypatch.setattr("decroche.recruiter.contact.fetch_json", _fake_fetch_json)

        c = await find_contact("Ghost User", "Ghost Corp")
        assert c.status == "not_found"

    @pytest.mark.asyncio
    async def test_api_error_propagates(self, monkeypatch):
        monkeypatch.setenv("DROPCONTACT_KEY", "test-key-abc")
        from decroche.source.http import ToolError

        async def _fake_fetch_json(url, **kwargs):
            raise ToolError("dropcontact: HTTP 429 error from upstream API.")

        monkeypatch.setattr("decroche.recruiter.contact.fetch_json", _fake_fetch_json)

        with pytest.raises(ToolError):
            await find_contact("Rate Limited", "Corp")

    @pytest.mark.asyncio
    async def test_verified_status_only_from_api(self, monkeypatch):
        """Guarantee: no matter what, guessed path NEVER returns 'verified'."""
        monkeypatch.delenv("DROPCONTACT_KEY", raising=False)
        c = await find_contact("Alice Bonus", "Co", domain="co.io")
        assert c.status in {"guessed_unverified", "not_found"}
        assert c.status != "verified"
