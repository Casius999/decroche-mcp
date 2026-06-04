"""Tests for the top-level render() orchestrator."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from decroche.cv.render import render
from decroche.models import Basics, JSONResume, Render, Work, Skill


# ── Fixtures ─────────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_resume() -> JSONResume:
    return JSONResume(
        basics=Basics(
            name="Jane Doe",
            email="jane.doe@example.com",
            phone="+1 415 555 0101",
            summary="Senior backend engineer.",
        ),
        work=[
            Work(
                name="Acme Corp",
                position="Staff Engineer",
                startDate="2020-01",
                endDate="2024-06",
                highlights=["Reduced API latency 38%."],
            )
        ],
        skills=[Skill(name="Python"), Skill(name="Kubernetes")],
    )


# ── Return type ─────────────────────────────────────────────────────────────────────

class TestRenderReturnType:
    def test_returns_render_model(self, sample_resume, tmp_path):
        result = render(sample_resume, "fr", tmp_path)
        assert isinstance(result, Render)

    def test_files_is_list(self, sample_resume, tmp_path):
        result = render(sample_resume, "fr", tmp_path)
        assert isinstance(result.files, list)

    def test_ats_safe_proof_is_dict(self, sample_resume, tmp_path):
        result = render(sample_resume, "fr", tmp_path)
        assert isinstance(result.ats_safe_proof, dict)

    def test_warnings_is_list(self, sample_resume, tmp_path):
        result = render(sample_resume, "fr", tmp_path)
        assert isinstance(result.warnings, list)


# ── Default targets ───────────────────────────────────────────────────────────────────

class TestRenderDefaultTargets:
    def test_ats_docx_in_files(self, sample_resume, tmp_path):
        result = render(sample_resume, "fr", tmp_path)
        kinds = [f.kind for f in result.files]
        assert "ats_docx" in kinds

    def test_styled_html_in_files(self, sample_resume, tmp_path):
        result = render(sample_resume, "fr", tmp_path)
        kinds = [f.kind for f in result.files]
        assert "styled_html" in kinds

    def test_json_resume_in_files(self, sample_resume, tmp_path):
        result = render(sample_resume, "fr", tmp_path)
        kinds = [f.kind for f in result.files]
        assert "json_resume" in kinds

    def test_plain_text_in_files(self, sample_resume, tmp_path):
        result = render(sample_resume, "fr", tmp_path)
        kinds = [f.kind for f in result.files]
        assert "plain_text" in kinds


# ── Files actually exist on disk ────────────────────────────────────────────────────────

class TestRenderFilesExist:
    def test_ats_docx_exists(self, sample_resume, tmp_path):
        result = render(sample_resume, "fr", tmp_path)
        docx_file = next(f for f in result.files if f.kind == "ats_docx")
        assert Path(docx_file.path).exists()
        assert Path(docx_file.path).stat().st_size > 0

    def test_styled_html_exists(self, sample_resume, tmp_path):
        result = render(sample_resume, "fr", tmp_path)
        html_file = next(f for f in result.files if f.kind == "styled_html")
        assert Path(html_file.path).exists()
        assert Path(html_file.path).stat().st_size > 0

    def test_json_resume_exists(self, sample_resume, tmp_path):
        result = render(sample_resume, "fr", tmp_path)
        json_file = next(f for f in result.files if f.kind == "json_resume")
        p = Path(json_file.path)
        assert p.exists()
        data = json.loads(p.read_text(encoding="utf-8"))
        assert "basics" in data

    def test_plain_text_exists(self, sample_resume, tmp_path):
        result = render(sample_resume, "fr", tmp_path)
        txt_file = next(f for f in result.files if f.kind == "plain_text")
        p = Path(txt_file.path)
        assert p.exists()
        content = p.read_text(encoding="utf-8")
        assert "Jane Doe" in content

    def test_all_paths_absolute(self, sample_resume, tmp_path):
        result = render(sample_resume, "fr", tmp_path)
        for rf in result.files:
            assert Path(rf.path).is_absolute(), f"{rf.kind} path is not absolute: {rf.path}"


# ── ATS safe proof ───────────────────────────────────────────────────────────────────

class TestRenderAtsSafeProof:
    def test_proof_populated(self, sample_resume, tmp_path):
        result = render(sample_resume, "fr", tmp_path)
        assert len(result.ats_safe_proof) >= 1

    def test_workday_score_gte_85(self, sample_resume, tmp_path):
        result = render(sample_resume, "fr", tmp_path)
        score = result.ats_safe_proof.get("workday")
        assert score is not None
        assert score >= 85, f"Workday score {score:.1f} < 85"

    def test_generic_score_gte_85(self, sample_resume, tmp_path):
        result = render(sample_resume, "fr", tmp_path)
        score = result.ats_safe_proof.get("generic")
        assert score is not None
        assert score >= 85, f"Generic score {score:.1f} < 85"

    def test_scores_are_floats(self, sample_resume, tmp_path):
        result = render(sample_resume, "fr", tmp_path)
        for ats_id, score in result.ats_safe_proof.items():
            assert isinstance(score, float), f"Score for {ats_id} is not float"


# ── PDF is optional / best-effort ──────────────────────────────────────────────────────

class TestRenderPdfOptional:
    def test_never_crashes_with_pdf_target(self, sample_resume, tmp_path):
        """PDF target must not raise even if weasyprint is unavailable."""
        try:
            result = render(sample_resume, "fr", tmp_path, targets=("pdf",))
            kinds = [f.kind for f in result.files]
            if "pdf" not in kinds:
                assert any("pdf" in w.lower() or "weasyprint" in w.lower() for w in result.warnings)
        except Exception as exc:  # noqa: BLE001
            pytest.fail(f"render() raised with pdf target: {exc}")

    def test_pdf_or_warning_when_in_default_targets(self, sample_resume, tmp_path):
        """Default targets include pdf; either it's there or a warning is recorded."""
        result = render(sample_resume, "fr", tmp_path)
        kinds = [f.kind for f in result.files]
        if "pdf" not in kinds:
            assert any("pdf" in w.lower() or "weasyprint" in w.lower() for w in result.warnings)


# ── Selective targets ────────────────────────────────────────────────────────────────────

class TestRenderSelectiveTargets:
    def test_only_requested_targets_written(self, sample_resume, tmp_path):
        result = render(sample_resume, "fr", tmp_path, targets=("ats_docx", "plain_text"))
        kinds = [f.kind for f in result.files]
        assert "ats_docx" in kinds
        assert "plain_text" in kinds
        assert "json_resume" not in kinds

    def test_json_resume_only(self, sample_resume, tmp_path):
        result = render(sample_resume, "fr", tmp_path, targets=("json_resume",))
        kinds = [f.kind for f in result.files]
        assert kinds == ["json_resume"]


# ── Default out_dir (None) ─────────────────────────────────────────────────────────────────

class TestRenderDefaultOutDir:
    def test_default_out_dir_creates_files(self, sample_resume):
        """When out_dir=None, files should be placed in a temp directory."""
        result = render(sample_resume, "fr", None, targets=("ats_docx",))
        assert len(result.files) >= 1
        p = Path(result.files[0].path)
        assert p.exists()

    def test_default_out_dir_paths_absolute(self, sample_resume):
        result = render(sample_resume, "fr", None, targets=("json_resume",))
        for rf in result.files:
            assert Path(rf.path).is_absolute()
