"""Tests for match.offer.parse_offer — deterministic offer parser."""
from __future__ import annotations


from decroche.match.offer import parse_offer
from decroche.models import Offer


OFFER_EN_STRUCTURED = """
Backend Engineer

Requirements:
- Python
- Kubernetes
- PostgreSQL
- 5+ years experience

Nice to have:
- Rust
- GraphQL
"""

OFFER_FR_STRUCTURED = """
Développeur Backend Senior

Profil recherché:
- Python
- Docker
- PostgreSQL

Apprécié:
- Rust
- Redis
"""

OFFER_NO_SECTIONS = """
We are looking for an engineer with skills in Python, Go, and Kubernetes.
Experience with Docker and CI/CD is a plus.
"""

OFFER_SENIORITY_SENIOR = """
Senior Software Engineer

Requirements:
- Python
- 5+ years experience

Nice to have:
- Rust
"""

OFFER_SENIORITY_JUNIOR = """
Junior Python Developer

Requirements:
- Python
"""

OFFER_SENIORITY_LEAD = """
Lead Backend Engineer

Requirements:
- Python
- Kubernetes
"""

OFFER_SENIORITY_STAGIAIRE = """
Stage Développeur Python

Requis:
- Python
"""


class TestParseOfferTitle:
    def test_extracts_title_as_first_nonempty_line(self):
        offer = parse_offer(OFFER_EN_STRUCTURED)
        assert offer.title == "Backend Engineer"

    def test_french_title(self):
        offer = parse_offer(OFFER_FR_STRUCTURED)
        assert offer.title == "Développeur Backend Senior"

    def test_raw_stored(self):
        offer = parse_offer(OFFER_EN_STRUCTURED)
        assert "Python" in offer.raw


class TestParseOfferMustHave:
    def test_required_section_populated(self):
        offer = parse_offer(OFFER_EN_STRUCTURED)
        must_lower = [m.lower() for m in offer.must_have]
        assert "python" in must_lower

    def test_kubernetes_in_must(self):
        offer = parse_offer(OFFER_EN_STRUCTURED)
        must_lower = [m.lower() for m in offer.must_have]
        assert "kubernetes" in must_lower

    def test_french_profil_recherche_section(self):
        offer = parse_offer(OFFER_FR_STRUCTURED)
        must_lower = [m.lower() for m in offer.must_have]
        assert "python" in must_lower
        assert "docker" in must_lower

    def test_no_section_fallback_salient_terms(self):
        offer = parse_offer(OFFER_NO_SECTIONS)
        # Without explicit section, salient tech terms land in must_have
        must_lower = [m.lower() for m in offer.must_have]
        # at least some terms extracted
        assert len(must_lower) >= 2


class TestParseOfferNiceToHave:
    def test_nice_to_have_section_populated(self):
        offer = parse_offer(OFFER_EN_STRUCTURED)
        nice_lower = [n.lower() for n in offer.nice_to_have]
        assert "rust" in nice_lower

    def test_french_apprecie_section(self):
        offer = parse_offer(OFFER_FR_STRUCTURED)
        nice_lower = [n.lower() for n in offer.nice_to_have]
        assert "rust" in nice_lower


class TestParseOfferSeniority:
    def test_senior_detected(self):
        offer = parse_offer(OFFER_SENIORITY_SENIOR)
        assert offer.seniority == "senior"

    def test_junior_detected(self):
        offer = parse_offer(OFFER_SENIORITY_JUNIOR)
        assert offer.seniority == "junior"

    def test_lead_detected(self):
        offer = parse_offer(OFFER_SENIORITY_LEAD)
        assert offer.seniority == "lead"

    def test_stagiaire_detected(self):
        offer = parse_offer(OFFER_SENIORITY_STAGIAIRE)
        assert offer.seniority == "stagiaire"

    def test_unknown_seniority_is_none(self):
        offer = parse_offer(OFFER_NO_SECTIONS)
        assert offer.seniority is None

    def test_years_seniority_detected(self):
        text = "Software Engineer\nRequirements:\n- Python\n- 7+ years experience"
        offer = parse_offer(text)
        assert offer.seniority is not None
        assert "7" in offer.seniority


class TestParseOfferReturnType:
    def test_returns_offer_instance(self):
        offer = parse_offer(OFFER_EN_STRUCTURED)
        assert isinstance(offer, Offer)

    def test_must_and_nice_disjoint(self):
        offer = parse_offer(OFFER_EN_STRUCTURED)
        must_set = set(m.lower() for m in offer.must_have)
        nice_set = set(n.lower() for n in offer.nice_to_have)
        # No term should appear in both
        assert must_set.isdisjoint(nice_set)
