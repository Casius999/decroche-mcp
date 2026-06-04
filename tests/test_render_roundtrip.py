"""Round-trip test: render_ats_docx → ats.parse_sim → parsability ≥ 85.

This is the KEY proof that our DOCX export is ATS-clean.
No tables, no header contact, single-column DOCX.
"""
from __future__ import annotations

import pytest

from decroche.ats.parse_sim import parse_sim
from decroche.cv.render_docx import render_ats_docx
from decroche.models import Basics, JSONResume, Work, Education, Skill, Language


# ── Fixtures ─────────────────────────────────────────────────────────────────────

@pytest.fixture
def rich_resume() -> JSONResume:
    """A representative resume that should round-trip perfectly."""
    return JSONResume(
        basics=Basics(
            name="Jane Doe",
            email="jane.doe@example.com",
            phone="+1 415 555 0101",
            label="Senior Backend Engineer",
            summary="Senior backend engineer with 8 years building distributed systems.",
        ),
        work=[
            Work(
                name="Acme Corp",
                position="Staff Engineer",
                startDate="2020-01",
                endDate="2024-06",
                highlights=[
                    "Reduced API latency 38% by introducing a caching layer.",
                    "Led migration of 12 services to Kubernetes.",
                    "Mentored 5 engineers, improving team velocity by 20%.",
                ],
            ),
            Work(
                name="Beta Inc",
                position="Software Engineer",
                startDate="2016-03",
                endDate="2019-12",
                highlights=[
                    "Built CI/CD pipeline used by 50+ engineers.",
                    "Reduced deploy time from 45 min to 8 min.",
                ],
            ),
        ],
        education=[
            Education(
                institution="MIT",
                area="Computer Science",
                studyType="B.S.",
                startDate="2012-09",
                endDate="2016-05",
            )
        ],
        skills=[
            Skill(name="Python"),
            Skill(name="Go"),
            Skill(name="Kubernetes"),
            Skill(name="PostgreSQL"),
            Skill(name="Docker"),
        ],
        languages=[Language(language="English", fluency="Native")],
    )


@pytest.fixture
def market_fr():
    from decroche.market.profiles import load_profile
    return load_profile("fr")


# ── Round-trip: Workday ─────────────────────────────────────────────────────────────────

class TestRoundTripWorkday:
    def test_parsability_gte_85(self, rich_resume, market_fr, tmp_path):
        """The generated DOCX must score ≥85 on Workday ATS."""
        out = tmp_path / "cv_workday_rt.docx"
        render_ats_docx(rich_resume, market_fr, out)
        result = parse_sim(str(out), "workday")
        assert result.parsability_score >= 85, (
            f"Workday parsability {result.parsability_score:.1f} < 85. "
            f"Breakages: {[b.type for b in result.breakages]}"
        )

    def test_no_two_column_breakage(self, rich_resume, market_fr, tmp_path):
        out = tmp_path / "cv_workday_cols.docx"
        render_ats_docx(rich_resume, market_fr, out)
        result = parse_sim(str(out), "workday")
        breakage_types = [b.type for b in result.breakages]
        assert "two_column" not in breakage_types

    def test_no_table_breakage(self, rich_resume, market_fr, tmp_path):
        out = tmp_path / "cv_workday_table.docx"
        render_ats_docx(rich_resume, market_fr, out)
        result = parse_sim(str(out), "workday")
        breakage_types = [b.type for b in result.breakages]
        assert "table" not in breakage_types

    def test_no_header_contact_breakage(self, rich_resume, market_fr, tmp_path):
        out = tmp_path / "cv_workday_hdr.docx"
        render_ats_docx(rich_resume, market_fr, out)
        result = parse_sim(str(out), "workday")
        breakage_types = [b.type for b in result.breakages]
        assert "header_contact" not in breakage_types

    def test_contact_extracted(self, rich_resume, market_fr, tmp_path):
        out = tmp_path / "cv_workday_contact.docx"
        render_ats_docx(rich_resume, market_fr, out)
        result = parse_sim(str(out), "workday")
        assert result.fields_extracted.get("contact") is True
        assert "contact" not in result.fields_lost


# ── Round-trip: Generic ─────────────────────────────────────────────────────────────────

class TestRoundTripGeneric:
    def test_parsability_gte_85(self, rich_resume, market_fr, tmp_path):
        """The generated DOCX must score ≥85 on the generic ATS profile."""
        out = tmp_path / "cv_generic_rt.docx"
        render_ats_docx(rich_resume, market_fr, out)
        result = parse_sim(str(out), "generic")
        assert result.parsability_score >= 85, (
            f"Generic parsability {result.parsability_score:.1f} < 85. "
            f"Breakages: {[b.type for b in result.breakages]}"
        )

    def test_no_structural_breakages(self, rich_resume, market_fr, tmp_path):
        """No two_column, table, or header_contact breakages on generic."""
        out = tmp_path / "cv_generic_struct.docx"
        render_ats_docx(rich_resume, market_fr, out)
        result = parse_sim(str(out), "generic")
        structural = {"two_column", "table", "header_contact"}
        found = {b.type for b in result.breakages} & structural
        assert not found, f"Structural breakages: {found}"


# ── Round-trip: fmt field ───────────────────────────────────────────────────────────────────

class TestRoundTripFmt:
    def test_detected_as_docx(self, rich_resume, market_fr, tmp_path):
        out = tmp_path / "cv_fmt.docx"
        render_ats_docx(rich_resume, market_fr, out)
        result = parse_sim(str(out), "workday")
        assert result.fmt == "docx"
