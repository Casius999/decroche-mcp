from __future__ import annotations

import re
from pathlib import Path

from decroche.models import Basics, CVParse, JSONResume, Section, Skill, Work

# Bilingual canonical heading map (FR + EN).
HEADINGS: dict[str, list[str]] = {
    "summary": ["summary", "professional summary", "profile", "about", "about me",
                "resume", "profil", "a propos"],
    "experience": ["experience", "work experience", "professional experience",
                   "employment", "experience professionnelle", "experiences"],
    "education": ["education", "academic background", "formation", "diplomes"],
    "skills": ["skills", "technical skills", "core competencies",
               "competences", "competences techniques"],
    "certifications": ["certifications", "licenses", "certificats"],
    "languages": ["languages", "langues"],
    "projects": ["projects", "projets"],
    "interests": ["interests", "hobbies", "loisirs", "centres d'interet"],
}


def _strip_accents(s: str) -> str:
    import unicodedata

    return "".join(
        c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)
    )


_ALIAS = {_strip_accents(a): k for k, aliases in HEADINGS.items() for a in aliases}

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"(?:(?:\+|00)\d{1,3}[\s.\-]?)?(?:\(?\d{1,4}\)?[\s.\-]?){2,5}\d")

# Lines whose accent-folded lowercase form are document-title noise (not a person's name).
_NAME_STOPLIST: frozenset[str] = frozenset({"curriculum vitae", "cv", "resume"})


def _first_phone(text: str) -> str | None:
    """Return the first PHONE_RE match that contains at least 7 digits.

    PHONE_RE is intentionally broad and can match short digit sequences such
    as years (``2015``) or metrics (``1.46``).  Requiring ≥7 digits filters
    those false positives while accepting every real phone format.
    """
    for m in PHONE_RE.finditer(text):
        candidate = m.group(0)
        if sum(c.isdigit() for c in candidate) >= 7:
            return candidate.strip()
    return None


def _norm_heading(line: str) -> str | None:
    key = _strip_accents(line.strip().rstrip(":").strip().lower())
    return _ALIAS.get(key)


def split_sections(text: str) -> list[Section]:
    sections: list[Section] = []
    cur_key: str | None = None
    cur_heading = ""
    buf: list[str] = []

    def flush() -> None:
        if cur_key is not None:
            sections.append(
                Section(name=cur_key, raw_heading=cur_heading, text="\n".join(buf).strip())
            )

    for line in text.splitlines():
        key = _norm_heading(line)
        if key is not None:
            flush()
            cur_key, cur_heading, buf = key, line.strip(), []
        else:
            buf.append(line)
    flush()
    return sections


def _bulletize(text: str) -> list[str]:
    out: list[str] = []
    for line in text.splitlines():
        s = line.strip().lstrip("-*•◦·").strip()
        if s:
            out.append(s)
    return out


def to_json_resume(text: str, sections: list[Section]) -> JSONResume:
    by_key = {s.name: s.text for s in sections}
    email_m = EMAIL_RE.search(text)

    name = None
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        # I2: skip lines that look like email/phone contacts or document titles.
        if EMAIL_RE.search(s):
            continue
        if _first_phone(s) is not None:
            continue
        if _strip_accents(s.lower()) in _NAME_STOPLIST:
            continue
        name = s
        break

    basics = Basics(
        name=name,
        email=email_m.group(0) if email_m else None,
        phone=_first_phone(text),  # I1: discard short-digit false positives
        summary=by_key.get("summary") or None,
    )

    skills = [
        Skill(name=tok.strip())
        for tok in re.split(r"[,\n;•]", by_key.get("skills", ""))
        if tok.strip()
    ][:50]

    work: list[Work] = []
    if by_key.get("experience"):
        work = [Work(highlights=_bulletize(by_key["experience"]))]

    return JSONResume(basics=basics, skills=skills, work=work)


def _confidence(text: str, sections: list[Section], has_email: bool) -> tuple[float, list[str]]:
    warnings: list[str] = []
    # I3 (Tranche 1 simplification): we use total extracted-text length as a
    # proxy for scanned/image-only detection.  Spec §11.5 calls for per-page
    # image-only detection; that is deferred to Tranche 2 (``ats.parse_sim``),
    # which performs structural PDF analysis.
    if len(text.strip()) < 50:
        warnings.append("scanned_or_empty: <50 chars extracted; image-only PDF?")
        return 0.0, warnings
    score = 1.0
    if not has_email:
        warnings.append("no_email_detected")
        score -= 0.3
    if not sections:
        warnings.append("no_recognized_sections")
        score -= 0.4
    if len(text.strip()) < 200:
        warnings.append("very_short_text")
        score -= 0.2
    return max(0.0, min(1.0, score)), warnings


def parse_text(text: str) -> CVParse:
    sections = split_sections(text)
    jr = to_json_resume(text, sections)
    conf, warns = _confidence(text, sections, jr.basics.email is not None)
    return CVParse(
        json_resume=jr, raw_text=text, sections=sections,
        parse_confidence=conf, warnings=warns,
    )


def extract_text(path: str | Path, data: bytes | None = None) -> str:
    p = Path(path)
    ext = p.suffix.lower()
    raw = data if data is not None else p.read_bytes()
    if ext in (".txt", ".md"):
        return raw.decode("utf-8", errors="replace")
    if ext == ".docx":
        from decroche.cv.docx_reader import read_docx

        return read_docx(raw)
    if ext == ".pdf":
        from decroche.cv.pdf_reader import read_pdf

        return read_pdf(raw)
    raise ValueError(f"unsupported file type: {ext!r}")


def parse_cv(path: str | Path, data: bytes | None = None) -> CVParse:
    return parse_text(extract_text(path, data))
