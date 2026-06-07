"""Tests for interview.mock (mock_evaluate)."""

from __future__ import annotations


from decroche.interview.mock import mock_evaluate
from decroche.models import MockEval

_GOOD_ANSWER_FR = (
    "Dans mon précédent poste (situation), j'étais chargé de réduire les temps "
    "de déploiement (tâche). J'ai mis en place un pipeline CI/CD automatisé avec "
    "GitHub Actions (action). Résultat : nous avons réduit le cycle de déploiement "
    "de 48 heures à 2 heures, soit une réduction de 95 % (résultat). "
    "Cela a permis à l'équipe de livrer 3× plus souvent en production. "
    "L'équipe est passée de 4 déploiements par mois à 12 déploiements par mois. "
    "Nous avons aussi amélioré la satisfaction des développeurs selon le sondage interne."
)

_GOOD_ANSWER_EN = (
    "In my previous role (situation), I was tasked with reducing deployment cycle time "
    "(task). I designed and implemented a CI/CD pipeline using Jenkins and Docker "
    "containers (action). As a result, we achieved a 90% reduction in deployment time, "
    "going from 40 hours to 4 hours (result). The team delivered twice the number of "
    "features per quarter, growing from 10 to 20 releases. I also coordinated training "
    "for 8 engineers which resulted in a 30% drop in production incidents."
)

_NO_STAR_SHORT = "I did some work on a project and it went well."

_ONLY_RESULT = "We ended up reducing costs by 30% and shipping faster."

_HEAVY_WE = (
    "We (situation) had a big challenge. We (task) needed to fix everything. "
    "We did many things. We achieved great outcomes. We saved lots of money. "
    "We improved the process. We made everyone happy. We delivered on time. "
    "We got praised by leadership. We repeated the success next quarter. "
    "We documented our learnings. We presented at the all-hands meeting."
)

_HEAVY_I = (
    "I noticed a problem. I took initiative. I planned everything. I executed alone. "
    "I fixed the bug. I wrote the tests. I deployed the change. I told the team. "
    "I got promoted. I repeated the process. I trained others. I documented it all. "
    "I presented the results. I celebrated alone. I moved on quickly."
)


def test_returns_mock_eval():
    result = mock_evaluate(_GOOD_ANSWER_FR)
    assert isinstance(result, MockEval)


def test_good_answer_has_star():
    result = mock_evaluate(_GOOD_ANSWER_FR)
    assert result.has_star is True


def test_good_answer_quantified():
    result = mock_evaluate(_GOOD_ANSWER_FR)
    assert result.quantified is True


def test_good_answer_score_high_band():
    result = mock_evaluate(_GOOD_ANSWER_FR)
    assert result.score_band in ("med", "high")


def test_good_en_answer_has_star():
    result = mock_evaluate(_GOOD_ANSWER_EN)
    assert result.has_star is True


def test_good_en_answer_quantified():
    result = mock_evaluate(_GOOD_ANSWER_EN)
    assert result.quantified is True


def test_no_star_short_has_star_false():
    result = mock_evaluate(_NO_STAR_SHORT)
    assert result.has_star is False


def test_no_star_short_low_score():
    result = mock_evaluate(_NO_STAR_SHORT)
    assert result.score_band == "low"


def test_score_between_0_and_100():
    for text in [_GOOD_ANSWER_FR, _NO_STAR_SHORT, _ONLY_RESULT]:
        result = mock_evaluate(text)
        assert 0.0 <= result.score_0_100 <= 100.0


def test_word_count_accurate():
    text = "one two three four five"
    result = mock_evaluate(text)
    assert result.word_count == 5


def test_est_seconds_approximate():
    # 130 words → ~60s
    text = " ".join(["word"] * 130)
    result = mock_evaluate(text)
    assert abs(result.est_seconds - 60) <= 2


def test_i_we_ratio_heavy_i():
    result = mock_evaluate(_HEAVY_I)
    assert result.i_we_ratio > 2.0


def test_i_we_ratio_heavy_we():
    result = mock_evaluate(_HEAVY_WE)
    assert result.i_we_ratio < 0.5


def test_feedback_list_non_empty():
    result = mock_evaluate(_GOOD_ANSWER_FR)
    assert len(result.feedback) > 0


def test_feedback_are_strings():
    result = mock_evaluate(_NO_STAR_SHORT)
    assert all(isinstance(f, str) for f in result.feedback)


def test_no_star_feedback_mentions_structure():
    result = mock_evaluate(_NO_STAR_SHORT)
    combined = " ".join(result.feedback).lower()
    assert "star" in combined or "structure" in combined


def test_quantified_false_feedback_mentions_metric():
    text = (
        "In my previous role I was responsible for the project. "
        "I implemented a new approach and the team was happy with the results. "
        "We achieved our goals and management praised us for the work done."
    )
    result = mock_evaluate(text)
    if not result.quantified:
        combined = " ".join(result.feedback).lower()
        assert (
            "chiffr" in combined
            or "métrique" in combined
            or "quantif" in combined
            or "metric" in combined
        )


def test_deterministic_same_input():
    r1 = mock_evaluate(_GOOD_ANSWER_FR)
    r2 = mock_evaluate(_GOOD_ANSWER_FR)
    assert r1.score_0_100 == r2.score_0_100
    assert r1.has_star == r2.has_star
    assert r1.quantified == r2.quantified


def test_empty_string():
    result = mock_evaluate("")
    assert result.word_count == 0
    assert result.score_band == "low"


def test_score_band_values():
    result = mock_evaluate(_GOOD_ANSWER_FR)
    assert result.score_band in ("low", "med", "high")


def test_high_score_answer_band_high():
    # A very complete answer should reach high band (≥70)
    result = mock_evaluate(_GOOD_ANSWER_EN)
    assert result.score_band == "high"
