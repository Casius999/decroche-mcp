"""recruiter sub-package — FastMCP sub-server for recruiter intelligence.

Tools (mounted under namespace "recruiter" in the main server):
- identify       : parse user-pasted text → Recruiter
- qualify        : score recruiter fit for a target
- find_contact   : find/guess email (Dropcontact or pattern)
- draft_message  : outreach scaffold (RGPD opt-out included for FR)
- store          : persist recruiter+contact to local JSON store

COMPLIANCE:
- NEVER scrapes any website or LinkedIn. Operates ONLY on user-provided text.
- Email "verified" status is set ONLY via Dropcontact (CNIL-audited).
- French outreach drafts always include RGPD opt-out text.
- Local store always marks records pii=true with 3-year retention metadata.
"""

from __future__ import annotations

from fastmcp import FastMCP

from decroche.models import Contact, IntroRequest, Recruiter, RecruiterQualification
from decroche.recruiter.contact import find_contact as _find_contact
from decroche.recruiter.identify import identify as _identify
from decroche.recruiter.message import draft_message as _draft_message
from decroche.recruiter.qualify import qualify as _qualify
from decroche.recruiter.store import store_recruiter as _store_recruiter

recruiter_server = FastMCP("recruiter")


@recruiter_server.tool
def identify(text: str, target_company: str = "") -> Recruiter:
    """Parse a user-pasted text block to identify a recruiter.

    Operates ONLY on the provided text — never fetches any URL.
    Accepts LinkedIn profile text copy-pasted by the user, email signatures,
    or company "team" page text.

    Args:
        text:           Raw pasted text.
        target_company: Optional target company name for kind classification.

    Returns:
        Recruiter with name, title, company, kind, source="pasted".
    """
    return _identify(text, target_company=target_company or None)


@recruiter_server.tool
def qualify(recruiter: Recruiter, target: dict) -> RecruiterQualification:
    """Score a recruiter's fit against a target job/company context.

    Args:
        recruiter: A Recruiter object.
        target:    Dict with optional keys: company, sector, role, seniority.

    Returns:
        RecruiterQualification with fit_score (0–1), recommend, reasons.
    """
    return _qualify(recruiter, target)


@recruiter_server.tool
async def find_contact(name: str, company: str = "", domain: str = "") -> Contact:
    """Find or guess a recruiter's email.

    If DROPCONTACT_KEY env var is set, calls Dropcontact API (CNIL-audited).
    Otherwise generates a pattern guess (status="guessed_unverified").
    Status "verified" is ONLY set when Dropcontact confirms.

    Args:
        name:    Full name of the recruiter.
        company: Company name (optional, improves Dropcontact results).
        domain:  Email domain (e.g. "acme.com"), required for pattern guessing.

    Returns:
        Contact with honest status.
    """
    return await _find_contact(name, company=company or None, domain=domain or None)


@recruiter_server.tool
def draft_message(
    recruiter: Recruiter,
    candidate_summary: str,
    offer_title: str,
    lang: str = "fr",
) -> IntroRequest:
    """Draft an outreach message scaffold for a recruiter.

    French drafts include a mandatory RGPD opt-out line.

    Args:
        recruiter:         Target recruiter.
        candidate_summary: Short summary of the candidate (1–3 sentences).
        offer_title:       Job title to reference in the message.
        lang:              "fr" (default) or "en".

    Returns:
        IntroRequest with to, subject, body (with opt-out for FR), lang.
    """
    return _draft_message(recruiter, candidate_summary, offer_title, lang=lang)


@recruiter_server.tool
def store(recruiter: Recruiter, contact: Contact, out_path: str) -> dict:
    """Persist a recruiter+contact record to a local JSON store.

    Records are always tagged pii=true with retention_max_years=3 (CNIL).

    Args:
        recruiter: Recruiter object.
        contact:   Contact object (may have status="not_found").
        out_path:  Absolute path to the JSON store file.

    Returns:
        The written record dict.
    """
    return _store_recruiter(recruiter, contact, out_path)
