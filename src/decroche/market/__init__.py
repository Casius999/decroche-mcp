from __future__ import annotations

from fastmcp import FastMCP

from decroche.market.profiles import list_profiles, load_profile
from decroche.models import MarketProfile

market_server = FastMCP("market")

# Session-scoped active profile pointer (single-user session state).
_state = {"current": "fr"}


@market_server.tool
def get() -> MarketProfile:
    """Return the currently active market profile."""
    return load_profile(_state["current"])


@market_server.tool
def set(market_id: str) -> MarketProfile:
    """Set the active market profile (e.g. 'fr', 'us') and return it."""
    profile = load_profile(market_id)  # raises ValueError if unknown
    _state["current"] = market_id
    return profile


@market_server.tool
def available() -> list[str]:
    """List available market profile ids."""
    return list_profiles()
