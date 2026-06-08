"""test_apply_send_gating — Gating tests for apply.browser.send_approved.

Verifies (without real Playwright or network):
1. confirm_send=False → dry-run (SendResult.dry_run=True, submitted=0).
2. Only approved items are considered; prepared/sent items are ignored.
3. An approved item whose apply_url is_payment_url → stopped, NOT submitted.
4. An approved item whose apply_url is_login_context → stopped, NOT submitted.
5. An approved item whose prefill has a sensitive field → skipped, NOT submitted.
6. A safe approved item with confirm_send=True would submit (browser stub records call).

The "browser stub" pattern: we monkeypatch _submit_item in browser_mod so tests
never touch real Playwright.  The stub records calls so we can assert submit was
(or was not) invoked.
"""

from __future__ import annotations

import json

import pytest

import decroche.apply.browser as browser_mod
from decroche.apply.browser import act, send_approved
from decroche.models import SendResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_queue(tmp_path, items: list[dict]) -> str:
    """Write a queue JSON and return its path."""
    queue_file = tmp_path / "queue.json"
    store = {item["job_id"]: item for item in items}
    queue_file.write_text(json.dumps(store), encoding="utf-8")
    return str(queue_file)


def _make_item(
    job_id: str,
    status: str = "approved",
    apply_url: str = "https://boards.greenhouse.io/acme/jobs/1",
    fields: dict | None = None,
) -> dict:
    fields = fields or {"full_name": "Alice", "email": "alice@example.com"}
    return {
        "job_id": job_id,
        "company": "Acme",
        "role_title": "Engineer",
        "apply_url": apply_url,
        "prefill": {
            "apply_url": apply_url,
            "fields": fields,
            "unmapped": [],
            "excluded_sensitive": [],
            "warnings": [],
        },
        "status": status,
        "preview": "",
    }


# ---------------------------------------------------------------------------
# Stub: capture submit calls without Playwright
# ---------------------------------------------------------------------------


class SubmitStub:
    """Records job_ids of _submit_item calls without doing anything real."""

    def __init__(self):
        self.submitted_ids: list[str] = []

    async def __call__(self, item: dict, fields: dict, apply_url: str) -> None:
        self.submitted_ids.append(item["job_id"])


@pytest.fixture()
def stub_submit(monkeypatch):
    """Patch _submit_item to a non-blocking stub and enable playwright flag."""
    stub = SubmitStub()
    monkeypatch.setattr(browser_mod, "_PLAYWRIGHT_AVAILABLE", True)
    monkeypatch.setattr(browser_mod, "_submit_item", stub)
    return stub


# ===========================================================================
# 1. Dry-run gating
# ===========================================================================


class TestDryRunGating:
    @pytest.mark.asyncio
    async def test_dry_run_submitted_is_zero(self, tmp_path):
        q = _write_queue(tmp_path, [_make_item("job-1")])
        result = await send_approved(q, confirm_send=False)
        assert isinstance(result, SendResult)
        assert result.dry_run is True
        assert result.submitted == 0

    @pytest.mark.asyncio
    async def test_dry_run_attempted_counts_approved(self, tmp_path):
        q = _write_queue(tmp_path, [_make_item("job-1"), _make_item("job-2")])
        result = await send_approved(q, confirm_send=False)
        assert result.attempted == 2

    @pytest.mark.asyncio
    async def test_dry_run_empty_queue(self, tmp_path):
        q = _write_queue(tmp_path, [])
        result = await send_approved(q, confirm_send=False)
        assert result.dry_run is True
        assert result.attempted == 0
        assert result.submitted == 0

    @pytest.mark.asyncio
    async def test_dry_run_missing_queue_file(self, tmp_path):
        nonexistent = str(tmp_path / "no_queue.json")
        result = await send_approved(nonexistent, confirm_send=False)
        assert result.dry_run is True
        assert result.attempted == 0


# ===========================================================================
# 2. Only approved items are considered
# ===========================================================================


class TestOnlyApprovedConsidered:
    @pytest.mark.asyncio
    async def test_prepared_item_not_attempted(self, tmp_path, stub_submit):
        q = _write_queue(tmp_path, [_make_item("job-1", status="prepared")])
        result = await send_approved(q, confirm_send=True)
        assert result.attempted == 0
        assert result.submitted == 0
        assert stub_submit.submitted_ids == []

    @pytest.mark.asyncio
    async def test_sent_item_not_attempted(self, tmp_path, stub_submit):
        q = _write_queue(tmp_path, [_make_item("job-1", status="sent")])
        result = await send_approved(q, confirm_send=True)
        assert result.attempted == 0
        assert stub_submit.submitted_ids == []

    @pytest.mark.asyncio
    async def test_skipped_item_not_attempted(self, tmp_path, stub_submit):
        q = _write_queue(tmp_path, [_make_item("job-1", status="skipped")])
        result = await send_approved(q, confirm_send=True)
        assert result.attempted == 0
        assert stub_submit.submitted_ids == []

    @pytest.mark.asyncio
    async def test_mixed_only_approved_attempted(self, tmp_path, stub_submit):
        q = _write_queue(
            tmp_path,
            [
                _make_item("job-approved", status="approved"),
                _make_item("job-prepared", status="prepared"),
                _make_item("job-sent", status="sent"),
            ],
        )
        result = await send_approved(q, confirm_send=True)
        assert result.attempted == 1
        assert stub_submit.submitted_ids == ["job-approved"]


# ===========================================================================
# 3. Payment URL → stopped, NOT submitted
# ===========================================================================


class TestPaymentUrlStopped:
    @pytest.mark.asyncio
    async def test_payment_url_stopped(self, tmp_path):
        q = _write_queue(
            tmp_path,
            [_make_item("job-1", apply_url="https://example.com/checkout")],
        )
        result = await send_approved(q, confirm_send=False)
        assert result.attempted == 1
        assert len(result.stopped) == 1
        assert result.stopped[0]["job_id"] == "job-1"
        assert (
            "payment" in result.stopped[0]["reason"].lower()
            or "STOP" in result.stopped[0]["reason"]
        )

    @pytest.mark.asyncio
    async def test_payment_url_not_submitted_even_with_confirm(self, tmp_path, stub_submit):
        q = _write_queue(
            tmp_path,
            [_make_item("job-1", apply_url="https://example.com/payment")],
        )
        result = await send_approved(q, confirm_send=True)
        assert result.submitted == 0
        assert stub_submit.submitted_ids == []
        assert len(result.stopped) == 1

    @pytest.mark.asyncio
    async def test_stripe_url_stopped(self, tmp_path, stub_submit):
        q = _write_queue(
            tmp_path,
            [_make_item("job-1", apply_url="https://checkout.stripe.com/pay/cs_test")],
        )
        result = await send_approved(q, confirm_send=True)
        assert result.submitted == 0
        assert stub_submit.submitted_ids == []


# ===========================================================================
# 4. Login context → stopped as needs_manual_login
# ===========================================================================


class TestLoginContextStopped:
    @pytest.mark.asyncio
    async def test_login_url_stopped(self, tmp_path):
        q = _write_queue(
            tmp_path,
            [_make_item("job-1", apply_url="https://example.com/login/apply")],
        )
        result = await send_approved(q, confirm_send=False)
        assert len(result.stopped) == 1
        assert (
            "login" in result.stopped[0]["reason"].lower()
            or "manual" in result.stopped[0]["reason"].lower()
        )

    @pytest.mark.asyncio
    async def test_signin_url_stopped_not_submitted(self, tmp_path, stub_submit):
        q = _write_queue(
            tmp_path,
            [_make_item("job-1", apply_url="https://example.com/signin")],
        )
        result = await send_approved(q, confirm_send=True)
        assert result.submitted == 0
        assert stub_submit.submitted_ids == []
        assert len(result.stopped) == 1

    @pytest.mark.asyncio
    async def test_connexion_url_stopped(self, tmp_path, stub_submit):
        q = _write_queue(
            tmp_path,
            [_make_item("job-1", apply_url="https://example.com/connexion/apply")],
        )
        result = await send_approved(q, confirm_send=True)
        assert stub_submit.submitted_ids == []
        assert len(result.stopped) == 1


# ===========================================================================
# 5. Sensitive prefill field → skipped, NOT submitted
# ===========================================================================


class TestSensitivePrefillFieldSkipped:
    @pytest.mark.asyncio
    async def test_password_in_fields_skipped(self, tmp_path, stub_submit):
        q = _write_queue(
            tmp_path,
            [
                _make_item(
                    "job-1",
                    fields={"email": "alice@example.com", "password": "secret"},
                )
            ],
        )
        result = await send_approved(q, confirm_send=True)
        assert result.submitted == 0
        assert stub_submit.submitted_ids == []
        assert len(result.skipped) == 1
        assert result.skipped[0]["job_id"] == "job-1"
        assert "sensitive" in result.skipped[0]["reason"].lower()

    @pytest.mark.asyncio
    async def test_card_in_fields_skipped(self, tmp_path, stub_submit):
        q = _write_queue(
            tmp_path,
            [_make_item("job-1", fields={"email": "a@b.com", "card_number": "4111..."})],
        )
        result = await send_approved(q, confirm_send=True)
        assert result.submitted == 0
        assert len(result.skipped) == 1

    @pytest.mark.asyncio
    async def test_iban_in_fields_skipped(self, tmp_path, stub_submit):
        q = _write_queue(
            tmp_path,
            [_make_item("job-1", fields={"full_name": "Alice", "iban": "FR76..."})],
        )
        result = await send_approved(q, confirm_send=True)
        assert result.submitted == 0
        assert len(result.skipped) == 1


# ===========================================================================
# 6. Safe approved item + confirm_send=True → stub records submit
# ===========================================================================


class TestSafeItemSubmitsViaStub:
    @pytest.mark.asyncio
    async def test_safe_item_submitted(self, tmp_path, stub_submit):
        q = _write_queue(tmp_path, [_make_item("job-safe")])
        result = await send_approved(q, confirm_send=True)
        assert result.submitted == 1
        assert stub_submit.submitted_ids == ["job-safe"]
        assert result.dry_run is False

    @pytest.mark.asyncio
    async def test_two_safe_items_both_submitted(self, tmp_path, stub_submit):
        q = _write_queue(tmp_path, [_make_item("job-a"), _make_item("job-b")])
        result = await send_approved(q, confirm_send=True)
        assert result.submitted == 2
        assert set(stub_submit.submitted_ids) == {"job-a", "job-b"}

    @pytest.mark.asyncio
    async def test_mixed_safe_and_blocked_correct_counts(self, tmp_path, stub_submit):
        q = _write_queue(
            tmp_path,
            [
                _make_item("job-safe"),
                _make_item("job-pay", apply_url="https://example.com/payment"),
                _make_item("job-login", apply_url="https://example.com/login"),
            ],
        )
        result = await send_approved(q, confirm_send=True)
        assert result.attempted == 3
        assert result.submitted == 1
        assert len(result.stopped) == 2
        assert stub_submit.submitted_ids == ["job-safe"]


# ===========================================================================
# I4 — act() blocks click on pay/subscribe/checkout targets
# ===========================================================================


class TestActClickPaymentTargetBlocked:
    @pytest.mark.asyncio
    async def test_click_pay_now_blocked(self) -> None:
        """I4 — click with name 'Pay now' must be blocked in preview mode."""
        result = await act("click", {"role": "button", "name": "Pay now"}, confirm=False)
        assert result.blocked is True
        assert result.block_reason is not None
        assert "pay" in result.block_reason.lower() or "payment" in result.block_reason.lower()

    @pytest.mark.asyncio
    async def test_click_subscribe_blocked(self) -> None:
        """I4 — click with name 'Subscribe' must be blocked."""
        result = await act("click", {"role": "button", "name": "Subscribe"}, confirm=False)
        assert result.blocked is True

    @pytest.mark.asyncio
    async def test_click_checkout_selector_blocked(self) -> None:
        """I4 — click with selector containing 'checkout' must be blocked."""
        result = await act("click", {"selector": "#checkout-btn"}, confirm=False)
        assert result.blocked is True

    @pytest.mark.asyncio
    async def test_click_confirm_payment_blocked(self) -> None:
        """I4 — click with name 'Confirm payment' must be blocked."""
        result = await act("click", {"role": "button", "name": "Confirm payment"}, confirm=False)
        assert result.blocked is True

    @pytest.mark.asyncio
    async def test_click_regler_fr_blocked(self) -> None:
        """I4 — click with name 'Régler' (FR) must be blocked."""
        result = await act("click", {"role": "button", "name": "Régler"}, confirm=False)
        assert result.blocked is True

    @pytest.mark.asyncio
    async def test_click_abonnement_blocked(self) -> None:
        """I4 — click with name 'Souscrire un abonnement' must be blocked."""
        result = await act(
            "click", {"role": "button", "name": "Souscrire un abonnement"}, confirm=False
        )
        assert result.blocked is True

    @pytest.mark.asyncio
    async def test_click_safe_submit_not_blocked(self) -> None:
        """I4 — a safe click like 'Next step' must NOT be blocked (no false positive)."""
        result = await act("click", {"role": "button", "name": "Next step"}, confirm=False)
        assert result.blocked is False

    @pytest.mark.asyncio
    async def test_click_apply_not_blocked(self) -> None:
        """I4 — a safe click 'Apply' must NOT be blocked."""
        result = await act("click", {"role": "button", "name": "Apply"}, confirm=False)
        assert result.blocked is False


# ===========================================================================
# I1 — _submit_item blocks when form contains a sensitive field
# ===========================================================================


class FakePage:
    """Minimal page stub for _submit_item testing."""

    def __init__(self, url: str = "https://jobs.acme.com/apply/1", input_names: list | None = None):
        self.url = url
        self._input_names = input_names or []

    async def goto(self, url: str, **kwargs: object) -> None:  # noqa: ARG002
        pass

    async def eval_on_selector_all(self, selector: str, expr: str) -> list[str]:  # noqa: ARG002
        return self._input_names

    def locator(self, sel: str):  # noqa: ARG002
        return _ZeroCount()

    def get_by_role(self, role: str, **kwargs: object):  # noqa: ARG002
        return _ZeroCount()


class _ZeroCount:
    async def count(self) -> int:
        return 0

    async def fill(self, value: str) -> None:  # noqa: ARG002
        pass

    async def click(self) -> None:
        pass

    @property
    def first(self):
        return self


class FakeBrowser:
    def __init__(self, page: FakePage):
        self._page = page
        self.contexts = [FakeContext(page)]

    async def close(self) -> None:
        pass


class FakeContext:
    def __init__(self, page: FakePage):
        self._page = page

    async def new_page(self) -> FakePage:
        return self._page


class FakePlaywright:
    def __init__(self, page: FakePage):
        self._page = page

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args: object) -> None:
        pass

    @property
    def chromium(self):
        return FakeChromium(self._page)


class FakeChromium:
    def __init__(self, page: FakePage):
        self._page = page

    async def connect_over_cdp(self, url: str) -> FakeBrowser:  # noqa: ARG002
        return FakeBrowser(self._page)


class TestSubmitItemSensitiveFieldOnFormBlocked:
    @pytest.mark.asyncio
    async def test_form_with_card_number_field_not_submitted(self, monkeypatch) -> None:
        """I1 — approved item whose form contains 'card_number' input → NOT submitted."""
        page = FakePage(input_names=["full_name", "email", "card_number"])
        fake_pw = FakePlaywright(page)

        submitted: list[str] = []

        # We test _submit_item directly with a fake playwright
        from fastmcp.exceptions import ToolError as _ToolError

        monkeypatch.setattr(browser_mod, "_async_playwright", lambda: fake_pw)
        monkeypatch.setattr(browser_mod, "_PLAYWRIGHT_AVAILABLE", True)

        item = {"job_id": "job-card"}
        fields = {"full_name": "Alice", "email": "alice@example.com"}
        apply_url = "https://jobs.acme.com/apply/1"

        with pytest.raises(_ToolError, match="sensitive"):
            await browser_mod._submit_item(item, fields, apply_url)

        assert submitted == []

    @pytest.mark.asyncio
    async def test_form_without_sensitive_fields_proceeds(self, monkeypatch) -> None:
        """I1 — form with only safe inputs does NOT raise on pre-submit scan."""
        page = FakePage(input_names=["full_name", "email", "phone"])
        fake_pw = FakePlaywright(page)

        monkeypatch.setattr(browser_mod, "_async_playwright", lambda: fake_pw)
        monkeypatch.setattr(browser_mod, "_PLAYWRIGHT_AVAILABLE", True)

        item = {"job_id": "job-safe"}
        fields = {"full_name": "Alice", "email": "alice@example.com"}
        apply_url = "https://jobs.acme.com/apply/1"

        # Should not raise — just run through fill + submit attempt
        await browser_mod._submit_item(item, fields, apply_url)

    @pytest.mark.asyncio
    async def test_form_with_password_field_triggers_login_stop(self, monkeypatch) -> None:
        """I2 — a non-login URL but with a 'password' DOM input → needs_manual_login."""
        page = FakePage(
            url="https://jobs.acme.com/apply/1",
            input_names=["username", "password"],
        )
        fake_pw = FakePlaywright(page)

        monkeypatch.setattr(browser_mod, "_async_playwright", lambda: fake_pw)
        monkeypatch.setattr(browser_mod, "_PLAYWRIGHT_AVAILABLE", True)

        from fastmcp.exceptions import ToolError as _ToolError

        item = {"job_id": "job-pw"}
        fields = {"full_name": "Bob"}
        apply_url = "https://jobs.acme.com/apply/1"

        with pytest.raises(_ToolError, match="login"):
            await browser_mod._submit_item(item, fields, apply_url)


# ===========================================================================
# M — exception scrub: unexpected error must not expose raw exc text
# ===========================================================================


class TestExceptionScrubInSendApproved:
    @pytest.mark.asyncio
    async def test_unexpected_error_reason_contains_type_not_message(
        self, tmp_path, monkeypatch
    ) -> None:
        """M — unexpected error reason must use type name, not raw exc string."""

        async def _failing_submit(item: dict, fields: dict, apply_url: str) -> None:
            raise RuntimeError("SECRET_VALUE_THAT_MUST_NOT_LEAK")

        monkeypatch.setattr(browser_mod, "_PLAYWRIGHT_AVAILABLE", True)
        monkeypatch.setattr(browser_mod, "_submit_item", _failing_submit)

        q = _write_queue(tmp_path, [_make_item("job-err")])
        result = await send_approved(q, confirm_send=True)

        assert len(result.stopped) == 1
        reason = result.stopped[0]["reason"]
        # Must contain the type name
        assert "RuntimeError" in reason
        # Must NOT contain the raw message text
        assert "SECRET_VALUE_THAT_MUST_NOT_LEAK" not in reason
