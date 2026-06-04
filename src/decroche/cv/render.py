"""Top-level render() orchestrator for Tranche 5.

Produces all requested CV artifacts and validates the ats_docx output
via a live parse_sim round-trip (ATS proof).
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from decroche.cv.render_docx import render_ats_docx
from decroche.cv.render_html import render_pdf_from_html, render_styled_html
from decroche.market.profiles import load_profile
from decroche.models import JSONResume, Render, RenderFile

# ATS IDs to use for round-trip proof
_PROOF_ATS_IDS = ("workday", "generic")

# Default render targets
DEFAULT_TARGETS = ("ats_docx", "styled_html", "json_resume", "plain_text", "pdf")


def _flatten_plain_text(json_resume: JSONResume) -> str:
    """Flatten a JSONResume to plain text."""
    lines: list[str] = []
    b = json_resume.basics

    if b.name:
        lines.append(b.name)
    if b.label:
        lines.append(b.label)

    contact_parts: list[str] = []
    if b.email:
        contact_parts.append(b.email)
    if b.phone:
        contact_parts.append(b.phone)
    if b.url:
        contact_parts.append(b.url)
    if b.location and b.location.city:
        contact_parts.append(b.location.city)
    if contact_parts:
        lines.append(" | ".join(contact_parts))

    lines.append("")

    if b.summary:
        lines.append("SUMMARY")
        lines.append(b.summary)
        lines.append("")

    if json_resume.work:
        lines.append("EXPERIENCE")
        for job in json_resume.work:
            parts: list[str] = []
            if job.position:
                parts.append(job.position)
            if job.name:
                parts.append(job.name)
            header = " @ ".join(parts)
            if job.startDate or job.endDate:
                # Reuse date formatter
                from decroche.cv.render_docx import _date_range

                dr = _date_range(job.startDate, job.endDate)
                if dr:
                    header = f"{header}  ({dr})"
            if header:
                lines.append(header)
            if job.summary:
                lines.append(f"  {job.summary}")
            for h in job.highlights:
                if h.strip():
                    lines.append(f"  • {h.strip()}")
            lines.append("")

    if json_resume.education:
        lines.append("EDUCATION")
        for edu in json_resume.education:
            parts = []
            if edu.studyType:
                parts.append(edu.studyType)
            if edu.area:
                parts.append(edu.area)
            if edu.institution:
                parts.append(edu.institution)
            from decroche.cv.render_docx import _date_range

            dr = _date_range(edu.startDate, edu.endDate)
            entry = ", ".join(parts)
            if dr:
                entry = f"{entry}  ({dr})"
            if entry.strip():
                lines.append(entry.strip())
        lines.append("")

    if json_resume.skills:
        lines.append("SKILLS")
        skill_names = []
        for s in json_resume.skills:
            if s.name:
                skill_names.append(s.name)
        lines.append(", ".join(skill_names))
        lines.append("")

    if json_resume.languages:
        lines.append("LANGUAGES")
        lang_parts = []
        for lang in json_resume.languages:
            if lang.language:
                part = lang.language
                if lang.fluency:
                    part = f"{lang.language} ({lang.fluency})"
                lang_parts.append(part)
        lines.append(", ".join(lang_parts))
        lines.append("")

    return "\n".join(lines)


def render(
    json_resume: JSONResume,
    market_id: str = "fr",
    out_dir: str | Path | None = None,
    targets: tuple[str, ...] = DEFAULT_TARGETS,
) -> Render:
    """Render CV artifacts and return an ATS-proof report.

    Args:
        json_resume: The structured resume data.
        market_id: Market profile id ("fr", "us", "uk", "ca-en", "ca-fr").
        out_dir: Directory for output files. If None, uses a system temp dir.
        targets: Which artifacts to produce. Any of:
            "ats_docx", "styled_html", "pdf", "json_resume", "plain_text".

    Returns:
        Render model with files written, ats_safe_proof scores, and warnings.
    """
    market = load_profile(market_id)
    files: list[RenderFile] = []
    warnings: list[str] = []
    ats_safe_proof: dict[str, float] = {}

    # Resolve output directory
    if out_dir is None:
        _tmp_dir = tempfile.mkdtemp(prefix="decroche_render_")
        out = Path(_tmp_dir)
    else:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)

    # ── ats_docx ─────────────────────────────────────────────────────────────────────────────
    docx_path: Path | None = None
    if "ats_docx" in targets:
        docx_path = out / "cv_ats.docx"
        render_ats_docx(json_resume, market, docx_path)
        files.append(RenderFile(kind="ats_docx", path=str(docx_path.resolve())))

    # ── Round-trip proof ────────────────────────────────────────────────────────────────────
    # Even if ats_docx was not requested, generate a temp docx just for proof
    if docx_path is None or not docx_path.exists():
        _proof_docx = out / "_cv_proof.docx"
        render_ats_docx(json_resume, market, _proof_docx)
        _proof_path = _proof_docx
    else:
        _proof_path = docx_path

    from decroche.ats.parse_sim import parse_sim

    for ats_id in _PROOF_ATS_IDS:
        try:
            result = parse_sim(str(_proof_path), ats_id)
            ats_safe_proof[ats_id] = result.parsability_score
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"ats_proof_{ats_id}_failed: {exc}")

    # ── styled_html ───────────────────────────────────────────────────────────────────────────
    html_str: str | None = None
    if "styled_html" in targets or "pdf" in targets:
        html_str = render_styled_html(json_resume, market)

    if "styled_html" in targets and html_str is not None:
        html_path = out / "cv_styled.html"
        html_path.write_text(html_str, encoding="utf-8")
        files.append(RenderFile(kind="styled_html", path=str(html_path.resolve())))

    # ── pdf (best-effort, guarded) ───────────────────────────────────────────────────────────────
    if "pdf" in targets:
        if html_str is None:
            html_str = render_styled_html(json_resume, market)
        pdf_path = out / "cv_styled.pdf"
        ok = render_pdf_from_html(html_str, pdf_path)
        if ok:
            files.append(RenderFile(kind="pdf", path=str(pdf_path.resolve())))
        else:
            warnings.append(
                "pdf_skipped: weasyprint not available or failed to render PDF; "
                "install with `pip install decroche-mcp[render]`"
            )

    # ── json_resume ───────────────────────────────────────────────────────────────────────────
    if "json_resume" in targets:
        json_path = out / "cv_resume.json"
        json_path.write_text(
            json_resume.model_dump_json(indent=2),
            encoding="utf-8",
        )
        files.append(RenderFile(kind="json_resume", path=str(json_path.resolve())))

    # ── plain_text ───────────────────────────────────────────────────────────────────────────
    if "plain_text" in targets:
        txt_path = out / "cv_plain.txt"
        txt_path.write_text(_flatten_plain_text(json_resume), encoding="utf-8")
        files.append(RenderFile(kind="plain_text", path=str(txt_path.resolve())))

    return Render(
        files=files,
        ats_safe_proof=ats_safe_proof,
        warnings=warnings,
    )
