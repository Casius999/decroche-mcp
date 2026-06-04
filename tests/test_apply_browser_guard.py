"""test_apply_browser_guard — Guard tests for apply.browser when playwright absent.

Tests two scenarios:
1. Playwright NOT installed (monkeypatched away):
   - act(confirm=True, ...) raises ToolError with the install instructions.
   - send_approved(confirm_send=True, ...) raises ToolError with the install instructions.
2. Pre-browser safety gate works WITHOUT a browser:
   - act(intent="fill", params={field="password",...}, confirm=False)
     → returns ActPreview(blocked=True) — no browser needed, safety fires first.
   - act(intent="fill", params={field="email",...}, confirm=False)
     → returns ActPreview(blocked=False, requires_confirm=True).
   - act(intent="navigate", params={url="https://example.com/checkout",...}, confirm=False)
     → returns ActPreview(blocked=True) because is_payment_url fires pre-browser.
"""

from __future__ import annotations

import json
import pytest

import decroche.apply.browser as browser_mod
from decroche.apply.browser import act, send_approved
from decroche.models import ActPreview, SendResult


@pytest.fixture()
def no_playwright(monkeypatch):
    monkeypatch.setattr(browser_mod, "_PLAYWRIGHT_AVAILABLE", False)
    monkeypatch.setattr(browser_mod, "_async_playwright", None)


@pytest.fixture()
def approved_queue(tmp_path):
    queue_file = tmp_path / "queue.json"
    queue_data = {
        "job-1": {
            "job_id": "job-1",
            "company": "Acme",
            "role_title": "Backend Engineer",
            "apply_url": "https://boards.greenhouse.io/acme/jobs/1",
            "prefill": {
                "apply_url": "https://boards.greenhouse.io/acme/jobs/1",
                "fields": {"full_name": "Alice", "email": "alice@example.com"},
                "unmapped": [],
                "excluded_sensitive": [],
                "warnings": [],
            },
            "status": "approved",
            "preview": "",
        }
    }
    queue_file.write_text(json.dumps(queue_data), encoding="utf-8")
    return str(queue_file)


class TestPlaywrightMissingRaisesToolError:
    @pytest.mark.asyncio
    async def test_act_confirm_true_raises_when_no_playwright(self, no_playwright):
        with pytest.raises(Exception) as exc_info:
            await act(
                intent="navigate",
                params={"url": "https://boards.greenhouse.io/acme/jobs/1"},
                confirm=True,
            )
        msg = str(exc_info.value)
        assert "playwright" in msg.lower()
        assert "install" in msg.lower() or "pip" in msg.lower()

    @pytest.mark.asyncio
    async def test_send_approved_confirm_true_raises_when_no_playwright(
        self, no_playwright, approved_queue
    ):
        with pytest.raises(Exception) as exc_info:
            await send_approved(queue_path=approved_queue, confirm_send=True)
        msg = str(exc_info.value)
        assert "playwright" in msg.lower()
        assert "install" in msg.lower() or "pip" in msg.lower()

    @pytest.mark.asyncio
    async def test_send_approved_dry_run_does_not_raise_when_no_playwright(
        self, no_playwright, approved_queue
    ):
        result = await send_approved(queue_path=approved_queue, confirm_send=False)
        assert isinstance(result, SendResult)
        assert result.dry_run is True
        assert result.submitted == 0


class TestActPreviewNoBrowserNeeded:
    @pytest.mark.asyncio
    async def test_sensitive_field_blocked_no_browser(self):
        result = await act(intent="fill", params={"field": "password", "value": "secret"}, confirm=False)
        assert isinstance(result, ActPreview)
        assert result.blocked is True
        assert result.block_reason is not None
        assert result.requires_confirm is False

    @pytest.mark.asyncio
    async def test_cvv_field_blocked_no_browser(self):
        result = await act(intent="fill", params={"field": "cvv", "value": "123"}, confirm=False)
        assert result.blocked is True

    @pytest.mark.asyncio
    async def test_iban_field_blocked_no_browser(self):
        result = await act(intent="fill", params={"field": "iban", "value": "FR76..."}, confirm=False)
        assert result.blocked is True

    @pytest.mark.asyncio
    async def test_card_number_field_blocked_no_browser(self):
        result = await act(intent="fill", params={"field": "card_number", "value": "4111111111111111"}, confirm=False)
        assert result.blocked is True

    @pytest.mark.asyncio
    async def test_payment_url_blocked_no_browser(self):
        result = await act(intent="navigate", params={"url": "https://example.com/checkout"}, confirm=False)
        assert isinstance(result, ActPreview)
        assert result.blocked is True
        assert result.block_reason is not None

    @pytest.mark.asyncio
    async def test_stripe_url_blocked(self):
        result = await act(intent="navigate", params={"url": "https://checkout.stripe.com/pay/cs_test"}, confirm=False)
        assert result.blocked is True

    @pytest.mark.asyncio
    async def test_safe_fill_returns_preview_not_blocked(self):
        result = await act(intent="fill", params={"field": "email", "value": "alice@example.com"}, confirm=False)
        assert isinstance(result, ActPreview)
        assert result.blocked is False
        assert result.requires_confirm is True

    @pytest.mark.asyncio
    async def test_safe_navigate_returns_preview_not_blocked(self):
        result = await act(intent="navigate", params={"url": "https://boards.greenhouse.io/acme/jobs/1"}, confirm=False)
        assert isinstance(result, ActPreview)
        assert result.blocked is False
        assert result.requires_confirm is True

    @pytest.mark.asyncio
    async def test_sensitive_label_blocks_fill(self):
        result = await act(intent="fill", params={"field": "secret_input", "value": "x", "label": "Mot de passe"}, confirm=False)
        assert result.blocked is True

    @pytest.mark.asyncio
    async def test_2fa_field_blocked(self):
        result = await act(intent="fill", params={"field": "2fa_code", "value": "123456"}, confirm=False)
        assert result.blocked is True
