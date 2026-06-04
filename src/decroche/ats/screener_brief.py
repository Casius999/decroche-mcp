"""Screener brief builder — no LLM.

Assembles the 'kit' Claude uses to simulate an ATS screener:
  - machine_view_text: flattened plain text as the ATS sees it
  - rubric: fixed scoring criteria
  - requirements: deterministic keyword extraction from offer_text
"""

from __future__ import annotations

import re
from collections import Counter

from decroche.models import JSONResume, ScreenerKit

# ── Stopwords (bilingual minimal set) ──────────────────────────────────────────────────────────────

_STOPWORDS = frozenset(
    {
        # English
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "for",
        "of",
        "in",
        "to",
        "with",
        "on",
        "at",
        "by",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "that",
        "this",
        "these",
        "those",
        "it",
        "its",
        "we",
        "you",
        "your",
        "they",
        "their",
        "our",
        "as",
        "from",
        "not",
        "no",
        "if",
        "all",
        "any",
        "also",
        "both",
        "each",
        "more",
        "other",
        "such",
        "than",
        "then",
        "there",
        "so",
        "about",
        "up",
        "what",
        "which",
        "who",
        "how",
        "can",
        "us",
        "me",
        "my",
        "he",
        "she",
        "him",
        "her",
        "his",
        "hers",
        # French
        "le",
        "la",
        "les",
        "un",
        "une",
        "des",
        "de",
        "du",
        "et",
        "ou",
        "mais",
        "pour",
        "avec",
        "sur",
        "en",
        "dans",
        "par",
        "est",
        "sont",
        "être",
        "avoir",
        "que",
        "qui",
        "ce",
        "se",
        "au",
        "aux",
        "nous",
        "vous",
        "ils",
        "elles",
        "je",
        "tu",
        "il",
        "elle",
        "on",
        "y",
        "ne",
        "pas",
        "plus",
        "très",
        "bien",
        "tout",
        "tous",
        "toutes",
        "cette",
        "ces",
        "même",
        # Generic filler
        "looking",
        "seeking",
        "candidate",
        "position",
        "role",
        "job",
        "work",
        "team",
        "company",
        "organization",
        "requirements",
        "required",
        "preferred",
        "experience",
        "ability",
        "strong",
        "excellent",
        "good",
        "great",
        "well",
        "profil",
        "poste",
        "emploi",
    }
)

# Multiword skill tokens that should be kept together
_MULTIWORD_SKILLS = [
    "machine learning",
    "deep learning",
    "natural language processing",
    "computer vision",
    "data science",
    "software engineering",
    "software development",
    "full stack",
    "front end",
    "back end",
    "continuous integration",
    "continuous delivery",
    "ci/cd",
    "github actions",
    "gitlab ci",
    "google cloud",
    "amazon web services",
    "microsoft azure",
    "rest api",
    "graphql",
    "postgresql",
    "mysql",
    "mongodb",
    "redis",
    "elasticsearch",
    "apache kafka",
    "docker compose",
    "kubernetes",
    "node.js",
    "react.js",
    "vue.js",
    "angular",
    "spring boot",
    "django",
    "machine learning engineering",
    "mlops",
    "devops",
    "data engineering",
]

# Fixed rubric criteria (used by Claude to simulate screening)
_RUBRIC = [
    "Required qualifications match: verify candidate meets all mandatory requirements",
    "Experience level fit: assess seniority alignment with the role",
    "Technical skills coverage: check keyword and skill overlap with the job description",
    "Quantified impact: look for measurable achievements (%, €, volume, rank)",
    "Active voice and strong verbs: XYZ bullet format (action + result + method)",
    "Section completeness: contact, experience, education, skills all present",
    "ATS parsability: no layout breakages that would cause data loss",
    "Market-specific compliance: photo, personal info, length per market profile",
    "Red-flag absence: no passive voice, banned words, unexplained gaps, job-hopping",
    "Professional contact: name-based email, current contact info in body",
]


# ── Helpers ──────────────────────────────────────────────────────────────────────────────


def _flatten_resume(jr: JSONResume) -> str:
    """Flatten a JSONResume to plain text as an ATS would see it."""
    parts: list[str] = []

    b = jr.basics
    if b.name:
        parts.append(b.name)
    if b.email:
        parts.append(b.email)
    if b.phone:
        parts.append(b.phone)
    if b.summary:
        parts.append(b.summary)

    if jr.work:
        parts.append("Experience")
        for job in jr.work:
            if job.name:
                parts.append(job.name)
            if job.position:
                parts.append(job.position)
            if job.startDate or job.endDate:
                parts.append(f"{job.startDate or ''} - {job.endDate or 'present'}")
            if job.summary:
                parts.append(job.summary)
            for h in job.highlights:
                parts.append(f"- {h}")

    if jr.education:
        parts.append("Education")
        for edu in jr.education:
            tokens = filter(
                None, [edu.institution, edu.area, edu.studyType, edu.startDate, edu.endDate]
            )
            parts.append(", ".join(tokens))

    if jr.skills:
        parts.append("Skills")
        parts.append(", ".join(s.name or "" for s in jr.skills if s.name))

    if jr.languages:
        parts.append("Languages")
        parts.append(
            ", ".join(f"{lang.language or ''} ({lang.fluency or ''})" for lang in jr.languages)
        )

    return "\n".join(parts)


def _extract_requirements(offer_text: str) -> list[str]:
    """Extract key requirements/keywords from the offer text.

    Deterministic: frequency-based, stopword-filtered, multiword skills preserved.
    Returns up to 20 items, sorted by salience (frequency descending).
    """
    if not offer_text or not offer_text.strip():
        return []

    text_lower = offer_text.lower()

    # 1. Find multiword skill tokens first
    found_multiword: list[str] = []
    for skill in _MULTIWORD_SKILLS:
        if skill in text_lower:
            found_multiword.append(skill)

    # 2. Tokenise remaining text into words
    tokens = re.findall(r"[a-zA-ZÀ-ÿ][a-zA-ZÀ-ÿ.#+\-]{2,}", offer_text)
    words = [t.lower() for t in tokens if t.lower() not in _STOPWORDS and len(t) > 2]

    # 3. Count frequencies
    counter = Counter(words)

    # 4. Remove words already covered by multiword skills
    for mw in found_multiword:
        for part in mw.split():
            counter.pop(part, None)

    # 5. Select top unigrams (freq ≥ 1, not stopwords)
    top_unigrams = [word for word, _count in counter.most_common(20)]

    # 6. Combine: multiword skills first, then top unigrams, deduplicate
    seen: set[str] = set()
    result: list[str] = []
    for item in found_multiword + top_unigrams:
        if item not in seen:
            seen.add(item)
            result.append(item)
        if len(result) >= 20:
            break

    return result


# ── Entry point ────────────────────────────────────────────────────────────────────────


def screener_brief(
    json_resume: JSONResume,
    offer_text: str,
    ats_id: str,
) -> ScreenerKit:
    """Build a deterministic screener kit.

    Args:
        json_resume: The parsed CV as a JSONResume.
        offer_text: Raw offer text (job description).
        ats_id: Target ATS identifier.

    Returns:
        ScreenerKit with machine_view_text, rubric, requirements, ats_id.
    """
    machine_view_text = _flatten_resume(json_resume)
    requirements = _extract_requirements(offer_text)

    return ScreenerKit(
        machine_view_text=machine_view_text,
        rubric=_RUBRIC,
        requirements=requirements,
        ats_id=ats_id,
    )
