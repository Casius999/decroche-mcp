"""network sub-package — FastMCP sub-server for warm referral paths.

Tools (mounted under namespace "network" in the main server):
- find_warm_path    : find intro paths over user-provided connections
- score_intro_value : score a NetworkPath
- draft_intro_request : draft an intro request scaffold (opt-out for FR)

COMPLIANCE:
- NEVER traverses LinkedIn or any external system.
- Operates ONLY on user-provided connection lists.
"""

from __future__ import annotations

from fastmcp import FastMCP

from decroche.models import IntroRequest, NetworkPath
from decroche.network.paths import draft_intro_request as _draft_intro_request
from decroche.network.paths import find_warm_path as _find_warm_path
from decroche.network.paths import score_intro_value as _score_intro_value

network_server = FastMCP("network")


@network_server.tool
def find_warm_path(target_company: str, connections: list[dict]) -> list[NetworkPath]:
    """Find warm introduction paths to a target company.

    Operates ONLY on the user-provided ``connections`` list.
    NO LinkedIn traversal, NO external lookups.

    Args:
        target_company: Company name to find paths to.
        connections:    List of connection dicts, each with:
                        ``name`` (str), ``company`` (str), ``relationship`` (str).
                        Optional: ``note`` (str).

    Returns:
        List of NetworkPath sorted by intro value (highest first).
    """
    return _find_warm_path(target_company, connections)


@network_server.tool
def score_intro_value(path: NetworkPath) -> float:
    """Score the intro value of a NetworkPath (0–1).

    Args:
        path: A NetworkPath.

    Returns:
        Float 0–1 (higher = stronger introduction potential).
    """
    return _score_intro_value(path)


@network_server.tool
def draft_intro_request(path: NetworkPath, context: str = "", lang: str = "fr") -> IntroRequest:
    """Draft an introduction request scaffold.

    French drafts include a mandatory opt-out line.

    Args:
        path:    A NetworkPath.
        context: Brief context (role sought, reason for interest).
        lang:    "fr" (default) or "en".

    Returns:
        IntroRequest with to, subject, body, lang.
    """
    return _draft_intro_request(path, context=context, lang=lang)
