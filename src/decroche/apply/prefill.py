"""apply.prefill — Pure deterministic ATS form pre-fill plan.

Maps well-known ATS form fields from a JSONResume + optional cover letter.
Sensitive fields (password, card, SSN, IBAN, DOB) are NEVER included in the
plan — they are listed in ``excluded_sensitive`` as a defensive registry.
"""

from __future__ import annotations

from decroche.models import JSONResume, JobPosting, PrefillPlan

# Fields that must NEVER be auto-filled. Maintained as a static registry so
# the caller can audit what we refuse to touch.
_SENSITIVE_FIELDS: list[str] = [
    "password",
    "mot_de_passe",
    "card_number",
    "carte_bancaire",
    "cvv",
    "cvc",
    "ssn",
    "social_security_number",
    "iban",
    "dob",
    "date_of_birth",
    "date_naissance",
    "numero_secu",
    "numero_securite_sociale",
]

# ATS common field names that we know how to fill
_FILLABLE_FIELDS = [
    "full_name",
    "email",
    "phone",
    "linkedin",
    "current_company",
    "current_title",
    "location",
    "resume_text",
    "cover_letter",
]


def _find_linkedin(resume: JSONResume) -> str | None:
    for profile in resume.basics.profiles:
        net = (profile.network or "").lower()
        url = profile.url or ""
        if "linkedin" in net or "linkedin.com" in url:
            return url
    return None


def prefill(
    job: JobPosting,
    json_resume: JSONResume,
    cover_letter: str | None = None,
) -> PrefillPlan:
    """Build a PrefillPlan by mapping resume data to common ATS form fields.

    Sensitive fields (password, card number, IBAN, SSN, DOB, etc.) are
    NEVER included in ``fields`` and are always listed in ``excluded_sensitive``.

    Args:
        job:          The target JobPosting (supplies apply_url).
        json_resume:  The candidate's JSON Resume.
        cover_letter: Optional cover letter text.

    Returns:
        PrefillPlan with mapped fields, unmapped fields, and excluded_sensitive.
    """
    basics = json_resume.basics
    fields: dict[str, str] = {}
    unmapped: list[str] = []
    warnings: list[str] = []

    # full_name
    if basics.name:
        fields["full_name"] = basics.name
    else:
        unmapped.append("full_name")

    # email
    if basics.email:
        fields["email"] = basics.email
    else:
        unmapped.append("email")

    # phone
    if basics.phone:
        fields["phone"] = basics.phone
    else:
        unmapped.append("phone")

    # linkedin
    linkedin_url = _find_linkedin(json_resume)
    if linkedin_url:
        fields["linkedin"] = linkedin_url
    else:
        unmapped.append("linkedin")

    # current_company — from most recent work entry
    current_company: str | None = None
    if json_resume.work:
        current_company = json_resume.work[0].name
    if current_company:
        fields["current_company"] = current_company
    else:
        unmapped.append("current_company")

    # current_title — from basics.label or most recent work position
    current_title: str | None = basics.label
    if not current_title and json_resume.work:
        current_title = json_resume.work[0].position
    if current_title:
        fields["current_title"] = current_title
    else:
        unmapped.append("current_title")

    # location
    location_str: str | None = None
    if basics.location:
        loc = basics.location
        parts = [p for p in [loc.city, loc.region, loc.countryCode] if p]
        location_str = ", ".join(parts) if parts else None
    if location_str:
        fields["location"] = location_str
    else:
        unmapped.append("location")

    # cover_letter (only if provided)
    if cover_letter is not None:
        fields["cover_letter"] = cover_letter

    # Defensive: ensure no sensitive key ever leaked into fields
    for sensitive in _SENSITIVE_FIELDS:
        if sensitive in fields:
            del fields[sensitive]
            warnings.append(f"Sensitive field {sensitive!r} was removed from plan.")

    return PrefillPlan(
        apply_url=job.apply_url or job.url,
        fields=fields,
        unmapped=unmapped,
        excluded_sensitive=list(_SENSITIVE_FIELDS),
        warnings=warnings,
    )
