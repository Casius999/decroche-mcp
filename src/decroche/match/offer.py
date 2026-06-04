"""Deterministic offer/job-description parser.

``parse_offer(text) -> Offer`` extracts:
- title (first non-empty line)
- must_have skills (under "Required / Requirements / must have / exigé /
  requis / profil recherché" sections)
- nice_to_have skills (under "Nice to have / plus / atout / apprécié" sections)
- seniority (keyword + "X+ years/ans" patterns)
- hard_requirements (raw sentences that mention years of experience)
- raw (original text)

Fallback when no sections found: salient tech tokens → must_have.

No LLM, no network.  Deterministic.
"""
from __future__ import annotations

import re


from decroche.match.tfidf import salience
from decroche.models import Offer

# ── Section heading patterns ─────────────────────────────────────────────────────

_MUST_PATTERNS = re.compile(
    r"^\s*(?:"
    r"requirements?|required|must[\s\-]have|exig[eé]|requis|profil\s+recherch[eé]"
    r")\s*:?\s*$",
    re.IGNORECASE | re.MULTILINE,
)

_NICE_PATTERNS = re.compile(
    r"^\s*(?:"
    r"nice[\s\-]to[\s\-]have|bonus|plus|atout|appr[eé]ci[eé]|un\s+plus|would\s+be\s+a\s+plus"
    r")\s*:?\s*$",
    re.IGNORECASE | re.MULTILINE,
)

# Generic "next section" boundary — headings likely to delimit end of must/nice blocks.
_SECTION_BOUNDARY = re.compile(
    r"^\s*(?:"
    r"responsibilities|about\s+(?:us|the\s+role|you)|we\s+offer|benefits?|"
    r"compensation|what\s+you|missions?|responsabilit[eé]s?|ce\s+que|"
    r"nous\s+offrons|avantages?|salary|salaire|r[eé]mun[eé]ration"
    r")\s*:?\s*$",
    re.IGNORECASE | re.MULTILINE,
)

# ── Seniority patterns ───────────────────────────────────────────────────────

_SENIORITY_KEYWORDS = re.compile(
    r"\b(junior|senior|lead|principal|stagiaire|stage|confirm[eé])\b",
    re.IGNORECASE,
)

_SENIORITY_NORMALISE: dict[str, str] = {
    "stage": "stagiaire",
    "confirme": "confirmé",
}

_YEARS_PATTERN = re.compile(
    r"\b(\d+)\s*\+?\s*(?:years?|ans?)\s*(?:of\s+)?(?:experience|exp[eé]rience)?\b",
    re.IGNORECASE,
)

# ── Tech token extraction ──────────────────────────────────────────────────────

# Tokens that look like technology names: capitalised, contain +/#, or known
# lowercase canonical tech terms from synonym map.
_TECH_TOKEN_RE = re.compile(r"\b[A-Z][a-zA-Z0-9+#/.'-]{1,49}\b")
_LOWERED_TECH = {
    "python", "go", "rust", "java", "scala", "ruby", "swift", "kotlin",
    "typescript", "javascript", "html", "css", "sql", "bash", "linux",
    "docker", "kubernetes", "terraform", "ansible", "nginx", "redis",
    "postgres", "postgresql", "mysql", "mongodb", "elasticsearch",
    "kafka", "rabbitmq", "graphql", "rest", "api", "grpc",
    "spark", "hadoop", "airflow", "dbt", "pandas", "numpy",
    "aws", "gcp", "azure", "k8s", "git", "github", "gitlab",
    "react", "vue", "angular", "nodejs", "django", "flask",
}

# Words that look capitalised but are definitely not tech skills.
_STOPWORDS_TITLE = frozenset({
    "The", "A", "An", "And", "Or", "But", "In", "On", "At", "To", "For",
    "Of", "With", "By", "From", "Is", "Are", "Was", "Were", "Be", "We",
    "You", "It", "As", "If", "This", "That", "These", "Those", "Our",
    "Your", "Its", "Their", "My", "Who", "Which", "What",
    # FR
    "Le", "La", "Les", "De", "Du", "Des", "Un", "Une", "Et", "Ou", "En",
    "Dans", "Sur", "Avec", "Par", "Pour", "Est", "Sont", "Nous", "Vous",
    "Il", "Elle", "Ils", "Elles", "Ce", "Cette", "Ces",
    # Offer section keywords (not skills)
    "Requirements", "Required", "Skills", "Experience", "Background",
    "Education", "Benefits", "Responsibilities", "About", "Missions",
    "Responsibilities", "Profil", "Compétences", "Formation",
})


def _extract_section_lines(text: str, start_pattern: re.Pattern) -> list[str]:
    """Extract bullet/dash lines from a section delimited by start_pattern.

    Returns lines from the first match of *start_pattern* until the next blank
    line group, another section marker, or end of text.
    """
    lines: list[str] = []
    in_section = False
    consecutive_blanks = 0

    for line in text.splitlines():
        if start_pattern.match(line):
            in_section = True
            consecutive_blanks = 0
            continue

        if in_section:
            stripped = line.strip()
            if not stripped:
                consecutive_blanks += 1
                if consecutive_blanks >= 2:
                    break
                continue
            consecutive_blanks = 0

            # Stop at the next recognizable section heading.
            if _MUST_PATTERNS.match(line) or _NICE_PATTERNS.match(line) or _SECTION_BOUNDARY.match(line):
                break

            # Accept bullet lines or plain text lines.
            cleaned = stripped.lstrip("-*•◦·▸▹–—").strip()
            if cleaned:
                lines.append(cleaned)

    return lines


def _is_hard_req(line: str) -> bool:
    return bool(_YEARS_PATTERN.search(line))


def _extract_skills_from_lines(lines: list[str]) -> tuple[list[str], list[str]]:
    """Split lines into skills and hard_requirements.

    Hard requirements contain year patterns; skills are the rest.
    Returns (skills, hard_requirements).
    """
    skills: list[str] = []
    hard: list[str] = []
    for line in lines:
        if _is_hard_req(line):
            hard.append(line)
            # Also try to extract a skill name from the line (e.g. "Python, 5+ years")
            # Extract everything before the years mention.
            before_years = _YEARS_PATTERN.split(line)[0].strip().rstrip(",").strip()
            if before_years and len(before_years) < 50:
                skills.append(before_years)
        else:
            skills.append(line)
    return skills, hard


def _tech_tokens_from_text(text: str, top_n: int = 15) -> list[str]:
    """Extract likely tech tokens from unstructured text, ranked by salience."""
    candidates: set[str] = set()

    # Capitalised tokens not in stopwords.
    for tok in _TECH_TOKEN_RE.findall(text):
        if tok not in _STOPWORDS_TITLE and len(tok) >= 2:
            candidates.add(tok)

    # Known lowercase tech terms.
    for tok in _LOWERED_TECH:
        if re.search(r"\b" + re.escape(tok) + r"\b", text, re.IGNORECASE):
            candidates.add(tok.capitalize() if tok[0].islower() else tok)

    scored = sorted(candidates, key=lambda t: salience(t.lower(), text), reverse=True)
    return scored[:top_n]


def parse_offer(text: str) -> Offer:
    """Parse a raw job offer/description into a structured ``Offer``.

    Strategy:
    1. title = first non-empty line.
    2. Seniority = keyword or "X+ years" pattern found anywhere.
    3. Detect must_have and nice_to_have sections.
    4. Fallback (no sections): salient tech tokens → must_have.
    5. Deduplicate; ensure must_have ∩ nice_to_have = ∅.
    """
    lines_raw = text.splitlines()

    # 1. Title — first non-empty line
    title: str | None = None
    for line in lines_raw:
        stripped = line.strip()
        if stripped:
            title = stripped
            break

    # 2. Seniority
    seniority: str | None = None
    kw_match = _SENIORITY_KEYWORDS.search(text)
    if kw_match:
        raw_kw = kw_match.group(1).lower()
        seniority = _SENIORITY_NORMALISE.get(raw_kw, raw_kw)
    else:
        yr_match = _YEARS_PATTERN.search(text)
        if yr_match:
            seniority = f"{yr_match.group(1)}+ years"

    # 3. Section extraction
    must_lines = _extract_section_lines(text, _MUST_PATTERNS)
    nice_lines = _extract_section_lines(text, _NICE_PATTERNS)

    must_skills, hard_reqs = _extract_skills_from_lines(must_lines)
    nice_skills, _ = _extract_skills_from_lines(nice_lines)

    has_sections = bool(must_lines or nice_lines)

    # 4. Fallback
    if not has_sections:
        must_skills = _tech_tokens_from_text(text)
        hard_reqs = [
            line.strip()
            for line in text.splitlines()
            if _is_hard_req(line.strip()) and line.strip()
        ]

    # 5. Deduplicate and ensure disjoint sets
    def _dedup(lst: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for item in lst:
            key = item.lower().strip()
            if key and key not in seen:
                seen.add(key)
                out.append(item.strip())
        return out

    must_skills = _dedup(must_skills)
    nice_skills = _dedup(nice_skills)

    # Remove from nice_have anything already in must_have.
    must_lower = {m.lower() for m in must_skills}
    nice_skills = [n for n in nice_skills if n.lower() not in must_lower]

    return Offer(
        title=title,
        must_have=must_skills,
        nice_to_have=nice_skills,
        seniority=seniority,
        hard_requirements=_dedup(hard_reqs),
        raw=text,
    )
