"""ATS parse simulation: simulate how a given ATS parses a CV file.

Returns an AtsParseResult with parsability_score, breakages, fields_extracted/lost.
Pure deterministic logic — no LLM, no network.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from decroche.ats.structure import DocStructure, analyze_file
from decroche.models import AtsParseResult, Breakage

# ── Load ATS quirks ────────────────────────────────────────────────────────────────

_DATA_DIR = Path(__file__).parent.parent / "data"
_QUIRKS_PATH = _DATA_DIR / "ats_quirks.json"

with _QUIRKS_PATH.open(encoding="utf-8") as _f:
    _ATS_QUIRKS: dict[str, dict] = json.load(_f)

VALID_ATS_IDS: list[str] = sorted(_ATS_QUIRKS.keys())

# ── Severity penalty weights ─────────────────────────────────────────────────────

_SEVERITY_PENALTY = {
    "CRITICAL": 30,
    "HIGH": 18,
    "MEDIUM": 8,
    "LOW": 3,
}

# ── Section-heading canonical check ────────────────────────────────────────────

_COMMON_NONCANON = {
    "work experience", "professional experience", "employment history",
    "expérience", "expériences professionnelles", "expérience professionnelle",
    "formation", "diplômes", "diplomes", "études",
    "compétences", "compétences techniques", "aptitudes",
    "about me", "profil", "à propos",
    "certifications & licenses", "licences",
    "langues",
}

def _build_canonical_aliases() -> frozenset[str]:
    try:
        from decroche.cv.parse import HEADINGS, _strip_accents
        aliases: set[str] = set()
        for _key, alias_list in HEADINGS.items():
            for a in alias_list:
                aliases.add(_strip_accents(a.lower()))
        return frozenset(aliases)
    except Exception:  # noqa: BLE001
        return frozenset()

_CV_PARSE_ALIASES: frozenset[str] = _build_canonical_aliases()


def _has_noncanon_heading(text: str, canonical: list[str]) -> bool:
    from decroche.cv.parse import _strip_accents

    canon_lower = {_strip_accents(h.lower()) for h in canonical}

    for line in text.splitlines():
        stripped_raw = line.strip().rstrip(":").strip()
        stripped = _strip_accents(stripped_raw.lower())
        if stripped in _COMMON_NONCANON and stripped not in canon_lower:
            if stripped in _CV_PARSE_ALIASES:
                continue
            return True
    return False


# ── Bad-date breakage detector ─────────────────────────────────────────────────

_MONTH_NAME_RE = re.compile(
    r"(?:jan(?:uary|vier)?|feb(?:ruary)?|f[eé]vr?(?:ier)?|mar(?:ch|s)?|"
    r"apr(?:il)?|avr(?:il)?|may|mai|jun(?:e)?|juin?|"
    r"jul(?:y)?|juil(?:let)?|aug(?:ust)?|ao[uû]t?|"
    r"sep(?:tember|tembre)?|oct(?:ober|obre)?|nov(?:ember|embre)?|"
    r"dec(?:ember|embre)?|d[eé]c(?:embre)?)"
    r"\.?\s+((19|20)\d{2})\b",
    re.IGNORECASE,
)

_YEAR_RANGE_RE = re.compile(
    r"\b(19|20)\d{2}\s*[-–—]\s*(19|20)\d{2}\b",
    re.IGNORECASE,
)


def _has_year_only_dates(text: str) -> bool:
    mon_years: set[str] = set()
    for m in _MONTH_NAME_RE.finditer(text):
        mon_years.add(m.group(1))

    for m in _YEAR_RANGE_RE.finditer(text):
        y1, y2 = m.group(1), m.group(2)
        if y1 not in mon_years and y2 not in mon_years:
            return True
    return False


_DATE_FAIL_PATTERNS: dict[str, re.Pattern | None] = {
    "YYYY": None,
    "'YY": re.compile(r"'\d{2}\b", re.IGNORECASE),
    "season": re.compile(
        r"\b(spring|summer|fall|autumn|winter|printemps|été|automne|hiver)\b",
        re.IGNORECASE,
    ),
    "ongoing": re.compile(r"\bongoing\b", re.IGNORECASE),
    "current":  re.compile(r"\bcurrent\b", re.IGNORECASE),
    "present":  re.compile(r"\bpresent\b", re.IGNORECASE),
    "inconsistency": None,
}


def _check_bad_dates(raw_text: str, date_formats_fail: list[str]) -> Breakage | None:
    for token in date_formats_fail:
        if token == "YYYY":
            if _has_year_only_dates(raw_text):
                return Breakage(
                    type="bad_dates",
                    location="date fields",
                    severity="MEDIUM",
                    fix="Use 'Mon YYYY' dates (e.g. Jan 2020) to avoid ATS parse failures.",
                )
            continue

        pattern = _DATE_FAIL_PATTERNS.get(token)
        if pattern is None:
            continue
        m = pattern.search(raw_text)
        if m:
            return Breakage(
                type="bad_dates",
                location="date fields",
                severity="MEDIUM",
                fix="Use 'Mon YYYY' dates (e.g. Jan 2020) to avoid ATS parse failures.",
            )
    return None


# ── Breakage detectors ──────────────────────────────────────────────────────────────

def _check_two_column(
    structure: DocStructure,
    rules: dict,
    text: str,
) -> Breakage | None:
    if structure.fmt not in ("pdf",):
        return None
    if structure.columns < 2:
        return None
    col_behavior = rules.get("column_behavior", "concatenate_lr")
    if col_behavior in ("best", "moderate"):
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
        return None
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

    try:
        from decroche.cv.parse import extract_text
        raw_text = extract_text(p, raw)
    except Exception:  # noqa: BLE001
        raw_text = ""

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

    date_formats_fail = rules.get("date_formats_fail", [])
    if raw_text and date_formats_fail:
        bad_dates_b = _check_bad_dates(raw_text, date_formats_fail)
        if bad_dates_b:
            breakages.append(bad_dates_b)

    fields_lost: list[str] = []
    if contact_lost:
        fields_lost.append("contact")

    if two_col and rules.get("column_behavior") == "omit_secondary":
        fields_lost.append("secondary_column_content")

    fields_extracted: dict[str, bool] = {
        "contact": "contact" not in fields_lost,
        "experience": True,
        "education": True,
        "skills": True,
    }

    fidelity = rules.get("parse_fidelity", {})
    if structure.columns >= 2 and "two_col" in fidelity:
        base = fidelity["two_col"] * 100
    else:
        base = fidelity.get("single_col", 0.85) * 100

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
