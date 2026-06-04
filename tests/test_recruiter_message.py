"""Tests for recruiter.message — outreach scaffold drafting."""

from __future__ import annotations


from decroche.models import Recruiter
from decroche.recruiter.message import _OPTOUT_FR, draft_message


def make_recruiter(name: str = "Sophie Martin", kind: str = "in_house") -> Recruiter:
    return Recruiter(name=name, title="Technical Recruiter", company="Acme", kind=kind)


CANDIDATE_SUMMARY = "Ingénieur backend 5 ans d'expérience, spécialisé Python et Kubernetes."
OFFER = "Ingénieur Backend Senior"


# ---------------------------------------------------------------------------
# Structure
# ---------------------------------------------------------------------------


class TestReturnStructure:
    def test_returns_intro_request(self):
        msg = draft_message(make_recruiter(), CANDIDATE_SUMMARY, OFFER)
        assert hasattr(msg, "to")
        assert hasattr(msg, "subject")
        assert hasattr(msg, "body")
        assert hasattr(msg, "lang")

    def test_to_is_recruiter_name(self):
        msg = draft_message(make_recruiter("Jean Dupont"), CANDIDATE_SUMMARY, OFFER)
        assert msg.to == "Jean Dupont"

    def test_subject_contains_offer_title(self):
        msg = draft_message(make_recruiter(), CANDIDATE_SUMMARY, OFFER)
        assert OFFER in msg.subject

    def test_body_contains_candidate_summary(self):
        msg = draft_message(make_recruiter(), CANDIDATE_SUMMARY, OFFER)
        assert CANDIDATE_SUMMARY in msg.body


# ---------------------------------------------------------------------------
# RGPD opt-out (CRITICAL compliance)
# ---------------------------------------------------------------------------


class TestOptOut:
    def test_fr_body_contains_optout(self):
        msg = draft_message(make_recruiter(), CANDIDATE_SUMMARY, OFFER, lang="fr")
        assert _OPTOUT_FR in msg.body

    def test_fr_default_contains_optout(self):
        msg = draft_message(make_recruiter(), CANDIDATE_SUMMARY, OFFER)
        assert _OPTOUT_FR in msg.body

    def test_en_body_has_optout_equivalent(self):
        msg = draft_message(make_recruiter(), CANDIDATE_SUMMARY, OFFER, lang="en")
        # English opt-out is not the same wording but must contain opt-out concept
        body_lower = msg.body.lower()
        assert "if you" in body_lower and ("prefer not" in body_lower or "rather not" in body_lower)

    def test_optout_present_regardless_of_recruiter_kind(self):
        for kind in ["in_house", "agency", "unknown"]:
            r = make_recruiter(kind=kind)
            msg = draft_message(r, CANDIDATE_SUMMARY, OFFER, lang="fr")
            assert _OPTOUT_FR in msg.body


# ---------------------------------------------------------------------------
# Language handling
# ---------------------------------------------------------------------------


class TestLanguage:
    def test_fr_lang_field(self):
        msg = draft_message(make_recruiter(), CANDIDATE_SUMMARY, OFFER, lang="fr")
        assert msg.lang == "fr"

    def test_en_lang_field(self):
        msg = draft_message(make_recruiter(), CANDIDATE_SUMMARY, OFFER, lang="en")
        assert msg.lang == "en"

    def test_unknown_lang_defaults_to_fr(self):
        msg = draft_message(make_recruiter(), CANDIDATE_SUMMARY, OFFER, lang="de")
        assert msg.lang == "fr"

    def test_en_subject_in_english(self):
        msg = draft_message(make_recruiter(), CANDIDATE_SUMMARY, OFFER, lang="en")
        assert "Application" in msg.subject or "application" in msg.subject.lower()

    def test_fr_subject_in_french(self):
        msg = draft_message(make_recruiter(), CANDIDATE_SUMMARY, OFFER, lang="fr")
        assert "Candidature" in msg.subject


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_same_inputs_same_output(self):
        r = make_recruiter()
        m1 = draft_message(r, CANDIDATE_SUMMARY, OFFER, lang="fr")
        m2 = draft_message(r, CANDIDATE_SUMMARY, OFFER, lang="fr")
        assert m1.body == m2.body
        assert m1.subject == m2.subject

    def test_first_name_used_in_greeting(self):
        r = make_recruiter("Marie-Claire Dupont")
        msg = draft_message(r, CANDIDATE_SUMMARY, OFFER, lang="fr")
        assert "Marie-Claire" in msg.body
