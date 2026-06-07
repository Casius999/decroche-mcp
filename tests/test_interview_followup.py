"""Tests for interview.followup (thank_you, debrief_template)."""

from __future__ import annotations


from decroche.interview.followup import debrief_template, thank_you


def test_thank_you_returns_string():
    result = thank_you("Marie", "Data Engineer")
    assert isinstance(result, str)


def test_thank_you_fr_contains_name():
    result = thank_you("Pierre", "PM Senior", lang="fr")
    assert "Pierre" in result


def test_thank_you_fr_contains_role():
    result = thank_you("Sophie", "Backend Engineer", lang="fr")
    assert "Backend Engineer" in result


def test_thank_you_fr_contains_subject():
    result = thank_you("Alex", "Designer", lang="fr")
    assert "Objet" in result


def test_thank_you_fr_is_french():
    result = thank_you("Jean", "Développeur", lang="fr")
    assert "Cordialement" in result or "remerci" in result.lower()


def test_thank_you_en_contains_name():
    result = thank_you("John", "Software Engineer", lang="en")
    assert "John" in result


def test_thank_you_en_contains_role():
    result = thank_you("Alice", "Product Manager", lang="en")
    assert "Product Manager" in result


def test_thank_you_en_subject_line():
    result = thank_you("Bob", "SRE", lang="en")
    assert "Subject:" in result


def test_thank_you_en_is_english():
    result = thank_you("Carol", "Lead Dev", lang="en")
    assert "Best regards" in result or "Thank you" in result


def test_thank_you_default_lang_fr():
    result = thank_you("Marie", "Analyste")
    assert "Cordialement" in result or "remerci" in result.lower()


def test_thank_you_has_placeholder():
    result = thank_you("Someone", "Some Role", lang="fr")
    assert "[" in result  # at least one placeholder


def test_debrief_template_returns_string():
    result = debrief_template("Senior Engineer")
    assert isinstance(result, str)


def test_debrief_fr_contains_role():
    result = debrief_template("Chef de Projet", lang="fr")
    assert "Chef de Projet" in result


def test_debrief_en_contains_role():
    result = debrief_template("Senior PM", lang="en")
    assert "Senior PM" in result


def test_debrief_fr_has_sections():
    result = debrief_template("Dev", lang="fr")
    for section in ["Informations", "passé", "Questions", "étapes"]:
        assert section in result


def test_debrief_en_has_sections():
    result = debrief_template("Dev", lang="en")
    for section in ["Key Info", "well", "Questions", "Next steps"]:
        assert section in result


def test_debrief_fr_has_action_items():
    result = debrief_template("PM", lang="fr")
    assert "- [ ]" in result or "Actions" in result


def test_debrief_en_has_action_items():
    result = debrief_template("PM", lang="en")
    assert "- [ ]" in result or "Actions" in result


def test_debrief_default_lang_fr():
    result = debrief_template("Role")
    assert "Compte-rendu" in result or "Informations" in result


def test_thank_you_deterministic():
    r1 = thank_you("Jean", "Dev", lang="fr")
    r2 = thank_you("Jean", "Dev", lang="fr")
    assert r1 == r2


def test_debrief_deterministic():
    r1 = debrief_template("PM", lang="en")
    r2 = debrief_template("PM", lang="en")
    assert r1 == r2
