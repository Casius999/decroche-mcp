"""apply.cover_letter — Honest, deterministic cover-letter scaffold.

``cover_letter(job, json_resume, lang="fr") -> CoverLetter``

HONESTY contract (non-negotiable):
- ``why_me`` bullets are pulled ONLY from real CV data (work highlights/summaries,
  skill names).  Nothing is invented.
- ``why_them`` is a clearly-marked [à compléter: …] placeholder — the host LLM
  fills it using actual company research.  We NEVER invent company facts.
- ``full_scaffold`` assembles all sections with placeholders visibly marked.
- ``notes`` explicitly tell the user/host what must be personalised and what must
  never be invented.

No network calls, no LLM invocations.  Deterministic.
"""

from __future__ import annotations

import re

from decroche.models import CoverLetter, JobPosting, JSONResume

# Maximum number of why_me bullets
_MAX_WHY_ME = 4


# ── language strings ──────────────────────────────────────────────────────────


_CLOSE_FR = (
    "Dans l'attente de votre retour, je reste à votre disposition pour tout échange. Cordialement,"
)

_CLOSE_EN = (
    "Thank you for considering my application. I look forward to the opportunity to "
    "discuss how I can contribute to your team. Best regards,"
)


def _hook(job: JobPosting, lang: str) -> str:
    company_part = f" chez {job.company}" if job.company else ""
    if lang == "en":
        company_part_en = f" at {job.company}" if job.company else ""
        return f"I am writing to express my interest in the {job.title} position{company_part_en}."
    return (
        f"Je vous contacte pour vous faire part de mon intérêt pour le poste de "
        f"{job.title}{company_part}."
    )


def _why_them_placeholder(job: JobPosting, lang: str) -> str:
    company = job.company or "l'entreprise"
    if lang == "en":
        company_en = job.company or "your organisation"
        return (
            f"[à compléter: expliquer pourquoi {company_en} — "
            "insérez ici une raison réelle basée sur vos recherches : "
            "mission, produit, culture, actualité récente. "
            "Ne rien inventer.]"
        )
    return (
        f"[à compléter: expliquer pourquoi {company} — "
        "insérez ici une raison réelle issue de vos recherches sur l'entreprise : "
        "mission, produit, culture, actualité récente. "
        "Ne rien inventer.]"
    )


# ── CV evidence extraction ────────────────────────────────────────────────────


def _extract_cv_bullets(json_resume: JSONResume) -> list[tuple[str, str]]:
    """Return (bullet_text, provenance) pairs from the candidate's real CV.

    Sources (in priority order):
    1. work[].highlights — most specific, already bullet-level
    2. work[].summary — paragraph, split on punctuation
    3. skill names — for skill-name bullets
    """
    results: list[tuple[str, str]] = []

    for i, work in enumerate(json_resume.work):
        provenance_base = f"work[{i}]"
        if work.name and work.position:
            provenance_base = f"work[{i}] ({work.position} @ {work.name})"
        elif work.name:
            provenance_base = f"work[{i}] (@ {work.name})"
        elif work.position:
            provenance_base = f"work[{i}] ({work.position})"

        for j, h in enumerate(work.highlights):
            h = h.strip()
            if h:
                results.append((h, f"{provenance_base}.highlights[{j}]"))

        if work.summary:
            # Split summary into sentence-level chunks
            for sent in re.split(r"[.;]\s+", work.summary):
                sent = sent.strip().rstrip(".")
                if len(sent) > 15:
                    results.append((sent, f"{provenance_base}.summary"))

    for i, skill in enumerate(json_resume.skills):
        if skill.name:
            results.append((skill.name, f"skills[{i}].name"))

    return results


def _select_why_me(
    cv_bullets: list[tuple[str, str]],
    job: JobPosting,
    max_bullets: int = _MAX_WHY_ME,
) -> tuple[list[str], list[str]]:
    """Select up to max_bullets highlights that best overlap with the job description.

    Returns (selected_bullets, evidence_used).

    Overlap is measured by simple token intersection between bullet text and job
    description/title.  Highlights are preferred over summaries and skill names.
    Only REAL CV bullets are used — nothing is generated.
    """
    if not cv_bullets:
        return [], []

    job_tokens: set[str] = set(
        re.findall(
            r"\b[a-zA-Z][a-zA-Z0-9#+/_.-]{1,49}\b", (job.description + " " + job.title).lower()
        )
    )

    def _score(bullet: str) -> int:
        bt = set(re.findall(r"\b[a-zA-Z][a-zA-Z0-9#+/_.-]{1,49}\b", bullet.lower()))
        return len(bt & job_tokens)

    # Sort by score descending, preserving deterministic order by index for ties
    scored = sorted(enumerate(cv_bullets), key=lambda idx_pair: -_score(idx_pair[1][0]))

    # Prefer highlights, then summaries, then skills — take top max_bullets
    # (Already weighted by job overlap; ties resolved by original order)
    selected_bullets: list[str] = []
    evidence_used: list[str] = []

    for _, (bullet, provenance) in scored[:max_bullets]:
        selected_bullets.append(bullet)
        evidence_used.append(provenance)

    return selected_bullets, evidence_used


# ── assembly ──────────────────────────────────────────────────────────────────


def _assemble_scaffold(
    hook: str,
    why_them: str,
    why_me: list[str],
    close: str,
    lang: str,
) -> str:
    lines = [hook, ""]
    if lang == "en":
        lines.append("Why I'm interested in this opportunity:")
    else:
        lines.append("Ce qui m'attire dans cette opportunité :")
    lines.append(why_them)
    lines.append("")
    if lang == "en":
        lines.append("What I bring:")
    else:
        lines.append("Ce que j'apporte :")
    if why_me:
        for bullet in why_me:
            lines.append(f"- {bullet}")
    else:
        if lang == "en":
            lines.append("[à compléter: add specific achievements from your CV]")
        else:
            lines.append("[à compléter: ajoutez des réalisations spécifiques de votre CV]")
    lines.append("")
    lines.append(close)
    return "\n".join(lines)


# ── public API ────────────────────────────────────────────────────────────────


def cover_letter(
    job: JobPosting,
    json_resume: JSONResume,
    lang: str = "fr",
) -> CoverLetter:
    """Build an honest cover-letter scaffold from a job posting and a JSONResume.

    HONESTY: why_me bullets come ONLY from real CV data.  why_them is a
    clearly-marked placeholder.  Nothing about the company is invented.

    Args:
        job:         The target job posting.
        json_resume: The candidate's JSON Resume.
        lang:        "fr" (default) or "en".

    Returns:
        CoverLetter with honest scaffold and placeholders for host LLM to fill.
    """
    hook = _hook(job, lang)
    why_them = _why_them_placeholder(job, lang)
    close = _CLOSE_EN if lang == "en" else _CLOSE_FR

    cv_bullets = _extract_cv_bullets(json_resume)
    why_me_bullets, evidence_used = _select_why_me(cv_bullets, job, max_bullets=_MAX_WHY_ME)

    full_scaffold = _assemble_scaffold(hook, why_them, why_me_bullets, close, lang)

    _company_fr = job.company if job.company else "l'entreprise"

    notes: list[str] = [
        f"Personnalise why_them avec une vraie information sur {_company_fr} ; ne rien inventer.",
        "Les bullets why_me proviennent de ton CV réel — vérifie qu'ils sont toujours d'actualité.",
        "Ajoute ton nom en signature avant d'envoyer.",
    ]
    if lang == "en":
        notes = [
            f"Personalise the why_them section with a real fact about {job.company or 'the company'} — do not invent.",
            "The why_me bullets are drawn from your real CV — verify they are still accurate.",
            "Add your name in the signature before sending.",
        ]

    return CoverLetter(
        role_title=job.title,
        company=job.company,
        lang=lang,
        hook=hook,
        why_them=why_them,
        why_me=why_me_bullets,
        close=close,
        full_scaffold=full_scaffold,
        evidence_used=evidence_used,
        notes=notes,
    )
