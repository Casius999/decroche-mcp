"""interview sub-package — FastMCP sub-server for interview preparation."""

from __future__ import annotations

from fastmcp import FastMCP

from decroche.interview.company_brief import company_brief as _company_brief
from decroche.interview.followup import debrief_template as _debrief_template
from decroche.interview.followup import thank_you as _thank_you
from decroche.interview.mock import mock_evaluate as _mock_evaluate
from decroche.interview.questions import question_bank as _question_bank
from decroche.interview.story_bank import add_story as _add_story
from decroche.interview.story_bank import suggest_stories as _suggest_stories
from decroche.models import (
    CompanyBrief,
    MockEval,
    Question,
    Story,
)

interview_server = FastMCP("interview")


@interview_server.tool
def company_brief(
    company: str,
    notes: str = "",
    jobs: list[dict] | None = None,
) -> CompanyBrief:
    """Build a structured research scaffold for interview preparation.

    PURE — no network, no LLM. Returns a CompanyBrief with [TO_RESEARCH]
    placeholders and a research checklist to fill before the interview.

    Args:
        company: Company name.
        notes:   Free-text notes the user has gathered (optional).
        jobs:    List of JobPosting-like dicts for role context (optional).

    Returns:
        CompanyBrief with 5 sections and a research checklist.
    """
    return _company_brief(company=company, notes=notes, jobs=jobs)


@interview_server.tool
def story_add(
    story: Story,
    store_path: str,
) -> Story:
    """Add a STAR+E story to the local JSON story bank.

    Validates STAR structure (situation, task, action, result must be
    non-empty). Raises ValueError if validation fails.

    Args:
        story:      The Story to persist.
        store_path: Absolute path to the JSON store file.

    Returns:
        The persisted Story.
    """
    return _add_story(story=story, path=store_path)


@interview_server.tool
def story_suggest(
    competency: str,
    store_path: str,
) -> list[Story]:
    """Return stories that cover a given competency (partial/case-insensitive match).

    Args:
        competency: The competency to look for.
        store_path: Absolute path to the JSON store file.

    Returns:
        List of matching Story objects.
    """
    return _suggest_stories(competency=competency, path=store_path)


@interview_server.tool
def question_bank(
    role_family: str,
    kind: str = "behavioral",
) -> list[Question]:
    """Return interview questions for a role family and kind.

    Args:
        role_family: One of ``software``, ``data``, ``product``, ``sales``,
                     ``generic`` (case-insensitive).
        kind:        ``"behavioral"``, ``"technical"``, or ``"case"``.
                     Defaults to ``"behavioral"``.

    Returns:
        List of Question objects from the bundled YAML bank.
    """
    return _question_bank(role_family=role_family, kind=kind)


@interview_server.tool
def mock_evaluate(answer_text: str) -> MockEval:
    """Evaluate a mock interview answer deterministically.

    Checks STAR structure, quantification, I/we ratio, duration (~130 wpm),
    and returns a scored MockEval with feedback.

    Args:
        answer_text: The candidate's free-text answer.

    Returns:
        MockEval with score, band, and feedback list.
    """
    return _mock_evaluate(answer_text=answer_text)


@interview_server.tool
def thank_you(
    interviewer: str,
    role: str,
    lang: str = "fr",
) -> str:
    """Generate a post-interview thank-you message scaffold.

    Args:
        interviewer: Interviewer's first name or full name.
        role:        Job title / role name.
        lang:        ``"fr"`` (default) or ``"en"``.

    Returns:
        Locale-appropriate message scaffold with [PLACEHOLDERS].
    """
    return _thank_you(interviewer=interviewer, role=role, lang=lang)


@interview_server.tool
def debrief(role: str, lang: str = "fr") -> str:
    """Generate a post-interview debrief Markdown template.

    Args:
        role: Job title / role name.
        lang: ``"fr"`` (default) or ``"en"``.

    Returns:
        Markdown debrief template.
    """
    return _debrief_template(role=role, lang=lang)
