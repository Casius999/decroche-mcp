"""Styled HTML CV renderer (hand-rolled, no Jinja2).

Produces a single-file HTML + inline CSS with tasteful, intentional design:
- Clear hierarchy via scale contrast (name >> headings >> body)
- One accent colour (deep indigo)
- System-stack fonts for reliability
- Generous whitespace, semantic HTML
- No external assets — fully self-contained

PDF rendering via weasyprint is guarded: if unavailable or system deps missing,
render_pdf_from_html() returns False (caller records a warning, never crashes).
"""
from __future__ import annotations

import html as html_module
import re
from pathlib import Path

from decroche.models import JSONResume, MarketProfile

# Month abbreviations for date formatting
_MONTHS = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]

_DATE_RE = re.compile(r"^(\d{4})-(\d{1,2})(?:-\d+)?$")


def _fmt_date(raw: str | None) -> str:
    if not raw:
        return ""
    raw = raw.strip()
    if re.match(r"^[A-Za-z]{3}\s+\d{4}$", raw):
        return raw
    m = _DATE_RE.match(raw)
    if m:
        year = int(m.group(1))
        month = int(m.group(2))
        if 1 <= month <= 12:
            return f"{_MONTHS[month - 1]} {year}"
        return str(year)
    if raw.lower() in ("ongoing", "present", "current"):
        return "Present"
    return raw


def _date_range(start: str | None, end: str | None) -> str:
    s = _fmt_date(start)
    e = _fmt_date(end) or "Present"
    if s and e:
        return f"{s} – {e}"
    return s or e


def _esc(text: str | None) -> str:
    """HTML-escape a string safely."""
    if not text:
        return ""
    return html_module.escape(str(text))


_CSS = """
* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

:root {
  --color-bg: #ffffff;
  --color-surface: #f8f9fc;
  --color-text: #1a1a2e;
  --color-muted: #555577;
  --color-accent: #3d2b8e;
  --color-accent-light: #ede9f8;
  --color-divider: #dde1f0;

  --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
               "Helvetica Neue", Arial, sans-serif;
  --font-mono: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;

  --radius: 4px;
  --space-xs: 4px;
  --space-sm: 8px;
  --space-md: 16px;
  --space-lg: 28px;
  --space-xl: 44px;
}

body {
  font-family: var(--font-sans);
  font-size: 10.5pt;
  line-height: 1.6;
  color: var(--color-text);
  background: var(--color-bg);
  max-width: 780px;
  margin: 0 auto;
  padding: var(--space-xl) var(--space-lg);
}

/* ── Header / identity ────────────────────────────────────────────────── */
header {
  border-bottom: 2px solid var(--color-accent);
  padding-bottom: var(--space-md);
  margin-bottom: var(--space-lg);
}

.name {
  font-size: 2.2rem;
  font-weight: 700;
  letter-spacing: -0.03em;
  color: var(--color-text);
  line-height: 1.1;
}

.label {
  font-size: 1.05rem;
  color: var(--color-accent);
  font-weight: 500;
  margin-top: var(--space-xs);
}

.contact {
  margin-top: var(--space-sm);
  font-size: 0.88rem;
  color: var(--color-muted);
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-sm);
}

.contact-item::after {
  content: "·";
  margin-left: var(--space-sm);
  color: var(--color-divider);
}

.contact-item:last-child::after {
  content: "";
}

/* ── Main content ────────────────────────────────────────────────────── */
main {
  display: flex;
  flex-direction: column;
  gap: var(--space-lg);
}

/* ── Section ─────────────────────────────────────────────────────────── */
section {
  break-inside: avoid;
}

.section-title {
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: var(--color-accent);
  border-bottom: 1px solid var(--color-divider);
  padding-bottom: var(--space-xs);
  margin-bottom: var(--space-md);
}

/* ── Summary ─────────────────────────────────────────────────────────── */
.summary-text {
  color: var(--color-muted);
  font-size: 0.95rem;
  line-height: 1.7;
}

/* ── Experience / Education entries ─────────────────────────────────────── */
.entry {
  margin-bottom: var(--space-md);
}

.entry:last-child {
  margin-bottom: 0;
}

.entry-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  flex-wrap: wrap;
  gap: var(--space-xs);
}

.entry-title {
  font-weight: 600;
  font-size: 0.95rem;
  color: var(--color-text);
}

.entry-org {
  font-size: 0.9rem;
  color: var(--color-accent);
}

.entry-date {
  font-size: 0.82rem;
  color: var(--color-muted);
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}

.entry-summary {
  font-size: 0.9rem;
  color: var(--color-muted);
  margin-top: var(--space-xs);
}

.highlights {
  list-style: none;
  margin-top: var(--space-xs);
  padding: 0;
}

.highlights li {
  position: relative;
  padding-left: 1.1em;
  font-size: 0.9rem;
  color: var(--color-text);
  margin-bottom: 2px;
  line-height: 1.55;
}

.highlights li::before {
  content: "•";
  position: absolute;
  left: 0;
  color: var(--color-accent);
  font-size: 0.85em;
  top: 0.1em;
}

/* ── Skills ─────────────────────────────────────────────────────────────── */
.skills-grid {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-xs);
}

.skill-tag {
  display: inline-block;
  background: var(--color-accent-light);
  color: var(--color-accent);
  font-size: 0.82rem;
  font-weight: 500;
  padding: 2px 10px;
  border-radius: 20px;
  white-space: nowrap;
}

/* ── Languages ───────────────────────────────────────────────────────────── */
.lang-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-sm);
  font-size: 0.9rem;
}

.lang-item .lang-name {
  font-weight: 600;
}

.lang-item .lang-fluency {
  color: var(--color-muted);
}

/* ── Print ─────────────────────────────────────────────────────────────── */
@media print {
  body {
    padding: 0;
    max-width: none;
  }
  section {
    break-inside: avoid;
  }
}
"""


def render_styled_html(
    json_resume: JSONResume,
    market: MarketProfile,
) -> str:
    """Render a single-file HTML+inline CSS CV.

    Deterministic: same input → same output.
    No external assets. No Jinja2 dependency.

    Args:
        json_resume: The structured resume data.
        market: Market profile (controls locale hints, but output is always EN).

    Returns:
        A complete HTML document as a string.
    """
    basics = json_resume.basics
    parts: list[str] = []

    def w(s: str) -> None:
        parts.append(s)

    w("<!DOCTYPE html>")
    w('<html lang="en">')
    w("<head>")
    w('<meta charset="UTF-8">')
    w('<meta name="viewport" content="width=device-width, initial-scale=1.0">')
    w(f"<title>{_esc(basics.name or 'CV')}</title>")
    w(f"<style>{_CSS}</style>")
    w("</head>")
    w("<body>")

    # ── Header ───────────────────────────────────────────────────────────────────
    w("<header>")
    w(f'<div class="name">{_esc(basics.name or "")}</div>')

    if basics.label:
        w(f'<div class="label">{_esc(basics.label)}</div>')

    # Contact info
    contact_items: list[str] = []
    if basics.email:
        contact_items.append(f'<span class="contact-item">{_esc(basics.email)}</span>')
    if basics.phone:
        contact_items.append(f'<span class="contact-item">{_esc(basics.phone)}</span>')
    if basics.url:
        contact_items.append(f'<span class="contact-item">{_esc(basics.url)}</span>')
    if basics.location:
        loc_parts = []
        if basics.location.city:
            loc_parts.append(basics.location.city)
        if basics.location.region:
            loc_parts.append(basics.location.region)
        if basics.location.countryCode:
            loc_parts.append(basics.location.countryCode)
        if loc_parts:
            contact_items.append(
                f'<span class="contact-item">{_esc(", ".join(loc_parts))}</span>'
            )
    for profile in basics.profiles:
        if profile.network and profile.url:
            contact_items.append(
                f'<span class="contact-item">{_esc(profile.network)}: {_esc(profile.url)}</span>'
            )

    if contact_items:
        w('<div class="contact">')
        for item in contact_items:
            w(item)
        w("</div>")

    w("</header>")

    # ── Main ─────────────────────────────────────────────────────────────────────
    w("<main>")

    # Summary
    if basics.summary:
        w('<section aria-labelledby="sec-summary">')
        w('<h2 class="section-title" id="sec-summary">Summary</h2>')
        w(f'<p class="summary-text">{_esc(basics.summary)}</p>')
        w("</section>")

    # Experience
    if json_resume.work:
        w('<section aria-labelledby="sec-experience">')
        w('<h2 class="section-title" id="sec-experience">Experience</h2>')
        for job in json_resume.work:
            date_str = _date_range(job.startDate, job.endDate)
            w('<div class="entry">')
            w('<div class="entry-header">')
            w('<div>')
            if job.position:
                w(f'<span class="entry-title">{_esc(job.position)}</span>')
            if job.name:
                w(f' <span class="entry-org">@ {_esc(job.name)}</span>')
            w("</div>")
            if date_str:
                w(f'<span class="entry-date">{_esc(date_str)}</span>')
            w("</div>")
            if job.summary:
                w(f'<p class="entry-summary">{_esc(job.summary)}</p>')
            if job.highlights:
                w('<ul class="highlights">')
                for h in job.highlights:
                    if h.strip():
                        w(f"<li>{_esc(h.strip())}</li>")
                w("</ul>")
            w("</div>")
        w("</section>")

    # Education
    if json_resume.education:
        w('<section aria-labelledby="sec-education">')
        w('<h2 class="section-title" id="sec-education">Education</h2>')
        for edu in json_resume.education:
            date_str = _date_range(edu.startDate, edu.endDate)
            degree_parts = []
            if edu.studyType:
                degree_parts.append(edu.studyType)
            if edu.area:
                degree_parts.append(edu.area)
            degree = ", ".join(degree_parts)
            w('<div class="entry">')
            w('<div class="entry-header">')
            w("<div>")
            if degree:
                w(f'<span class="entry-title">{_esc(degree)}</span>')
            if edu.institution:
                sep = " — " if degree else ""
                w(f'<span class="entry-org">{_esc(sep + edu.institution)}</span>')
            w("</div>")
            if date_str:
                w(f'<span class="entry-date">{_esc(date_str)}</span>')
            w("</div>")
            w("</div>")
        w("</section>")

    # Skills
    if json_resume.skills:
        w('<section aria-labelledby="sec-skills">')
        w('<h2 class="section-title" id="sec-skills">Skills</h2>')
        w('<div class="skills-grid">')
        for skill in json_resume.skills:
            if skill.name:
                display = skill.name
                if skill.keywords:
                    kw = ", ".join(k for k in skill.keywords if k)
                    display = f"{skill.name} ({kw})"
                w(f'<span class="skill-tag">{_esc(display)}</span>')
        w("</div>")
        w("</section>")

    # Languages
    if json_resume.languages:
        w('<section aria-labelledby="sec-languages">')
        w('<h2 class="section-title" id="sec-languages">Languages</h2>')
        w('<div class="lang-list">')
        for lang in json_resume.languages:
            if lang.language:
                w('<span class="lang-item">')
                w(f'<span class="lang-name">{_esc(lang.language)}</span>')
                if lang.fluency:
                    w(f' <span class="lang-fluency">({_esc(lang.fluency)})</span>')
                w("</span>")
        w("</div>")
        w("</section>")

    w("</main>")
    w("</body>")
    w("</html>")

    return "\n".join(parts)


def render_pdf_from_html(html: str, out_path: str | Path) -> bool:
    """Render HTML to PDF using weasyprint.

    Guards the import: if weasyprint is not installed or system libs (GTK/Cairo)
    are missing, returns False without raising.

    Args:
        html: The complete HTML string to render.
        out_path: Destination PDF file path.

    Returns:
        True if PDF was written successfully, False if weasyprint unavailable.
    """
    try:
        from weasyprint import HTML  # type: ignore[import]
    except Exception:  # noqa: BLE001
        return False

    try:
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        HTML(string=html).write_pdf(str(out))
        return out.exists() and out.stat().st_size > 0
    except Exception:  # noqa: BLE001
        return False
