"""Tests for decroche/storage.py — data-root path confinement."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastmcp.exceptions import ToolError

from decroche.storage import resolve_data_path


# ── helpers ────────────────────────────────────────────────────────────────────


def _with_data_dir(monkeypatch, tmp_path: Path):
    """Set DECROCHE_DATA_DIR to a tmp subdir and return it."""
    data_dir = tmp_path / "data_root"
    data_dir.mkdir()
    monkeypatch.setenv("DECROCHE_DATA_DIR", str(data_dir))
    return data_dir


# ── traversal blocked ───────────────────────────────────────────────────────


class TestTraversalBlocked:
    def test_dotdot_etc_passwd_blocked(self, monkeypatch, tmp_path):
        """Relative path with .. traversal escaping data root is blocked."""
        _with_data_dir(monkeypatch, tmp_path)
        with pytest.raises(ToolError, match="escapes data root"):
            resolve_data_path("../../etc/passwd")

    def test_dotdot_windows_style_blocked(self, monkeypatch, tmp_path):
        _with_data_dir(monkeypatch, tmp_path)
        with pytest.raises(ToolError, match="escapes data root"):
            resolve_data_path("..\\..\\windows\\system32\\hosts")

    def test_single_dotdot_blocked(self, monkeypatch, tmp_path):
        _with_data_dir(monkeypatch, tmp_path)
        with pytest.raises(ToolError, match="escapes data root"):
            resolve_data_path("../sibling/file.json")


# ── relative paths resolved under base ──────────────────────────────────


class TestRelativeResolved:
    def test_plain_filename_resolves_under_base(self, monkeypatch, tmp_path):
        data_dir = _with_data_dir(monkeypatch, tmp_path)
        result = resolve_data_path("queue.json")
        assert result == data_dir / "queue.json"

    def test_relative_subpath_resolves_under_base(self, monkeypatch, tmp_path):
        data_dir = _with_data_dir(monkeypatch, tmp_path)
        result = resolve_data_path("sub/dir/store.json")
        assert result == data_dir / "sub" / "dir" / "store.json"

    def test_returned_path_is_absolute(self, monkeypatch, tmp_path):
        _with_data_dir(monkeypatch, tmp_path)
        result = resolve_data_path("myfile.db")
        assert result.is_absolute()

    def test_env_var_overrides_default(self, monkeypatch, tmp_path):
        data_dir = _with_data_dir(monkeypatch, tmp_path)
        result = resolve_data_path("test.json")
        assert str(result).startswith(str(data_dir))


# ── absolute tmp paths allowed (existing tests must stay green) ─────────────


class TestAbsoluteTmpAllowed:
    def test_tmp_path_absolute_allowed(self, monkeypatch, tmp_path):
        """An absolute path inside system tmp must NOT raise."""
        _with_data_dir(monkeypatch, tmp_path)
        file_in_tmp = tmp_path / "queue.json"
        # Should not raise
        result = resolve_data_path(str(file_in_tmp))
        assert result == file_in_tmp.resolve()

    def test_nested_tmp_path_allowed(self, monkeypatch, tmp_path):
        _with_data_dir(monkeypatch, tmp_path)
        nested = tmp_path / "subdir" / "crm.db"
        result = resolve_data_path(str(nested))
        assert result == nested.resolve()

    def test_data_root_absolute_path_allowed(self, monkeypatch, tmp_path):
        """An absolute path inside the data root itself is allowed."""
        data_dir = _with_data_dir(monkeypatch, tmp_path)
        inside = data_dir / "subdir" / "file.json"
        result = resolve_data_path(str(inside))
        assert result == inside.resolve()


# ── store integration: existing tests remain green ──────────────────────────


class TestQueueStoreGreen:
    """Confirm apply.queue still works with tmp_path absolute paths."""

    def test_queue_add_and_review(self, monkeypatch, tmp_path):
        _with_data_dir(monkeypatch, tmp_path)
        from decroche.apply.queue import queue_add, queue_review
        from decroche.models import PrefillPlan, QueueItem

        path = str(tmp_path / "queue.json")
        item = QueueItem(
            job_id="j-storage-test",
            apply_url="https://example.com/apply",
            prefill=PrefillPlan(apply_url="https://example.com/apply"),
        )
        queue_add(item, path)
        items = queue_review(path)
        assert len(items) == 1
        assert items[0].job_id == "j-storage-test"


class TestRecruiterStoreGreen:
    """Confirm recruiter.store still works with tmp_path absolute paths."""

    def test_store_recruiter(self, monkeypatch, tmp_path):
        _with_data_dir(monkeypatch, tmp_path)
        from decroche.models import Contact, Recruiter
        from decroche.recruiter.store import load_store, store_recruiter

        p = tmp_path / "store.json"
        r = Recruiter(name="Test Recruiter", kind="in_house")
        c = Contact(name="Test Recruiter", status="not_found", source="test")
        record = store_recruiter(r, c, p)
        assert record["pii"] is True
        records = load_store(str(p))
        assert len(records) == 1


class TestCrmGreen:
    """Confirm analytics.crm still works with tmp_path absolute paths."""

    def test_track_and_get(self, monkeypatch, tmp_path):
        _with_data_dir(monkeypatch, tmp_path)
        from decroche.analytics.crm import get, track
        from decroche.models import Application

        db = str(tmp_path / "crm.db")
        app = Application(id="app-storage-test", stage="saved")
        track(app, db)
        result = get("app-storage-test", db)
        assert result is not None
        assert result.stage == "saved"
