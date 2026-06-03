from __future__ import annotations

from pathlib import Path

import yaml

from decroche.models import MarketProfile

PROFILES_DIR = Path(__file__).resolve().parent.parent / "profiles"


def load_profile(market_id: str) -> MarketProfile:
    path = PROFILES_DIR / f"{market_id}.yaml"
    if not path.exists():
        raise ValueError(f"unknown market profile: {market_id!r}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return MarketProfile(**data)


def list_profiles() -> list[str]:
    return sorted(p.stem for p in PROFILES_DIR.glob("*.yaml"))
