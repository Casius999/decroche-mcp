"""match_score — deterministic skill-coverage scorer.

``match_score(json_resume, offer_text) -> MatchScore``

Coverage algorithm (per requirement):
1. Exact match (after normalize).
2. Synonym set overlap (expand() ∩ candidate_terms ≠ ∅).
3. rapidfuzz token_set_ratio ≥ 85 between requirement and any candidate term.

Seniority fit:
- Extract seniority from offer via parse_offer.
- Extract seniority from resume basics.label or summary.
- Map to: "under" | "match" | "over" | "unknown".

Score formula:
    score = 100 * (0.75 * must_ratio + 0.25 * nice_ratio) * seniority_multiplier

where seniority_multiplier is 1.0 for match/unknown, 0.9 for under/over.

No LLM, no network.  Deterministic.
"""
from __future__ import annotations

import re

from rapidfuzz.fuzz import token_set_ratio  # type: ignore[import-untyped]

from decroche.match.offer import parse_offer
from decroche.match.synonyms import expand, normalize
from decroche.models import JSONResume, MatchScore, Offer, RequirementCoverage

_FUZZY_THRESHOLD = 85

# Seniority keyword patterns.
_SENIORITY_RE = re.compile(
    r"\b(junior|senior|lead|principal|stagiaire|stage|confirm[eé])\b",
    re.IGNORECASE,
)

_SENIORITY_RANK: dict[str, int] = {
    "stagiaire": 0,
    "stage": 0,
    "junior": 1,
    "confirmé": 2,
    "confirme": 2,
    "senior": 3,
    "lead": 4,
    "principal": 5,
}


def _extract_cv_seniority(jr: JSONResume) -> str | None:
    """Return the seniority keyword found in basics.label or basics.summary."""
    text_parts = [jr.basics.label or "", jr.basics.summary or ""]
    for part in text_parts:
        m = _SENIORITY_RE.search(part)
        if m:
            return m.group(1).lower()
    return None


def _seniority_fit(cv_seniority: str | None, offer_seniority: str | None) -> str:
    """Return 'match', 'under', 'over', or 'unknown'."""
    if cv_seniority is None or offer_seniority is None:
        return "unknown"
    cv_rank = _SENIORITY_RANK.get(cv_seniority.lower())
    offer_rank = _SENIORITY_RANK.get(offer_seniority.lower())
    if cv_rank is None or offer_rank is None:
        return "unknown"
    if cv_rank == offer_rank:
        return "match"
    if cv_rank < offer_rank:
        return "under"
    return "over"


def _candidate_terms(jr: JSONResume) -> set[str]:
    """Build the normalized candidate skill set from the resume."""
    terms: set[str] = set()

    # Skill names
    for skill in jr.skills:
        if skill.name:
            terms.add(normalize(skill.name))
        for kw in skill.keywords:
            terms.add(normalize(kw))

    # Work highlights and summaries
    for work in jr.work:
        for highlight in work.highlights:
            for token in re.findall(r"\b\w[\w+#/.'-]{1,49}\b", highlight):
                terms.add(normalize(token))
        if work.summary:
            for token in re.findall(r"\b\w[\w+#/.'-]{1,49}\b", work.summary):
                terms.add(normalize(token))

    # Basics summary
    if jr.basics.summary:
        for token in re.findall(r"\b\w[\w+#/.'-]{1,49}\b", jr.basics.summary):
            terms.add(normalize(token))

    return terms


def _check_coverage(
    requirement: str,
    kind: str,
    candidate_terms: set[str],
) -> RequirementCoverage:
    """Return RequirementCoverage for a single requirement."""
    req_norm = normalize(requirement)
    req_aliases = expand(req_norm)

    # 1. Exact match (normalized)
    if req_norm in candidate_terms:
        return RequirementCoverage(
            requirement=requirement,
            kind=kind,
            covered=True,
            evidence=f"exact: {req_norm}",
        )

    # 2. Synonym/alias overlap
    overlap = req_aliases & candidate_terms
    if overlap:
        matched = sorted(overlap)[0]
        return RequirementCoverage(
            requirement=requirement,
            kind=kind,
            covered=True,
            evidence=f"synonym: {matched}",
        )

    # 3. Fuzzy match via rapidfuzz token_set_ratio ≥ 85
    for candidate in candidate_terms:
        if token_set_ratio(req_norm, candidate) >= _FUZZY_THRESHOLD:
            return RequirementCoverage(
                requirement=requirement,
                kind=kind,
                covered=True,
                evidence=f"fuzzy~{candidate}",
            )

    return RequirementCoverage(
        requirement=requirement,
        kind=kind,
        covered=False,
        evidence=None,
    )


def match_score(json_resume: JSONResume, offer_text: str) -> MatchScore:
    """Compute a match score between *json_resume* and *offer_text*.

    Returns MatchScore with score_0_100, requirement_coverage,
    seniority_fit, and missing_must.
    """
    offer: Offer = parse_offer(offer_text)
    candidates = _candidate_terms(json_resume)

    coverage: list[RequirementCoverage] = []

    for req in offer.must_have:
        coverage.append(_check_coverage(req, "must_have", candidates))

    for req in offer.nice_to_have:
        coverage.append(_check_coverage(req, "nice_to_have", candidates))

    must_coverage = [rc for rc in coverage if rc.kind == "must_have"]
    nice_coverage = [rc for rc in coverage if rc.kind == "nice_to_have"]

    must_ratio = (
        sum(1 for rc in must_coverage if rc.covered) / len(must_coverage)
        if must_coverage else 0.0
    )
    nice_ratio = (
        sum(1 for rc in nice_coverage if rc.covered) / len(nice_coverage)
        if nice_coverage else 0.0
    )

    # Seniority
    cv_seniority = _extract_cv_seniority(json_resume)
    offer_seniority = offer.seniority
    fit = _seniority_fit(cv_seniority, offer_seniority)

    seniority_multiplier = 0.9 if fit in ("under", "over") else 1.0

    raw_score = 100.0 * (0.75 * must_ratio + 0.25 * nice_ratio) * seniority_multiplier
    score = min(100.0, max(0.0, raw_score))

    missing_must = [rc.requirement for rc in must_coverage if not rc.covered]

    return MatchScore(
        score_0_100=round(score, 2),
        requirement_coverage=coverage,
        seniority_fit=fit,
        missing_must=missing_must,
    )
