"""apply.browser — Gated Playwright CDP browser layer for ATS form automation.

SAFETY-CRITICAL module.  Hard rules — non-negotiable, enforced in code:

Rule 1  classify_sensitive_field() is called BEFORE any fill().
        A sensitive field → ActPreview(blocked=True) or stopped entry.
        NEVER auto-fill passwords, card numbers, CVC/CVV, IBAN, SSN, 2FA.

Rule 2  is_payment_url() is checked before navigating AND before submit.
        Payment/checkout page → STOP, item added to SendResult.stopped.
        NEVER proceed past a payment page.

Rule 3  is_login_context() is checked before submit.
        Login wall → item added to SendResult.stopped with "needs_manual_login".
        NEVER attempt login; user logs in themselves.

Rule 4  act() is confirm-gated:
        confirm=False → returns ActPreview (preview, no browser action).
        confirm=True  → performs exactly ONE step.

Rule 5  send_approved() is confirm-gated AND status-gated:
        confirm_send=False → dry-run, SendResult.dry_run=True, submitted=0.
        confirm_send=True  → submits ONLY items with status=="approved".
        NEVER submits non-approved items. NEVER unsupervised bulk submit.

Playwright is an OPTIONAL dependency.  Every entry point raises a clear
ToolError when playwright is not installed, so the core package (and all CI
tests) work without it.

CDP endpoint: env var CHROME_CDP_URL (default http://localhost:9222).
The user opens their own Chrome with --remote-debugging-port=9222, logs in
themselves, and we attach — we never see the user's password.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastmcp.exceptions import ToolError

from decroche.apply.queue import queue_mark_sent
from decroche.apply.safety import (
    classify_sensitive_field,
    is_login_context,
    is_payment_url,
    should_block_step,
)
from decroche.models import ActPreview, SendResult

# ---------------------------------------------------------------------------
# Optional Playwright import — guarded so core tests pass without it.
# ---------------------------------------------------------------------------

try:
    from playwright.async_api import async_playwright as _async_playwright  # type: ignore[import-untyped]

    _PLAYWRIGHT_AVAILABLE = True
except ImportError:
    _async_playwright = None  # type: ignore[assignment]
    _PLAYWRIGHT_AVAILABLE = False

_PLAYWRIGHT_MISSING_MSG = (
    "playwright not installed — run: "
    "pip install 'decroche-mcp[browser]' && playwright install chromium"
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_DEFAULT_CDP_URL = "http://localhost:9222"


def _cdp_url() -> str:
    return os.environ.get("CHROME_CDP_URL", _DEFAULT_CDP_URL).strip()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _require_playwright() -> None:
    """Raise ToolError if playwright is not installed."""
    if not _PLAYWRIGHT_AVAILABLE:
        raise ToolError(_PLAYWRIGHT_MISSING_MSG)


def _load_queue(queue_path: str) -> dict[str, dict]:
    """Load the queue JSON file; return empty dict if absent."""
    p = Path(queue_path)
    if not p.exists():
        return {}
    with p.open(encoding="utf-8") as fh:
        data = json.load(fh)
    return data if isinstance(data, dict) else {}


# ---------------------------------------------------------------------------
# Public API — act()
# ---------------------------------------------------------------------------


async def act(
    intent: str,
    params: dict[str, Any],
    confirm: bool = False,
) -> ActPreview:
    """Perform (or preview) a single browser step, gated by safety predicates.

    Safety checks run BEFORE any Playwright interaction:
    - Payment URL → blocked.
    - Login page → blocked.
    - Sensitive target field → blocked.

    Args:
        intent:  Human-readable description: "navigate", "click", "fill".
        params:  Step-specific params dict.
                 navigate → {url: str}
                 click    → {selector: str} or {role: str, name: str}
                 fill     → {field: str, value: str, label: str=""}
        confirm: False (default) → preview only, no browser action.
                 True            → perform exactly ONE step (if not blocked).

    Returns:
        ActPreview with blocked/block_reason set when refused.
        requires_confirm=True when confirm=False and step is not blocked.
    """
    url = params.get("url", "")
    target_field = params.get("field", "")
    label = params.get("label", "")

    # ── Pre-browser safety gate (Rules 1-3) ────────────────────────────────
    blocked, reason = should_block_step(intent=intent, target_field=target_field, url=url)

    # Additional sensitive-field check using label too (Rule 1 extended).
    if not blocked and target_field and classify_sensitive_field(target_field, label):
        blocked = True
        reason = (
            f"REFUSED: sensitive field {target_field!r} (label={label!r}) must not be auto-filled"
        )

    if blocked:
        return ActPreview(
            intent=intent,
            target=target_field or url or None,
            would_do=f"{intent} — BLOCKED",
            blocked=True,
            block_reason=reason,
            requires_confirm=False,
        )

    # ── Preview mode (no browser) ───────────────────────────────────────────
    if not confirm:
        return ActPreview(
            intent=intent,
            target=target_field or url or None,
            would_do=_describe_step(intent, params),
            blocked=False,
            block_reason=None,
            requires_confirm=True,
        )

    # ── Perform the step (Playwright required) ──────────────────────────────
    _require_playwright()
    return await _perform_act(intent, params)


def _describe_step(intent: str, params: dict[str, Any]) -> str:
    """Build a human-readable description of what the step would do."""
    if intent == "navigate":
        return f"navigate to {params.get('url', '?')!r}"
    if intent == "click":
        sel = params.get("selector") or f"role={params.get('role')} name={params.get('name')}"
        return f"click {sel!r}"
    if intent == "fill":
        return f"fill field {params.get('field', '?')!r} with a non-sensitive value"
    return f"{intent} with params {params}"


async def _perform_act(intent: str, params: dict[str, Any]) -> ActPreview:
    """Execute ONE browser step via Playwright CDP. Called only after safety gate."""
    async with _async_playwright() as pw:
        browser = await pw.chromium.connect_over_cdp(_cdp_url())
        try:
            contexts = browser.contexts
            if not contexts:
                raise ToolError(
                    "Connected to Chrome but no browser context found. "
                    "Open a tab in your debug Chrome window and retry."
                )
            context = contexts[0]
            pages = context.pages
            page = pages[0] if pages else await context.new_page()

            if intent == "navigate":
                target_url = params["url"]
                await page.goto(target_url, wait_until="domcontentloaded")
                return ActPreview(
                    intent=intent,
                    target=target_url,
                    would_do=f"navigated to {target_url!r}",
                    blocked=False,
                    requires_confirm=False,
                )

            if intent == "click":
                if "selector" in params:
                    await page.locator(params["selector"]).first.click()
                    target = params["selector"]
                else:
                    role = params.get("role", "button")
                    name = params.get("name", "")
                    await page.get_by_role(role, name=name).first.click()
                    target = f"role={role} name={name!r}"
                return ActPreview(
                    intent=intent,
                    target=target,
                    would_do=f"clicked {target!r}",
                    blocked=False,
                    requires_confirm=False,
                )

            if intent == "fill":
                field = params.get("field", "")
                value = params.get("value", "")
                label = params.get("label", "")
                # Double-check sensitive (should already be blocked above, but
                # we enforce again here as a defence-in-depth measure).
                if classify_sensitive_field(field, label):
                    raise ToolError(
                        f"REFUSED: fill into sensitive field {field!r} blocked at execute time"
                    )
                locator = page.locator(f'[name="{field}"]')
                if await locator.count() == 0:
                    locator = page.get_by_label(label or field)
                await locator.first.fill(value)
                return ActPreview(
                    intent=intent,
                    target=field,
                    would_do=f"filled field {field!r}",
                    blocked=False,
                    requires_confirm=False,
                )

            raise ToolError(f"Unknown intent {intent!r}. Supported: navigate, click, fill.")

        finally:
            await browser.close()


# ---------------------------------------------------------------------------
# Public API — send_approved()
# ---------------------------------------------------------------------------


async def send_approved(
    queue_path: str,
    confirm_send: bool = False,
) -> SendResult:
    """Submit ATS applications for items in the queue with status=="approved".

    Safety gates (all checked before any submit):
    - Only items with status=="approved" are attempted.
    - is_payment_url() on apply_url → stopped (never submitted).
    - is_login_context() on apply_url → stopped (needs_manual_login).
    - classify_sensitive_field() on any prefill field → skipped field (not submitted).
    - confirm_send=False → dry-run, nothing submitted (SendResult.dry_run=True).

    Args:
        queue_path:   Absolute path to the JSON queue file.
        confirm_send: False (default) → dry-run plan only.
                      True           → actually submit (Playwright required).

    Returns:
        SendResult with attempted/submitted/skipped/stopped counts + dry_run flag.
    """
    store = _load_queue(queue_path)
    approved = [v for v in store.values() if v.get("status") == "approved"]

    skipped: list[dict] = []
    stopped: list[dict] = []
    submitted_count = 0

    for item in approved:
        job_id = item.get("job_id", "?")
        apply_url = item.get("apply_url", "")

        # Rule 2 — payment URL check
        if apply_url and is_payment_url(apply_url):
            stopped.append(
                {
                    "job_id": job_id,
                    "reason": f"STOP: payment URL detected — {apply_url!r}",
                }
            )
            continue

        # Rule 3 — login context check (URL-based heuristic)
        if apply_url and is_login_context(url=apply_url):
            stopped.append(
                {
                    "job_id": job_id,
                    "reason": "needs_manual_login",
                }
            )
            continue

        # Rule 1 — check all prefill fields for sensitive content
        prefill_data = item.get("prefill", {})
        fields: dict = prefill_data.get("fields", {}) if isinstance(prefill_data, dict) else {}
        sensitive_fields = [f for f in fields if classify_sensitive_field(f)]
        if sensitive_fields:
            skipped.append(
                {
                    "job_id": job_id,
                    "reason": f"sensitive fields in prefill: {sensitive_fields}",
                }
            )
            continue

        # Rule 4/5 — dry-run gate
        if not confirm_send:
            # Dry run: count as attempted but not submitted
            continue

        # ── Perform the actual submission (Playwright required) ─────────────
        _require_playwright()
        try:
            await _submit_item(item, fields, apply_url)
            queue_mark_sent(job_id, queue_path)
            submitted_count += 1
        except ToolError as exc:
            stopped.append({"job_id": job_id, "reason": str(exc)})
        except Exception as exc:  # noqa: BLE001
            stopped.append({"job_id": job_id, "reason": f"unexpected error: {exc}"})

    return SendResult(
        attempted=len(approved),
        submitted=submitted_count,
        skipped=skipped,
        stopped=stopped,
        dry_run=not confirm_send,
    )


async def _submit_item(
    item: dict,
    fields: dict[str, str],
    apply_url: str,
) -> None:
    """Open apply_url, fill non-sensitive fields, click submit. Playwright required."""
    async with _async_playwright() as pw:
        browser = await pw.chromium.connect_over_cdp(_cdp_url())
        try:
            contexts = browser.contexts
            if not contexts:
                raise ToolError("No browser context available.")
            context = contexts[0]
            page = await context.new_page()
            await page.goto(apply_url, wait_until="domcontentloaded")

            # Re-check payment/login after navigation (URL may redirect)
            current_url = page.url
            if is_payment_url(current_url):
                raise ToolError(f"STOP: redirected to payment URL — {current_url!r}")
            if is_login_context(url=current_url):
                raise ToolError("needs_manual_login after navigation")

            # Fill non-sensitive fields
            for field_name, value in fields.items():
                if classify_sensitive_field(field_name):
                    continue  # Already guarded above but double-check
                locator = page.locator(f'[name="{field_name}"]')
                if await locator.count() > 0:
                    await locator.first.fill(value)

            # Click submit
            submit = page.get_by_role("button", name="submit")
            if await submit.count() == 0:
                submit = page.locator('[type="submit"]')
            if await submit.count() > 0:
                await submit.first.click()

        finally:
            await browser.close()
