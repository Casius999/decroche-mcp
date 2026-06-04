"""test_apply_send_gating — Gating tests for apply.browser.send_approved."""

from __future__ import annotations

import json
import pytest
import decroche.apply.browser as browser_mod
from decroche.apply.browser import send_approved
from decroche.models import SendResult


def _write_queue(tmp_path, items: list[dict]) -> str:
    queue_file = tmp_path / "queue.json"
    store = {item["job_id"]: item for item in items}
    queue_file.write_text(json.dumps(store), encoding="utf-8")
    return str(queue_file)

def _make_item(job_id: str, status: str = "approved", apply_url: str = "https://boards.greenhouse.io/acme/jobs/1", fields: dict | None = None) -> dict:
    fields = fields or {"full_name": "Alice", "email": "alice@example.com"}
    return {"job_id": job_id, "company": "Acme", "role_title": "Engineer", "apply_url": apply_url, "prefill": {"apply_url": apply_url, "fields": fields, "unmapped": [], "excluded_sensitive": [], "warnings": []}, "status": status, "preview": ""}


class SubmitStub:
    def __init__(self): self.submitted_ids: list[str] = []
    async def __call__(self, item: dict, fields: dict, apply_url: str) -> None:
        self.submitted_ids.append(item["job_id"])

@pytest.fixture()
def stub_submit(monkeypatch):
    stub = SubmitStub()
    monkeypatch.setattr(browser_mod, "_PLAYWRIGHT_AVAILABLE", True)
    monkeypatch.setattr(browser_mod, "_submit_item", stub)
    return stub


class TestDryRunGating:
    @pytest.mark.asyncio
    async def test_dry_run_submitted_is_zero(self, tmp_path):
        q = _write_queue(tmp_path, [_make_item("job-1")])
        result = await send_approved(q, confirm_send=False)
        assert result.dry_run is True and result.submitted == 0

    @pytest.mark.asyncio
    async def test_dry_run_attempted_counts_approved(self, tmp_path):
        q = _write_queue(tmp_path, [_make_item("job-1"), _make_item("job-2")])
        assert (await send_approved(q, confirm_send=False)).attempted == 2

    @pytest.mark.asyncio
    async def test_dry_run_empty_queue(self, tmp_path):
        q = _write_queue(tmp_path, [])
        result = await send_approved(q, confirm_send=False)
        assert result.dry_run is True and result.attempted == 0 and result.submitted == 0

    @pytest.mark.asyncio
    async def test_dry_run_missing_queue_file(self, tmp_path):
        result = await send_approved(str(tmp_path / "no_queue.json"), confirm_send=False)
        assert result.dry_run is True and result.attempted == 0


class TestOnlyApprovedConsidered:
    @pytest.mark.asyncio
    async def test_prepared_item_not_attempted(self, tmp_path, stub_submit):
        q = _write_queue(tmp_path, [_make_item("job-1", status="prepared")])
        result = await send_approved(q, confirm_send=True)
        assert result.attempted == 0 and result.submitted == 0 and stub_submit.submitted_ids == []

    @pytest.mark.asyncio
    async def test_sent_item_not_attempted(self, tmp_path, stub_submit):
        q = _write_queue(tmp_path, [_make_item("job-1", status="sent")])
        result = await send_approved(q, confirm_send=True)
        assert result.attempted == 0 and stub_submit.submitted_ids == []

    @pytest.mark.asyncio
    async def test_skipped_item_not_attempted(self, tmp_path, stub_submit):
        q = _write_queue(tmp_path, [_make_item("job-1", status="skipped")])
        result = await send_approved(q, confirm_send=True)
        assert result.attempted == 0 and stub_submit.submitted_ids == []

    @pytest.mark.asyncio
    async def test_mixed_only_approved_attempted(self, tmp_path, stub_submit):
        q = _write_queue(tmp_path, [_make_item("job-approved"), _make_item("job-prepared", status="prepared"), _make_item("job-sent", status="sent")])
        result = await send_approved(q, confirm_send=True)
        assert result.attempted == 1 and stub_submit.submitted_ids == ["job-approved"]


class TestPaymentUrlStopped:
    @pytest.mark.asyncio
    async def test_payment_url_stopped(self, tmp_path):
        q = _write_queue(tmp_path, [_make_item("job-1", apply_url="https://example.com/checkout")])
        result = await send_approved(q, confirm_send=False)
        assert result.attempted == 1 and len(result.stopped) == 1
        assert result.stopped[0]["job_id"] == "job-1"

    @pytest.mark.asyncio
    async def test_payment_url_not_submitted_even_with_confirm(self, tmp_path, stub_submit):
        q = _write_queue(tmp_path, [_make_item("job-1", apply_url="https://example.com/payment")])
        result = await send_approved(q, confirm_send=True)
        assert result.submitted == 0 and stub_submit.submitted_ids == [] and len(result.stopped) == 1

    @pytest.mark.asyncio
    async def test_stripe_url_stopped(self, tmp_path, stub_submit):
        q = _write_queue(tmp_path, [_make_item("job-1", apply_url="https://checkout.stripe.com/pay/cs_test")])
        result = await send_approved(q, confirm_send=True)
        assert result.submitted == 0 and stub_submit.submitted_ids == []


class TestLoginContextStopped:
    @pytest.mark.asyncio
    async def test_login_url_stopped(self, tmp_path):
        q = _write_queue(tmp_path, [_make_item("job-1", apply_url="https://example.com/login/apply")])
        result = await send_approved(q, confirm_send=False)
        assert len(result.stopped) == 1

    @pytest.mark.asyncio
    async def test_signin_url_stopped_not_submitted(self, tmp_path, stub_submit):
        q = _write_queue(tmp_path, [_make_item("job-1", apply_url="https://example.com/signin")])
        result = await send_approved(q, confirm_send=True)
        assert result.submitted == 0 and stub_submit.submitted_ids == [] and len(result.stopped) == 1

    @pytest.mark.asyncio
    async def test_connexion_url_stopped(self, tmp_path, stub_submit):
        q = _write_queue(tmp_path, [_make_item("job-1", apply_url="https://example.com/connexion/apply")])
        result = await send_approved(q, confirm_send=True)
        assert stub_submit.submitted_ids == [] and len(result.stopped) == 1


class TestSensitivePrefillFieldSkipped:
    @pytest.mark.asyncio
    async def test_password_in_fields_skipped(self, tmp_path, stub_submit):
        q = _write_queue(tmp_path, [_make_item("job-1", fields={"email": "alice@example.com", "password": "secret"})])
        result = await send_approved(q, confirm_send=True)
        assert result.submitted == 0 and stub_submit.submitted_ids == [] and len(result.skipped) == 1
        assert result.skipped[0]["job_id"] == "job-1"

    @pytest.mark.asyncio
    async def test_card_in_fields_skipped(self, tmp_path, stub_submit):
        q = _write_queue(tmp_path, [_make_item("job-1", fields={"email": "a@b.com", "card_number": "4111..."})])
        result = await send_approved(q, confirm_send=True)
        assert result.submitted == 0 and len(result.skipped) == 1

    @pytest.mark.asyncio
    async def test_iban_in_fields_skipped(self, tmp_path, stub_submit):
        q = _write_queue(tmp_path, [_make_item("job-1", fields={"full_name": "Alice", "iban": "FR76..."})])
        result = await send_approved(q, confirm_send=True)
        assert result.submitted == 0 and len(result.skipped) == 1


class TestSafeItemSubmitsViaStub:
    @pytest.mark.asyncio
    async def test_safe_item_submitted(self, tmp_path, stub_submit):
        q = _write_queue(tmp_path, [_make_item("job-safe")])
        result = await send_approved(q, confirm_send=True)
        assert result.submitted == 1 and stub_submit.submitted_ids == ["job-safe"] and result.dry_run is False

    @pytest.mark.asyncio
    async def test_two_safe_items_both_submitted(self, tmp_path, stub_submit):
        q = _write_queue(tmp_path, [_make_item("job-a"), _make_item("job-b")])
        result = await send_approved(q, confirm_send=True)
        assert result.submitted == 2 and set(stub_submit.submitted_ids) == {"job-a", "job-b"}

    @pytest.mark.asyncio
    async def test_mixed_safe_and_blocked_correct_counts(self, tmp_path, stub_submit):
        q = _write_queue(tmp_path, [_make_item("job-safe"), _make_item("job-pay", apply_url="https://example.com/payment"), _make_item("job-login", apply_url="https://example.com/login")])
        result = await send_approved(q, confirm_send=True)
        assert result.attempted == 3 and result.submitted == 1 and len(result.stopped) == 2
        assert stub_submit.submitted_ids == ["job-safe"]
