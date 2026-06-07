"""interview.story_bank — Local JSON store for STAR+E stories.

Stories are persisted in a UTF-8 JSON file.  All mutating operations return
the updated story or list — no in-place mutation of caller data.

STAR+E validation: situation, task, action, result must be non-empty.
Effect is optional.  Competencies list should be non-empty for coverage.
"""

from __future__ import annotations

import json
from pathlib import Path

from decroche.models import Story, StoryGap

_ENCODING = "utf-8"


# ── private helpers ───────────────────────────────────────────────────────────────────────────


def _load(path: str | Path) -> list[Story]:
    p = Path(path)
    if not p.exists():
        return []
    raw = json.loads(p.read_text(encoding=_ENCODING))
    return [Story(**item) for item in raw]


def _save(stories: list[Story], path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    data = [s.model_dump() for s in stories]
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding=_ENCODING)


def _validate_star(story: Story) -> list[str]:
    """Return a list of validation errors (empty = valid)."""
    errors: list[str] = []
    if not story.situation.strip():
        errors.append("situation is required")
    if not story.task.strip():
        errors.append("task is required")
    if not story.action.strip():
        errors.append("action is required")
    if not story.result.strip():
        errors.append("result is required")
    return errors


# ── public API ──────────────────────────────────────────────────────────────────────────────


def add_story(story: Story, path: str | Path) -> Story:
    """Persist a STAR+E story to the local JSON bank.

    Validates STAR structure; raises ``ValueError`` if invalid.

    Args:
        story: The Story to add.
        path:  Path to the JSON store file.

    Returns:
        The persisted Story.

    Raises:
        ValueError: if any required STAR field is empty.
    """
    errors = _validate_star(story)
    if errors:
        raise ValueError(f"Story STAR validation failed: {'; '.join(errors)}")

    stories = _load(path)
    stories.append(story)
    _save(stories, path)
    return story


def list_stories(path: str | Path) -> list[Story]:
    """Return all stories in the local JSON bank.

    Args:
        path: Path to the JSON store file.

    Returns:
        List of Story objects (empty list if file not found).
    """
    return _load(path)


def suggest_stories(competency: str, path: str | Path) -> list[Story]:
    """Return stories that cover a given competency.

    Matching is case-insensitive and partial (substring).

    Args:
        competency: The competency to look for.
        path:       Path to the JSON store file.

    Returns:
        List of matching Story objects.
    """
    key = competency.lower().strip()
    return [s for s in _load(path) if any(key in c.lower() for c in s.competencies)]


def coverage(stories: list[Story], target_competencies: list[str]) -> list[StoryGap]:
    """Check which target competencies are covered by the story bank.

    Args:
        stories:              List of Story objects (from ``list_stories``).
        target_competencies:  Competencies to check coverage for.

    Returns:
        List of StoryGap, one per target competency.
    """
    covered_set: set[str] = set()
    for s in stories:
        for c in s.competencies:
            covered_set.add(c.lower().strip())

    gaps: list[StoryGap] = []
    for comp in target_competencies:
        key = comp.lower().strip()
        # Partial match: check if any covered competency contains the key
        is_covered = any(key in c or c in key for c in covered_set)
        gaps.append(StoryGap(competency=comp, covered=is_covered))
    return gaps
