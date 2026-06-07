"""apply.safety — Phase 4b browser-automation safety helpers.

This module implements the five Phase 4b non-negotiable safety rules
for autonomous form-filling:

I1 – Sensitive field classification
    ``classify_sensitive_field(name)`` returns a category string:
    ``"password"``, ``"card"``, ``"cvc_cvv"``, ``"iban"``, ``"ssn"``,
    ``"otp_2fa"``, ``"crypto"``, or ``"safe"``.
    Callers MUST skip any field that is not ``"safe"``.

I2 – Payment URL detection
    ``is_payment_url(url)`` returns True if the URL looks like a payment
    checkout page.  Such pages must never be visited by automated flows.

I3 – Login context detection
    ``is_login_context(url)`` returns True if the URL looks like a login
    or authentication page.

I4/I5 – Confirm-gate helpers
    ``should_block_step(intent, params)`` is a convenience wrapper that
    combines I2 + I3 checks for a given (intent, params) pair.

No external dependencies.  All regexes are pre-compiled at import time.
"""

from __future__ import annotations

import re

# ────────────────────────────────────────────────────────────────────────────────
# I1: Sensitive field patterns
# ────────────────────────────────────────────────────────────────────────────────

_SENSITIVE_FIELD_RE: dict[str, re.Pattern[str]] = {
    "password": re.compile(
        r"(password|passwd|pass|mot.?de.?passe|mdp|secret|pin\b|code.?secret)",
        re.IGNORECASE,
    ),
    "card": re.compile(
        r"(card.?number|num.?carte|card.?num|numero.?carte|credit.?card"
        r"|debit.?card|carte.?bancaire|carte.?credit|pan\b|cc.?number"
        r"|cc_num|cardnumber|numero_carte)",
        re.IGNORECASE,
    ),
    "cvc_cvv": re.compile(
        r"(cvv|cvc|csc|security.?code|card.?security|cryptogramme"
        r"|crypto.?visuel|code.?carte|cv2|card.?verif)",
        re.IGNORECASE,
    ),
    "iban": re.compile(
        r"(iban|bic|swift|rib\b|account.?number|num.?compte|numero.?compte"
        r"|bank.?account|compte.?bancaire|routing.?number|sort.?code)",
        re.IGNORECASE,
    ),
    "ssn": re.compile(
        r"(ssn|social.?security|numero.?secu|numéro.?sécu|nir\b"
        r"|sin\b|national.?id|national.?insurance|nino\b|tax.?id"
        r"|tin\b|fiscal.?id|identifiant.?fiscal)",
        re.IGNORECASE,
    ),
    "otp_2fa": re.compile(
        r"(otp|totp|one.?time|2fa|two.?factor|mfa|auth.?code|verification.?code"
        r"|code.?verification|sms.?code|code.?sms|token.?auth)",
        re.IGNORECASE,
    ),
    "crypto": re.compile(
        r"(wallet.?address|private.?key|seed.?phrase|mnemonic|crypto.?address"
        r"|btc.?address|eth.?address|public.?key)",
        re.IGNORECASE,
    ),
}


def classify_sensitive_field(field_name: str) -> str:
    """Classify a form-field name/id as sensitive or safe.

    Returns one of:
    - ``"password"``: password / PIN / secret fields
    - ``"card"``:     credit/debit card number fields
    - ``"cvc_cvv"``:  CVV / CVC / security-code fields
    - ``"iban"``:     bank account / IBAN / BIC fields
    - ``"ssn"``:      social-security / national-id fields
    - ``"otp_2fa"``:  one-time password / 2FA code fields
    - ``"crypto"``:   crypto wallet / private-key fields
    - ``"safe"``:     does not match any sensitive pattern

    Args:
        field_name: The HTML name, id, or placeholder of the form field.

    Returns:
        Category string (one of the above).
    """
    for category, pattern in _SENSITIVE_FIELD_RE.items():
        if pattern.search(field_name):
            return category
    return "safe"


# ────────────────────────────────────────────────────────────────────────────────
# I2: Payment URL patterns
# ────────────────────────────────────────────────────────────────────────────────

_PAYMENT_URL_RE = re.compile(
    r"("
    r"checkout"
    r"|/pay(?:ment)?(?:/|$|\.)"
    r"|\.pay(?:ment)?(?:/|$|\.)"
    r"|/billing"
    r"|\.billing"
    r"|/cart(?:/|$|\.)"
    r"|/order(?:s)?(?:/checkout|/pay|/payment)"
    r"|stripe\.com"
    r"|paypal\.com"
    r"|braintree"
    r"|square\.com/payments"
    r"|adyen\.com"
    r"|mollie\.com"
    r"|paiement"
    r"|/encaissement"
    r")",
    re.IGNORECASE,
)


def is_payment_url(url: str) -> bool:
    """Return True if *url* looks like a payment or checkout page.

    Args:
        url: Full URL string.

    Returns:
        True if the URL matches known payment/checkout patterns.
    """
    return bool(_PAYMENT_URL_RE.search(url))


# ────────────────────────────────────────────────────────────────────────────────
# I3: Login URL patterns
# ────────────────────────────────────────────────────────────────────────────────

_LOGIN_URL_RE = re.compile(
    r"("
    r"/login"
    r"|/signin"
    r"|/sign.in"
    r"|/connexion"
    r"|/authentification"
    r"|/auth(?:/|$|\.)"
    r"|/session(?:s)?(?:/new|/create)"
    r"|/sso"
    r"|/oauth"
    r"|/oidc"
    r"|/saml"
    r"|/password.?reset"
    r"|/forgot.?password"
    r"|/mot.?de.?passe"
    r")",
    re.IGNORECASE,
)


def is_login_context(url: str) -> bool:
    """Return True if *url* looks like a login or authentication page.

    Args:
        url: Full URL string.

    Returns:
        True if the URL matches known login/auth patterns.
    """
    return bool(_LOGIN_URL_RE.search(url))


# ────────────────────────────────────────────────────────────────────────────────
# I4/I5: Convenience gate check
# ────────────────────────────────────────────────────────────────────────────────


def should_block_step(intent: str, params: dict) -> tuple[bool, str]:
    """Determine whether an action step should be blocked.

    Combines I2 (payment URL) and I3 (login URL) checks for a given
    (intent, params) pair.

    Args:
        intent: Action intent string (e.g. ``"fill_form"``, ``"click"``).
        params: Action parameters dict.

    Returns:
        ``(True, reason_string)`` if the step should be blocked,
        ``(False, "")`` if it is safe to proceed.
    """
    url = params.get("url", "")
    if is_payment_url(url):
        return True, f"payment URL: {url!r}"
    if is_login_context(url):
        return True, f"login URL: {url!r}"
    return False, ""
