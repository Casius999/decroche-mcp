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
