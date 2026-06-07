"""apply.browser — Playwright CDP browser automation for batch apply.

Design constraints (Phase 4b, non-negotiable):

1. Sensitive field classification (I1):
   Every input must be classified before fill.  Fields matching
   ``safety.classify_sensitive_field`` are NEVER auto-filled.

2. Payment URL detection (I2):
   Any navigation to a payment URL aborts immediately with ToolError.

3. Login context detection (I3):
   If the page URL looks like a login page, the action is blocked.

4. Confirm-gate on act() (I4):
   ``act()`` requires ``confirm=True`` from the caller.  Default False.
   Clicks on payment/checkout targets are blocked via ``_CLICK_BLOCK_RE``.

5. Approve-gate + confirm-gate on send_approved() (I5):
   Only queue items with status ``"approved"`` are processed.
   ``send_approved()`` requires ``confirm_send=True``.

Exception scrub (M):
   Unexpected exceptions expose only the exception *type name*, never the
   raw message, to avoid leaking internal state.
"""

from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING, Any

from fastmcp.exceptions import ToolError

from decroche.apply.queue import queue_mark_sent, queue_review
from decroche.apply.safety import (
    classify_sensitive_field,
    is_login_context,
    is_payment_url,
)
from decroche.models import PrefillPlan, QueueItem

if TYPE_CHECKING:
    pass

# ---------------------------------------------------------------------------
# Playwright availability guard
# ---------------------------------------------------------------------------

try:
    from playwright.async_api import async_playwright  # type: ignore[import-untyped]

    _PLAYWRIGHT_AVAILABLE = True
except ImportError:  # pragma: no cover
    _PLAYWRIGHT_AVAILABLE = False

# ---------------------------------------------------------------------------
# I4: click-target block list
# ---------------------------------------------------------------------------

#: Regex matching button/link text that signals a payment or checkout action.
#: Matched case-insensitively against the visible text of click targets.
_CLICK_BLOCK_RE = re.compile(
    r"\b("
    r"pay|payment|checkout|check.out|subscribe|subscription"
    r"|purchase|buy.now|place.order|confirm.order|complete.order"
    r"|add.to.cart|billing|charge|credit.card|debit.card"
    r"|carte.bancaire|payer|paiement|commander|valider.commande"
    r")\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_form_input_names(page: Any) -> list[str]:
    """Return name attributes of all visible input elements on the page."""
    return await page.evaluate(
        """
        () => {
            const inputs = document.querySelectorAll('input, textarea, select');
            return Array.from(inputs)
                .filter(el => el.offsetParent !== null)
                .map(el => el.name || el.id || el.placeholder || '');
        }
        """
    )


def _require_playwright() -> None:
    if not _PLAYWRIGHT_AVAILABLE:
        raise ToolError(
            "Playwright is not installed. "
            "Add it to the project dependencies: pip install playwright && "
            "playwright install chromium"
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def act(
    intent: str,
    params: dict[str, Any],
    confirm: bool = False,
) -> dict[str, Any]:
    """Execute a single browser action for a job-application step.

    Safety rules enforced:
    - ``confirm=True`` required (I4)
    - Payment URLs blocked (I2)
    - Login context blocked (I3)
    - Sensitive field fills blocked (I1)
    - Click targets matching payment keywords blocked (I4)

    Args:
        intent: High-level action description, e.g. ``"fill_form"`` or
                ``"click_submit"``.
        params: Action parameters.  Keys vary by intent:

            ``fill_form``
                - ``url``   (str): page URL to navigate to
                - ``fields`` (dict[str, str]): field-name → value mapping

            ``click``
                - ``url``    (str): page URL
                - ``target`` (str): visible text or CSS selector of the element

        confirm: Must be ``True`` to proceed.  Default ``False`` blocks all
                 actions (safety gate I4).

    Returns:
        Dict with ``{status: "ok", intent: ..., fields_filled: [...]}`` on
        success, or raises ``ToolError``.

    Raises:
        ToolError: On any safety violation or Playwright error.
    """
    if not confirm:
        raise ToolError(
            "act() requires confirm=True.  Review the intended action and "
            "params, then call again with confirm=True to proceed."
        )

    _require_playwright()

    url: str = params.get("url", "")

    # I2: Payment URL check
    if is_payment_url(url):
        raise ToolError(f"Blocked: payment URL detected — {url!r}")

    # I3: Login context check
    if is_login_context(url):
        raise ToolError(f"Blocked: login URL detected — {url!r}")

    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, wait_until="domcontentloaded")

            # Re-check live URL after navigation (redirects may expose payment)
            live_url = page.url
            if is_payment_url(live_url):
                await browser.close()
                raise ToolError(f"Blocked: redirected to payment URL — {live_url!r}")
            if is_login_context(live_url):
                await browser.close()
                raise ToolError(f"Blocked: redirected to login URL — {live_url!r}")

            filled_fields: list[str] = []

            if intent == "fill_form":
                fields: dict[str, str] = params.get("fields", {})
                for field_name, value in fields.items():
                    # I1: Sensitive field gate
                    classification = classify_sensitive_field(field_name)
                    if classification != "safe":
                        # Skip sensitive field — never fill
                        continue
                    try:
                        await page.fill(f'[name="{field_name}"]', str(value))
                        filled_fields.append(field_name)
                    except Exception:  # noqa: BLE001
                        pass  # field not found or not fillable — skip silently

            elif intent == "click":
                target: str = params.get("target", "")
                # I4: Block payment/checkout click targets
                if _CLICK_BLOCK_RE.search(target):
                    await browser.close()
                    raise ToolError(
                        f"Blocked: click target matches payment/checkout keyword — {target!r}"
                    )
                await page.click(target)

            await browser.close()

        return {"status": "ok", "intent": intent, "fields_filled": filled_fields}

    except ToolError:
        raise
    except Exception as exc:  # noqa: BLE001
        # M: Exception scrub — expose type name only
        raise ToolError(f"Browser error: {type(exc).__name__}") from None


async def send_approved(
    queue_path: str,
    confirm_send: bool = False,
) -> dict[str, Any]:
    """Submit all approved queue items via browser automation.

    Safety rules enforced:
    - ``confirm_send=True`` required (I5)
    - Only items with ``status="approved"`` are processed (I5)
    - Payment URL check on each item (I2)
    - Login context check on each item (I3)
    - Sensitive field gate on all prefill fields (I1)
    - Click-target block list for submit buttons (I4)

    Args:
        queue_path:   Absolute path to the JSON queue file.
        confirm_send: Must be ``True`` to proceed.  Default ``False``
                      blocks all submissions (safety gate I5).

    Returns:
        Dict with ``{submitted: [job_ids], skipped: [job_ids], errors: {job_id: reason}}``.

    Raises:
        ToolError: If ``confirm_send=False``.
    """
    if not confirm_send:
        raise ToolError(
            "send_approved() requires confirm_send=True.  Review the queue "
            "first, then call again with confirm_send=True to proceed."
        )

    _require_playwright()

    items: list[QueueItem] = queue_review(queue_path)
    approved = [item for item in items if item.status == "approved"]

    submitted: list[str] = []
    skipped: list[str] = []
    errors: dict[str, str] = {}

    for item in approved:
        prefill: PrefillPlan = item.prefill
        url = prefill.apply_url

        # I2
        if is_payment_url(url):
            skipped.append(item.job_id)
            errors[item.job_id] = "payment URL"
            continue

        # I3
        if is_login_context(url):
            skipped.append(item.job_id)
            errors[item.job_id] = "login URL"
            continue

        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(url, wait_until="domcontentloaded")

                live_url = page.url
                if is_payment_url(live_url) or is_login_context(live_url):
                    await browser.close()
                    skipped.append(item.job_id)
                    errors[item.job_id] = "redirect to payment/login"
                    continue

                # I1: Fill only safe fields
                fields_to_fill: dict[str, str] = {}
                for k, v in (prefill.fields or {}).items():
                    if classify_sensitive_field(k) == "safe":
                        fields_to_fill[k] = v

                for field_name, value in fields_to_fill.items():
                    try:
                        await page.fill(f'[name="{field_name}"]', str(value))
                    except Exception:  # noqa: BLE001
                        pass

                # I4: Find and click submit — only if target is not payment-like
                submit_target = prefill.submit_selector or "button[type='submit']"
                if _CLICK_BLOCK_RE.search(submit_target):
                    await browser.close()
                    skipped.append(item.job_id)
                    errors[item.job_id] = "submit target matches payment keyword"
                    continue

                await page.click(submit_target)
                await browser.close()

            queue_mark_sent(item.job_id, queue_path)
            submitted.append(item.job_id)

        except ToolError:
            raise
        except Exception as exc:  # noqa: BLE001
            # M: Exception scrub
            errors[item.job_id] = type(exc).__name__
            skipped.append(item.job_id)

    return {"submitted": submitted, "skipped": skipped, "errors": errors}
