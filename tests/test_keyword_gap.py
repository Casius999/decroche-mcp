"""Tests for match.keyword_gap — addable_honestly vs genuinely_missing."""
from __future__ import annotations


from decroche.match.keyword_gap import keyword_gap
from decroche.models import Basics, JSONResume, KeywordGap, Skill, Work


# ── Fixtures ─────────────────────────────────────────────────────────────────────

def _resume_with_k8s_hidden() -> JSONResume:
    return JSONResume(
        basics=Basics(name="Jane", label="kubernetes expert", summary=None),
        skills=[Skill(name="Python")],
        work=[Work(highlights=["Maintained backend systems"])],
    )


def _resume_no_k8s() -> JSONResume:
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
        result = keyword_gap(_resume_with_k8s_hidden(), OFFER_K8S_RUST)
        assert any(g.status == "addable_honestly" for g in result)

    def test_addable_has_evidence(self):
        result = keyword_gap(_resume_with_k8s_hidden(), OFFER_K8S_RUST)
        addable = [g for g in result if g.status == "addable_honestly"]
        for item in addable:
            assert item.evidence is not None


class TestGenuinelyMissing:
    def test_absent_term_is_genuinely_missing(self):
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
        result = keyword_gap(_resume_no_k8s(), OFFER_K8S_RUST)
        for item in result:
            assert item.status in ("addable_honestly", "genuinely_missing")


# ── FIX 4: meaningful ranking ─────────────────────────────────────────────────────

OFFER_PRIORITY_RANKING = """
Senior Backend Engineer

Requirements:
- PostgreSQL
- Docker

Nice to have:
- GraphQL
- Redis
"""

OFFER_FREQUENCY_RANKING = """
Backend Engineer

Requirements:
- Kafka
- Kafka integration
- Kafka streaming
- Kafka consumer

Nice to have:
- Flink
"""


def _resume_empty() -> JSONResume:
    return JSONResume(
        basics=Basics(name="Empty"),
        skills=[Skill(name="COBOL")],
        work=[Work(highlights=["Maintained legacy systems"])],
    )


class TestRankingPriority:
    def test_must_have_ranks_above_nice_to_have(self):
        result = keyword_gap(_resume_empty(), OFFER_PRIORITY_RANKING, n=10)
        must_items = [g for g in result if g.term.lower() in ("postgresql", "docker")]
        nice_items = [g for g in result if g.term.lower() in ("graphql", "redis")]
        assert must_items, f"must_have terms not in results: {[g.term for g in result]}"
        assert nice_items, f"nice_to_have terms not in results: {[g.term for g in result]}"
        result_terms = [g.term.lower() for g in result]
        last_must_idx = max(result_terms.index(g.term.lower()) for g in must_items)
        first_nice_idx = min(result_terms.index(g.term.lower()) for g in nice_items)
        assert last_must_idx < first_nice_idx, (
            f"must_have (last at {last_must_idx}) not before nice_to_have "
            f"(first at {first_nice_idx}): {result_terms}"
        )

    def test_high_frequency_term_ranks_above_low_frequency(self):
        result = keyword_gap(_resume_empty(), OFFER_FREQUENCY_RANKING, n=10)
        terms = [g.term.lower() for g in result]
        assert "kafka" in terms, f"kafka not in results: {terms}"
        assert "flink" in terms, f"flink not in results: {terms}"
        kafka_idx = terms.index("kafka")
        flink_idx = terms.index("flink")
        assert kafka_idx < flink_idx, (
            f"kafka (idx {kafka_idx}) should rank above flink (idx {flink_idx})"
        )
