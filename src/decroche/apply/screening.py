"""apply.screening — Honest, deterministic screening-question answerer.

``answer_screening(question, json_resume, offer=None) -> ScreeningAnswer``

HONESTY contract (non-negotiable):
- Work authorization / visa / sponsorship → ALWAYS needs_human=True, suggested_answer=None.
- Salary expectations → ALWAYS needs_human=True, suggested_answer=None.
- Relocation / notice period / availability / start date → ALWAYS needs_human=True.
- "Why do you want to work here" → ALWAYS needs_human=True.
- Unknown questions → needs_human=True.
- Only factual, derivable answers from the CV are returned with source="derived_from_cv".
- NEVER fabricates eligibility, authorization, availability, or salary.

No network calls, no LLM invocations.  Deterministic.
"""

from __future__ import annotations

import re
from datetime import date

from decroche.models import JSONResume, ScreeningAnswer

# ── pattern lists (order matters — more specific first) ───────────────────────

# Authorization / visa — ALWAYS needs_human
_AUTHORIZATION_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\bauthoriz",
        r"\bwork\s+(authorization|permit|visa|eligib)",
        r"\bvisa\b",
        r"\bsponsorship\b",
        r"\bsponsor\b",
        r"\bright\s+to\s+work",
        r"\bdroit\s+de\s+travailler",
        r"\bautoris[ée]\b",
        r"\bpermis\s+de\s+travail",
        r"\béligib",
        r"\beligib",
        r"\bcould\s+you\s+legally",
        r"\blegally\s+work",
        r"\bcan\s+you\s+(legally|work)",
    ]
]

# Salary — ALWAYS needs_human
_SALARY_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\bsalar[yi]",
        r"\bcompensation\b",
        r"\bpay\b",
        r"\bremunera",
        r"\bpaid\b",
        r"\bpretentions?\s+salarial",
        r"\bsalaire\b",
        r"\bremunér",
        r"\bsalary\s+expect",
        r"\bexpected\s+salary",
        r"\bwhat\s+(do\s+you\s+expect|are\s+you\s+(looking|expecting)\s+for|compensation)",
    ]
]

# Relocation / notice / start date — ALWAYS needs_human
_AVAILABILITY_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\brelocat",
        r"\bmobile\b",
        r"\bmobilit[eé]\b",
        r"\bnotice\s+period",
        r"\bpréavis\b",
        r"\bpreavis\b",
        r"\bavailab",
        r"\bdisponib",
        r"\bstart\s+date",
        r"\bwhen\s+can\s+you\s+start",
        r"\bquand\s+(pouvez|peut)",
        r"\bdate\s+de\s+début",
        r"\bwilling\s+to\s+(move|relocate)",
    ]
]

# "Why this company" — ALWAYS needs_human
_WHY_HERE_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\bwhy\s+(do\s+you\s+want|are\s+you\s+interested|this\s+company|this\s+role|work\s+here)",
        r"\bpourquoi\s+(voulez|souhaitez|cette\s+entreprise|ce\s+poste|travailler\s+ici)",
        r"\bwhat\s+attracts\s+you",
        r"\bwhat\s+interests\s+you",
    ]
]

# Years of experience (total or per skill)
_YEARS_EXP_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\bhow\s+many\s+years",
        r"\byears\s+of\s+experience",
        r"\byears?\s+experience",
        r"\bcombien\s+d.ann[ée]es",
        r"\dann[ée]es\s+d.exp[eé]rience",
        r"\bann[ée]es?\s+d.exp[eé]rience",
    ]
]

# Skill experience question
_SKILL_EXP_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\bdo\s+you\s+have\s+(experience\s+with|knowledge\s+of|worked\s+with)",
        r"\bavez[- ]vous\s+(de\s+l.exp[eé]rience|travaill[eé])\s+(avec|en|sur)",
        r"\bexperience\s+with\b",
        r"\bfamiliar\s+with\b",
        r"\bknowledge\s+of\b",
        r"\bused\s+\w+\s+(before|previously)",
        r"\bdo\s+you\s+know\b",
        r"\bavez[- ]vous\s+utilis[eé]",
        r"\bavez[- ]vous\s+une\s+exp[eé]rience",
        r"\bmaîtrisez[- ]vous",
    ]
]


# ── date utilities ────────────────────────────────────────────────────────────


def _parse_year_month(date_str: str | None) -> date | None:
    """Parse 'YYYY-MM' or 'YYYY' into a date object. Returns None if unparseable."""
    if not date_str:
        return None
    # Try YYYY-MM-DD
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", date_str.strip())
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    # Try YYYY-MM
    m = re.match(r"^(\d{4})-(\d{2})$", date_str.strip())
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), 1)
        except ValueError:
            pass
    # Try YYYY
    m = re.match(r"^(\d{4})$", date_str.strip())
    if m:
        return date(int(m.group(1)), 1, 1)
    return None


def _total_years_from_work(json_resume: JSONResume) -> float:
    """Sum up total experience months from work entries, return as decimal years."""
    today = date.today()
    total_days = 0
    for work in json_resume.work:
        start = _parse_year_month(work.startDate)
        if start is None:
            continue
        end_raw = work.endDate
        if end_raw and end_raw.lower() in ("present", "current", "aujourd'hui", ""):
            end = today
        else:
            end = _parse_year_month(work.endDate) or today
        if end < start:
            continue
        total_days += (end - start).days
    return round(total_days / 365.25, 1)


# ── skill detection ───────────────────────────────────────────────────────────


def _normalize_term(t: str) -> str:
    return t.lower().strip()


def _candidate_skill_terms(json_resume: JSONResume) -> set[str]:
    """Return a flat set of normalized skill/experience terms from the CV."""
    terms: set[str] = set()
    for skill in json_resume.skills:
        if skill.name:
            terms.add(_normalize_term(skill.name))
        for kw in skill.keywords:
            if kw:
                terms.add(_normalize_term(kw))
    for work in json_resume.work:
        if work.position:
            for tok in re.findall(r"\b\w[\w+#./\-]{1,49}\b", work.position.lower()):
                terms.add(tok)
        if work.summary:
            for tok in re.findall(r"\b\w[\w+#./\-]{1,49}\b", work.summary.lower()):
                terms.add(tok)
        for h in work.highlights:
            for tok in re.findall(r"\b\w[\w+#./\-]{1,49}\b", h.lower()):
                terms.add(tok)
    return terms


def _extract_skill_from_question(question: str) -> str | None:
    """Try to extract the target skill/tool from a skill-experience question."""
    patterns = [
        r"experience\s+with\s+([A-Za-z][A-Za-z0-9#+_.\-/ ]{1,40}?)(?:\?|$|\s+in\b|\s+for\b|\s+or\b)",
        r"knowledge\s+of\s+([A-Za-z][A-Za-z0-9#+_.\-/ ]{1,40}?)(?:\?|$|\s+in\b)",
        r"familiar\s+with\s+([A-Za-z][A-Za-z0-9#+_.\-/ ]{1,40}?)(?:\?|$)",
        r"have\s+you\s+(?:used|worked\s+with|worked\s+on)\s+([A-Za-z][A-Za-z0-9#+_.\-/ ]{1,40}?)(?:\?|$|\s+before\b)",
        r"do\s+you\s+know\s+([A-Za-z][A-Za-z0-9#+_.\-/ ]{1,40}?)(?:\?|$)",
        r"avez[- ]vous\s+(?:utilis[eé]|une\s+exp[eé]rience\s+avec|travaill[eé]\s+(?:avec|sur))\s+([A-Za-z][A-Za-z0-9#+_.\-/ ]{1,40}?)(?:\?|$|\s+en\b)",
        r"maîtrisez[- ]vous\s+([A-Za-z][A-Za-z0-9#+_.\-/ ]{1,40}?)(?:\?|$)",
        r"avec\s+([A-Za-z][A-Za-z0-9#+_.\-/ ]{1,40}?)(?:\?|$|\s+\?)",
    ]
    for pat in patterns:
        m = re.search(pat, question, re.IGNORECASE)
        if m:
            skill = m.group(1).strip().rstrip("?. ")
            return skill.lower()
    return None


def _skill_in_cv(skill_name: str, candidate_terms: set[str]) -> bool:
    """Check whether a skill name (or close variant) is present in candidate terms."""
    normalized = _normalize_term(skill_name)
    if normalized in candidate_terms:
        return True
    tokens = re.findall(r"\b\w[\w+#./\-]{1,49}\b", normalized)
    for tok in tokens:
        if tok in candidate_terms:
            return True
    return False


# ── answer builders ───────────────────────────────────────────────────────────


def _needs_human_answer(question: str) -> ScreeningAnswer:
    return ScreeningAnswer(
        question=question,
        suggested_answer=None,
        source="needs_human",
        confidence="none",
        needs_human=True,
    )


def _answer_years(
    question: str, json_resume: JSONResume, skill: str | None = None
) -> ScreeningAnswer:
    total_years = _total_years_from_work(json_resume)
    if total_years == 0.0:
        return ScreeningAnswer(
            question=question,
            suggested_answer=None,
            source="needs_human",
            confidence="none",
            needs_human=True,
        )
    years_int = int(total_years)
    if skill:
        answer = (
            f"I have approximately {years_int} years of overall professional experience, including work with {skill}."
            if years_int
            else f"I have some experience with {skill} across my roles."
        )
    else:
        answer = f"I have approximately {years_int} year{'s' if years_int != 1 else ''} of professional experience."
    return ScreeningAnswer(
        question=question,
        suggested_answer=answer,
        source="derived_from_cv",
        confidence="medium",
        needs_human=False,
    )


def _answer_skill(question: str, skill_name: str, json_resume: JSONResume) -> ScreeningAnswer:
    candidate_terms = _candidate_skill_terms(json_resume)
    present = _skill_in_cv(skill_name, candidate_terms)
    if present:
        answer = (
            f"Yes, I have experience with {skill_name.title()}. "
            "This is reflected in my work history and/or skills section."
        )
        return ScreeningAnswer(
            question=question,
            suggested_answer=answer,
            source="derived_from_cv",
            confidence="high",
            needs_human=False,
        )
    else:
        answer = (
            f"No, {skill_name.title()} is not listed in my current CV. "
            "I do not have documented experience with this technology."
        )
        return ScreeningAnswer(
            question=question,
            suggested_answer=answer,
            source="derived_from_cv",
            confidence="high",
            needs_human=False,
        )


# ── main public API ───────────────────────────────────────────────────────────


def answer_screening(
    question: str,
    json_resume: JSONResume,
    offer: dict | None = None,
) -> ScreeningAnswer:
    """Answer a screening question factually from the CV, or flag needs_human."""
    if any(pat.search(question) for pat in _AUTHORIZATION_PATTERNS):
        return _needs_human_answer(question)
    if any(pat.search(question) for pat in _SALARY_PATTERNS):
        return _needs_human_answer(question)
    if any(pat.search(question) for pat in _AVAILABILITY_PATTERNS):
        return _needs_human_answer(question)
    if any(pat.search(question) for pat in _WHY_HERE_PATTERNS):
        return _needs_human_answer(question)
    if any(pat.search(question) for pat in _YEARS_EXP_PATTERNS):
        skill = _extract_skill_from_question(question)
        return _answer_years(question, json_resume, skill=skill)
    if any(pat.search(question) for pat in _SKILL_EXP_PATTERNS):
        skill = _extract_skill_from_question(question)
        if skill:
            return _answer_skill(question, skill, json_resume)
        return _needs_human_answer(question)
    return _needs_human_answer(question)
