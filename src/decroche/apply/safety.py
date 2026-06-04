"""apply.safety — Pure, stateless safety predicates for browser automation.

These predicates are the SAFETY CORE for Phase 4b.  They have zero side
effects, require no I/O, and are exhaustively unit-tested.

Hard safety rules enforced here (non-negotiable, cannot be bypassed):

Rule 1 — classify_sensitive_field():
    Returns True for any field name / label that looks like a password,
    card number, CVC/CVV, IBAN, SSN, OTP, 2FA, or other credential.
    Called BEFORE any Playwright fill().  A True result → immediate refusal.

Rule 2 — is_payment_url():
    Returns True when a URL contains a payment/checkout keyword.
    Called before navigating or submitting on any page.
    A True result → STOP, never proceed.

Rule 3 — is_login_context():
    Returns True when the page looks like a login wall.
    Called before submitting a form.
    A True result → return "needs_manual_login" to the caller.

Rule 4/5 — should_block_step():
    Combines Rules 1-3 into a single (blocked: bool, reason: str | None)
    tuple consumed by act() and send_approved().
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Rule 1 — sensitive field detection
# ---------------------------------------------------------------------------

# Matches field name / label text that must never be auto-filled.
# FR + EN, intentionally broad: refusing a safe field is benign;
# typing into a credential/card field is a hard violation.
_SENSITIVE_FIELD_RE = re.compile(
    r"password|mot.?de.?passe|\bpass\b|\bpwd\b"
    r"|card|carte|\bcb\b|card.?number|num[eé]ro.*carte"
    r"|\bcvc\b|\bcvv\b|\bcvx\b|\bcsc\b"
    r"|iban|\brib\b"
    r"|ssn|social.?security|num[eé]ro.*s[eé]curit[eé]|num[eé]ro.?s[eé]cu|n[oO].*s[eé]cu"
    r"|secu\b|s[eé]curit[eé].?sociale"
    r"|\botp\b|one.?time.?pass"
    r"|2fa|two.?factor|auth.?code|verification.?code"
    r"|crypto|seed.?phrase|mnemonic",
    re.IGNORECASE,
)


def classify_sensitive_field(name: str, label: str = "") -> bool:
    """Return True if the field must NEVER be auto-filled.

    Checks the field ``name`` attribute and an optional human-readable
    ``label`` string against a broad FR+EN regex that covers passwords,
    card numbers, CVC/CVV, IBAN, SSN/numéro sécu, OTP, 2FA, and crypto
    seed phrases.

    This predicate is the first gate called by act() before any fill()
    attempt.  A True result → immediate refusal, no browser interaction.

    Args:
        name:  HTML field name or id attribute (lowercased by caller or not —
               the regex is case-insensitive).
        label: Human-readable label text or placeholder (optional).

    Returns:
        True  → field is sensitive, MUST be refused.
        False → field appears safe to fill.
    """
    haystack = " ".join(filter(None, [name, label]))
    return bool(_SENSITIVE_FIELD_RE.search(haystack))


# ---------------------------------------------------------------------------
# Rule 2 — payment / checkout URL detection
# ---------------------------------------------------------------------------

_PAYMENT_URL_RE = re.compile(
    r"payment|paiement|checkout|stripe\.com|adyen\.com|paypal\.com"
    r"|billing|/pay(?:[/?#]|$)",
    re.IGNORECASE,
)


def is_payment_url(url: str) -> bool:
    """Return True when *url* points to a payment or checkout page.

    Called before any navigation or form submission.  A True result means
    the browser step is STOPPED — we never proceed past a payment page.

    Args:
        url: The full URL to inspect.

    Returns:
        True  → payment/checkout context, STOP.
        False → URL does not match a payment pattern.
    """
    return bool(_PAYMENT_URL_RE.search(url))


# ---------------------------------------------------------------------------
# Rule 3 — login wall detection
# ---------------------------------------------------------------------------

_LOGIN_FIELD_RE = re.compile(
    r"password|mot.?de.?passe|\bpwd\b",
    re.IGNORECASE,
)

_LOGIN_URL_RE = re.compile(
    r"login|signin|sign.in|connexion|/auth(?:[/?#]|$)",
    re.IGNORECASE,
)


def is_login_context(
    field_names: list[str] | None = None,
    url: str = "",
) -> bool:
    """Return True when the page looks like a login wall.

    A login context is detected when EITHER:
    - The URL matches a login/signin/connexion pattern, OR
    - One of the visible field names is a password field (implies login form).

    The caller (send_approved) checks this before submitting; a True result
    means the item is added to ``stopped`` with reason "needs_manual_login".

    Args:
        field_names: List of HTML field names / ids from the form (optional).
        url:         Current page URL (optional).

    Returns:
        True  → login wall detected.
        False → no login context detected.
    """
    if url and _LOGIN_URL_RE.search(url):
        return True
    if field_names:
        for fname in field_names:
            if _LOGIN_FIELD_RE.search(fname):
                return True
    return False


# ---------------------------------------------------------------------------
# Combined gate — should_block_step()
# ---------------------------------------------------------------------------


def should_block_step(
    intent: str,
    target_field: str = "",
    url: str = "",
) -> tuple[bool, str | None]:
    """Decide whether a browser step must be blocked.

    Combines Rules 1-3:
    - If *url* is a payment URL → block.
    - If *url* is a login URL → block.
    - If *target_field* is sensitive → block.

    The *intent* string is included in the reason for audit purposes.

    Args:
        intent:       Human-readable description of what we intend to do.
        target_field: The field name / id we intend to fill (empty for
                      navigate/click steps).
        url:          The current or target URL.

    Returns:
        ``(False, None)`` when safe to proceed.
        ``(True, reason_string)`` when the step must be refused.
    """
    if url and is_payment_url(url):
        return True, f"STOP: payment/checkout URL detected ({url!r}) — intent={intent!r}"

    if url and is_login_context(url=url):
        return True, f"STOP: login page detected ({url!r}) — needs_manual_login"

    if target_field and classify_sensitive_field(target_field):
        return (
            True,
            f"REFUSED: sensitive field {target_field!r} must not be auto-filled — intent={intent!r}",
        )

    return False, None
