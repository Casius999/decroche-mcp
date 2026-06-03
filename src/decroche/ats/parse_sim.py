"""ATS parse simulation: simulate how a given ATS parses a CV file.

Returns an AtsParseResult with parsability_score, breakages, fields_extracted/lost.
Pure deterministic logic — no LLM, no network.
"""
from __future__ import annotations

import json
from pathlib import Path

from decroche.ats.structure import DocStructure, analyze_file
from decroche.models import AtsParseResult, Breakage

# ── Load ATS quirks ──────────────────────────────────────────────────────────

_DATA_DIR = Path(__file__).parent.parent / "data"
_QUIRKS_PATH = _DATA_DIR / "ats_quirks.json"

with _QUIRKS_PATH.open(encoding="utf-8") as _f:
    _ATS_QUIRKS: dict[str, dict] = json.load(_f)

VALID_ATS_IDS: list[str] = sorted(_ATS_QUIRKS.keys())

# ── Severity penalty weights ─────────────────────────────────────────────────

_SEVERITY_PENALTY = {
    "CRITICAL": 30,
    "HIGH": 18,
    "MEDIUM": 8,
    "LOW": 3,
}

# ── Section-heading canonical check ─────────────────────────────────────────

# Common non-canonical headings users actually use
_COMMON_NONCANON = {
    "work experience", "professional experience", "employment history",
    "expérience", "expériences professionnelles", "expérience professionnelle",
    "formation", "diplômes", "diplomes", "études",
    "compétences", "compétences techniques", "aptitudes",
    "about me", "profil", "à propos",
    "certifications & licenses", "licences",
    "langues",
}


def _has_noncanon_heading(text: str, canonical: list[str]) -> bool:
    """Return True if the text contains section headings that are NOT canonical."""
    # Normalise canonical set to lowercase
    canon_lower = {h.lower() for h in canonical}
    for line in text.splitlines():
        stripped = line.strip().rstrip(":").strip().lower()
        if stripped in _COMMON_NONCANON and stripped not in canon_lower:
            return True
    return False


# ── Breakage detectors ───────────────────────────────────────────────────────

def _check_two_column(
    structure: DocStructure,
    rules: dict,
    text: str,
) -> Breakage | None:
    if structure.fmt not in ("pdf",):
        # Two-column detection only meaningful for PDF; DOCX is always single-col logically
        return None
    if structure.columns < 2:
        return None
    col_behavior = rules.get("column_behavior", "concatenate_lr")
    if col_behavior in ("best", "moderate"):
        # These ATS handle two-column tolerably — only LOW/MEDIUM
        sev = "MEDIUM"
    elif col_behavior == "omit_secondary":
        sev = "HIGH"
    elif col_behavior in ("concatenate_lr", "scramble"):
        sev = "HIGH"
    else:
        sev = "MEDIUM"
    return Breakage(
        type="two_column",
        location="page layout",
        severity=sev,
        fix="Reformat as a single-column layout to avoid ATS misreading or content omission.",
    )


def _check_table(structure: DocStructure, rules: dict) -> Breakage | None:
    if not structure.has_tables:
        return None
    table_behavior = rules.get("table_behavior", "scramble")
    if table_behavior in ("tolerant",):
        return None  # No breakage for tolerant ATS
    if table_behavior == "risky":
        sev = "MEDIUM"
    elif table_behavior in ("scramble", "merge"):
        sev = "HIGH"
    else:
        sev = "MEDIUM"
    return Breakage(
        type="table",
        location="table(s) in document",
        severity=sev,
        fix="Replace all tables with plain-text lists or paragraphs to guarantee correct parsing.",
    )


def _check_header_contact(
    structure: DocStructure,
    rules: dict,
) -> tuple[Breakage | None, bool]:
    """Return (breakage_or_none, contact_will_be_lost)."""
    if not structure.contact_in_header:
        return None, False
    hf_behavior = rules.get("header_footer", "stripped")
    if hf_behavior == "stripped":
        return (
            Breakage(
                type="header_contact",
                location="document header",
                severity="CRITICAL",
                fix="Move all contact information (email, phone) into the main body of the CV.",
            ),
            True,
        )
    if hf_behavior in ("ignored", "risky"):
        return (
            Breakage(
                type="header_contact",
                location="document header",
                severity="HIGH",
                fix="Move contact information to the document body — header content may be ignored.",
            ),
            True,
        )
    # partial / readable — flag as LOW
    return (
        Breakage(
            type="header_contact",
            location="document header",
            severity="LOW",
            fix="Consider moving contact info to body for maximum compatibility.",
        ),
        False,
    )


def _check_scanned(structure: DocStructure) -> Breakage | None:
    if structure.total_chars > 0 and structure.page_count > 0:
        chars_per_page = structure.total_chars / structure.page_count
        if chars_per_page < 50:
            return Breakage(
                type="scanned",
                location="entire document",
                severity="CRITICAL",
                fix="The CV appears to be a scanned image. Use a text-based PDF with selectable text.",
            )
    return None


def _check_oversized(structure: DocStructure, rules: dict, file_size_mb: float) -> Breakage | None:
    max_mb = rules.get("max_file_mb", 2.0)
    if file_size_mb > max_mb:
        return Breakage(
            type="oversized",
            location="file",
            severity="HIGH",
            fix=f"Reduce file size below {max_mb} MB (current: {file_size_mb:.1f} MB).",
        )
    return None


# ── Main entry point ─────────────────────────────────────────────────────────

def parse_sim(
    path: str | Path,
    ats_id: str,
    fmt: str | None = None,
    data: bytes | None = None,
) -> AtsParseResult:
    """Simulate how a given ATS parses the CV file at *path*.

    Args:
        path: Path to the CV file (PDF, DOCX, TXT, MD).
        ats_id: ATS identifier from ats_quirks.json (or "generic").
        fmt: Optional format override ("pdf", "docx", "txt", "md").
        data: Optional raw bytes (if already loaded).

    Returns:
        AtsParseResult with parsability_score, breakages, fields_extracted/lost.

    Raises:
        ValueError: If ats_id is not in ats_quirks.json.
    """
    if ats_id not in _ATS_QUIRKS:
        raise ValueError(
            f"Unknown ATS id: {ats_id!r}. Valid ids: {VALID_ATS_IDS}"
        )

    rules = _ATS_QUIRKS[ats_id]
    p = Path(path)
    raw = data if data is not None else p.read_bytes()
    file_size_mb = len(raw) / (1024 * 1024)

    structure = analyze_file(p, raw)
    detected_fmt = fmt or structure.fmt

    # Also get raw text for heading check
    try:
        from decroche.cv.parse import extract_text
        raw_text = extract_text(p, raw)
    except Exception:  # noqa: BLE001
        raw_text = ""

    # ── Collect breakages ────────────────────────────────────────────────────
    breakages: list[Breakage] = []

    two_col = _check_two_column(structure, rules, raw_text)
    if two_col:
        breakages.append(two_col)

    table_b = _check_table(structure, rules)
    if table_b:
        breakages.append(table_b)

    hdr_b, contact_lost = _check_header_contact(structure, rules)
    if hdr_b:
        breakages.append(hdr_b)

    scanned_b = _check_scanned(structure)
    if scanned_b:
        breakages.append(scanned_b)

    oversized_b = _check_oversized(structure, rules, file_size_mb)
    if oversized_b:
        breakages.append(oversized_b)

    # Non-canonical section headings
    canonical = rules.get("section_headings_canonical", [])
    if raw_text and _has_noncanon_heading(raw_text, canonical):
        breakages.append(Breakage(
            type="dropped_section",
            location="section headings",
            severity="MEDIUM",
            fix=(
                "Use canonical section headings: "
                + ", ".join(canonical)
                + "."
            ),
        ))

    # ── Fields extracted / lost ──────────────────────────────────────────────
    fields_lost: list[str] = []
    if contact_lost:
        fields_lost.append("contact")

    # Two-column for lever → second column omitted (may lose skills)
    if two_col and rules.get("column_behavior") == "omit_secondary":
        fields_lost.append("secondary_column_content")

    fields_extracted: dict[str, bool] = {
        "contact": "contact" not in fields_lost,
        "experience": True,
        "education": True,
        "skills": True,
    }

    # ── Parsability score ────────────────────────────────────────────────────
    # Base from ATS single_col fidelity × 100
    fidelity = rules.get("parse_fidelity", {})
    if structure.columns >= 2 and "two_col" in fidelity:
        base = fidelity["two_col"] * 100
    else:
        base = fidelity.get("single_col", 0.85) * 100

    # Subtract weighted penalty for each breakage
    penalty = sum(_SEVERITY_PENALTY.get(b.severity, 8) for b in breakages)
    score = max(0.0, min(100.0, base - penalty))

    return AtsParseResult(
        ats_id=ats_id,
        fmt=detected_fmt,
        parsability_score=score,
        fields_extracted=fields_extracted,
        fields_lost=fields_lost,
        breakages=breakages,
    )
