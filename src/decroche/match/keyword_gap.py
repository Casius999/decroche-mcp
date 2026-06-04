"""keyword_gap — rank offer terms by absence × salience.

``keyword_gap(json_resume, offer_text, n=5) -> list[KeywordGap]``

Algorithm:
1. Parse offer → Offer (must_have + nice_to_have).
2. For each offer term, compute salience × absence_weight.
3. Only include terms NOT already covered by match_score.
4. For uncovered terms: check if the raw CV text (all fields joined) contains
   the term or any synonym → "addable_honestly", else "genuinely_missing".
5. Return top *n* by salience score.

Integrity rule: never fabricate.  "addable_honestly" only when the term or a
synonym appears ANYWHERE in the raw CV text.  Evidence records where found.
"""
from __future__ import annotations

import re

from decroche.match.offer import parse_offer
from decroche.match.score import _candidate_terms, _check_coverage
from decroche.match.synonyms import expand, normalize
from decroche.match.tfidf import salience as tfidf_salience
from decroche.models import JSONResume, KeywordGap

_TOKEN_RE = re.compile(r"\b\w[\w+#/.'-]{0,49}\b")


def _raw_cv_text(jr: JSONResume) -> str:
    """Flatten all text fields in the resume into a single lowercased string."""
    parts: list[str] = []
    b = jr.basics
    for field in (b.name, b.label, b.email, b.summary):
        if field:
            parts.append(field)
    for work in jr.work:
        if work.name:
            parts.append(work.name)
        if work.position:
            parts.append(work.position)
        if work.summary:
            parts.append(work.summary)
        parts.extend(work.highlights)
    for edu in jr.education:
        for field in (edu.institution, edu.area, edu.studyType):
            if field:
                parts.append(field)
    for skill in jr.skills:
        if skill.name:
            parts.append(skill.name)
        parts.extend(skill.keywords)
    for lang in jr.languages:
        if lang.language:
            parts.append(lang.language)
    return " ".join(parts).lower()


def _term_in_raw(term: str, raw_lower: str) -> str | None:
    """Return evidence string if *term* or any synonym appears in *raw_lower*, else None."""
    # Check term itself
    term_lower = term.lower()
    if re.search(r"\b" + re.escape(term_lower) + r"\b", raw_lower):
        return f"found '{term_lower}' in CV text"

    # Check synonyms
    for alias in expand(normalize(term_lower)):
        if alias != term_lower and re.search(r"\b" + re.escape(alias) + r"\b", raw_lower):
            return f"found synonym '{alias}' in CV text"

    return None


def keyword_gap(
    json_resume: JSONResume,
    offer_text: str,
    n: int = 5,
) -> list[KeywordGap]:
    """Return the top *n* uncovered offer terms ranked by salience × absence.

    Each gap is classified as:
    - "addable_honestly": term or synonym appears anywhere in raw CV text
      (candidate can legitimately add it without fabricating).
    - "genuinely_missing": no trace in CV text at all.

    Args:
        json_resume: Parsed resume.
        offer_text: Raw job offer text.
        n: Maximum number of gaps to return.

    Returns:
        List of KeywordGap sorted by salience descending, length ≤ n.
    """
    offer = parse_offer(offer_text)
    candidates = _candidate_terms(json_resume)
    raw_cv = _raw_cv_text(json_resume)

    all_terms: list[tuple[str, str]] = [
        (t, "must_have") for t in offer.must_have
    ] + [
        (t, "nice_to_have") for t in offer.nice_to_have
    ]

    gaps: list[KeywordGap] = []

    seen_norms: set[str] = set()

    for term, kind in all_terms:
        req_norm = normalize(term)
        if req_norm in seen_norms:
            continue
        seen_norms.add(req_norm)

        coverage = _check_coverage(term, kind, candidates)
        if coverage.covered:
            continue  # Already covered — not a gap.

        sal = tfidf_salience(term.lower(), offer_text)

        evidence = _term_in_raw(term, raw_cv)
        status = "addable_honestly" if evidence is not None else "genuinely_missing"

        gaps.append(
            KeywordGap(
                term=term,
                salience=sal,
                status=status,
                evidence=evidence,
            )
        )

    # Sort by salience descending, take top n.
    gaps.sort(key=lambda g: g.salience, reverse=True)
    return gaps[:n]
