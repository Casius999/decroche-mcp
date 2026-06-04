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

# ── Load ATS quirks ─────────────────────────────────────────────────────────────────────────

_DATA_DIR = Path(__file__).parent.parent / "data"
_QUIRKS_PATH = _DATA_DIR / "ats_quirks.json"

with _QUIRKS_PATH.open(encoding="utf-8") as _f:
    _ATS_QUIRKS: dict[str, dict] = json.load(_f)

VALID_ATS_IDS: list[str] = sorted(_ATS_QUIRKS.keys())

# ── Severity penalty weights ────────────────────────────────────────────────────────────────────

_SEVERITY_PENALTY = {
    "CRITICAL": 30,
    "HIGH": 18,
    "MEDIUM": 8,
    "LOW": 3,
}

# ── Section-heading canonical check ──────────────────────────────────────────────────

# Common non-canonical headings users actually use.
# NOTE: This set intentionally includes French variants so they can be
# matched — but _has_noncanon_heading now also accepts FR canonical headings
# (via cv.parse.HEADINGS aliases) so an honest FR CV is not penalised.
_COMMON_NONCANON = {
    "work experience",
    "professional experience",
    "employment history",
    "expérience",
    "expériences professionnelles",
    "expérience professionnelle",
    "formation",
    "diplômes",
    "diplomes",
    "études",
    "compétences",
    "compétences techniques",
    "aptitudes",
    "about me",
    "profil",
    "à propos",
    "certifications & licenses",
    "licences",
    "langues",
}


# Precompute the full set of accent-stripped aliases from cv.parse.HEADINGS.
# This lets us recognise FR canonical headings as valid without penalising them.
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
    """Return True if the text contains non-canonical headings the ATS won't parse.

    Locale-aware: FR canonical headings recognised by cv.parse.HEADINGS (e.g.
    Expérience, Compétences, Formation, Langues) are accepted even when the ATS
    canonical list is English-only.  Only headings that are neither in the ATS
    canonical list NOR in the shared bilingual alias map trigger a breakage.
    """
    from decroche.cv.parse import _strip_accents

    canon_lower = {_strip_accents(h.lower()) for h in canonical}

    for line in text.splitlines():
        stripped_raw = line.strip().rstrip(":").strip()
        stripped = _strip_accents(stripped_raw.lower())
        if stripped in _COMMON_NONCANON and stripped not in canon_lower:
            # Accept if it matches any bilingual alias (e.g. FR canonical)
            if stripped in _CV_PARSE_ALIASES:
                continue
            return True
    return False


# ── Bad-date breakage detector ─────────────────────────────────────────────────────────────────

# Map of ATS date_formats_fail token → detection regex.
# "YYYY" means a year-only date range like "2019-2021".  A bare year that
#   appears as part of "Mon YYYY" (e.g. "Jan 2020") is valid and not flagged.
# "ongoing"/"current"/"present" mean those literal words as a date value.
# "season" means seasonal references: fall/spring/summer/winter.

# Matches abbreviated or full month names in EN/FR (used to filter out Mon YYYY).
_MONTH_NAME_RE = re.compile(
    r"(?:jan(?:uary|vier)?|feb(?:ruary)?|f[eé]vr?(?:ier)?|mar(?:ch|s)?|"
    r"apr(?:il)?|avr(?:il)?|may|mai|jun(?:e)?|juin?|"
    r"jul(?:y)?|juil(?:let)?|aug(?:ust)?|ao[uû]t?|"
    r"sep(?:tember|tembre)?|oct(?:ober|obre)?|nov(?:ember|embre)?|"
    r"dec(?:ember|embre)?|d[eé]c(?:embre)?)"
    r"\\?.\\s+((19|20)\\d{2})\\b",
    re.IGNORECASE,
)

# Year-only range: "2019-2021", "2019 – 2021" etc.
_YEAR_RANGE_RE = re.compile(
    r"\b(19|20)\d{2}\s*[-–—]\s*(19|20)\d{2}\b",
    re.IGNORECASE,
)


def _has_year_only_dates(text: str) -> bool:
    """Return True if text contains year-only date ranges (e.g. 2019-2021).

    Years that appear as part of 'Mon YYYY' (e.g. 'Jan 2020') are excluded.
    """
    # Collect all years in Mon-YYYY context; exclude them from range check.
    mon_years: set[str] = set()
    for m in _MONTH_NAME_RE.finditer(text):
        mon_years.add(m.group(1))  # the YYYY part

    for m in _YEAR_RANGE_RE.finditer(text):
        y1, y2 = m.group(1), m.group(2)
        # Flag if neither year is part of a Mon-YYYY pairing
        if y1 not in mon_years and y2 not in mon_years:
            return True
    return False


_DATE_FAIL_PATTERNS: dict[str, re.Pattern | None] = {
    "YYYY": None,  # handled by _has_year_only_dates — not a simple regex
    "'YY": re.compile(r"'\d{2}\b", re.IGNORECASE),
    "season": re.compile(
        r"\b(spring|summer|fall|autumn|winter|printemps|été|automne|hiver)\b",
        re.IGNORECASE,
    ),
    "ongoing": re.compile(r"\bongoing\b", re.IGNORECASE),
    "current": re.compile(r"\bcurrent\b", re.IGNORECASE),
    "present": re.compile(r"\bpresent\b", re.IGNORECASE),
    "inconsistency": None,  # structural; cannot detect from text alone
}


def _check_bad_dates(raw_text: str, date_formats_fail: list[str]) -> Breakage | None:
    """Detect date formats that the ATS lists as failing.

    Scans raw_text for patterns corresponding to each token in
    date_formats_fail.  "YYYY" is handled by _has_year_only_dates which
    excludes years that are part of valid 'Mon YYYY' pairs.  Other tokens use
    direct regex.  Returns a single MEDIUM Breakage when any match is found.
    """
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
            continue  # "inconsistency" or unknown — skip text-based detection
        m = pattern.search(raw_text)
        if m:
            return Breakage(
                type="bad_dates",
                location="date fields",
                severity="MEDIUM",
                fix="Use 'Mon YYYY' dates (e.g. Jan 2020) to avoid ATS parse failures.",
            )
    return None


# ── Breakage detectors ────────────────────────────────────────────────────────────────────────


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


# ── Main entry point ─────────────────────────────────────────────────────────────────────────────


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
        raise ValueError(f"Unknown ATS id: {ats_id!r}. Valid ids: {VALID_ATS_IDS}")

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

    # ── Collect breakages ────────────────────────────────────────────────────────────────────────────
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

    # Non-canonical section headings (locale-aware)
    canonical = rules.get("section_headings_canonical", [])
    if raw_text and _has_noncanon_heading(raw_text, canonical):
        breakages.append(
            Breakage(
                type="dropped_section",
                location="section headings",
                severity="MEDIUM",
                fix=("Use canonical section headings: " + ", ".join(canonical) + "."),
            )
        )

    # Bad date formats per ATS quirks
    date_formats_fail = rules.get("date_formats_fail", [])
    if raw_text and date_formats_fail:
        bad_dates_b = _check_bad_dates(raw_text, date_formats_fail)
        if bad_dates_b:
            breakages.append(bad_dates_b)

    # ── Fields extracted / lost ──────────────────────────────────────────────────────────────────────────
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

    # ── Parsability score ──────────────────────────────────────────────────────────────────────────
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
