"""match sub-package — FastMCP sub-server exposing score and keyword_gap tools.

Tools (mounted under namespace "match" in the main server):
- match_score  : compute skill-coverage score between a CV file and offer text
- match_keyword_gap : top-N uncovered offer keywords with addable/missing status

All tools are thin wrappers: CV parsing delegates to ``decroche.cv.parse.parse_cv``;
offer parsing to ``decroche.match.offer.parse_offer``.
No LLM, no network.  Deterministic.
"""
from __future__ import annotations

from fastmcp import FastMCP

from decroche.cv.parse import parse_cv
from decroche.match.keyword_gap import keyword_gap as _keyword_gap
from decroche.match.score import match_score as _match_score
from decroche.models import KeywordGap, MatchScore

match_server = FastMCP("match")


@match_server.tool
def score(cv_path: str, offer_text: str) -> MatchScore:
    """Compute a skill-coverage match score between a CV file and a job offer.

    Args:
        cv_path: Path to the CV file (PDF/DOCX/MD/TXT).
        offer_text: Raw job-offer/job-description text.

    Returns:
        MatchScore with score_0_100, per-requirement coverage, seniority_fit,
        and missing_must list.
    """
    cv_parse = parse_cv(cv_path)
    return _match_score(cv_parse.json_resume, offer_text)


@match_server.tool
def keyword_gap(cv_path: str, offer_text: str, n: int = 5) -> list[KeywordGap]:
    """Return the top-N offer keywords not covered by the CV, ranked by salience.

    Each gap is classified as:
    - "addable_honestly": term or synonym appears anywhere in CV text.
    - "genuinely_missing": no trace in the CV at all.

    Args:
        cv_path: Path to the CV file (PDF/DOCX/MD/TXT).
        offer_text: Raw job-offer/job-description text.
        n: Maximum number of gaps to return (default 5).

    Returns:
        List of KeywordGap sorted by salience descending, length ≤ n.
    """
    cv_parse = parse_cv(cv_path)
    return _keyword_gap(cv_parse.json_resume, offer_text, n=n)
