from decroche.models import JSONResume, CVParse, MarketProfile, Section


def test_jsonresume_defaults_are_empty():
    jr = JSONResume()
    assert jr.basics.name is None
    assert jr.work == []
    assert jr.meta.market == "fr"
    assert jr.meta.anonymized is False


def test_cvparse_requires_confidence():
    jr = JSONResume()
    cv = CVParse(json_resume=jr, raw_text="hello", parse_confidence=0.5)
    assert cv.parse_confidence == 0.5
    assert cv.sections == []
    assert cv.warnings == []


def test_section_roundtrip():
    s = Section(name="experience", raw_heading="Experience", text="- did X")
    assert s.name == "experience"


def test_marketprofile_from_dict():
    mp = MarketProfile(
        id="fr", photo="optional", personal_info_ok=False, hobbies_common=True,
        cover_letter_expected=True, length_ideal_pages=1, length_max_pages=2,
        paper="A4", date_format="MM/YYYY", spelling="fr", anonymized_variant=True,
    )
    assert mp.id == "fr"
    assert mp.paper == "A4"
