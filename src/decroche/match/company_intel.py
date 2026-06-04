"""match.company_intel — deterministic company intelligence synthesiser.

``company_intel(company, jobs) -> CompanyIntel``

Derives ONLY what is knowable from the provided job postings:
- open_roles_count
- locations (unique list)
- remote_ratio (fraction of postings with remote=True)
- tech_tags (frequency map of tags across postings)

Everything else (Glassdoor rating, funding, layoff signals, visa sponsorship) is
placed in a ``research_checklist`` with status ``"to_research"`` — never asserted.

No LLM, no network.  Deterministic.  Honest.
"""
from __future__ import annotations

from collections import Counter

from decroche.models import CompanyIntel, JobPosting

# Items that require external research — always listed as to_research
_RESEARCH_ITEMS = [
    {
        "item": "Glassdoor/Indeed rating and recent reviews",
        "why": "Employee sentiment, management quality, work-life balance signals",
        "status": "to_research",
    },
    {
        "item": "Recent funding / news (Crunchbase, LinkedIn News, TechCrunch)",
        "why": "Growth trajectory, runway, acquisition risk",
        "status": "to_research",
    },
    {
        "item": "Layoff signals (layoffs.fyi, Blind, LinkedIn posts)",
        "why": "Hiring freeze risk, team stability",
        "status": "to_research",
    },
    {
        "item": "Visa sponsorship policy",
        "why": "Eligibility for non-citizens",
        "status": "to_research",
    },
    {
        "item": "Interview process / difficulty (Glassdoor, levels.fyi)",
        "why": "Prep strategy and timeline",
        "status": "to_research",
    },
]


def company_intel(
    company: str,
    jobs: list[JobPosting] | None = None,
) -> CompanyIntel:
    """Synthesise company intelligence from provided job postings.

    Only asserts facts derivable from the postings.  Everything else is a
    research checklist item with status ``"to_research"``.

    Args:
        company: Company name (for labelling).
        jobs:    List of JobPosting objects for this company (may be None/empty).

    Returns:
        CompanyIntel with derived dict, research_checklist, and notes.
    """
    postings = [j for j in (jobs or []) if j.company == company or not company]
    # If company filter yields nothing but jobs were given, use all
    if not postings and jobs:
        postings = list(jobs)

    notes: list[str] = []
    derived: dict = {}

    if postings:
        # open_roles_count
        derived["open_roles_count"] = len(postings)

        # locations
        raw_locations = [j.location for j in postings if j.location]
        unique_locations = list(dict.fromkeys(raw_locations))  # preserve order, dedupe
        derived["locations"] = unique_locations

        # remote_ratio
        remote_flags = [j.remote for j in postings if j.remote is not None]
        if remote_flags:
            remote_ratio = round(sum(1 for f in remote_flags if f) / len(remote_flags), 3)
            derived["remote_ratio"] = remote_ratio
        else:
            notes.append("remote_ratio: remote field absent in all postings — not computed")

        # tech_tags frequency
        all_tags: list[str] = []
        for j in postings:
            all_tags.extend(j.tags)
        if all_tags:
            tag_freq = dict(Counter(all_tags).most_common(20))
            derived["tech_tags"] = tag_freq
        else:
            notes.append("tech_tags: no tags present in postings — not computed")

        # date range
        dates = [j.date_posted for j in postings if j.date_posted]
        if dates:
            derived["earliest_posting"] = min(dates)
            derived["latest_posting"] = max(dates)
    else:
        notes.append(
            "No job postings provided — derived section is empty. "
            "Pass jobs= to enable derived analysis."
        )

    return CompanyIntel(
        company=company,
        derived=derived,
        research_checklist=list(_RESEARCH_ITEMS),  # always include all checklist items
        notes=notes,
    )
