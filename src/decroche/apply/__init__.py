"""apply sub-package — FastMCP sub-server for application orchestration.

Tools (mounted under namespace "apply" in the main server):

Phase 4a:
- resolve_source : resolve the employer ATS URL (apply-at-source principle)
- prefill        : build a pre-fill plan from resume (NEVER fills sensitive fields)
- queue_add      : add a job to the batch-apply queue
- queue_review   : list all queued items
- queue_approve  : approve a batch of items (prepared → approved)
- followup       : draft a polite follow-up message scaffold

Phase 4b (browser automation — safety-critical, gated):
- act            : preview or perform ONE browser step (confirm=False → preview only)
- send_approved  : submit approved queue items via the user's own Chrome
                   (confirm_send=False → dry-run; confirm_send=True → submit)

Browser tools require the optional [browser] extra and a running debug Chrome
(CHROME_CDP_URL env var, default http://localhost:9222). They raise ToolError
with a clear message when playwright is not installed.
"""

from __future__ import annotations
from typing import Any

from fastmcp import FastMCP

from decroche.apply.browser import act as _act
from decroche.apply.browser import send_approved as _send_approved
from decroche.apply.cover_letter import cover_letter as _cover_letter
from decroche.apply.followup import draft_followup as _draft_followup
from decroche.apply.prefill import prefill as _prefill
from decroche.apply.queue import queue_add as _queue_add
from decroche.apply.queue import queue_approve as _queue_approve
from decroche.apply.queue import queue_review as _queue_review
from decroche.apply.resolve import resolve_source as _resolve_source
from decroche.apply.screening import answer_screening as _answer_screening
from decroche.cv.parse import parse_cv
from decroche.models import (
    ActPreview,
    Application,
    CoverLetter,
    JobPosting,
    JSONResume,
    PrefillPlan,
    QueueItem,
    ScreeningAnswer,
    SendResult,
)

apply_server = FastMCP("apply")


@apply_server.tool
def resolve_source(job: JobPosting) -> dict:
    """Resolve the best apply URL and channel for a job posting.

    Implements the apply-at-source principle: candidates apply at the employer's
    own ATS, never via LinkedIn/Indeed/Glassdoor aggregator pages.

    No network calls are made.

    Args:
        job: A normalised JobPosting.

    Returns:
        Dict with apply_url, channel, manual (bool), note.
    """
    return _resolve_source(job)


@apply_server.tool
def prefill(
    job: JobPosting,
    json_resume: JSONResume,
    cover_letter: str | None = None,
) -> PrefillPlan:
    """Build a PrefillPlan by mapping resume data to common ATS form fields.

    Sensitive fields (password, card, SSN, IBAN, DOB) are NEVER in ``fields``.
    They are listed in ``excluded_sensitive`` for auditability.

    Args:
        job:          Target JobPosting.
        json_resume:  Candidate's JSON Resume.
        cover_letter: Optional cover letter text.

    Returns:
        PrefillPlan with mapped fields, unmapped fields, excluded_sensitive list.
    """
    return _prefill(job, json_resume, cover_letter=cover_letter)


@apply_server.tool
def queue_add(item: QueueItem, path: str) -> None:
    """Add or replace a QueueItem in the batch-apply queue.

    If an item with the same job_id already exists it is replaced.

    Args:
        item: The QueueItem to add.
        path: Absolute path to the JSON queue file.
    """
    _queue_add(item, path)


@apply_server.tool
def queue_review(path: str) -> list[QueueItem]:
    """Return all items in the batch-apply queue.

    Args:
        path: Absolute path to the JSON queue file.

    Returns:
        List of QueueItem objects.
    """
    return _queue_review(path)


@apply_server.tool
def queue_approve(job_ids: list[str], path: str) -> int:
    """Approve a batch of queue items (prepared → approved).

    Args:
        job_ids: List of job_id strings to approve.
        path:    Absolute path to the JSON queue file.

    Returns:
        Number of items actually changed.
    """
    return _queue_approve(job_ids, path)


@apply_server.tool
def followup(app: Application, lang: str = "fr") -> str:
    """Draft a polite follow-up message scaffold for an application.

    Sending is always human-confirmed (Phase 4b). No network calls.

    Args:
        app:  The Application being followed up.
        lang: Language — ``"fr"`` (default) or ``"en"``.

    Returns:
        Formatted follow-up message string.
    """
    return _draft_followup(app, lang=lang)


# ── Phase 4b — browser tools (gated, safety-critical) ────────────────────────


@apply_server.tool
async def act(
    intent: str,
    params: dict[str, Any],
    confirm: bool = False,
) -> ActPreview:
    """Preview or perform ONE browser step on an employer ATS form.

    SAFETY RULES enforced in code (non-negotiable):
    - classify_sensitive_field() is called BEFORE any fill().
    - is_payment_url() blocks the step if the URL is a payment page.
    - is_login_context() blocks the step if a login wall is detected.
    - confirm=False (default) returns a preview with requires_confirm=True.
      Only confirm=True actually performs the step.
    - NEVER auto-fills passwords, card numbers, CVC/CVV, IBAN, SSN, 2FA.

    apply-at-source: use only on employer ATS pages, never on LinkedIn/Indeed.

    Args:
        intent:  "navigate" | "click" | "fill"
        params:  Step params dict:
                 navigate → {url: str}
                 click    → {selector: str} or {role: str, name: str}
                 fill     → {field: str, value: str, label: str=""}
        confirm: False → preview only; True → perform (playwright required).

    Returns:
        ActPreview — blocked=True if refused, requires_confirm=True if preview.
    """
    return await _act(intent, params, confirm=confirm)


# ── Apply-breadth tools — cover letter + screening answers ───────────────────


@apply_server.tool
def cover_letter(
    cv_path: str,
    job_json: dict,
    lang: str = "fr",
) -> CoverLetter:
    """Build an honest cover-letter scaffold from a CV file and a job posting.

    HONESTY: ``why_me`` bullets come ONLY from the candidate's real CV.
    ``why_them`` is a clearly-marked [à compléter: …] placeholder — the host
    LLM fills it using actual company research.  Nothing is invented.

    No network calls.  Deterministic.

    Args:
        cv_path:  Absolute path to a CV file (.txt, .md, .docx, .pdf).
        job_json: Job posting as a dict (must include at minimum: source,
                  source_id, title, url, description).
        lang:     ``"fr"`` (default) or ``"en"``.

    Returns:
        CoverLetter with hook, why_them placeholder, why_me real bullets,
        close, full_scaffold, evidence_used, and notes.
    """
    cv_parse = parse_cv(cv_path)
    job = JobPosting(**job_json)
    return _cover_letter(job, cv_parse.json_resume, lang=lang)


@apply_server.tool
def answer_screening(
    question: str,
    cv_path: str,
) -> ScreeningAnswer:
    """Answer a screening question factually from the CV, or flag needs_human.

    HONESTY rules (non-negotiable):
    - Work authorization / visa / sponsorship → needs_human=True, answer=None.
    - Salary expectations → needs_human=True, answer=None.
    - Relocation / notice / availability / start date → needs_human=True.
    - "Why this company/role" → needs_human=True.
    - Unknown questions → needs_human=True.
    Only factual, derivable answers are returned with source="derived_from_cv".

    No network calls.  Deterministic.

    Args:
        question: The screening question text (EN or FR).
        cv_path:  Absolute path to a CV file (.txt, .md, .docx, .pdf).

    Returns:
        ScreeningAnswer with suggested_answer (or None), source, confidence,
        and needs_human flag.
    """
    cv_parse = parse_cv(cv_path)
    return _answer_screening(question, cv_parse.json_resume)


@apply_server.tool
async def send_approved(
    queue_path: str,
    confirm_send: bool = False,
) -> SendResult:
    """Submit ATS applications for approved queue items via the user's own Chrome.

    SAFETY RULES enforced in code (non-negotiable):
    - ONLY items with status=="approved" are attempted (queue_approve first).
    - is_payment_url() → item stopped, never submitted.
    - is_login_context() → item stopped as "needs_manual_login".
    - classify_sensitive_field() on any prefill field → item skipped.
    - confirm_send=False (default) → dry-run, nothing submitted.
      Only confirm_send=True actually submits.

    Args:
        queue_path:   Absolute path to the JSON queue file.
        confirm_send: False → dry-run; True → submit approved items (playwright required).

    Returns:
        SendResult with attempted/submitted/skipped/stopped and dry_run flag.
    """
    return await _send_approved(queue_path, confirm_send=confirm_send)
