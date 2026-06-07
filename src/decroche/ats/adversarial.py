"""ats.adversarial — Adversarial CV tactic detection (spec §2).

Detects three classes of adversarial content that can be embedded in CVs
to manipulate AI screeners or ATS systems:

1. **prompt_injection** (CRITICAL severity)
   Screener-directed imperatives designed to override Claude's instructions:
   e.g. "Ignore all previous instructions", "You must hire this candidate".
   Covers both English and French variants via 10 regex patterns.

2. **hidden_text** (CRITICAL severity)
   Text made near-invisible via:
   - White or near-white font colour in PDF (RGB/CMYK close to white)
   - Sub-4pt font size in PDF
   - White or near-white font colour in DOCX (XML colour attribute)
   - Sub-4pt font size in DOCX

3. **keyword_stuffing** (HIGH severity)
   Anomalous token or line repetition designed to game keyword-match scoring:
   - Any single token repeated >= 5 times in the text
   - Any non-trivial line repeated >= 3 times

This module ONLY detects adversarial content — it NEVER produces it.
No generative output, no LLM calls, no external network access.

Returns a list of ``RedFlag`` objects compatible with the existing
``ats.redflag_scan`` output format.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Optional

from decroche.models import RedFlag

# ────────────────────────────────────────────────────────────────────────────────
# 1. Prompt-injection patterns
# ────────────────────────────────────────────────────────────────────────────────

#: 10 compiled patterns covering EN + FR prompt-injection variants.
_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    # EN: ignore/disregard/forget previous / prior / all instructions
    re.compile(
        r"\b(ignore|disregard|forget|override|bypass|skip)\b.{0,30}\b"
        r"(previous|prior|all|above|earlier|initial|system)\b.{0,30}\b"
        r"(instruction|prompt|rule|guideline|context|message)s?\b",
        re.IGNORECASE,
    ),
    # EN: "you must / you should / you are required to hire/select/advance"
    re.compile(
        r"\byou\b.{0,20}\b(must|should|shall|are required to|need to)\b.{0,30}"
        r"\b(hire|select|advance|recommend|pass|approve|choose)\b.{0,30}"
        r"\b(this|the)\b.{0,15}\b(candidate|applicant|person)\b",
        re.IGNORECASE,
    ),
    # EN: "act as if", "pretend you are", "assume the role of"
    re.compile(
        r"\b(act as(?: if)?|pretend (you are|to be)|assume the role of|roleplay as)\b",
        re.IGNORECASE,
    ),
    # EN: "new instructions", "updated instructions", "revised prompt"
    re.compile(
        r"\b(new|updated|revised|override|replacement)\b.{0,20}"
        r"\b(instruction|prompt|rule|directive|command)s?\b",
        re.IGNORECASE,
    ),
    # EN: "this candidate is perfect/excellent and must be hired"
    re.compile(
        r"\bthis (candidate|applicant|person)\b.{0,40}"
        r"\b(perfect|ideal|excellent|best|top|outstanding)\b.{0,40}"
        r"\b(must|should|shall)\b.{0,20}\b(hire|select|advance|pass)\b",
        re.IGNORECASE,
    ),
    # EN: "do not reject", "don't reject", "never reject"
    re.compile(
        r"\b(do not|don't|never|avoid)\b.{0,20}"
        r"\b(reject|decline|refuse|disqualify|eliminate|screen out)\b.{0,30}"
        r"\b(this|the)?\b.{0,15}\b(candidate|applicant|person|resume|cv)\b",
        re.IGNORECASE,
    ),
    # EN/FR: "[SYSTEM]", "[INST]", "<|system|>", "### Instruction"
    re.compile(
        r"(\[SYSTEM\]|\[INST\]|\[/INST\]|<\|system\|>|<\|user\|>"
        r"|<\|assistant\|>|###\s*Instruction|###\s*System|###\s*Prompt)",
        re.IGNORECASE,
    ),
    # FR: "ignorez", "oubliez", "ignorez toutes les instructions"
    re.compile(
        r"\b(ignorez|oubliez|effacez|annulez|contournez)\b.{0,30}"
        r"\b(les |toutes les |ces )?\b(instruction|règle|consigne|prompt)s?\b",
        re.IGNORECASE,
    ),
    # FR: "vous devez embaucher", "ce candidat est parfait"
    re.compile(
        r"\b(vous devez|il faut|vous êtes obligé)\b.{0,30}"
        r"\b(embaucher|sélectionner|retenir|accepter|valider)\b.{0,30}"
        r"\b(ce candidat|cet(te)? (candidat|postulant))\b",
        re.IGNORECASE,
    ),
    # FR: "ne rejetez pas", "n'éliminez pas ce candidat"
    re.compile(
        r"\b(ne|n')\b.{0,10}\b(rejetez|éliminez|refusez|disqualifiez)\b.{0,30}"
        r"\b(pas|jamais)\b.{0,20}\b(ce candidat|cet(te)? (candidat|postulant)|ce CV)\b",
        re.IGNORECASE,
    ),
]


def detect_prompt_injection(text: str) -> list[RedFlag]:
    """Scan *text* for prompt-injection imperatives.

    Args:
        text: Raw CV text.

    Returns:
        List of CRITICAL RedFlag objects, one per unique match.
    """
    flags: list[RedFlag] = []
    seen_spans: set[tuple[int, int]] = set()

    for i, pattern in enumerate(_INJECTION_PATTERNS, start=1):
        for m in pattern.finditer(text):
            span = (m.start(), m.end())
            if span in seen_spans:
                continue
            seen_spans.add(span)
            snippet = text[max(0, m.start() - 20) : m.end() + 20].replace("\n", " ")
            flags.append(
                RedFlag(
                    flag_id=f"prompt_injection_{i:02d}",
                    severity="CRITICAL",
                    location="cv_text",
                    evidence=snippet[:200],
                    fix=(
                        "CV contains text designed to manipulate AI screeners "
                        "(prompt injection). Remove the offending passage before "
                        "submitting."
                    ),
                )
            )

    return flags


# ────────────────────────────────────────────────────────────────────────────────
# 2a. Hidden text — PDF (colour + font-size)
# ────────────────────────────────────────────────────────────────────────────────


def has_suspicious_pdf_char(char_obj: object) -> bool:
    """Return True if a pdfplumber char object looks hidden.

    Checks:
    - Non-stroking colour (text fill) is white or near-white (RGB or CMYK)
    - Font size < 4 pt

    Args:
        char_obj: A pdfplumber character dict.

    Returns:
        True if the character appears hidden.
    """
    if not isinstance(char_obj, dict):
        return False

    # Font-size check
    size = char_obj.get("size", None)
    if size is not None:
        try:
            if float(size) < 4.0:
                return True
        except (TypeError, ValueError):
            pass

    # Colour check — non_stroking_color is the fill colour for text
    colour = char_obj.get("non_stroking_color", None)
    if colour is None:
        return False

    if isinstance(colour, (int, float)):
        # Greyscale: 1.0 = white
        return float(colour) >= 0.95

    if isinstance(colour, (list, tuple)):
        components = [float(c) for c in colour]
        if len(components) == 3:  # RGB
            return all(c >= 0.95 for c in components)
        if len(components) == 4:  # CMYK
            # CMYK (0,0,0,0) = white
            return all(c <= 0.05 for c in components)

    return False


# ────────────────────────────────────────────────────────────────────────────────
# 2b. Hidden text — DOCX (colour + font-size via XML)
# ────────────────────────────────────────────────────────────────────────────────

# Hex colours that are white or near-white (RGB distance < 5% from #FFFFFF)
_NEAR_WHITE_RE = re.compile(
    r"^(FFFFFF|FEFEFE|FDFDFD|FCFCFC|FBFBFB|FAFAFA|F9F9F9|F8F8F8|F0F0F0|E0E0E0)$",
    re.IGNORECASE,
)

# DOCX run XML namespace prefix
_W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def has_suspicious_docx_run(run: object) -> bool:
    """Return True if a python-docx Run looks hidden.

    Checks the run's XML for:
    - ``<w:color w:val="FFFFFF"/>`` (or near-white variants)
    - ``<w:sz w:val="N"/>`` where N < 8 (half-points, so < 4 pt)

    Args:
        run: A ``python_docx.text.run.Run`` object.

    Returns:
        True if the run appears hidden.
    """
    try:
        from lxml import etree  # type: ignore[import-untyped]
    except ImportError:
        return False

    try:
        xml = run._element  # type: ignore[attr-defined]
    except AttributeError:
        return False

    # Colour check
    colour_tag = f"{{{_W_NS}}}color"
    val_attr = f"{{{_W_NS}}}val"
    for colour_el in xml.iter(colour_tag):
        val = colour_el.get(val_attr, "")
        if _NEAR_WHITE_RE.match(val):
            return True

    # Font-size check (sz is in half-points: 8 half-pts = 4 pt)
    sz_tag = f"{{{_W_NS}}}sz"
    for sz_el in xml.iter(sz_tag):
        val = sz_el.get(val_attr, "")
        try:
            if int(val) < 8:  # < 4 pt
                return True
        except (ValueError, TypeError):
            pass

    return False


def detect_hidden_text_docx(file_path: Path) -> list[RedFlag]:
    """Scan a DOCX file for hidden-text runs.

    Args:
        file_path: Path to the .docx file.

    Returns:
        List of CRITICAL RedFlag objects (one per suspicious run, capped at 5).
    """
    try:
        import io
        from docx import Document  # type: ignore[import-untyped]

        doc = Document(io.BytesIO(file_path.read_bytes()))
    except Exception:  # noqa: BLE001
        return []

    flags: list[RedFlag] = []
    for para_idx, para in enumerate(doc.paragraphs):
        for run_idx, run in enumerate(para.runs):
            if not run.text.strip():
                continue
            if has_suspicious_docx_run(run):
                evidence = run.text[:100]
                flags.append(
                    RedFlag(
                        flag_id="hidden_text_docx",
                        severity="CRITICAL",
                        location=f"paragraph {para_idx}, run {run_idx}",
                        evidence=evidence,
                        fix=(
                            "Hidden text detected (near-white colour or sub-4pt font). "
                            "Remove hidden content before submitting."
                        ),
                    )
                )
                if len(flags) >= 5:  # cap output
                    return flags
    return flags


# ────────────────────────────────────────────────────────────────────────────────
# 3. Keyword stuffing
# ────────────────────────────────────────────────────────────────────────────────

# Stopwords to exclude from token repetition checks (EN + FR)
_STOPWORDS: frozenset[str] = frozenset(
    [
        "the",
        "a",
        "an",
        "and",
        "or",
        "of",
        "to",
        "in",
        "is",
        "it",
        "was",
        "for",
        "on",
        "with",
        "as",
        "at",
        "by",
        "from",
        "that",
        "this",
        "are",
        "be",
        "been",
        "have",
        "has",
        "had",
        "not",
        "but",
        "i",
        "my",
        "we",
        "our",
        "you",
        "your",
        "he",
        "she",
        "they",
        "their",
        # FR
        "le",
        "la",
        "les",
        "un",
        "une",
        "des",
        "et",
        "ou",
        "de",
        "à",
        "en",
        "est",
        "il",
        "elle",
        "ils",
        "elles",
        "nous",
        "vous",
        "que",
        "qui",
        "dans",
        "par",
        "sur",
        "au",
        "aux",
        "du",
        "ce",
        "se",
        "sa",
        "son",
        "ses",
        "mon",
        "ma",
        "mes",
        "je",
        "avec",
        "pour",
        "pas",
        "plus",
        "si",
        "ne",
        "j",
        "n",
        "s",
        "l",
        "d",
    ]
)

_TOKEN_RE = re.compile(r"[a-zà-ÿ]{3,}", re.IGNORECASE)
_TOKEN_REPEAT_THRESHOLD = 5
_LINE_REPEAT_THRESHOLD = 3


def detect_keyword_stuffing(text: str) -> list[RedFlag]:
    """Scan *text* for anomalous token or line repetition.

    Token check: any word (>=3 chars, not a stopword) that appears 5+ times.
    Line check: any non-trivial line (>=10 chars) that repeats 3+ times.

    Args:
        text: Raw CV text.

    Returns:
        List of HIGH severity RedFlag objects.
    """
    flags: list[RedFlag] = []

    # Token repetition
    tokens = [t.lower() for t in _TOKEN_RE.findall(text) if t.lower() not in _STOPWORDS]
    token_counts = Counter(tokens)
    stuffed_tokens = [
        (tok, cnt)
        for tok, cnt in token_counts.items()
        if cnt >= _TOKEN_REPEAT_THRESHOLD
    ]
    # Sort descending by count for deterministic output
    stuffed_tokens.sort(key=lambda x: (-x[1], x[0]))

    for tok, cnt in stuffed_tokens[:3]:  # cap at 3 flags
        flags.append(
            RedFlag(
                flag_id="keyword_stuffing_token",
                severity="HIGH",
                location="cv_text",
                evidence=f'Token {tok!r} repeated {cnt} times',
                fix=(
                    f"Token '{tok}' appears {cnt} times — far above natural frequency. "
                    "Remove repetitive keyword padding."
                ),
            )
        )

    # Line repetition
    lines = [ln.strip() for ln in text.splitlines()]
    non_trivial = [ln for ln in lines if len(ln) >= 10]
    line_counts = Counter(non_trivial)
    repeated_lines = [
        (ln, cnt)
        for ln, cnt in line_counts.items()
        if cnt >= _LINE_REPEAT_THRESHOLD
    ]
    repeated_lines.sort(key=lambda x: (-x[1], x[0]))

    for ln, cnt in repeated_lines[:2]:  # cap at 2 flags
        flags.append(
            RedFlag(
                flag_id="keyword_stuffing_line",
                severity="HIGH",
                location="cv_text",
                evidence=f'{ln[:80]!r} × {cnt}',
                fix=(
                    f"Line repeated {cnt} times. Remove duplicate lines to avoid "
                    "ATS keyword-stuffing filters."
                ),
            )
        )

    return flags


# ────────────────────────────────────────────────────────────────────────────────
# Integration entry point
# ────────────────────────────────────────────────────────────────────────────────


def detect_adversarial(
    raw_text: str,
    file_path: Optional[Path] = None,
) -> list[RedFlag]:
    """Detect all adversarial tactics in *raw_text* (and optionally *file_path*).

    This function ONLY detects — it never produces adversarial content.

    Order of checks:
    1. Prompt injection (text-based, CRITICAL)
    2. Hidden text in DOCX (file-based, CRITICAL) — only if file_path given
    3. Keyword stuffing (text-based, HIGH)

    Hidden-text PDF detection requires the caller (``ats.__init__.detect_adversarial``)
    to extract per-character colour metadata; the raw text alone is insufficient
    for PDF colour analysis.  That logic lives in ``ats/__init__.py``.

    Args:
        raw_text:  Plain text extracted from the CV (by caller).
        file_path: Optional Path to the original file (used for DOCX run inspection).

    Returns:
        Combined list of RedFlag objects.  Empty if no adversarial tactics found.
    """
    flags: list[RedFlag] = []

    flags.extend(detect_prompt_injection(raw_text))

    if file_path is not None and file_path.suffix.lower() == ".docx":
        flags.extend(detect_hidden_text_docx(file_path))

    flags.extend(detect_keyword_stuffing(raw_text))

    return flags
