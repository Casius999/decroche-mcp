"""Tests for recruiter.identify — parse pasted text → Recruiter."""

from __future__ import annotations


from decroche.recruiter.identify import identify

# ---------------------------------------------------------------------------
# Sample pasted texts
# ---------------------------------------------------------------------------

AGENCY_TEXT = """\
Sophie Martin
Talent Acquisition Manager
Hays Recruitment
sophie.martin@hays.fr
https://www.linkedin.com/in/sophiemartin/
"""

INHOUSE_TEXT = """\
Pierre Dupont
Technical Recruiter
Acme Corp
pierre.dupont@acme.fr
"""

GENERIC_HR_TEXT = """\
Marie Leroy
HR Manager
GlobalTech
marie.leroy@globaltech.com
"""

UNKNOWN_TEXT = """\
François Girard
Chef de projet digital
"""

EMAIL_SIGNATURE = """\
Cordialement,
Jean-Baptiste Rousseau
Chargé de recrutement
Cabinet de recrutement TalentSearch
+33 6 12 34 56 78
"""

LINKEDIN_SNIPPET = """\
Alice Fontaine
Talent Partner at Stripe
https://www.linkedin.com/in/alicefontaine
"""


# ---------------------------------------------------------------------------
# Agency detection
# ---------------------------------------------------------------------------


class TestAgencyDetection:
    def test_hays_is_agency(self):
        r = identify(AGENCY_TEXT)
        assert r.kind == "agency"

    def test_cabinet_recrutement_is_agency(self):
        r = identify(EMAIL_SIGNATURE)
        assert r.kind == "agency"

    def test_agency_source_is_pasted(self):
        r = identify(AGENCY_TEXT)
        assert r.source == "pasted"

    def test_agency_name_extracted(self):
        r = identify(AGENCY_TEXT)
        assert "Sophie" in r.name or "Martin" in r.name

    def test_agency_title_contains_talent(self):
        r = identify(AGENCY_TEXT)
        assert r.title is not None
        assert "talent" in r.title.lower() or "acquisition" in r.title.lower()


# ---------------------------------------------------------------------------
# In-house detection
# ---------------------------------------------------------------------------


class TestInhouseDetection:
    def test_exact_target_company_match_is_inhouse(self):
        r = identify(INHOUSE_TEXT, target_company="Acme Corp")
        assert r.kind == "in_house"

    def test_no_agency_signal_defaults_to_inhouse(self):
        r = identify(INHOUSE_TEXT)
        assert r.kind == "in_house"

    def test_inhouse_company_extracted(self):
        r = identify(INHOUSE_TEXT)
        assert r.company is not None

    def test_inhouse_name_extracted(self):
        r = identify(INHOUSE_TEXT)
        assert r.name != ""


# ---------------------------------------------------------------------------
# Unknown / edge cases
# ---------------------------------------------------------------------------


class TestUnknownCases:
    def test_no_recruiter_keywords_is_unknown_or_inhouse(self):
        # No agency signals, so will be in_house or unknown depending on title
        r = identify(UNKNOWN_TEXT)
        assert r.kind in {"unknown", "in_house"}

    def test_empty_text_does_not_raise(self):
        r = identify("")
        assert isinstance(r.name, str)
        assert r.kind in {"in_house", "unknown", "agency"}

    def test_single_line_name(self):
        r = identify("Nathalie Perrin")
        assert "Nathalie" in r.name or "Perrin" in r.name


# ---------------------------------------------------------------------------
# LinkedIn URL extraction
# ---------------------------------------------------------------------------


class TestLinkedInExtraction:
    def test_linkedin_url_extracted(self):
        r = identify(AGENCY_TEXT)
        assert r.linkedin_url is not None
        assert "linkedin.com/in/" in r.linkedin_url

    def test_no_linkedin_url_is_none(self):
        r = identify(INHOUSE_TEXT)
        assert r.linkedin_url is None

    def test_linkedin_in_snippet(self):
        r = identify(LINKEDIN_SNIPPET)
        assert r.linkedin_url is not None


# ---------------------------------------------------------------------------
# Source always "pasted"
# ---------------------------------------------------------------------------


class TestSource:
    def test_source_always_pasted(self):
        for text in [AGENCY_TEXT, INHOUSE_TEXT, UNKNOWN_TEXT]:
            r = identify(text)
            assert r.source == "pasted"


# ---------------------------------------------------------------------------
# Generic HR
# ---------------------------------------------------------------------------


class TestGenericHR:
    def test_hr_manager_title_detected(self):
        r = identify(GENERIC_HR_TEXT)
        assert r.title is not None
        assert "hr" in r.title.lower() or "manager" in r.title.lower()
