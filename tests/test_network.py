"""Tests for network.paths — warm path finding and intro drafting."""

from __future__ import annotations


from decroche.models import NetworkPath
from decroche.network.paths import (
    draft_intro_request,
    find_warm_path,
    score_intro_value,
)

# ---------------------------------------------------------------------------
# Sample connection lists
# ---------------------------------------------------------------------------

CONNECTIONS = [
    {"name": "Alice Dupont", "company": "Acme Corp", "relationship": "former colleague"},
    {"name": "Bob Martin", "company": "Beta Inc", "relationship": "friend"},
    {"name": "Carol Petit", "company": "Acme Corp", "relationship": "mentor"},
    {"name": "Dave Moreau", "company": "Gamma SAS", "relationship": "linkedin connection"},
]


# ---------------------------------------------------------------------------
# find_warm_path
# ---------------------------------------------------------------------------


class TestFindWarmPath:
    def test_finds_connections_at_target(self):
        paths = find_warm_path("Acme Corp", CONNECTIONS)
        assert len(paths) >= 1
        connectors = [p.connector for p in paths]
        assert "Alice Dupont" in connectors or "Carol Petit" in connectors

    def test_does_not_include_other_companies(self):
        paths = find_warm_path("Acme Corp", CONNECTIONS)
        for p in paths:
            assert p.target_company == "Acme Corp"

    def test_returns_empty_for_no_match(self):
        paths = find_warm_path("Unknown Corp", CONNECTIONS)
        assert paths == []

    def test_empty_connections_returns_empty(self):
        paths = find_warm_path("Acme Corp", [])
        assert paths == []

    def test_hops_is_1_for_direct(self):
        paths = find_warm_path("Acme Corp", CONNECTIONS)
        for p in paths:
            assert p.hops == 1

    def test_sorted_by_value_descending(self):
        paths = find_warm_path("Acme Corp", CONNECTIONS)
        values = [score_intro_value(p) for p in paths]
        assert values == sorted(values, reverse=True)

    def test_mentor_scored_higher_than_colleague(self):
        paths = find_warm_path("Acme Corp", CONNECTIONS)
        connector_scores = {p.connector: score_intro_value(p) for p in paths}
        if "Carol Petit" in connector_scores and "Alice Dupont" in connector_scores:
            assert connector_scores["Carol Petit"] >= connector_scores["Alice Dupont"]

    def test_partial_company_match(self):
        connections = [{"name": "Eve", "company": "Acme Corp SARL", "relationship": "friend"}]
        paths = find_warm_path("Acme Corp", connections)
        assert len(paths) >= 1

    def test_note_preserved(self):
        connections = [
            {
                "name": "Frank",
                "company": "Acme",
                "relationship": "former colleague",
                "note": "hiring freeze in Q1",
            }
        ]
        paths = find_warm_path("Acme", connections)
        assert any(p.note == "hiring freeze in Q1" for p in paths)


# ---------------------------------------------------------------------------
# score_intro_value
# ---------------------------------------------------------------------------


class TestScoreIntroValue:
    def test_score_within_bounds(self):
        for rel in ["friend", "former colleague", "linkedin connection", "unknown"]:
            path = NetworkPath(target_company="Acme", connector="X", relationship=rel, hops=1)
            s = score_intro_value(path)
            assert 0.0 <= s <= 1.0

    def test_friend_higher_than_linkedin(self):
        p_friend = NetworkPath(target_company="X", connector="A", relationship="friend", hops=1)
        p_li = NetworkPath(
            target_company="X", connector="B", relationship="linkedin connection", hops=1
        )
        assert score_intro_value(p_friend) > score_intro_value(p_li)

    def test_hops_discounts_score(self):
        p1 = NetworkPath(target_company="X", connector="A", relationship="friend", hops=1)
        p2 = NetworkPath(target_company="X", connector="A", relationship="friend", hops=2)
        assert score_intro_value(p1) > score_intro_value(p2)

    def test_deterministic(self):
        p = NetworkPath(target_company="X", connector="A", relationship="mentor", hops=1)
        assert score_intro_value(p) == score_intro_value(p)


# ---------------------------------------------------------------------------
# draft_intro_request
# ---------------------------------------------------------------------------


class TestDraftIntroRequest:
    def _make_path(self, connector: str = "Alice Dupont") -> NetworkPath:
        return NetworkPath(
            target_company="Acme Corp",
            connector=connector,
            relationship="former colleague",
            hops=1,
        )

    def test_returns_intro_request(self):
        req = draft_intro_request(self._make_path())
        assert hasattr(req, "to")
        assert hasattr(req, "subject")
        assert hasattr(req, "body")
        assert hasattr(req, "lang")

    def test_to_is_connector(self):
        req = draft_intro_request(self._make_path("Bob Martin"))
        assert req.to == "Bob Martin"

    def test_subject_contains_target_company(self):
        req = draft_intro_request(self._make_path())
        assert "Acme Corp" in req.subject

    def test_fr_body_contains_optout(self):
        req = draft_intro_request(self._make_path(), lang="fr")
        body_lower = req.body.lower()
        assert "ne souhait" in body_lower or "supprimerai" in body_lower

    def test_en_body_contains_optout(self):
        req = draft_intro_request(self._make_path(), lang="en")
        body_lower = req.body.lower()
        assert "prefer not" in body_lower or "rather not" in body_lower

    def test_context_appears_in_body(self):
        req = draft_intro_request(self._make_path(), context="poste Python backend", lang="fr")
        assert "poste Python backend" in req.body or "Python" in req.body

    def test_lang_field_correct(self):
        req_fr = draft_intro_request(self._make_path(), lang="fr")
        req_en = draft_intro_request(self._make_path(), lang="en")
        assert req_fr.lang == "fr"
        assert req_en.lang == "en"
