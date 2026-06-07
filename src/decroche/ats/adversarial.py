"""Adversarial CV tactic DETECTOR (spec §2).

Detects three classes of adversarial tactics that candidates might embed in a
submitted CV.  This module ONLY detects — it contains NO generator, NO helper
that produces any adversarial content.

Tactics detected:
1. prompt_injection (CRITICAL) — screener-directed imperatives hidden in text.
2. hidden_text (CRITICAL) — near-invisible text: white/near-white colour or
   sub-4pt font size (PDF via pdfplumber, DOCX via python-docx).
3. keyword_stuffing (HIGH) — anomalous token repetition (any non-stopword
   token repeated > max(8, 3% of total tokens) times, or a line verbatim
   repeated ≥4×).

Public API
----------
detect_adversarial(raw_text: str, file_path: str | Path | None = None)
    -> list[RedFlag]

detect_prompt_injection(raw_text: str) -> list[RedFlag]
detect_hidden_text(file_path: str | Path) -> list[RedFlag]
detect_keyword_stuffing(raw_text: str) -> list[RedFlag]
has_suspicious_pdf_char(char_info: dict) -> bool      (unit-testable predicate)
has_suspicious_docx_run(run) -> bool                  (unit-testable predicate)
"""

from __future__ import annotations

import re
from pathlib import Path

from decroche.models import RedFlag

# ── Constants ──────────────────────────────────────────────────────────────────

_FIX_INJECTION = "Remove embedded instructions to the screener — detected + disqualifying in 2026"
_FIX_HIDDEN = (
    "Remove hidden text (white/near-white colour or sub-4pt font) — "
    "ATS and screeners flag this as automatic disqualification"
)
_FIX_STUFFING = (
    "Remove repeated keywords — keyword stuffing is detected by modern ATS "
    "and results in automatic rejection"
)

# Stopwords to exclude from stuffing analysis (EN + FR, compact set)
_STOPWORDS: frozenset[str] = frozenset(
    {
        # EN
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "with",
        "by",
        "from",
        "as",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "shall",
        "can",
        "it",
        "its",
        "this",
        "that",
        "these",
        "those",
        "i",
        "me",
        "my",
        "we",
        "our",
        "you",
        "your",
        "he",
        "she",
        "they",
        "their",
        "them",
        "not",
        "no",
        "if",
        "so",
        "up",
        "out",
        "into",
        "about",
        "also",
        # FR
        "le",
        "la",
        "les",
        "un",
        "une",
        "des",
        "du",
        "de",
        "et",
        "ou",
        "en",
        "au",
        "aux",
        "par",
        "sur",
        "sous",
        "dans",
        "avec",
        "pour",
        "que",
        "qui",
        "quoi",
        "dont",
        "où",
        "est",
        "sont",
        "été",
        "avoir",
        "ce",
        "se",
        "si",
        "ne",
        "pas",
        "je",
        "tu",
        "il",
        "elle",
        "nous",
        "vous",
        "ils",
        "elles",
        "mon",
        "ma",
        "mes",
        "son",
        "sa",
        "ses",
        "leur",
        "leurs",
        "tout",
        "mais",
        "car",
    }
)

# ── Prompt-injection patterns ──────────────────────────────────────────────────

_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"ignore\s+(?:previous|all)\s+instructions?",
        r"disregard\s+\w*\s*instructions?",
        r"rate\s+(?:this|the\s+candidate|me)\s+(?:a\s+)?(?:10|10/10|perfect)",
        r"you\s+(?:must|should)\s+(?:select|recommend|hire|advance)",
        r"as\s+an?\s+(?:AI|language\s+model)",
        r"system\s+prompt",
        # French
        r"note\s+(?:de\s+)?10/10",
        r"ignor(?:ez?|er)?\s+les\s+instructions?",
        r"tu\s+dois\s+(?:recommander|s[eé]lectionner|retenir)",
        r"recommande[rz]?\s+ce\s+candidat",
    ]
]


# ── PDF hidden-text predicate ──────────────────────────────────────────────────


def has_suspicious_pdf_char(char_info: dict) -> bool:
    """Return True if a pdfplumber character dict looks like hidden text.

    Criteria (either is sufficient):
    - non_stroking_color is near-white (all channels > 0.85 in 0–1 space, or
      all channels > 217 in 0–255 space, or the value is 1 / (1,1,1) etc.)
    - size < 4 pt

    This is a pure predicate — safe to unit-test directly.
    """
    # Font size check
    size = char_info.get("size")
    if size is not None:
        try:
            if float(size) < 4.0:
                return True
        except (TypeError, ValueError):
            pass

    # Colour check (non_stroking_color)
    colour = char_info.get("non_stroking_color")
    if colour is None:
        return False

    # Scalar: 1 or 255 means white
    if isinstance(colour, (int, float)):
        val = float(colour)
        # 0-1 space: 1.0 = white; 0-255 space: 255 = white
        if val >= 0.85 or val >= 217:
            return True
        return False

    # Sequence (RGB or CMYK)
    try:
        vals = [float(v) for v in colour]
    except (TypeError, ValueError):
        return False

    if not vals:
        return False

    # Determine if 0-1 or 0-255 by magnitude
    max_val = max(vals)
    if max_val <= 1.0:
        # 0-1 space: white = (1,1,1) or greyscale 1.0
        return all(v >= 0.85 for v in vals)
    else:
        # 0-255 space
        return all(v >= 217 for v in vals)


# ── DOCX hidden-text predicate ─────────────────────────────────────────────────


def has_suspicious_docx_run(run) -> bool:  # type: ignore[no-untyped-def]
    """Return True if a python-docx Run is hidden (white colour or tiny font).

    Criteria (either is sufficient):
    - font.size < 4pt  (914400 EMUs per inch, 12700 EMUs per pt)
    - font.color.rgb is near-white (all channels ≥ 0xDD)

    This is a pure predicate — safe to unit-test directly.
    """
    from docx.shared import Pt

    font = run.font

    # Size check
    if font.size is not None:
        try:
            if font.size < Pt(4):
                return True
        except (TypeError, ValueError):
            pass

    # Colour check
    try:
        rgb = font.color.rgb
        if rgb is not None:
            r, g, b = rgb[0], rgb[1], rgb[2]
            if r >= 0xDD and g >= 0xDD and b >= 0xDD:
                return True
    except Exception:  # noqa: BLE001
        pass

    return False


# ── Detector functions ─────────────────────────────────────────────────────────


def detect_prompt_injection(raw_text: str) -> list[RedFlag]:
    """Scan raw_text for screener-directed imperatives (EN + FR).

    Returns at most one RedFlag per match (one flag per injection pattern hit).
    Evidence is a short excerpt around the match.
    """
    flags: list[RedFlag] = []
    seen_patterns: set[int] = set()

    for i, pat in enumerate(_INJECTION_PATTERNS):
        m = pat.search(raw_text)
        if m and i not in seen_patterns:
            seen_patterns.add(i)
            start = max(0, m.start() - 10)
            end = min(len(raw_text), m.end() + 30)
            excerpt = raw_text[start:end].strip()
            flags.append(
                RedFlag(
                    flag_id="prompt_injection",
                    severity="CRITICAL",
                    location="document text",
                    evidence=excerpt[:120],
                    fix=_FIX_INJECTION,
                )
            )

    return flags


def _scan_pdf_hidden(data: bytes) -> list[RedFlag]:
    """Scan a PDF for near-invisible characters (pdfplumber)."""
    try:
        import io
        import pdfplumber
    except ImportError:
        return []

    flags: list[RedFlag] = []
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                chars = page.chars or []
                for ch in chars:
                    if has_suspicious_pdf_char(ch):
                        text_sample = ch.get("text", "?")
                        flags.append(
                            RedFlag(
                                flag_id="hidden_text",
                                severity="CRITICAL",
                                location=f"pdf page {page_num}",
                                evidence=f"char={text_sample!r} size={ch.get('size')} "
                                f"color={ch.get('non_stroking_color')}",
                                fix=_FIX_HIDDEN,
                            )
                        )
                        # One flag per page is enough
                        break
    except Exception:  # noqa: BLE001
        pass

    return flags


def _scan_docx_hidden(data: bytes) -> list[RedFlag]:
    """Scan a DOCX for near-invisible runs (python-docx)."""
    try:
        import io
        from docx import Document
    except ImportError:
        return []

    flags: list[RedFlag] = []
    try:
        doc = Document(io.BytesIO(data))
        for para_idx, para in enumerate(doc.paragraphs):
            for run_idx, run in enumerate(para.runs):
                if run.text and has_suspicious_docx_run(run):
                    flags.append(
                        RedFlag(
                            flag_id="hidden_text",
                            severity="CRITICAL",
                            location=f"docx para {para_idx} run {run_idx}",
                            evidence=f"run text={run.text[:40]!r} "
                            f"size={run.font.size} "
                            f"color={_safe_rgb(run)}",
                            fix=_FIX_HIDDEN,
                        )
                    )
                    # One flag per document is sufficient to alert
                    return flags
    except Exception:  # noqa: BLE001
        pass

    return flags


def _safe_rgb(run) -> str:  # type: ignore[no-untyped-def]
    try:
        return str(run.font.color.rgb)
    except Exception:  # noqa: BLE001
        return "N/A"


def detect_hidden_text(file_path: str | Path) -> list[RedFlag]:
    """Detect near-invisible text in a PDF or DOCX file.

    For PDF: scans pdfplumber character dicts for near-white colour or
    sub-4pt font size.
    For DOCX: scans python-docx Run objects for near-white colour or
    sub-4pt font size.

    Returns list[RedFlag] — empty if no hidden text is found or file type is
    unsupported.
    """
    p = Path(file_path)
    ext = p.suffix.lower()
    data = p.read_bytes()

    if ext == ".pdf":
        return _scan_pdf_hidden(data)
    if ext == ".docx":
        return _scan_docx_hidden(data)
    return []


def detect_keyword_stuffing(raw_text: str) -> list[RedFlag]:
    """Detect anomalous token repetition in raw_text.

    Two signals:
    1. Any non-stopword token repeated > max(8, 3% of total_tokens) times.
    2. Any non-empty line repeated verbatim ≥4 times.

    Returns at most one RedFlag per signal (first hit reported).
    """
    flags: list[RedFlag] = []

    # ── Token repetition ──────────────────────────────────────────────────────
    tokens = re.findall(r"[a-zA-ZÀ-ÿ]{3,}", raw_text.lower())
    total = len(tokens)
    if total > 0:
        threshold = max(8, int(total * 0.03))
        counts: dict[str, int] = {}
        for tok in tokens:
            if tok not in _STOPWORDS:
                counts[tok] = counts.get(tok, 0) + 1

        for tok, count in counts.items():
            if count > threshold:
                flags.append(
                    RedFlag(
                        flag_id="keyword_stuffing",
                        severity="HIGH",
                        location="document text",
                        evidence=f"token={tok!r} count={count} threshold={threshold}",
                        fix=_FIX_STUFFING,
                    )
                )
                break  # One flag is enough

    # ── Line repetition ───────────────────────────────────────────────────────
    lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]
    line_counts: dict[str, int] = {}
    for ln in lines:
        line_counts[ln] = line_counts.get(ln, 0) + 1

    for ln, count in line_counts.items():
        if count >= 4:
            flags.append(
                RedFlag(
                    flag_id="keyword_stuffing",
                    severity="HIGH",
                    location="document text",
                    evidence=f"line repeated {count}×: {ln[:60]!r}",
                    fix=_FIX_STUFFING,
                )
            )
            break  # One flag per signal

    return flags


# ── Main entry point ───────────────────────────────────────────────────────────


def detect_adversarial(
    raw_text: str,
    file_path: str | Path | None = None,
) -> list[RedFlag]:
    """Run all three adversarial tactic detectors on a submitted CV.

    Args:
        raw_text:  Plain text extracted from the CV (used for prompt-injection
                   and keyword-stuffing checks).
        file_path: Path to the original CV file (used for hidden-text check;
                   supports .pdf and .docx).  Pass None to skip hidden-text.

    Returns:
        list[RedFlag] — empty if no adversarial tactics are detected.

    Note: This function ONLY detects adversarial content.  It does NOT produce,
    generate, or suggest any adversarial text.
    """
    flags: list[RedFlag] = []
    flags.extend(detect_prompt_injection(raw_text))
    flags.extend(detect_keyword_stuffing(raw_text))
    if file_path is not None:
        flags.extend(detect_hidden_text(file_path))
    return flags
