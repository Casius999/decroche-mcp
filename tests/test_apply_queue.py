"""Tests for apply.queue — pure JSON-backed batch-apply queue (deterministic)."""

from __future__ import annotations

from decroche.apply.queue import queue_add, queue_approve, queue_mark_sent, queue_review
from decroche.models import PrefillPlan, QueueItem


def _prefill(apply_url: str = "https://acme.com/apply/1") -> PrefillPlan:
    return PrefillPlan(apply_url=apply_url, fields={"full_name": "Jane Doe", "email": "jane@example.com"}, excluded_sensitive=["password", "card_number"])

def _item(job_id: str = "job-001", apply_url: str = "https://acme.com/apply/1", status: str = "prepared") -> QueueItem:
    return QueueItem(job_id=job_id, company="Acme", role_title="Senior Dev", apply_url=apply_url, prefill=_prefill(apply_url), status=status, preview="Acme — Senior Dev — https://acme.com/apply/1")


def test_queue_add_persists_item(tmp_path):
    path = str(tmp_path / "queue.json")
    queue_add(_item(), path)
    items = queue_review(path)
    assert len(items) == 1
    assert items[0].job_id == "job-001"

def test_queue_add_multiple_items(tmp_path):
    path = str(tmp_path / "queue.json")
    queue_add(_item("j1"), path); queue_add(_item("j2"), path); queue_add(_item("j3"), path)
    assert len(queue_review(path)) == 3

def test_queue_add_default_status_prepared(tmp_path):
    path = str(tmp_path / "queue.json")
    queue_add(_item(), path)
    assert queue_review(path)[0].status == "prepared"

def test_queue_add_replaces_same_job_id(tmp_path):
    path = str(tmp_path / "queue.json")
    queue_add(_item("j-dup", apply_url="https://old.com"), path)
    queue_add(_item("j-dup", apply_url="https://new.com"), path)
    items = queue_review(path)
    assert len(items) == 1
    assert items[0].apply_url == "https://new.com"

def test_queue_add_creates_file_if_missing(tmp_path):
    path = str(tmp_path / "new_queue.json")
    queue_add(_item(), path)
    assert (tmp_path / "new_queue.json").exists()

def test_queue_review_empty_when_no_file(tmp_path):
    assert queue_review(str(tmp_path / "nonexistent.json")) == []

def test_queue_review_returns_queue_items(tmp_path):
    path = str(tmp_path / "queue.json")
    queue_add(_item("j1"), path)
    assert all(isinstance(i, QueueItem) for i in queue_review(path))

def test_queue_review_preserves_prefill(tmp_path):
    path = str(tmp_path / "queue.json")
    queue_add(_item("j-pf"), path)
    assert queue_review(path)[0].prefill.fields["full_name"] == "Jane Doe"

def test_queue_review_encoding_utf8(tmp_path):
    path = str(tmp_path / "queue.json")
    item = _item("j-utf8").model_copy(update={"company": "Société Générale"})
    queue_add(item, path)
    assert queue_review(path)[0].company == "Société Générale"

def test_queue_approve_flips_prepared_to_approved(tmp_path):
    path = str(tmp_path / "queue.json")
    queue_add(_item("j-a"), path)
    assert queue_approve(["j-a"], path) == 1
    assert queue_review(path)[0].status == "approved"

def test_queue_approve_returns_count(tmp_path):
    path = str(tmp_path / "queue.json")
    queue_add(_item("j-b1"), path); queue_add(_item("j-b2"), path)
    assert queue_approve(["j-b1", "j-b2"], path) == 2

def test_queue_approve_only_changes_listed_ids(tmp_path):
    path = str(tmp_path / "queue.json")
    queue_add(_item("j-c1"), path); queue_add(_item("j-c2"), path)
    queue_approve(["j-c1"], path)
    items = {i.job_id: i for i in queue_review(path)}
    assert items["j-c1"].status == "approved"
    assert items["j-c2"].status == "prepared"

def test_queue_approve_unknown_id_not_counted(tmp_path):
    path = str(tmp_path / "queue.json")
    queue_add(_item("j-d"), path)
    assert queue_approve(["does-not-exist"], path) == 0

def test_queue_approve_empty_list(tmp_path):
    path = str(tmp_path / "queue.json")
    queue_add(_item("j-e"), path)
    assert queue_approve([], path) == 0

def test_queue_mark_sent_changes_status(tmp_path):
    path = str(tmp_path / "queue.json")
    queue_add(_item("j-s"), path); queue_approve(["j-s"], path); queue_mark_sent("j-s", path)
    assert queue_review(path)[0].status == "sent"

def test_queue_mark_sent_unknown_id_no_error(tmp_path):
    path = str(tmp_path / "queue.json")
    queue_add(_item("j-t"), path)
    queue_mark_sent("nonexistent", path)  # should not raise

def test_queue_mark_sent_does_not_affect_others(tmp_path):
    path = str(tmp_path / "queue.json")
    queue_add(_item("j-u1"), path); queue_add(_item("j-u2"), path)
    queue_approve(["j-u1"], path); queue_mark_sent("j-u1", path)
    items = {i.job_id: i for i in queue_review(path)}
    assert items["j-u1"].status == "sent"
    assert items["j-u2"].status == "prepared"
