from __future__ import annotations

from pathlib import Path

from fastmcp import FastMCP

from decroche.cv.parse import parse_cv
from decroche.cv.render import render as _render_cv
from decroche.cv.verify_claims import verify_claims as _verify_claims
from decroche.cv.xyz_scaffold import scaffold_resume
from decroche.models import CVParse, Claim, Render, XyzScaffold

cv_server = FastMCP("cv")


@cv_server.tool
def parse(path: str) -> CVParse:
    """Parse a CV file (PDF/DOCX/MD/TXT) into a validated JSON Resume,
    detected sections, a parse-confidence score, and warnings."""
    return parse_cv(path)


@cv_server.tool
def xyz_scaffold(cv_path: str) -> list[XyzScaffold]:
    """Decompose every highlight bullet in a CV into an XYZ scaffold.

    For each highlight returns: detected verb, achievement object (X),
    metric-present flag (Y), method clause (Z), a fill-in template, and
    a prompt to request a real metric when Y is absent.

    NEVER fabricates metrics — only asks the candidate for real data.
    """
    parsed = parse_cv(cv_path)
    return scaffold_resume(parsed.json_resume)


@cv_server.tool
def verify_claims(cv_path: str) -> list[Claim]:
    """Flag quantified achievements, leadership claims, named project outcomes,
    certifications, and awards that should be backed by a verifiable artefact.

    Returns only actionable claims (needs_evidence=True).
    Suggests the artefact type for each (dashboard link, repo URL, credential
    ID, reference contact, etc.).  The host LLM asks the candidate to supply
    the actual link — never fabricated.
    """
    parsed = parse_cv(cv_path)
    return _verify_claims(parsed.json_resume)


@cv_server.tool
def render(
    cv_path: str,
    market_id: str = "fr",
    out_dir: str | None = None,
) -> Render:
    """Parse a CV file then render ATS-safe export artifacts.

    Produces:
    - ats_docx: ATS-safe single-column DOCX (proven via parse_sim round-trip)
    - styled_html: Self-contained styled HTML (no external assets)
    - pdf: PDF rendered from styled HTML (best-effort; skipped if weasyprint missing)
    - json_resume: Structured JSON Resume (.json)
    - plain_text: Flat plain-text version (.txt)

    Returns a Render model with:
    - files: list of RenderFile(kind, path) — all absolute paths
    - ats_safe_proof: dict of {ats_id → parsability_score} from live round-trip
    - warnings: any non-fatal issues (e.g. pdf_skipped)

    The ats_safe_proof proves the exported DOCX is machine-readable.
    All artifacts are written to out_dir (or a system temp dir if omitted).
    """
    parsed = parse_cv(cv_path)
    out: Path | None = Path(out_dir) if out_dir is not None else None
    return _render_cv(parsed.json_resume, market_id=market_id, out_dir=out)
