"""Pure deterministic XYZ bullet scaffolding.

Decomposes a CV highlight bullet into:
  X — the achievement object
  Y — whether a metric is present (%, €, $, ×, count, time)
  Z — the method clause after "by/via/using/en/à l'aide de/grâce à"

The host LLM fills the prose later; this module only produces structure and
flags.  NEVER invents metrics.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Final

import yaml

from decroche.models import JSONResume, XyzScaffold

# ── Strong verb list (loaded once) ──────────────────────────────────────────────────

_VERBS_YAML: Final[Path] = Path(__file__).parent.parent / "data" / "strong_verbs.yaml"


@lru_cache(maxsize=1)
def _load_strong_verbs() -> frozenset[str]:
    """Return a frozenset of lowercased strong verbs (FR + EN)."""
    data = yaml.safe_load(_VERBS_YAML.read_text(encoding="utf-8"))
    verbs: set[str] = set()
    for lang_verbs in data.values():
        verbs.update(v.lower().strip() for v in lang_verbs)
    return frozenset(verbs)


# ── Weak / duty patterns ──────────────────────────────────────────────────────────────

# Phrases or single words that signal a duty bullet rather than an achievement.
# Matched case-insensitively at the start (after optional whitespace).
_WEAK_PATTERNS: Final[tuple[str, ...]] = (
    r"responsible\s+for",
    r"worked\s+on",
    r"helped\s+",
    r"assisted\s+",
    r"involved\s+in",
    r"participated\s+in",
    r"in\s+charge\s+of",
    r"tasked\s+with",
    r"duties\s+included",
    r"a\s+charge\s+de",          # FR: "à charge de"
    r"chargé\s+de",
    r"responsable\s+de",
)

_WEAK_RE: Final[re.Pattern[str]] = re.compile(
    r"^(?:" + "|".join(_WEAK_PATTERNS) + r")",
    re.IGNORECASE,
)

# Verbs that are "strong" in the list but signal a duty/scope statement when
# used WITHOUT a metric.  Spec says "managed-without-metric" is weak.
_AMBIGUOUS_VERBS: Final[frozenset[str]] = frozenset({
    "managed", "directed", "coordinated", "supervised", "oversaw",
    "géré", "dirigé", "coordonné",
})

# ── Metric detection ──────────────────────────────────────────────────────────────

# Detect any of: %, €, $, £, ×, "x" as multiplier, plain numbers, durations
_METRIC_RE: Final[re.Pattern[str]] = re.compile(
    r"""
    (?:
        \d+(?:[.,]\d+)?\s*%          # 38%, 3.5%
      | [€\$£]\s*\d+                  # €2M, $500k, £10k
      | \d+\s*[€\$£]                  # 10k€
      | \d+(?:[.,]\d+)?\s*[xX×]       # 2x, 3×
      | [xX×]\s*\d+(?:[.,]\d+)?       # x2
      | \d+(?:[.,]\d+)?\s*(?:M|k|K)   # 2M, 500k
      | \d+\s+(?:months?|weeks?|days?|years?|mois|semaines?|jours?|ans?) # durations
    )
    """,
    re.VERBOSE | re.IGNORECASE,
)

# ── Method clause detection ─────────────────────────────────────────────────────────

# Split bullet into [achievement part] / [method clause] at a boundary word.
_METHOD_SPLIT_RE: Final[re.Pattern[str]] = re.compile(
    r"\s+(?:by|via|using|through|en|à\s+l'aide\s+de|grâce\s+à|en\s+utilisant|par)\s+",
    re.IGNORECASE,
)

# ── Verb extraction ───────────────────────────────────────────────────────────────

# First token that looks like a verb (word chars, possibly accented)
_FIRST_WORD_RE: Final[re.Pattern[str]] = re.compile(r"^([\wÀ-ÿ]+(?:\s+en)?)", re.IGNORECASE)

# Some FR verbs are past-participle compounds like "mis en place", "réduit de moitié"
_COMPOUND_VERB_PREFIXES: Final[tuple[str, ...]] = (
    "mis en place",
    "réduit de moitié",
    "mise en place",
)


def _extract_verb(text: str) -> tuple[str | None, bool]:
    """Return (verb_lowercased, weak_verb_flag).

    weak_verb=True when:
    - the leading phrase matches _WEAK_RE (duty phrase), OR
    - the leading verb is not in the strong verbs list AND not a duty phrase
      (i.e. generic/ambiguous verb like "managed" without a metric context
       is still kept strong if it is in the strong list).
    """
    stripped = text.strip()

    # Check duty phrases first
    if _WEAK_RE.match(stripped):
        # Extract a plausible verb from the phrase
        m = _FIRST_WORD_RE.match(stripped)
        verb = m.group(1).lower() if m else None
        return verb, True

    # Check compound FR verbs
    lower = stripped.lower()
    for compound in _COMPOUND_VERB_PREFIXES:
        if lower.startswith(compound):
            strong = compound in _load_strong_verbs()
            return compound, not strong

    # Single-word verb
    m = _FIRST_WORD_RE.match(stripped)
    if not m:
        return None, False

    verb = m.group(1).lower().rstrip("é").rstrip("e")  # naive normalisation
    # Try both the raw form and normalised
    strong_set = _load_strong_verbs()
    raw_verb = m.group(1).lower()

    is_strong = raw_verb in strong_set or verb in strong_set
    return raw_verb, not is_strong


def _extract_x(text: str, verb: str | None) -> str:
    """Extract the achievement object X from the bullet.

    Removes:
    1. The leading verb (if detected).
    2. The trailing method clause (if any).
    3. Any embedded metric tokens (since Y is separate).
    Returns a cleaned, stripped string.
    """
    s = text.strip()

    # Remove leading verb
    if verb:
        # Match the verb at the start, case-insensitively
        s = re.sub(r"^" + re.escape(verb) + r"\s*", "", s, flags=re.IGNORECASE).strip()

    # Remove method clause
    parts = _METHOD_SPLIT_RE.split(s, maxsplit=1)
    s = parts[0].strip()

    # Remove leading metric that sits right at the start (edge case)
    # Keep metrics embedded in the object since they contribute to X description
    return s.strip()


def scaffold_bullet(bullet: str) -> XyzScaffold:
    """Decompose a single CV highlight bullet into an XyzScaffold.

    Deterministic, no LLM, no network.
    """
    text = bullet.strip()

    # --- Y: metric detection ---
    y_present = bool(_METRIC_RE.search(text))

    # --- Z: method clause ---
    method_parts = _METHOD_SPLIT_RE.split(text, maxsplit=1)
    z: str | None = method_parts[1].strip() if len(method_parts) > 1 else None

    # --- Verb + weak flag ---
    verb, weak_verb = _extract_verb(text)

    # Ambiguous verbs (managed, directed…) are weak when used without a metric.
    if verb and not weak_verb and verb.lower() in _AMBIGUOUS_VERBS and not y_present:
        weak_verb = True

    # --- X: achievement object ---
    x = _extract_x(text, verb)

    # --- Build template ---
    # Fill known parts; leave bracketed placeholders for unknown.
    x_part = x if x else "[X: achievement object]"
    y_part: str
    if y_present:
        # Try to pull the metric token for the template
        m = _METRIC_RE.search(text)
        y_part = m.group(0).strip() if m else "[Y: metric]"
    else:
        y_part = "[Y: add a real metric — %, count, €, time]"

    z_part = z if z else "[Z: how / by doing what]"

    template = f"Accomplished {x_part} as measured by {y_part} by doing {z_part}"

    # --- Missing metric prompt (never fabricate — only ask) ---
    missing_metric_prompt: str | None = None
    if not y_present:
        missing_metric_prompt = (
            "Add a real number for Y (%, count, €, time). "
            "Do NOT invent — ask the candidate for the actual figure."
        )

    return XyzScaffold(
        original=bullet,
        verb=verb,
        x=x,
        y_present=y_present,
        z=z,
        template=template,
        missing_metric_prompt=missing_metric_prompt,
        weak_verb=weak_verb,
    )


def scaffold_resume(json_resume: JSONResume) -> list[XyzScaffold]:
    """Scaffold every highlight across all work entries in the JSON Resume."""
    results: list[XyzScaffold] = []
    for work in json_resume.work:
        for highlight in work.highlights:
            if highlight.strip():
                results.append(scaffold_bullet(highlight))
    return results
