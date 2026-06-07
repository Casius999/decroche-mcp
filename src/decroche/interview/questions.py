"""interview.questions — Load questions from YAML question bank.

Deterministic, no network, no LLM.  Returns questions filtered by role_family
and kind from the bundled ``data/interview_questions.yaml``.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from decroche.models import Question

_DATA_DIR = Path(__file__).parent.parent / "data"
_DEFAULT_YAML = _DATA_DIR / "interview_questions.yaml"

_VALID_KINDS = frozenset({"behavioral", "technical", "case"})


def question_bank(
    role_family: str,
    kind: str = "behavioral",
    yaml_path: str | Path | None = None,
) -> list[Question]:
    """Return questions for a given role_family and kind.

    Args:
        role_family: One of the top-level keys in the YAML
                     (e.g. ``"software"``, ``"data"``, ``"product"``,
                     ``"sales"``, ``"generic"``).  Case-insensitive.
        kind:        ``"behavioral"``, ``"technical"``, or ``"case"``.
                     Defaults to ``"behavioral"``.  Case-insensitive.
        yaml_path:   Override YAML path (for testing).

    Returns:
        List of Question objects. Empty list if the combination is absent.

    Raises:
        ValueError: if *kind* is not one of the three recognised values.
    """
    kind_lower = kind.lower().strip()
    if kind_lower not in _VALID_KINDS:
        raise ValueError(f"Invalid kind {kind!r}. Must be one of: {sorted(_VALID_KINDS)}")

    path = Path(yaml_path) if yaml_path else _DEFAULT_YAML
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    family_data = raw.get(role_family.lower().strip(), {})
    entries = family_data.get(kind_lower, [])

    return [
        Question(
            text=entry["text"],
            kind=kind_lower,
            rationale=entry.get("rationale", ""),
        )
        for entry in entries
        if isinstance(entry, dict) and entry.get("text")
    ]
