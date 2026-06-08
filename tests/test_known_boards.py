"""Tests for src/decroche/data/known_boards.yaml structure and content.

Rules:
- Minimum 50 rows, maximum 200.
- Every row has: provider, token, company.
- Allowed providers: greenhouse | lever | ashby | recruitee.
- No duplicate (provider, token) pair.
- Minimum count per provider: greenhouse>=10, lever>=5, ashby>=5, recruitee>=5.
"""

from __future__ import annotations

from pathlib import Path

import yaml

_YAML_PATH = (
    Path(__file__).parent.parent / "src" / "decroche" / "data" / "known_boards.yaml"
)

ALLOWED_PROVIDERS = {"greenhouse", "lever", "ashby", "recruitee"}


def _load() -> list[dict]:
    return yaml.safe_load(_YAML_PATH.read_text(encoding="utf-8")) or []


# ── structure ─────────────────────────────────────────────────────────────────


class TestKnownBoardsStructure:
    def test_file_exists(self):
        assert _YAML_PATH.exists(), f"File not found: {_YAML_PATH}"

    def test_is_list(self):
        assert isinstance(_load(), list)

    def test_min_rows(self):
        rows = _load()
        assert len(rows) >= 50, f"Expected ≥50 rows, got {len(rows)}"

    def test_max_rows(self):
        rows = _load()
        assert len(rows) <= 200, f"Expected ≤200 rows, got {len(rows)}"

    def test_required_keys_present(self):
        for i, row in enumerate(_load()):
            for key in ("provider", "token", "company"):
                assert key in row, f"Row {i} missing key {key!r}: {row}"

    def test_no_empty_token(self):
        for i, row in enumerate(_load()):
            assert row.get("token"), f"Row {i} has empty/missing token: {row}"

    def test_no_empty_company(self):
        for i, row in enumerate(_load()):
            assert row.get("company"), f"Row {i} has empty/missing company: {row}"

    def test_allowed_providers_only(self):
        for i, row in enumerate(_load()):
            provider = row.get("provider", "")
            assert provider in ALLOWED_PROVIDERS, (
                f"Row {i} has unknown provider {provider!r}. Allowed: {ALLOWED_PROVIDERS}"
            )

    def test_no_duplicate_provider_token(self):
        seen: set[tuple] = set()
        for i, row in enumerate(_load()):
            key = (row.get("provider"), row.get("token"))
            assert key not in seen, f"Duplicate (provider, token) at row {i}: {key}"
            seen.add(key)


# ── per-provider minimums ─────────────────────────────────────────────────────


class TestKnownBoardsRows:
    def _counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for row in _load():
            p = row.get("provider", "")
            counts[p] = counts.get(p, 0) + 1
        return counts

    def test_greenhouse_min_10(self):
        counts = self._counts()
        assert counts.get("greenhouse", 0) >= 10, (
            f"Expected ≥10 greenhouse rows, got {counts.get('greenhouse', 0)}"
        )

    def test_lever_min_5(self):
        counts = self._counts()
        assert counts.get("lever", 0) >= 5, (
            f"Expected ≥5 lever rows, got {counts.get('lever', 0)}"
        )

    def test_ashby_min_5(self):
        counts = self._counts()
        assert counts.get("ashby", 0) >= 5, (
            f"Expected ≥5 ashby rows, got {counts.get('ashby', 0)}"
        )

    def test_recruitee_min_5(self):
        counts = self._counts()
        assert counts.get("recruitee", 0) >= 5, (
            f"Expected ≥5 recruitee rows, got {counts.get('recruitee', 0)}"
        )
