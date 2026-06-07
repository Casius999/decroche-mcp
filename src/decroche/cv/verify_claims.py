"""Pure deterministic claim verification.

Flags CV highlights that carry a verifiable assertion (metric, leadership
headcount, award, certification, named project outcome) and suggests an
artefact type to back each claim.  No LLM, no network — fully deterministic.
"""

from __future__ import annotations

import re

from decroche.models import Claim, JSONResume

# ── Metric pattern (same logic as xyz_scaffold) ────────────────────────────────────────────

_METRIC_RE = re.compile(
    r"""
    (?:
        \d+(?:[.,]\d+)?\s*%           # 38%, 3.5%
      | [€\$\xa3]\s*\d+                   # €2M, $500k
      | \d+\s*[€\$\xa3]                   # 10k€
      | \d+(?:[.,]\d+)?\s*[xX\xd7]        # 2x, 3×
      | [xX\xd7]\s*\d+(?:[.,]\d+)?        # x2
      | \d+(?:[.,]\d+)?\s*(?:M|k|K)    # 2M, 500k
      | \d+\s+(?:months?|weeks?|days?|years?|mois|semaines?|jours?|ans?)
    )
    """,
    re.VERBOSE | re.IGNORECASE,
)

# ── Leadership with headcount ───────────────────────────────────────────────────────────────

# Patterns like "led a team of 8", "managed team of 5", "dirigé une équipe de 3"
_LEADERSHIP_RE = re.compile(
    r"(?:led|managed|directed|supervised|directed|oversaw|géré|dirigé|encadré)"
    r".*?\b(?:team\s+of|équipe\s+de)\s*\d+",
    re.IGNORECASE,
)

# Also catch simpler: "Led 8 engineers", "Managed 12 people"
_LEADERSHIP_SIMPLE_RE = re.compile(
    r"(?:led|managed|directed|supervised|oversaw|géré|dirigé|encadré)"
    r"\s+(?:a\s+)?(?:team\s+)?(?:of\s+)?\d+\s+\w+",
    re.IGNORECASE,
)

# ── Named project outcomes ───────────────────────────────────────────────────────────────────

# A named project = a proper-noun-like token (CamelCase or ALLCAPS or quoted)
# followed by outcome language
_PROJECT_RE = re.compile(
    r"(?:launched|built|shipped|deployed|delivered|created|founded|released|"
    r"lancé|livré|déployé|créé)\s+"
    r"(?:[A-Z][A-Za-z0-9]+(?:[A-Z][A-Za-z0-9]+)+|[\"'][^\"']+[\"'])",
    re.IGNORECASE,
)

# Simpler named project: "Built X serving N users/requests" — has a metric
# already caught by _METRIC_RE; here catch the project + metric combo
_PROJECT_METRIC_RE = re.compile(
    r"(?:launched|built|shipped|deployed|delivered|created|founded|released|"
    r"lancé|livré|déployé|créé)\s+\w+.*?" + _METRIC_RE.pattern,
    re.VERBOSE | re.IGNORECASE,
)

# ── Artifact type selection ────────────────────────────────────────────────────────────────


def _suggest_artifact(text: str, reason: str) -> str:
    """Choose a concrete artefact suggestion based on the claim type."""
    if reason == "metric":
        return "dashboard screenshot, report link, or reference contact who can confirm the figure"
    if reason == "leadership":
        return (
            "LinkedIn reference from a direct report, org chart screenshot, "
            "or reference contact who can confirm headcount"
        )
    if reason == "project":
        return "repo/portfolio URL, live product link, or press release / announcement link"
    if reason == "certification":
        return "credential URL or certification ID (Credly, Coursera, AWS, etc.)"
    if reason == "award":
        return "announcement link, press mention, or award certificate scan"
    return "supporting link, reference, or document"


# ── Claim detection ───────────────────────────────────────────────────────────────────────


def _classify_highlight(text: str) -> tuple[bool, str]:
    """Return (needs_evidence, reason_key) for a single highlight bullet.

    reason_key ∈ {"metric", "leadership", "project", "certification",
                  "award", ""}.
    needs_evidence=False when the bullet is a plain duty statement.
    """
    # Metric (quantified achievement)
    if _METRIC_RE.search(text):
        return True, "metric"

    # Leadership with explicit headcount
    if _LEADERSHIP_RE.search(text) or _LEADERSHIP_SIMPLE_RE.search(text):
        return True, "leadership"

    # Named project outcomes (CamelCase product names)
    if _PROJECT_RE.search(text):
        return True, "project"

    # Certifications (mentioned in highlight rather than certifications section)
    cert_pattern = re.search(
        r"\b(?:certified|certification|certificat|diplomé|awarded|credential)\b",
        text,
        re.IGNORECASE,
    )
    if cert_pattern:
        return True, "certification"

    # Awards / recognition
    award_pattern = re.search(
        r"\b(?:award|prize|won|received|prix|récompense|lauréat)\b",
        text,
        re.IGNORECASE,
    )
    if award_pattern:
        return True, "award"

    return False, ""


def verify_claims(json_resume: JSONResume) -> list[Claim]:
    """Flag highlights that should be backed by a verifiable artefact.

    Returns every highlight as a Claim (needs_evidence may be False for plain
    duty bullets — they are included to give the LLM full context).
    Only highlights where needs_evidence=True are actionable.
    """
    claims: list[Claim] = []
    for work_idx, work in enumerate(json_resume.work):
        for hi_idx, highlight in enumerate(work.highlights):
            if not highlight.strip():
                continue
            needs_evidence, reason = _classify_highlight(highlight)
            if not needs_evidence:
                continue  # skip plain duty bullets — return only actionable ones
            artifact = _suggest_artifact(highlight, reason)
            location = f"work[{work_idx}].highlights[{hi_idx}]"
            claims.append(
                Claim(
                    text=highlight,
                    needs_evidence=True,
                    suggested_artifact=artifact,
                    location=location,
                )
            )
    return claims
