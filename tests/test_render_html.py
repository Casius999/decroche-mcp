"""Tests for render_styled_html and render_pdf_from_html."""
from __future__ import annotations

import pytest

from decroche.cv.render_html import render_styled_html, render_pdf_from_html
from decroche.models import Basics, JSONResume, Work, Education, Skill, Language


# ── Fixtures ─────────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_resume() -> JSONResume:
    return JSONResume(
        basics=Basics(
            name="Jane Doe",
            email="jane.doe@example.com",
            phone="+1 415 555 0101",
            label="Senior Backend Engineer",
            summary="8 years building distributed systems.",
        ),
        work=[
            Work(
                name="Acme Corp",
                position="Staff Engineer",
                startDate="2020-01",
                endDate="2024-06",
                highlights=[
                    "Reduced API latency 38% by introducing a caching layer.",
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
        skills=[Skill(name="Python"), Skill(name="Go")],
        languages=[Language(language="English", fluency="native")],
    )


@pytest.fixture
def market_fr():
    from decroche.market.profiles import load_profile
    return load_profile("fr")


# ── render_styled_html ──────────────────────────────────────────────────────────────

class TestRenderStyledHtml:
    def test_returns_string(self, sample_resume, market_fr):
        html = render_styled_html(sample_resume, market_fr)
        assert isinstance(html, str)

    def test_non_empty(self, sample_resume, market_fr):
        html = render_styled_html(sample_resume, market_fr)
        assert len(html) > 200

    def test_has_html_tag(self, sample_resume, market_fr):
        html = render_styled_html(sample_resume, market_fr)
        assert "<html" in html.lower()

    def test_has_closing_html_tag(self, sample_resume, market_fr):
        html = render_styled_html(sample_resume, market_fr)
        assert "</html>" in html.lower()

    def test_contains_candidate_name(self, sample_resume, market_fr):
        html = render_styled_html(sample_resume, market_fr)
        assert "Jane Doe" in html

    def test_contains_email(self, sample_resume, market_fr):
        html = render_styled_html(sample_resume, market_fr)
        assert "jane.doe@example.com" in html

    def test_contains_summary(self, sample_resume, market_fr):
        html = render_styled_html(sample_resume, market_fr)
        assert "distributed systems" in html

    def test_contains_section_headings(self, sample_resume, market_fr):
        html = render_styled_html(sample_resume, market_fr)
        for heading in ("Experience", "Education", "Skills"):
            assert heading in html, f"Heading {heading!r} missing from HTML"

    def test_contains_work_highlight(self, sample_resume, market_fr):
        html = render_styled_html(sample_resume, market_fr)
        assert "38%" in html

    def test_contains_inline_css(self, sample_resume, market_fr):
        html = render_styled_html(sample_resume, market_fr)
        assert "<style" in html.lower()

    def test_no_external_links(self, sample_resume, market_fr):
        import re
        html = render_styled_html(sample_resume, market_fr)
        assert not re.search(r'<link[^>]+rel=["\']stylesheet["\']', html, re.I)
        assert not re.search(r'<script[^>]+src=["\']https?://', html, re.I)

    def test_deterministic(self, sample_resume, market_fr):
        html1 = render_styled_html(sample_resume, market_fr)
        html2 = render_styled_html(sample_resume, market_fr)
        assert html1 == html2

    def test_semantic_tags(self, sample_resume, market_fr):
        html = render_styled_html(sample_resume, market_fr)
        assert any(tag in html for tag in ("<header", "<main", "<section", "<article", "<h1", "<h2"))

    def test_skills_in_html(self, sample_resume, market_fr):
        html = render_styled_html(sample_resume, market_fr)
        assert "Python" in html


class TestRenderLocalization:
    """FIX 3: localized headings and date formats by market."""

    def test_fr_market_uses_french_headings(self, sample_resume):
        from decroche.market.profiles import load_profile
        market_fr = load_profile("fr")
        html = render_styled_html(sample_resume, market_fr)
        assert "Expérience" in html or "Expérience" in html
        assert "Compétences" in html

    def test_us_market_uses_english_headings(self, sample_resume):
        from decroche.market.profiles import load_profile
        market_us = load_profile("us")
        html = render_styled_html(sample_resume, market_us)
        assert "Experience" in html
        assert "Skills" in html

    def test_fr_market_no_english_experience_heading(self, sample_resume):
        from decroche.market.profiles import load_profile
        import re
        market_fr = load_profile("fr")
        html = render_styled_html(sample_resume, market_fr)
        section_titles = re.findall(r'class="section-title"[^>]*>([^<]+)<', html)
        for title in section_titles:
            assert title.strip() != "Experience", (
                f"Found English 'Experience' heading in FR-market HTML: {title!r}"
            )

    def test_fr_market_summary_heading_localized(self):
        from decroche.market.profiles import load_profile
        from decroche.models import Basics, JSONResume
        market_fr = load_profile("fr")
        resume = JSONResume(basics=Basics(name="Test", summary="A great engineer."))
        html = render_styled_html(resume, market_fr)
        assert "Profil" in html


class TestRenderStyledHtmlMinimal:
    def test_minimal_resume(self, market_fr):
        resume = JSONResume(basics=Basics(name="Solo Person"))
        html = render_styled_html(resume, market_fr)
        assert "Solo Person" in html
        assert "<html" in html.lower()

    def test_no_work_section(self, market_fr):
        resume = JSONResume(
            basics=Basics(name="Fresher", email="f@f.com"),
            skills=[Skill(name="Java")],
        )
        html = render_styled_html(resume, market_fr)
        assert "Fresher" in html
        assert "Java" in html


# ── render_pdf_from_html ────────────────────────────────────────────────────────────

class TestRenderPdfFromHtml:
    def test_returns_bool(self, sample_resume, market_fr, tmp_path):
        html = render_styled_html(sample_resume, market_fr)
        out = tmp_path / "cv.pdf"
        result = render_pdf_from_html(html, out)
        assert isinstance(result, bool)

    def test_never_raises(self, sample_resume, market_fr, tmp_path):
        html = render_styled_html(sample_resume, market_fr)
        out = tmp_path / "cv_safe.pdf"
        try:
            result = render_pdf_from_html(html, out)
            assert isinstance(result, bool)
        except Exception as exc:  # noqa: BLE001
            pytest.fail(f"render_pdf_from_html raised unexpectedly: {exc}")

    def test_pdf_created_if_true(self, sample_resume, market_fr, tmp_path):
        html = render_styled_html(sample_resume, market_fr)
        out = tmp_path / "cv_if_true.pdf"
        result = render_pdf_from_html(html, out)
        if result:
            assert out.exists()
            assert out.stat().st_size > 0
