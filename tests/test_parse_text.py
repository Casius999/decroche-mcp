from decroche.cv.parse import parse_text, split_sections
from tests.conftest import SAMPLE_EN, SAMPLE_FR


def test_split_sections_en_maps_canonical_keys():
    keys = {s.name for s in split_sections(SAMPLE_EN)}
    assert {"summary", "experience", "skills", "education"} <= keys


def test_split_sections_fr_maps_canonical_keys():
    keys = {s.name for s in split_sections(SAMPLE_FR)}
    # profil->summary, experience->experience, competences->skills, formation->education
    assert {"summary", "experience", "skills", "education"} <= keys


def test_parse_text_en_extracts_contact_and_confidence():
    cv = parse_text(SAMPLE_EN)
    assert cv.json_resume.basics.email == "jane.doe@example.com"
    assert cv.json_resume.basics.name == "Jane Doe"
    assert cv.parse_confidence >= 0.8
    assert cv.warnings == []


def test_parse_text_fr_extracts_email():
    cv = parse_text(SAMPLE_FR)
    assert cv.json_resume.basics.email == "jean.dupont@example.com"
    assert any(s.name == "skills" for s in cv.sections)


def test_parse_text_empty_flags_scanned():
    cv = parse_text("")
    assert cv.parse_confidence == 0.0
    assert any("scanned_or_empty" in w for w in cv.warnings)


# I1 — phone regex: metrics/years before the real phone must not win
def test_phone_false_positive_year_ignored():
    """A year like '2015' or a metric like '1.46x' above the phone must not
    be stored as basics.phone; the real phone (≥7 digits) must win."""
    text = (
        "Graduated 2015\n"
        "revenue 1.46x\n"
        "jane@example.com\n"
        "+1 415 555 0101\n"
    )
    cv = parse_text(text)
    phone = cv.json_resume.basics.phone
    assert phone is not None, "real phone should be found"
    assert "2015" not in phone, f"year matched as phone: {phone!r}"
    assert "1.46" not in phone, f"metric matched as phone: {phone!r}"
    digit_count = sum(c.isdigit() for c in phone)
    assert digit_count >= 7, f"extracted phone has too few digits: {phone!r}"


def test_phone_only_short_numbers_returns_none():
    """When the only digit sequences are too short (< 7 digits), phone must be None."""
    text = "Graduated 2015\nrevenue 1.46x\njane@example.com\n"
    cv = parse_text(text)
    assert cv.json_resume.basics.phone is None


# I2 — name heuristic: CV title lines must be skipped
def test_name_heuristic_skips_curriculum_vitae_title():
    """When the first non-empty line is 'CURRICULUM VITAE', the picker must
    skip it and return the next valid candidate line as the name."""
    text = (
        "CURRICULUM VITAE\n"
        "Jane Doe\n"
        "jane@example.com\n"
        "+1 415 555 0101\n"
        "\n"
        "Summary\n"
        "Engineer.\n"
    )
    cv = parse_text(text)
    assert cv.json_resume.basics.name == "Jane Doe"


def test_name_heuristic_skips_resume_title():
    """'RESUME' as first line must be skipped in favour of the real name."""
    text = (
        "RESUME\n"
        "John Smith\n"
        "john@example.com\n"
    )
    cv = parse_text(text)
    assert cv.json_resume.basics.name == "John Smith"
