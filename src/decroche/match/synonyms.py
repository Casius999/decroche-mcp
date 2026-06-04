"""Skill synonym normalization — deterministic, offline, bilingual FR+EN.

Loads ``data/skill_synonyms.yaml`` once at import time.
No network access, no external LLM dependency.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

_DATA_FILE = Path(__file__).parent.parent / "data" / "skill_synonyms.yaml"


@lru_cache(maxsize=1)
def _load() -> tuple[dict[str, str], dict[str, list[str]]]:
    """Return (alias_to_canonical, canonical_to_aliases) mappings.

    Both keys are lowercased/stripped.  The canonical is the top-level key in
    the YAML (already lowercase by convention); each alias is lowercased here.
    """
    raw: dict = yaml.safe_load(_DATA_FILE.read_text(encoding="utf-8")) or {}

    alias_to_canonical: dict[str, str] = {}
    canonical_to_aliases: dict[str, list[str]] = {}

    for canonical, aliases in raw.items():
        canon_lower = canonical.lower().strip()
        alias_list: list[str] = []
        if aliases:
            for a in aliases:
                a_lower = str(a).lower().strip()
                alias_to_canonical[a_lower] = canon_lower
                alias_list.append(a_lower)
        # Also map canonical → itself for lookup convenience
        alias_to_canonical[canon_lower] = canon_lower
        canonical_to_aliases[canon_lower] = alias_list

    return alias_to_canonical, canonical_to_aliases


def normalize(term: str) -> str:
    """Return the canonical form of *term*.

    Lowercases and strips the input, looks it up in the alias map.
    If not found, returns the lowercased/stripped term unchanged.
    """
    alias_to_canonical, _ = _load()
    key = term.lower().strip()
    return alias_to_canonical.get(key, key)


def expand(term: str) -> set[str]:
    """Return the full set of equivalent terms for *term* (including itself).

    Resolves *term* to its canonical form first, then returns that canonical
    plus all its known aliases.  Unknown terms return a singleton set.
    """
    _, canonical_to_aliases = _load()
    canon = normalize(term)
    aliases = canonical_to_aliases.get(canon, [])
    return {canon} | set(aliases)
