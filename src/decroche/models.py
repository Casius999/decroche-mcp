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


# ── ATS / double-reader models (Tranche 2) ──────────────────────────────────────────────

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


# ── Match / gap models (Tranche 3) ─────────────────────────────────────────────────

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


# ── Rewrite scaffolding models (Tranche 4) ──────────────────────────────────────────────

class XyzScaffold(BaseModel):
    """Skeleton for an XYZ-formula bullet rewrite.

    The host LLM fills the prose; this model provides structure + diagnostics.
    """
    original: str                    # The raw bullet as-found in the CV
    verb: str | None                 # Leading action verb detected (lowercased)
    x: str                           # Achievement object (what was accomplished)
    y_present: bool                  # True if a metric was detected (%, €, $, ×, number)
    z: str | None                    # Method clause after "by/via/using/en/à l'aide de"
    template: str                    # Filled template with bracketed placeholders for unknowns
    missing_metric_prompt: str | None  # Set when y_present=False — asks for real data only
    weak_verb: bool                  # True if verb is a duty/responsibility phrase not in strong list


class Claim(BaseModel):
    """A claim in the CV that should be backed by a verifiable artefact."""
    text: str                        # The bullet / claim text
    needs_evidence: bool             # True if the claim should be backed by an artefact
    suggested_artifact: str          # What type of artefact would support this claim
    location: str                    # JSON-path-style location, e.g. "work[0].highlights[2]"


# ── Render models (Tranche 5) ──────────────────────────────────────────────────────

class RenderFile(BaseModel):
    """A single output artifact produced by cv.render."""
    kind: str   # "ats_docx" | "styled_html" | "pdf" | "json_resume" | "plain_text"
    path: str   # Absolute path to the written file


class Render(BaseModel):
    """Result of cv.render: produced files + ATS round-trip proof + warnings."""
    files: list[RenderFile] = Field(default_factory=list)
    ats_safe_proof: dict[str, float] = Field(default_factory=dict)
    # key = "{ats_id}" → parsability_score (0-100)
    warnings: list[str] = Field(default_factory=list)


# ── Source / job-board models (Phase 2) ─────────────────────────────────────────────

class JobPosting(BaseModel):
    """A normalised job posting from any provider."""
    source: str                          # provider id, e.g. "greenhouse"
    source_id: str                       # opaque id within that provider
    title: str
    company: str | None = None
    location: str | None = None
    remote: bool | None = None
    url: str                             # canonical job URL
    apply_url: str | None = None
    date_posted: str | None = None       # ISO-8601 or provider string; None if absent
    description: str                     # full text; may be HTML or plain
    salary: str | None = None
    tags: list[str] = Field(default_factory=list)
    raw: dict = Field(default_factory=dict)   # original item dict from provider


class SourceResult(BaseModel):
    """Aggregated result from a single source-provider tool call."""
    provider: str
    query: str | None = None
    count: int
    jobs: list[JobPosting] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


# ── Phase 2b models ─────────────────────────────────────────────────────────────

class SuccessProbability(BaseModel):
    """Deterministic estimate of application success probability."""
    score_0_100: float
    factors: dict[str, float] = Field(default_factory=dict)
    # Keys: "fit", "recency", "competition", "hiring_signal", "network"
    confidence: str  # "low" | "med" | "high"
    notes: list[str] = Field(default_factory=list)


class CompanyIntel(BaseModel):
    """Synthesised company intelligence derived from job postings + research checklist."""
    company: str
    derived: dict = Field(default_factory=dict)
    # E.g. open_roles_count, locations, remote_ratio, tech_tags
    research_checklist: list[dict] = Field(default_factory=list)
    # Each item: {item, status: "to_research"}
    notes: list[str] = Field(default_factory=list)


class MonitorDiff(BaseModel):
    """Result of comparing a current provider fetch against a stored snapshot."""
    provider: str
    key: str
    new_jobs: list[JobPosting] = Field(default_factory=list)
    new_count: int
    total_count: int
