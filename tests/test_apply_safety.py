"""test_apply_safety — Exhaustive unit tests for apply.safety predicates.

These tests cover the SAFETY CORE of Phase 4b.  All predicates are pure
functions (no I/O), so tests are fast and deterministic.

Coverage matrix:
- classify_sensitive_field: password, card, CVC, IBAN, SSN/sécu, OTP, 2FA,
  crypto, seed, mnemonic (True); name, email, phone, linkedin, company (False).
  Both FR and EN variants for each category.
- is_payment_url: stripe, adyen, paypal, /pay, checkout, billing, paiement.
- is_login_context: login/signin URL; password field name; combined.
- should_block_step: all three block reasons; safe pass-through.
"""

from __future__ import annotations

import pytest

from decroche.apply.safety import (
    classify_sensitive_field,
    is_login_context,
    is_payment_url,
    should_block_step,
)


# ===========================================================================
# classify_sensitive_field
# ===========================================================================


class TestClassifySensitiveFieldPasswords:
    def test_password_en(self):
        assert classify_sensitive_field("password") is True

    def test_Password_capitalised(self):
        assert classify_sensitive_field("Password") is True

    def test_PASSWORD_upper(self):
        assert classify_sensitive_field("PASSWORD") is True

    def test_mot_de_passe_fr(self):
        assert classify_sensitive_field("mot_de_passe") is True

    def test_mot_de_passe_spaced(self):
        assert classify_sensitive_field("mot de passe") is True

    def test_pass_word_hyphen(self):
        assert classify_sensitive_field("pass-word") is True

    def test_pass_standalone(self):
        assert classify_sensitive_field("pass") is True

    def test_pwd_standalone(self):
        assert classify_sensitive_field("pwd") is True

    def test_password_in_label(self):
        assert classify_sensitive_field("secret_field", "Enter your password") is True

    def test_mot_de_passe_in_label(self):
        assert classify_sensitive_field("field", "Mot de passe") is True


class TestClassifySensitiveFieldCards:
    def test_card_en(self):
        assert classify_sensitive_field("card") is True

    def test_card_number(self):
        assert classify_sensitive_field("card_number") is True

    def test_carte_fr(self):
        assert classify_sensitive_field("carte") is True

    def test_carte_bancaire(self):
        assert classify_sensitive_field("carte_bancaire") is True

    def test_cb_standalone(self):
        assert classify_sensitive_field("cb") is True

    def test_CB_upper(self):
        assert classify_sensitive_field("CB") is True

    def test_numero_carte_fr(self):
        assert classify_sensitive_field("numéro_carte") is True

    def test_card_number_label(self):
        assert classify_sensitive_field("field", "Card Number") is True


class TestClassifySensitiveFieldCvcCvv:
    def test_cvc(self):
        assert classify_sensitive_field("cvc") is True

    def test_cvv(self):
        assert classify_sensitive_field("cvv") is True

    def test_CVC_upper(self):
        assert classify_sensitive_field("CVC") is True

    def test_CVV_upper(self):
        assert classify_sensitive_field("CVV") is True

    def test_cvx(self):
        assert classify_sensitive_field("cvx") is True

    def test_csc(self):
        assert classify_sensitive_field("csc") is True

    def test_cvc_label(self):
        assert classify_sensitive_field("security", "CVC") is True

    def test_cvv_label(self):
        assert classify_sensitive_field("code", "CVV") is True


class TestClassifySensitiveFieldIban:
    def test_iban_lower(self):
        assert classify_sensitive_field("iban") is True

    def test_IBAN_upper(self):
        assert classify_sensitive_field("IBAN") is True

    def test_rib_standalone(self):
        assert classify_sensitive_field("rib") is True

    def test_iban_label(self):
        assert classify_sensitive_field("account", "IBAN") is True


class TestClassifySensitiveFieldSsn:
    def test_ssn(self):
        assert classify_sensitive_field("ssn") is True

    def test_social_security(self):
        assert classify_sensitive_field("social_security_number") is True

    def test_social_security_en(self):
        assert classify_sensitive_field("social security") is True

    def test_numero_securite_sociale(self):
        assert classify_sensitive_field("numéro_sécurité_sociale") is True

    def test_numero_secu(self):
        assert classify_sensitive_field("numero_secu") is True

    def test_securite_sociale_label(self):
        assert classify_sensitive_field("field", "Numéro de sécurité sociale") is True


class TestClassifySensitiveFieldOtp2fa:
    def test_otp(self):
        assert classify_sensitive_field("otp") is True

    def test_OTP_upper(self):
        assert classify_sensitive_field("OTP") is True

    def test_one_time_pass(self):
        assert classify_sensitive_field("one_time_pass") is True

    def test_2fa(self):
        assert classify_sensitive_field("2fa") is True

    def test_2FA_upper(self):
        assert classify_sensitive_field("2FA") is True

    def test_two_factor(self):
        assert classify_sensitive_field("two_factor") is True

    def test_auth_code(self):
        assert classify_sensitive_field("auth_code") is True

    def test_verification_code(self):
        assert classify_sensitive_field("verification_code") is True


class TestClassifySensitiveFieldCrypto:
    def test_crypto(self):
        assert classify_sensitive_field("crypto") is True

    def test_seed_phrase(self):
        assert classify_sensitive_field("seed_phrase") is True

    def test_mnemonic(self):
        assert classify_sensitive_field("mnemonic") is True


class TestClassifySensitiveFieldSafe:
    """Fields that must NOT be classified as sensitive."""

    def test_full_name(self):
        assert classify_sensitive_field("full_name") is False

    def test_name(self):
        assert classify_sensitive_field("name") is False

    def test_email(self):
        assert classify_sensitive_field("email") is False

    def test_phone(self):
        assert classify_sensitive_field("phone") is False

    def test_linkedin(self):
        assert classify_sensitive_field("linkedin") is False

    def test_current_company(self):
        assert classify_sensitive_field("current_company") is False

    def test_current_title(self):
        assert classify_sensitive_field("current_title") is False

    def test_location(self):
        assert classify_sensitive_field("location") is False

    def test_cover_letter(self):
        assert classify_sensitive_field("cover_letter") is False

    def test_resume_text(self):
        assert classify_sensitive_field("resume_text") is False

    def test_empty_field(self):
        assert classify_sensitive_field("") is False

    def test_empty_both(self):
        assert classify_sensitive_field("", "") is False

    def test_safe_name_en_label(self):
        assert classify_sensitive_field("first_name", "First Name") is False

    def test_safe_address(self):
        assert classify_sensitive_field("address") is False


# ===========================================================================
# is_payment_url
# ===========================================================================


class TestIsPaymentUrl:
    def test_stripe(self):
        assert is_payment_url("https://checkout.stripe.com/pay/cs_123") is True

    def test_adyen(self):
        assert is_payment_url("https://checkout.adyen.com/pay/") is True

    def test_paypal(self):
        assert is_payment_url("https://www.paypal.com/checkout") is True

    def test_checkout_keyword(self):
        assert is_payment_url("https://example.com/checkout") is True

    def test_payment_keyword(self):
        assert is_payment_url("https://example.com/payment") is True

    def test_paiement_fr(self):
        assert is_payment_url("https://example.com/paiement") is True

    def test_billing(self):
        assert is_payment_url("https://example.com/billing") is True

    def test_slash_pay(self):
        assert is_payment_url("https://example.com/pay") is True

    def test_slash_pay_slash(self):
        assert is_payment_url("https://example.com/pay/now") is True

    def test_slash_pay_query(self):
        assert is_payment_url("https://example.com/pay?id=1") is True

    def test_slash_pay_hash(self):
        assert is_payment_url("https://example.com/pay#step2") is True

    def test_safe_apply_url(self):
        assert is_payment_url("https://jobs.acme.com/apply/backend-engineer") is False

    def test_safe_greenhouse(self):
        assert is_payment_url("https://boards.greenhouse.io/acme/jobs/123") is False

    def test_safe_workday(self):
        assert is_payment_url("https://acme.wd3.myworkdayjobs.com/careers/0/apply") is False

    def test_empty_url(self):
        assert is_payment_url("") is False

    def test_payment_in_subdomain(self):
        # "payment" in hostname → still caught
        assert is_payment_url("https://payment.example.com/page") is True


# ===========================================================================
# is_login_context
# ===========================================================================


class TestIsLoginContext:
    def test_login_url(self):
        assert is_login_context(url="https://example.com/login") is True

    def test_signin_url(self):
        assert is_login_context(url="https://example.com/signin") is True

    def test_sign_in_hyphen(self):
        assert is_login_context(url="https://example.com/sign-in") is True

    def test_connexion_url_fr(self):
        assert is_login_context(url="https://example.com/connexion") is True

    def test_auth_url(self):
        assert is_login_context(url="https://example.com/auth") is True

    def test_auth_slash(self):
        assert is_login_context(url="https://example.com/auth/login") is True

    def test_password_field_name(self):
        assert is_login_context(field_names=["email", "password"]) is True

    def test_mot_de_passe_field(self):
        assert is_login_context(field_names=["email", "mot_de_passe"]) is True

    def test_pwd_field(self):
        assert is_login_context(field_names=["user", "pwd"]) is True

    def test_safe_apply_no_password(self):
        assert is_login_context(field_names=["full_name", "email", "phone"]) is False

    def test_safe_url_no_login_keyword(self):
        assert is_login_context(url="https://jobs.acme.com/apply/123") is False

    def test_empty(self):
        assert is_login_context() is False

    def test_empty_list_safe_url(self):
        assert is_login_context(field_names=[], url="https://example.com/apply") is False


# ===========================================================================
# should_block_step
# ===========================================================================


class TestShouldBlockStep:
    def test_safe_step_not_blocked(self):
        blocked, reason = should_block_step(
            intent="fill",
            target_field="email",
            url="https://jobs.acme.com/apply/123",
        )
        assert blocked is False
        assert reason is None

    def test_payment_url_blocks(self):
        blocked, reason = should_block_step(
            intent="navigate",
            target_field="",
            url="https://example.com/checkout",
        )
        assert blocked is True
        assert reason is not None
        assert "payment" in reason.lower() or "checkout" in reason.lower() or "STOP" in reason

    def test_login_url_blocks(self):
        blocked, reason = should_block_step(
            intent="fill",
            target_field="email",
            url="https://example.com/login",
        )
        assert blocked is True
        assert reason is not None
        assert "login" in reason.lower() or "needs_manual_login" in reason

    def test_sensitive_field_blocks(self):
        blocked, reason = should_block_step(
            intent="fill",
            target_field="password",
            url="https://jobs.acme.com/apply/123",
        )
        assert blocked is True
        assert reason is not None
        assert "sensitive" in reason.lower() or "REFUSED" in reason

    def test_card_field_blocks(self):
        blocked, reason = should_block_step(
            intent="fill",
            target_field="card_number",
            url="https://jobs.acme.com/apply/123",
        )
        assert blocked is True
        assert reason is not None

    def test_iban_field_blocks(self):
        blocked, reason = should_block_step(
            intent="fill",
            target_field="iban",
            url="https://jobs.acme.com/apply",
        )
        assert blocked is True

    def test_payment_url_takes_priority_over_field(self):
        # Even if no sensitive field, payment URL alone blocks
        blocked, reason = should_block_step(
            intent="fill",
            target_field="full_name",
            url="https://example.com/pay",
        )
        assert blocked is True

    def test_navigate_safe_url_no_field(self):
        blocked, reason = should_block_step(
            intent="navigate",
            target_field="",
            url="https://boards.greenhouse.io/acme/jobs/456",
        )
        assert blocked is False
        assert reason is None

    def test_click_no_url_no_field(self):
        blocked, reason = should_block_step(
            intent="click",
        )
        assert blocked is False
        assert reason is None


# ===========================================================================
# C1 — New sensitive field tokens (adversarial review gaps)
# ===========================================================================


@pytest.mark.parametrize(
    "field_name",
    [
        # CVV digit-suffix variants
        "ccv",
        "cvv2",
        "cvc2",
        "ccv2",
        "cid",
        # Card number aliases
        "cc_number",
        "ccnumber",
        "cc-num",
        "pan",
        "primaryAccountNumber",
        "account_number",
        # Bank / account
        "bank_account",
        "numero_compte",
        "sort code",
        "routing number",
        "bic",
        "swift",
        "sepa",
        "rib",
        # Security codes (FR/EN)
        "security code",
        "code de sécurité",
        "code secret",
        "cryptogramme",
        # National / tax IDs
        "nir",
        "national_id",
        "tax_id",
        "numero_fiscal",
        # Passport
        "passport",
        "passport_number",
        # MFA / TOTP / OTP aliases
        "totp",
        "mfa",
        "mfa_code",
        "one time code",
        "code unique",
        "passcode",
        # Password aliases
        "newPwd",
        "userPassword",
        "confirmPassword",
        # Date of birth
        "dob",
        "date_of_birth",
        "date_naissance",
        "birthdate",
        "bday",
        # PIN / passphrase
        "pin",
        "passphrase",
    ],
)
def test_c1_new_sensitive_tokens_blocked(field_name: str) -> None:
    """C1 — every previously-missed token must now return True."""
    assert classify_sensitive_field(field_name) is True, (
        f"classify_sensitive_field({field_name!r}) should be True but returned False"
    )


# C1 — safe-list must still return False after regex broadening
@pytest.mark.parametrize(
    "field_name",
    [
        "name",
        "full_name",
        "email",
        "phone",
        "linkedin",
        "company",
        "title",
        "location",
        "city",
        "current_company",
        "current_title",
        "cover_letter",
        "resume_text",
        "address",
        "first_name",
        "last_name",
    ],
)
def test_c1_safe_list_no_false_positives(field_name: str) -> None:
    """C1 safe-list — none of these must trigger sensitive detection."""
    assert classify_sensitive_field(field_name) is False, (
        f"classify_sensitive_field({field_name!r}) should be False but returned True"
    )


# ===========================================================================
# C2 — New payment/subscribe/order URL keywords
# ===========================================================================


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/subscribe",
        "https://example.com/subscription",
        "https://example.com/abonnement",
        "https://example.com/order",
        "https://example.com/cart",
        "https://example.com/panier",
        "https://example.com/upgrade",
        "https://example.com/purchase",
        "https://example.com/buy",
        "https://example.com/premium",
        "https://example.com/payer",
        "https://example.com/regler",
        "https://example.com/checkout",
        # already existing (regression)
        "https://example.com/payment",
        "https://example.com/paiement",
        "https://example.com/billing",
        "https://example.com/pay",
    ],
)
def test_c2_payment_urls_blocked(url: str) -> None:
    """C2 — all payment/subscribe/order URL patterns must return True."""
    assert is_payment_url(url) is True, f"is_payment_url({url!r}) should be True but returned False"


@pytest.mark.parametrize(
    "url",
    [
        "https://jobs.acme.com/apply",
        "https://boards.greenhouse.io/acme/jobs/123",
        "https://example.com/careers",
    ],
)
def test_c2_safe_urls_not_blocked(url: str) -> None:
    """C2 — benign apply/job URLs must not be misclassified as payment."""
    assert is_payment_url(url) is False, (
        f"is_payment_url({url!r}) should be False but returned True"
    )


# ===========================================================================
# I2 — Login detection: expanded URL regex + DOM field-name branch
# ===========================================================================


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/sso",
        "https://example.com/oauth/token",
        "https://identity.example.com/",
        "https://example.com/identifier",
        "https://example.com/se-connecter",
        "https://example.com/authenticate",
        "https://example.com/log-in",
        "https://example.com/signon",
        "https://example.com/account",
        # regression — existing
        "https://example.com/login",
        "https://example.com/signin",
        "https://example.com/connexion",
    ],
)
def test_i2_expanded_login_urls_blocked(url: str) -> None:
    """I2 — expanded login URL keywords must be detected."""
    assert is_login_context(url=url) is True, (
        f"is_login_context(url={url!r}) should be True but returned False"
    )


def test_i2_password_field_on_non_login_url_blocked() -> None:
    """I2 — a page with a 'password' input on a non-login URL must still be detected."""
    # Non-login URL alone → safe
    assert is_login_context(url="https://jobs.acme.com/apply/123") is False
    # But once the DOM contains a 'password' field → blocked (field-name branch)
    assert (
        is_login_context(
            field_names=["full_name", "email", "password"],
            url="https://jobs.acme.com/apply/123",
        )
        is True
    )
