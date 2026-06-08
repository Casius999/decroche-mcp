"""Tests for interview.story_bank."""

from __future__ import annotations


import pytest

from decroche.interview.story_bank import (
    add_story,
    coverage,
    list_stories,
    suggest_stories,
)
from decroche.models import Story, StoryGap


def _make_story(**kwargs) -> Story:
    defaults = dict(
        title="Test story",
        situation="S: we had a problem",
        task="T: I was responsible",
        action="A: I implemented the fix",
        result="R: we reduced errors by 30%",
        effect="E: saved 10h/week",
        competencies=["problem-solving", "communication"],
    )
    defaults.update(kwargs)
    return Story(**defaults)


@pytest.fixture
def store(tmp_path):
    return tmp_path / "stories.json"


def test_add_story_returns_story(store):
    s = _make_story()
    result = add_story(s, store)
    assert isinstance(result, Story)


def test_add_story_persists(store):
    s = _make_story(title="Persist me")
    add_story(s, store)
    stories = list_stories(store)
    assert len(stories) == 1
    assert stories[0].title == "Persist me"


def test_add_multiple_stories(store):
    add_story(_make_story(title="A"), store)
    add_story(_make_story(title="B"), store)
    assert len(list_stories(store)) == 2


def test_list_stories_empty_when_no_file(tmp_path):
    result = list_stories(tmp_path / "nonexistent.json")
    assert result == []


def test_add_story_fails_missing_situation(store):
    s = _make_story(situation="")
    with pytest.raises(ValueError, match="situation"):
        add_story(s, store)


def test_add_story_fails_missing_task(store):
    s = _make_story(task="")
    with pytest.raises(ValueError, match="task"):
        add_story(s, store)


def test_add_story_fails_missing_action(store):
    s = _make_story(action="")
    with pytest.raises(ValueError, match="action"):
        add_story(s, store)


def test_add_story_fails_missing_result(store):
    s = _make_story(result="")
    with pytest.raises(ValueError, match="result"):
        add_story(s, store)


def test_effect_is_optional(store):
    s = _make_story(effect="")
    result = add_story(s, store)
    assert result.effect == ""


def test_suggest_stories_finds_match(store):
    add_story(_make_story(competencies=["leadership", "communication"]), store)
    matches = suggest_stories("leadership", store)
    assert len(matches) == 1


def test_suggest_stories_case_insensitive(store):
    add_story(_make_story(competencies=["Leadership"]), store)
    matches = suggest_stories("leadership", store)
    assert len(matches) == 1


def test_suggest_stories_partial_match(store):
    add_story(_make_story(competencies=["problem-solving"]), store)
    matches = suggest_stories("problem", store)
    assert len(matches) == 1


def test_suggest_stories_no_match(store):
    add_story(_make_story(competencies=["analytics"]), store)
    matches = suggest_stories("leadership", store)
    assert len(matches) == 0


def test_coverage_all_covered(store):
    s = _make_story(competencies=["leadership", "communication"])
    add_story(s, store)
    stories = list_stories(store)
    gaps = coverage(stories, ["leadership", "communication"])
    assert all(g.covered for g in gaps)


def test_coverage_gap_detected():
    stories = [_make_story(competencies=["leadership"])]
    gaps = coverage(stories, ["leadership", "negotiation"])
    gap_comps = {g.competency for g in gaps if not g.covered}
    assert "negotiation" in gap_comps


def test_coverage_returns_story_gap_objects():
    gaps = coverage([], ["foo"])
    assert all(isinstance(g, StoryGap) for g in gaps)


def test_coverage_empty_stories():
    gaps = coverage([], ["leadership", "communication"])
    assert all(not g.covered for g in gaps)


def test_file_written_utf8(store):
    s = _make_story(title="Épreuve difficile", situation="Situation avec accents éàü")
    add_story(s, store)
    raw = store.read_text(encoding="utf-8")
    assert "Épreuve" in raw


def test_stories_not_mutated_across_calls(store):
    s1 = _make_story(title="One")
    s2 = _make_story(title="Two")
    add_story(s1, store)
    add_story(s2, store)
    result = list_stories(store)
    assert {r.title for r in result} == {"One", "Two"}
