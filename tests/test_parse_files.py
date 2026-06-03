from decroche.cv.parse import parse_cv


def test_parse_docx(fixtures_dir):
    cv = parse_cv(str(fixtures_dir / "sample.docx"))
    assert cv.json_resume.basics.email == "jane.doe@example.com"
    assert cv.parse_confidence >= 0.8


def test_parse_pdf_text(fixtures_dir):
    cv = parse_cv(str(fixtures_dir / "sample.pdf"))
    assert cv.json_resume.basics.email == "jane.doe@example.com"
    assert cv.parse_confidence >= 0.6


def test_parse_pdf_scanned_flags_warning(fixtures_dir):
    cv = parse_cv(str(fixtures_dir / "scanned.pdf"))
    assert cv.parse_confidence == 0.0
    assert any("scanned_or_empty" in w for w in cv.warnings)


def test_parse_txt_en(fixtures_dir):
    cv = parse_cv(str(fixtures_dir / "sample_en.txt"))
    assert cv.json_resume.basics.name == "Jane Doe"


def test_unsupported_extension_raises(tmp_path):
    bad = tmp_path / "cv.rtf"
    bad.write_text("x", encoding="utf-8")
    import pytest

    with pytest.raises(ValueError, match="unsupported file type"):
        parse_cv(str(bad))
