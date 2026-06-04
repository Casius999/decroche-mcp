"""Tests for source.monitor — snapshot + diff, no network."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from decroche.models import JobPosting, MonitorDiff
from decroche.source.monitor import monitor_diff, monitor_snapshot
from decroche.source.providers import greenhouse


def _raw_greenhouse(job_ids: list[str]) -> dict:
    return {
        "jobs": [
            {
                "id": jid,
                "title": f"Job {jid}",
                "absolute_url": f"https://boards.greenhouse.io/acme/jobs/{jid}",
                "content": "A job.",
                "location": {"name": "Paris"},
            }
            for jid in job_ids
        ]
    }


class TestMonitorSnapshot:
    @pytest.mark.asyncio
    async def test_creates_snapshot_file(self, monkeypatch, tmp_path):
        monkeypatch.setattr(greenhouse, "fetch", AsyncMock(return_value=_raw_greenhouse(["id1", "id2"])))
        out = str(tmp_path / "snap.json")
        result = await monitor_snapshot("greenhouse", "acme", out)
        assert Path(out).exists()
        assert result["job_count"] == 2
        assert result["provider"] == "greenhouse"

    @pytest.mark.asyncio
    async def test_snapshot_contains_job_ids(self, monkeypatch, tmp_path):
        monkeypatch.setattr(greenhouse, "fetch", AsyncMock(return_value=_raw_greenhouse(["id1", "id2", "id3"])))
        out = str(tmp_path / "snap.json")
        await monitor_snapshot("greenhouse", "acme", out)
        data = json.loads(Path(out).read_text(encoding="utf-8"))
        assert set(data["job_ids"]) == {"id1", "id2", "id3"}

    @pytest.mark.asyncio
    async def test_snapshot_provider_and_key_stored(self, monkeypatch, tmp_path):
        monkeypatch.setattr(greenhouse, "fetch", AsyncMock(return_value=_raw_greenhouse(["id1"])))
        out = str(tmp_path / "snap.json")
        await monitor_snapshot("greenhouse", "mytoken", out)
        data = json.loads(Path(out).read_text(encoding="utf-8"))
        assert data["provider"] == "greenhouse"
        assert data["key"] == "mytoken"

    @pytest.mark.asyncio
    async def test_snapshot_summary_dict_keys(self, monkeypatch, tmp_path):
        monkeypatch.setattr(greenhouse, "fetch", AsyncMock(return_value=_raw_greenhouse(["id1"])))
        out = str(tmp_path / "snap.json")
        result = await monitor_snapshot("greenhouse", "acme", out)
        for k in ("provider", "key", "job_count", "snapshot_path"):
            assert k in result


class TestMonitorDiff:
    @pytest.mark.asyncio
    async def test_no_new_jobs_empty_diff(self, monkeypatch, tmp_path):
        monkeypatch.setattr(greenhouse, "fetch", AsyncMock(return_value=_raw_greenhouse(["id1", "id2"])))
        snap = str(tmp_path / "snap.json")
        await monitor_snapshot("greenhouse", "acme", snap)
        result = await monitor_diff("greenhouse", "acme", snap)
        assert isinstance(result, MonitorDiff)
        assert result.new_count == 0
        assert result.total_count == 2

    @pytest.mark.asyncio
    async def test_one_new_job_detected(self, monkeypatch, tmp_path):
        monkeypatch.setattr(greenhouse, "fetch", AsyncMock(return_value=_raw_greenhouse(["id1", "id2"])))
        snap = str(tmp_path / "snap.json")
        await monitor_snapshot("greenhouse", "acme", snap)
        monkeypatch.setattr(greenhouse, "fetch", AsyncMock(return_value=_raw_greenhouse(["id1", "id2", "id3"])))
        result = await monitor_diff("greenhouse", "acme", snap)
        assert result.new_count == 1
        assert result.new_jobs[0].source_id == "id3"

    @pytest.mark.asyncio
    async def test_multiple_new_jobs_detected(self, monkeypatch, tmp_path):
        monkeypatch.setattr(greenhouse, "fetch", AsyncMock(return_value=_raw_greenhouse(["id1"])))
        snap = str(tmp_path / "snap.json")
        await monitor_snapshot("greenhouse", "acme", snap)
        monkeypatch.setattr(greenhouse, "fetch", AsyncMock(return_value=_raw_greenhouse(["id1", "id2", "id3", "id4"])))
        result = await monitor_diff("greenhouse", "acme", snap)
        assert result.new_count == 3
        assert {j.source_id for j in result.new_jobs} == {"id2", "id3", "id4"}

    @pytest.mark.asyncio
    async def test_removed_jobs_not_in_diff(self, monkeypatch, tmp_path):
        monkeypatch.setattr(greenhouse, "fetch", AsyncMock(return_value=_raw_greenhouse(["id1", "id2"])))
        snap = str(tmp_path / "snap.json")
        await monitor_snapshot("greenhouse", "acme", snap)
        monkeypatch.setattr(greenhouse, "fetch", AsyncMock(return_value=_raw_greenhouse(["id1", "id3"])))
        result = await monitor_diff("greenhouse", "acme", snap)
        assert result.new_count == 1
        assert result.new_jobs[0].source_id == "id3"

    @pytest.mark.asyncio
    async def test_missing_snapshot_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            await monitor_diff("greenhouse", "acme", str(tmp_path / "nonexistent.json"))

    @pytest.mark.asyncio
    async def test_new_jobs_are_job_posting_instances(self, monkeypatch, tmp_path):
        monkeypatch.setattr(greenhouse, "fetch", AsyncMock(return_value=_raw_greenhouse(["id1"])))
        snap = str(tmp_path / "snap.json")
        await monitor_snapshot("greenhouse", "acme", snap)
        monkeypatch.setattr(greenhouse, "fetch", AsyncMock(return_value=_raw_greenhouse(["id1", "id2"])))
        result = await monitor_diff("greenhouse", "acme", snap)
        assert all(isinstance(j, JobPosting) for j in result.new_jobs)


class TestMonitorInvalidProvider:
    @pytest.mark.asyncio
    async def test_unknown_provider_raises(self, tmp_path):
        with pytest.raises(ValueError, match="Unknown monitor provider"):
            await monitor_snapshot("unknown_provider", "key", str(tmp_path / "snap.json"))
