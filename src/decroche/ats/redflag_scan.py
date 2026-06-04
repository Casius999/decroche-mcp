"""Red-flag scanner for CVs.

Implements all flags defined in data/redflags.yaml.
Pure deterministic logic — no LLM, no network.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from decroche.models import JSONResume, MarketProfile, RedFlag

# ── Load assets ────────────────────────────────────────────────────────────────────────────

_DATA_DIR = Path(__file__).parent.parent / "data"


def _load_yaml(filename: str) -> Any:
    with (_DATA_DIR / filename).open(encoding="utf-8") as f:
        return yaml.safe_load(f)


_REDFLAGS_DEF: dict[str, dict] = {flag["id"]: flag for flag in _load_yaml("redflags.yaml")["flags"]}

_BANNED_WORDS_RAW = _load_yaml("banned_words.yaml")
_BANNED_WORDS: list[str] = [
    w.lower() for w in (_BANNED_WORDS_RAW.get("en", []) + _BANNED_WORDS_RAW.get("fr", []))
]

_STRONG_VERBS_RAW = _load_yaml("strong_verbs.yaml")
_STRONG_VERBS: set[str] = {
    v.lower() for v in (_STRONG_VERBS_RAW.get("en", []) + _STRONG_VERBS_RAW.get("fr", []))
}

# ── Constants ─────────────────────────────────────────────────────────────────────────────

# Markets where photos are forbidden
_PHOTO_FORBIDDEN_MARKETS = {"us", "uk", "ca", "ca-en"}
# Markets where DOB/nationality are forbidden
_PERSONAL_INFO_FORBIDDEN_MARKETS = {"us", "uk", "ca", "ca-en"}

# Patterns for passive voice: "was/were/been/a été/ont été + past participle"
_PASSIVE_RE = re.compile(
    r"\b(?:was|were|been|is|are|a été|ont été|est|sont)\b\s+\w+(?:ed|en|ied|ée?s?)\b",
    re.IGNORECASE,
)

# Generic/AI phrasing patterns
_AI_PHRASES = [
    r"\bresponsible for\b",
    r"\bworked on\b",
    r"\bhelped with\b",
    r"\bin order to\b",
    r"\bassisted with\b",
    r"\bparticipated in\b",
    r"\bcontributed to\b",
    r"\bwas involved in\b",
    r"\bsupported\b.*\bteam\b",
]
_AI_RE = re.compile("|".join(_AI_PHRASES), re.IGNORECASE)

# Metric patterns: percentages, €/$, numbers with units
_METRIC_RE = re.compile(
    r"\d+\s*%|\$[\d,]+|€[\d,]+|\d+[xX×]\b|\d+\s*(?:k|M|B|heures?|hours?|jours?|days?|mois|month)"
)

# Year-only date: exactly 4 digits, optionally surrounded by whitespace/punctuation
_YEAR_ONLY_RE = re.compile(r"(?<!\d)(\d{4})(?!\d)")
_FULL_DATE_RE = re.compile(
    r"\b(?:0?[1-9]|1[0-2])[\/\-]\d{4}\b|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|"
    r"jan|fev|mar|avr|mai|jun|jui|aou|sep|oct|nov|dec)[a-z]*[\s.,-]+\d{4}",
    re.IGNORECASE,
)

# Throwaway / non-professional email domains
_THROWAWAY_DOMAINS = {
    "mailinator.com",
    "guerrillamail.com",
    "trashmail.com",
    "yopmail.com",
    "sharklasers.com",
    "guerrillamailblock.com",
    "spam4.me",
    "trashmail.io",
    "throwam.com",
    "dispostable.com",
}

# Email patterns that look non-professional (local part)
_UNPROFESSIONAL_EMAIL_RE = re.compile(
    r"^(?:"
    r"[a-z]+[_.]?\d{2,}"  # word + 2+ digits
    r"|[a-z]*[xX]{2,}[a-z]*"  # xXx style
    r"|[a-z]+_?[a-z]+\d{2,}"  # letters then 2+ digits
    r"|.*(?:gamer|kool|leet|swag|xd|irl|pr0|pwn|noob|based).*"  # gaming terms
    r")$",
    re.IGNORECASE,
)


# ── Helpers ──────────────────────────────────────────────────────────────────────────────────


def _sev(flag_id: str) -> str:
    return _REDFLAGS_DEF.get(flag_id, {}).get("severity", "MEDIUM")


def _fix(flag_id: str) -> str:
    return _REDFLAGS_DEF.get(flag_id, {}).get(
        "description_en", "See redflags.yaml for remediation."
    )


def _make_flag(flag_id: str, location: str, evidence: str) -> RedFlag:
    return RedFlag(
        flag_id=flag_id,
        severity=_sev(flag_id),
        location=location,
        evidence=evidence,
        fix=_fix(flag_id),
    )


def _parse_date(date_str: str | None) -> tuple[int, int] | None:
    """Parse a date string like '2020-01', '2020', 'Jan 2020' → (year, month)."""
    if not date_str:
        return None
    s = date_str.strip()

    # YYYY-MM
    m = re.match(r"^(\d{4})-(\d{2})$", s)
    if m:
        return int(m.group(1)), int(m.group(2))

    # YYYY
    m = re.match(r"^(\d{4})$", s)
    if m:
        return int(m.group(1)), 0  # month=0 means year-only

    # MM/YYYY
    m = re.match(r"^(\d{1,2})/(\d{4})$", s)
    if m:
        return int(m.group(2)), int(m.group(1))

    # Month YYYY (English)
    month_map = {
        "jan": 1,
        "feb": 2,
        "mar": 3,
        "apr": 4,
        "may": 5,
        "jun": 6,
        "jul": 7,
        "aug": 8,
        "sep": 9,
        "oct": 10,
        "nov": 11,
        "dec": 12,
        "fev": 2,
        "avr": 4,
        "mai": 5,
        "jui": 7,
        "aou": 8,
    }
    m = re.match(r"^([a-z]{3})[a-z]*\s+(\d{4})$", s, re.IGNORECASE)
    if m:
        month = month_map.get(m.group(1).lower(), 0)
        return int(m.group(2)), month

    return None


def _months_between(a: tuple[int, int], b: tuple[int, int]) -> int:
    """Return number of months between two (year, month) tuples."""
    ay, am = a
    by, bm = b
    # Treat month=0 as month=6 for gap estimation
    am = am or 6
    bm = bm or 6
    return (by - ay) * 12 + (bm - am)


# ── Individual flag detectors ────────────────────────────────────────────────────────────────────


def _check_passive_voice(jr: JSONResume) -> list[RedFlag]:
    flags: list[RedFlag] = []
    for i, job in enumerate(jr.work):
        for j, bullet in enumerate(job.highlights):
            if _PASSIVE_RE.search(bullet):
                flags.append(
                    _make_flag(
                        "passive_voice",
                        f"work[{i}].highlights[{j}]",
                        bullet[:80],
                    )
                )
    return flags


def _check_duty_bullets(jr: JSONResume) -> list[RedFlag]:
    """Flag bullets with no strong verb AND no metric."""
    flags: list[RedFlag] = []
    for i, job in enumerate(jr.work):
        for j, bullet in enumerate(job.highlights):
            first_word = bullet.strip().split()[0].lower().rstrip(".,;:") if bullet.strip() else ""
            has_strong = first_word in _STRONG_VERBS or any(
                sv in bullet.lower()
                for sv in _STRONG_VERBS
                if len(sv) > 4  # avoid short false positives
            )
            has_metric = bool(_METRIC_RE.search(bullet))
            if not has_strong and not has_metric:
                flags.append(
                    _make_flag(
                        "duty_bullets",
                        f"work[{i}].highlights[{j}]",
                        bullet[:80],
                    )
                )
    return flags


def _check_banned_words(raw_text: str) -> list[RedFlag]:
    flags: list[RedFlag] = []
    text_lower = raw_text.lower()
    found: set[str] = set()
    for word in _BANNED_WORDS:
        if word in text_lower and word not in found:
            found.add(word)
            flags.append(
                _make_flag(
                    "banned_word",
                    "document text",
                    f"Found: {word!r}",
                )
            )
    return flags


def _check_employment_gaps(jr: JSONResume) -> list[RedFlag]:
    """Flag gaps > 3 months between work entries."""
    flags: list[RedFlag] = []
    dated = []
    for job in jr.work:
        start = _parse_date(job.startDate)
        end = _parse_date(job.endDate)
        if start:
            dated.append((start, end or start, job.name or ""))

    # Sort by start date
    dated.sort(key=lambda x: (x[0][0], x[0][1] or 6))

    for k in range(len(dated) - 1):
        _, end_k, name_k = dated[k]
        start_next, _, name_next = dated[k + 1]
        gap = _months_between(end_k, start_next)
        if gap > 3:
            flags.append(
                _make_flag(
                    "gap_unlabeled",
                    f"between '{name_k}' and '{name_next}'",
                    f"~{gap} month gap",
                )
            )
    return flags


def _check_job_hopping(jr: JSONResume) -> list[RedFlag]:
    """Flag if ≥3 stints are shorter than 12 months."""
    short_stints = 0
    for job in jr.work:
        start = _parse_date(job.startDate)
        end = _parse_date(job.endDate)
        if start and end:
            dur = _months_between(start, end)
            if 0 < dur < 12:
                short_stints += 1
    if short_stints >= 3:
        return [
            _make_flag(
                "job_hopping",
                "work history",
                f"{short_stints} stints shorter than 12 months",
            )
        ]
    return []


def _check_years_only_dates(jr: JSONResume) -> list[RedFlag]:
    """Flag work entries using year-only date format."""
    flags: list[RedFlag] = []
    for i, job in enumerate(jr.work):
        for field_name, val in [("startDate", job.startDate), ("endDate", job.endDate)]:
            if val and re.match(r"^\d{4}$", val.strip()):
                flags.append(
                    _make_flag(
                        "years_only_dates",
                        f"work[{i}].{field_name}",
                        f"Year-only date: {val!r}",
                    )
                )
    return flags


def _check_email(jr: JSONResume) -> list[RedFlag]:
    """Flag unprofessional email addresses."""
    email = jr.basics.email
    if not email:
        return []

    parts = email.lower().split("@")
    if len(parts) != 2:
        return []

    local, domain = parts[0], parts[1]

    if domain in _THROWAWAY_DOMAINS:
        return [
            _make_flag(
                "email_unprofessional",
                "basics.email",
                f"Throwaway domain: {domain!r}",
            )
        ]

    if _UNPROFESSIONAL_EMAIL_RE.match(local):
        return [
            _make_flag(
                "email_unprofessional",
                "basics.email",
                f"Non-professional local part: {local!r}",
            )
        ]

    return []


def _check_photo_market(market_id: str, has_photo: bool) -> list[RedFlag]:
    if has_photo and market_id.lower() in _PHOTO_FORBIDDEN_MARKETS:
        return [
            _make_flag(
                "wrong_photo_market",
                "basics (photo)",
                f"Photo present; forbidden in market: {market_id}",
            )
        ]
    return []


def _check_personal_info_market(
    market_id: str, jr: JSONResume, raw_text: str = ""
) -> list[RedFlag]:
    """Check raw_text for DOB/nationality/marital status when market forbids it.

    Loads the MarketProfile for the given market; if personal_info_ok is False,
    scans raw_text with conservative regex patterns.  Emits wrong_personal_info
    (CRITICAL) when any of the following are found:
    - Date of birth indicators: "date de naissance", "né(e) le", "born", "birth",
      "D.O.B", "DOB", or a 4-digit year near "naissance"/"birth"
    - Nationality indicators: "nationalit(é/y)"
    - Marital status: "marital", "situation familiale"
    """
    try:
        from decroche.market.profiles import load_profile

        profile: MarketProfile = load_profile(market_id)
    except ValueError:
        return []

    if profile.personal_info_ok:
        return []

    _PI_RE = re.compile(
        r"date\s+de\s+naissance"
        r"|n[eé]{1,2}(?:e)?\s+le\b"
        r"|\bborn\b"
        r"|\bbirth(?:date|day)?\b"
        r"|\bD\.?O\.?B\.?\b"
        r"|\bnational(?:it[eé]|ity)\b"
        r"|\bmarital\b"
        r"|situation\s+familiale",
        re.IGNORECASE,
    )

    if _PI_RE.search(raw_text):
        m = _PI_RE.search(raw_text)
        snippet = raw_text[max(0, m.start() - 10) : m.end() + 30].strip()
        return [
            RedFlag(
                flag_id="wrong_personal_info",
                severity=_sev("wrong_personal_info"),
                location="document text",
                evidence=snippet[:80],
                fix=f"Remove DOB/nationality/marital status for the {market_id} market.",
            )
        ]
    return []


_CHARS_PER_PAGE = 3500  # heuristic: ~3500 printable chars per A4/Letter page


def _check_length_violation(market_id: str, raw_text: str) -> list[RedFlag]:
    """Estimate page count from raw_text and flag if it exceeds market's max pages.

    Page-count heuristic: max(chars/3500, lines/45).
    Uses MarketProfile.length_max_pages for the threshold.
    """
    try:
        from decroche.market.profiles import load_profile

        profile: MarketProfile = load_profile(market_id)
    except ValueError:
        return []

    chars = len(raw_text)
    lines = len([ln for ln in raw_text.splitlines() if ln.strip()])
    est_pages = max(chars / _CHARS_PER_PAGE, lines / 45)

    if est_pages > profile.length_max_pages:
        return [
            RedFlag(
                flag_id="length_violation",
                severity=_sev("length_violation"),
                location="document",
                evidence=f"Estimated ~{est_pages:.1f} pages (limit: {profile.length_max_pages})",
                fix=(
                    f"Shorten the CV to {profile.length_max_pages} page(s) "
                    f"for the {market_id} market."
                ),
            )
        ]
    return []


# Patterns for conservative typo detection (no spellchecker dependency).
# Philosophy: only flag clear-cut mechanical errors, never linguistic choices.
# Full spell-check is out of scope (deferred — would require a language model or
# dictionary dep).  This heuristic keeps precision high by targeting only:
#   1. Doubled consecutive words (e.g. "the the", "le le")
#   2. Three or more identical letters in a row inside a word (e.g. "excelllent")
#   3. Stray double-spaces inside a sentence (mid-sentence, not at line start)
# Rationale for exclusion: lowercase-first-letter of bullet is too context-
# dependent (French lowercase after colon, code samples, etc.) → omitted.
_DOUBLED_WORD_RE = re.compile(
    r"\b(\w{2,})\s+\1\b",  # same word (≥2 chars) repeated: "the the"
    re.IGNORECASE,
)
_TRIPLE_LETTER_RE = re.compile(
    r"\b\w*([a-zA-Z])\1\1\w*\b",  # 3+ identical consecutive letters inside a word
)
_DOUBLE_SPACE_RE = re.compile(
    r"(?<=[^\s.?!:])  +(?=\w)",  # double space mid-sentence (not after punctuation)
)


def _check_typo_risk(raw_text: str) -> list[RedFlag]:
    """Conservative deterministic typo heuristics (no spellchecker dependency).

    Only flags clear mechanical errors with very low false-positive rate:
    - Doubled consecutive words ("the the", "le le")
    - Three or more identical consecutive letters inside a word ("excelllent")
    - Stray double spaces mid-sentence

    Full spell-check is intentionally deferred; this function is designed for
    high precision over high recall.
    """
    flags: list[RedFlag] = []

    m = _DOUBLED_WORD_RE.search(raw_text)
    if m:
        flags.append(
            _make_flag(
                "typo_risk",
                "document text",
                f"Doubled word: {m.group(0)!r}",
            )
        )
        return flags  # One flag per document is enough

    m = _TRIPLE_LETTER_RE.search(raw_text)
    if m:
        flags.append(
            _make_flag(
                "typo_risk",
                "document text",
                f"Repeated letters: {m.group(0)!r}",
            )
        )
        return flags

    m = _DOUBLE_SPACE_RE.search(raw_text)
    if m:
        snippet = raw_text[max(0, m.start() - 5) : m.end() + 10].strip()
        flags.append(
            _make_flag(
                "typo_risk",
                "document text",
                f"Double space: {snippet!r}",
            )
        )

    return flags


def _check_ai_phrasing(raw_text: str) -> list[RedFlag]:
    flags: list[RedFlag] = []
    for m in _AI_RE.finditer(raw_text):
        snippet = raw_text[max(0, m.start() - 10) : m.end() + 30].strip()
        flags.append(
            _make_flag(
                "ai_generic_phrasing",
                "document text",
                snippet[:80],
            )
        )
        break  # One flag per document is sufficient to avoid noise
    return flags


def _check_no_quantification(jr: JSONResume) -> list[RedFlag]:
    """If all highlights have zero metrics → no_quantification."""
    all_highlights = [h for job in jr.work for h in job.highlights]
    if not all_highlights:
        return []
    any_metric = any(_METRIC_RE.search(h) for h in all_highlights)
    if not any_metric:
        return [
            _make_flag(
                "no_quantification",
                "work highlights",
                "No metrics found in any work highlight.",
            )
        ]
    return []


# ── Main entry point ─────────────────────────────────────────────────────────────────────────────


def redflag_scan(
    json_resume: JSONResume,
    raw_text: str,
    market_id: str = "fr",
    has_photo: bool = False,
) -> list[RedFlag]:
    """Scan a CV for red flags.

    Args:
        json_resume: Parsed JSON Resume.
        raw_text: Raw text of the CV (as extracted from the file).
        market_id: Target market ("fr", "us", "uk", "ca", "ca-en", "ca-fr").
        has_photo: Whether the CV contains a photo (caller must detect this).

    Returns:
        List of RedFlag objects.
    """
    flags: list[RedFlag] = []

    flags.extend(_check_passive_voice(json_resume))
    flags.extend(_check_duty_bullets(json_resume))
    flags.extend(_check_banned_words(raw_text))
    flags.extend(_check_employment_gaps(json_resume))
    flags.extend(_check_job_hopping(json_resume))
    flags.extend(_check_years_only_dates(json_resume))
    flags.extend(_check_email(json_resume))
    flags.extend(_check_photo_market(market_id, has_photo))
    flags.extend(_check_personal_info_market(market_id, json_resume, raw_text))
    flags.extend(_check_ai_phrasing(raw_text))
    flags.extend(_check_no_quantification(json_resume))
    flags.extend(_check_length_violation(market_id, raw_text))
    flags.extend(_check_typo_risk(raw_text))

    return flags
