"""recruiter.identify — parse a user-pasted block to identify a recruiter.

COMPLIANCE: NEVER fetches a URL. Operates ONLY on text the user explicitly provides
(LinkedIn profile text copy-pasted, email signature, company "team" page text, etc.).
No automated profile traversal. No scraping.
"""

from __future__ import annotations

import re

from decroche.models import Recruiter

# Title keywords that indicate a recruiter role
_RECRUITER_TITLE_PATTERNS = re.compile(
    r"\b("
    r"recruiter|recruteur|recrutrice"
    r"|talent\s+acquisition|talent\s+partner|talent\s+lead"
    r"|hiring\s+manager|charg[ée]\s+de\s+recrutement"
    r"|hr\s+manager|responsable\s+rh|drh|rrh"
    r"|head\s+of\s+talent|chief\s+people|people\s+partner"
    r"|sourcer|sourcing\s+specialist"
    r"|staffing|placement\s+specialist"
    r")\b",
    re.IGNORECASE,
)

# Agency signals in company name
_AGENCY_SIGNALS = re.compile(
    r"\b("
    r"recruitment|recrutement|staffing|headhunt|headhunting"
    r"|cabinet\s+de\s+recrutement|talent\s+partners"
    r"|esn|ssii|consulting\s+rh|hr\s+consulting"
    r"|search\s+firm|executive\s+search|search\s+&\s+selection"
    r"|interim|intérim|manpower|adecco|hays|michael\s+page"
    r"|robert\s+half|randstad|kelly\s+services|talentsoft"
    r"|approach\s+people|approach\s+recruitment"
    r"|hunt\s+scarce|paradigm\s+exec"
    r")\b",
    re.IGNORECASE,
)

# LinkedIn URL pattern
_LINKEDIN_RE = re.compile(r"https?://(?:www\.)?linkedin\.com/in/[\w\-]+/?", re.IGNORECASE)

# Name heuristic: a line with 2-4 words, each capitalised (with hyphen/apostrophe support)
_NAME_RE = re.compile(
    r"^([A-ZÀ-ÖØ-Ý][A-Za-zà-öø-ÿ\-']+(?:\s+[A-ZÀ-ÖØ-Ý][A-Za-zà-öø-ÿ\-']+){1,3})\s*$"
)


def _extract_name(lines: list[str]) -> str | None:
    """Return the first line that looks like a person's name."""
    for line in lines:
        line = line.strip()
        if _NAME_RE.match(line) and not _RECRUITER_TITLE_PATTERNS.search(line):
            return line
    return None


def _extract_title(lines: list[str]) -> str | None:
    """Return the first line that contains a recruiter/HR title keyword."""
    for line in lines:
        if _RECRUITER_TITLE_PATTERNS.search(line):
            return line.strip()
    return None


def _extract_company(lines: list[str], name: str | None, title_line: str | None) -> str | None:
    """Heuristic: the line after the name or after the title that isn't a contact detail."""
    skip = {name, title_line}
    contact_re = re.compile(r"(@|linkedin\.com|http|www\.|tel:|mob:|mobile:|\+\d)", re.IGNORECASE)
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped in skip or not stripped:
            continue
        # Skip lines that look like contact details
        if contact_re.search(stripped):
            continue
        # Skip pure title lines already captured
        if _RECRUITER_TITLE_PATTERNS.search(stripped):
            continue
        # Skip lines that are entirely in lower case (descriptions / body text)
        if stripped == stripped.lower() and len(stripped) > 30:
            continue
        # A company name candidate: short-ish, not all lower, not just punctuation
        if 2 <= len(stripped) <= 80:
            return stripped
    return None


def _classify_kind(
    company: str | None,
    target_company: str | None = None,
    all_lines: list[str] | None = None,
) -> str:
    """Classify recruiter kind based on company name signals.

    Also scans ``all_lines`` for agency signals when the extracted company doesn't
    trigger them directly (e.g. "TalentSearch" alongside "Cabinet de recrutement").
    """
    if company is None and not all_lines:
        return "unknown"
    # Check extracted company first
    if company and _AGENCY_SIGNALS.search(company):
        return "agency"
    # Check all text lines for agency signals (catches "Cabinet de recrutement ...")
    if all_lines:
        full_text = " ".join(all_lines)
        if _AGENCY_SIGNALS.search(full_text):
            return "agency"
    if company is None:
        return "unknown"
    if target_company and company.lower().strip() == target_company.lower().strip():
        return "in_house"
    # Default: assume in_house if no agency signal and company is present
    return "in_house"


def identify(text: str, target_company: str | None = None) -> Recruiter:
    """Parse a user-pasted text block and return a :class:`Recruiter`.

    COMPLIANCE: reads ONLY the ``text`` argument — never fetches any URL.
    ``target_company`` is used to classify ``kind`` as ``"in_house"`` when the
    company extracted matches; otherwise agency signals are used.

    Args:
        text:           Raw pasted text (LinkedIn profile, email signature, team page).
        target_company: Optional name of the target employer for kind classification.

    Returns:
        Recruiter with name, title, company, kind (in_house/agency/unknown),
        source="pasted", and linkedin_url if found.
    """
    lines = [ln for ln in text.splitlines()]
    non_empty = [ln for ln in lines if ln.strip()]

    name = _extract_name(non_empty) or (non_empty[0].strip() if non_empty else "Unknown")
    title = _extract_title(non_empty)
    title_line = title  # may be None
    company = _extract_company(non_empty, name, title_line)
    kind = _classify_kind(company, target_company, all_lines=non_empty)

    # Extract LinkedIn URL if present
    linkedin_url: str | None = None
    m = _LINKEDIN_RE.search(text)
    if m:
        linkedin_url = m.group(0)

    return Recruiter(
        name=name,
        title=title,
        company=company,
        kind=kind,
        source="pasted",
        linkedin_url=linkedin_url,
    )
