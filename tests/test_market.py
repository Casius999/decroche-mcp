import pytest

from decroche.market.profiles import load_profile, list_profiles


def test_load_fr_profile():
    p = load_profile("fr")
    assert p.id == "fr"
    assert p.paper == "A4"
    assert p.cover_letter_expected is True
    assert p.personal_info_ok is False


def test_load_us_profile():
    p = load_profile("us")
    assert p.photo == "forbidden"
    assert p.spelling == "en-US"


def test_unknown_profile_raises():
    with pytest.raises(ValueError, match="unknown market profile"):
        load_profile("zz")


def test_list_profiles_contains_fr_us():
    ids = list_profiles()
    assert "fr" in ids and "us" in ids


# ── FIX 2: uk, ca-en, ca-fr profiles ────────────────────────────────────────

def test_load_uk_profile():
    p = load_profile("uk")
    assert p.id == "uk"
    assert p.photo == "discouraged"
    assert p.personal_info_ok is False
    assert p.hobbies_common is False
    assert p.cover_letter_expected is False
    assert p.length_ideal_pages == 2
    assert p.length_max_pages == 2
    assert p.paper == "A4"
    assert p.date_format == "Mon YYYY"
    assert p.spelling == "en-GB"
    assert p.anonymized_variant is False


def test_load_ca_en_profile():
    p = load_profile("ca-en")
    assert p.id == "ca-en"
    assert p.photo == "forbidden"
    assert p.personal_info_ok is False
    assert p.hobbies_common is False
    assert p.cover_letter_expected is False
    assert p.length_ideal_pages == 2
    assert p.length_max_pages == 2
    assert p.paper == "Letter"
    assert p.date_format == "Mon YYYY"
    assert p.spelling == "en-CA"
    assert p.anonymized_variant is False


def test_load_ca_fr_profile():
    p = load_profile("ca-fr")
    assert p.id == "ca-fr"
    assert p.photo == "optional"
    assert p.personal_info_ok is False
    assert p.hobbies_common is True
    assert p.cover_letter_expected is True
    assert p.length_ideal_pages == 2
    assert p.length_max_pages == 2
    assert p.paper == "Letter"
    assert p.date_format == "MM/YYYY"
    assert p.spelling == "fr"
    assert p.anonymized_variant is False


def test_list_profiles_contains_all_five():
    ids = list_profiles()
    for expected in ("fr", "us", "uk", "ca-en", "ca-fr"):
        assert expected in ids, f"Missing profile: {expected}"
