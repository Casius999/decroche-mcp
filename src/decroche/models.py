from __future__ import annotations

from pydantic import BaseModel, Field


class Location(BaseModel):
    address: str | None = None
    postalCode: str | None = None
    city: str | None = None
    countryCode: str | None = None
    region: str | None = None


class Profile(BaseModel):
    network: str | None = None
    username: str | None = None
    url: str | None = None


class Basics(BaseModel):
    name: str | None = None
    label: str | None = None
    email: str | None = None
    phone: str | None = None
    url: str | None = None
    summary: str | None = None
    location: Location | None = None
    profiles: list[Profile] = Field(default_factory=list)


class Work(BaseModel):
    name: str | None = None
    position: str | None = None
    startDate: str | None = None
    endDate: str | None = None
    summary: str | None = None
    highlights: list[str] = Field(default_factory=list)


class Education(BaseModel):
    institution: str | None = None
    area: str | None = None
    studyType: str | None = None
    startDate: str | None = None
    endDate: str | None = None


class Skill(BaseModel):
    name: str | None = None
    level: str | None = None
    keywords: list[str] = Field(default_factory=list)


class Language(BaseModel):
    language: str | None = None
    fluency: str | None = None


class Meta(BaseModel):
    market: str = "fr"
    anonymized: bool = False


class JSONResume(BaseModel):
    basics: Basics = Field(default_factory=Basics)
    work: list[Work] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    skills: list[Skill] = Field(default_factory=list)
    languages: list[Language] = Field(default_factory=list)
    meta: Meta = Field(default_factory=Meta)


class Section(BaseModel):
    name: str          # canonical key, e.g. "experience"
    raw_heading: str   # heading as found in the document
    text: str


class CVParse(BaseModel):
    json_resume: JSONResume
    raw_text: str
    sections: list[Section] = Field(default_factory=list)
    parse_confidence: float
    warnings: list[str] = Field(default_factory=list)


class MarketProfile(BaseModel):
    id: str
    photo: str                # "forbidden" | "optional" | "discouraged"
    personal_info_ok: bool    # DOB / nationality acceptable on CV
    hobbies_common: bool
    cover_letter_expected: bool
    length_ideal_pages: int
    length_max_pages: int
    paper: str                # "A4" | "Letter"
    date_format: str          # "MM/YYYY" | "Mon YYYY"
    spelling: str             # "fr" | "en-US" | "en-GB" | "en-CA"
    anonymized_variant: bool


# ── ATS / double-reader models (Tranche 2) ───────────────────────────────────────────────

class Breakage(BaseModel):
    type: str       # e.g. "two_column", "table", "header_contact", "scanned", "oversized"
    location: str   # human-readable location in the document
    severity: str   # "CRITICAL" | "HIGH" | "MEDIUM" | "LOW"
    fix: str        # concrete remediation instruction


class AtsParseResult(BaseModel):
    ats_id: str
    fmt: str                            # "pdf" | "docx" | "unknown"
    parsability_score: float            # 0-100
    fields_extracted: dict[str, bool]   # field_name → successfully extracted
    fields_lost: list[str]              # fields the ATS will not receive
    breakages: list[Breakage]


class RedFlag(BaseModel):
    flag_id: str    # matches redflags.yaml id
    severity: str   # "CRITICAL" | "HIGH" | "MEDIUM" | "LOW"
    location: str   # e.g. "work[0].highlights[2]"
    evidence: str   # short excerpt or reason
    fix: str        # concrete fix instruction


class ScreenerKit(BaseModel):
    machine_view_text: str      # flattened plain-text as the machine reads it
    rubric: list[str]           # fixed scoring criteria strings
    requirements: list[str]     # extracted from offer_text
    ats_id: str


class ScoreReport(BaseModel):
    parsability: float          # 0-100
    match: float | None         # 0-100 if provided
    screener_readiness: str     # "low" | "medium" | "high"
    redflag_count: int
    delta: dict | None          # {parsability_before, parsability_after, breakage_delta} if after given


# ── Match / gap models (Tranche 3) ───────────────────────────────────────────────────────

class RequirementCoverage(BaseModel):
    requirement: str
    kind: str                   # "must_have" | "nice_to_have"
    covered: bool
    evidence: str | None = None  # e.g. "via synonym k8s" or skill name matched


class Offer(BaseModel):
    title: str | None = None
    must_have: list[str] = Field(default_factory=list)
    nice_to_have: list[str] = Field(default_factory=list)
    seniority: str | None = None   # junior|senior|lead|principal|stagiaire|confirmé or "X+ years/ans"
    hard_requirements: list[str] = Field(default_factory=list)
    raw: str


class MatchScore(BaseModel):
    score_0_100: float
    requirement_coverage: list[RequirementCoverage] = Field(default_factory=list)
    seniority_fit: str          # "under" | "match" | "over" | "unknown"
    missing_must: list[str] = Field(default_factory=list)


class KeywordGap(BaseModel):
    term: str
    salience: float
    status: str                 # "addable_honestly" | "genuinely_missing"
    evidence: str | None = None
