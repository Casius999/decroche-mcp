"""Tests for match.keyword_gap — addable_honestly vs genuinely_missing."""
from __future__ import annotations


from decroche.match.keyword_gap import keyword_gap
from decroche.models import Basics, JSONResume, KeywordGap, Skill, Work


# ── Fixtures ───────────────────────────────────────────────────────────────────────────

def _resume_with_k8s_hidden() -> JSONResume:
    """Resume where 'kubernetes' appears in basics.label (scanned by _raw_cv_text) but
    NOT in candidate_terms (which only scans skills, work highlights/summary, basics.summary).

    This means: Kubernetes gap → uncovered by match_score → addable_honestly (found in label).
    """
    return JSONResume(
        basics=Basics(name="Jane", label="kubernetes expert", summary=None),
        skills=[Skill(name="Python")],
        work=[Work(highlights=["Maintained backend systems"])],
    )


def _resume_no_k8s() -> JSONResume:
    """Resume with no mention of k8s or Kubernetes anywhere."""
    return JSONResume(
        basics=Basics(name="Bob"),
        skills=[Skill(name="COBOL")],
        work=[Work(highlights=["Maintained legacy systems"])],
    )


OFFER_K8S_RUST = """
Backend Engineer

Requirements:
- Kubernetes
- Rust

Nice to have:
- GraphQL
"""


OFFER_ONLY_ABSENT = """
Staff Engineer

Requirements:
- Haskell
- Erlang
- COBOL
"""


class TestKeywordGapReturnType:
    def test_returns_list(self):
        result = keyword_gap(_resume_no_k8s(), OFFER_K8S_RUST)
        assert isinstance(result, list)

    def test_returns_keyword_gap_instances(self):
        result = keyword_gap(_resume_no_k8s(), OFFER_K8S_RUST)
        for item in result:
            assert isinstance(item, KeywordGap)


class TestAddableHonestly:
    def test_buried_term_is_addable(self):
        """'Kubernetes' absent from skills but 'k8s' in raw CV text → addable_honestly."""
        result = keyword_gap(_resume_with_k8s_hidden(), OFFER_K8S_RUST)
        # kubernetes or k8s should appear and be addable
        assert any(g.status == "addable_honestly" for g in result)

    def test_addable_has_evidence(self):
        result = keyword_gap(_resume_with_k8s_hidden(), OFFER_K8S_RUST)
        addable = [g for g in result if g.status == "addable_honestly"]
        for item in addable:
            assert item.evidence is not None


class TestGenuinelyMissing:
    def test_absent_term_is_genuinely_missing(self):
        """'Haskell' not mentioned anywhere → genuinely_missing."""
        result = keyword_gap(_resume_no_k8s(), OFFER_ONLY_ABSENT)
        statuses = {g.status for g in result}
        assert "genuinely_missing" in statuses

    def test_rust_absent_from_no_k8s_resume(self):
        result = keyword_gap(_resume_no_k8s(), OFFER_K8S_RUST)
        missing_terms = {g.term.lower() for g in result if g.status == "genuinely_missing"}
        assert "rust" in missing_terms


class TestTopN:
    def test_default_n_is_5(self):
        result = keyword_gap(_resume_no_k8s(), OFFER_ONLY_ABSENT)
        assert len(result) <= 5

    def test_custom_n_respected(self):
        result = keyword_gap(_resume_no_k8s(), OFFER_K8S_RUST, n=2)
        assert len(result) <= 2

    def test_n_1_returns_one(self):
        result = keyword_gap(_resume_no_k8s(), OFFER_K8S_RUST, n=1)
        assert len(result) == 1


class TestSalience:
    def test_salience_is_float(self):
        result = keyword_gap(_resume_no_k8s(), OFFER_K8S_RUST)
        for item in result:
            assert isinstance(item.salience, float)

    def test_salience_in_range(self):
        result = keyword_gap(_resume_no_k8s(), OFFER_K8S_RUST)
        for item in result:
            assert 0.0 <= item.salience <= 1.0


class TestNeverFabricate:
    def test_status_only_valid_values(self):
        """Status must be one of the two defined values — never anything fabricated."""
        result = keyword_gap(_resume_no_k8s(), OFFER_K8S_RUST)
        for item in result:
            assert item.status in ("addable_honestly", "genuinely_missing")
