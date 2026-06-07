"""negotiate.benchmark — Salary range lookup from bundled YAML dataset.

Deterministic, no network. Performs exact match first, then falls back to
closest available match (same role_family and region, closest seniority).
"""

from __future__ import annotations

from pathlib import Path

import yaml

from decroche.models import SalaryRange

_DATA_DIR = Path(__file__).parent.parent / "data"
_DEFAULT_YAML = _DATA_DIR / "salary_benchmarks.yaml"

_SENIORITY_ORDER = ["junior", "mid", "senior", "lead"]


def _load(yaml_path: Path) -> list[dict]:
    raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    return raw if isinstance(raw, list) else []


def _seniority_distance(a: str, b: str) -> int:
    """Return absolute index distance between two seniority levels."""
    idx_a = _SENIORITY_ORDER.index(a) if a in _SENIORITY_ORDER else 99
    idx_b = _SENIORITY_ORDER.index(b) if b in _SENIORITY_ORDER else 99
    return abs(idx_a - idx_b)


def benchmark_range(
    role_family: str,
    seniority: str,
    region: str,
    yaml_path: str | Path | None = None,
) -> SalaryRange:
    """Return the salary benchmark for a given role/seniority/region.

    Tries an exact match first. If none found, returns the closest entry
    (same role_family + region, nearest seniority) with ``approximate=True``
    and a descriptive ``note``.

    Args:
        role_family: e.g. ``"software"``, ``"data"``, ``"product"``, ``"sales"``.
        seniority:   One of ``"junior"``, ``"mid"``, ``"senior"``, ``"lead"``.
        region:      One of ``"fr"``, ``"us"``, ``"uk"``, ``"ca"``.
        yaml_path:   Override YAML path (for testing).

    Returns:
        SalaryRange.

    Raises:
        LookupError: if no entry matches even approximately.
    """
    path = Path(yaml_path) if yaml_path else _DEFAULT_YAML
    rows = _load(path)

    rf = role_family.lower().strip()
    sn = seniority.lower().strip()
    rg = region.lower().strip()

    # ── exact match ──────────────────────────────────────────────────────────────────────────
    for row in rows:
        if (
            row.get("role_family", "").lower() == rf
            and row.get("seniority", "").lower() == sn
            and row.get("region", "").lower() == rg
        ):
            return SalaryRange(
                role_family=row["role_family"],
                seniority=row["seniority"],
                region=row["region"],
                currency=row["currency"],
                p25=row["p25"],
                p50=row["p50"],
                p75=row["p75"],
                variable_pct=float(row.get("variable_pct", 0.0)),
                source=row.get("source", ""),
                approximate=bool(row.get("approximate", False)),
                note="",
            )

    # ── closest match (same role_family + region, nearest seniority) ─────────────────
    candidates = [
        row
        for row in rows
        if row.get("role_family", "").lower() == rf and row.get("region", "").lower() == rg
    ]

    if not candidates:
        # Widen: same role_family, any region
        candidates = [row for row in rows if row.get("role_family", "").lower() == rf]

    if not candidates:
        raise LookupError(
            f"No salary benchmark found for role_family={rf!r}, region={rg!r}. "
            "Check the salary_benchmarks.yaml dataset."
        )

    best = min(
        candidates,
        key=lambda r: _seniority_distance(r.get("seniority", ""), sn),
    )

    note = (
        f"Approx. — requested seniority={sn!r} not in dataset for "
        f"role_family={rf!r}, region={rg!r}. "
        f"Returning nearest match (seniority={best.get('seniority')!r})."
    )

    return SalaryRange(
        role_family=best["role_family"],
        seniority=best["seniority"],
        region=best["region"],
        currency=best["currency"],
        p25=best["p25"],
        p50=best["p50"],
        p75=best["p75"],
        variable_pct=float(best.get("variable_pct", 0.0)),
        source=best.get("source", ""),
        approximate=True,
        note=note,
    )
