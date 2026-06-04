"""Shared HTTP utilities for source providers.

- ``fetch_json``:   async JSON fetch via httpx (GET or POST).
- ``env_key``:      read one or more env-vars; return a mapping if ALL present, else None.
- ``require_env``:  like env_key but raises ToolError when any var is missing.
- ``MissingKeyError``: raised when a required env-var is absent (legacy).
- ``ToolError``:    user-visible error surfaced by MCP tools.

Security note:
    ``fetch_json`` wraps all httpx errors so that URLs — which may contain API keys
    in path segments (Jooble) or query params (Adzuna) — NEVER reach the caller.
    Only the HTTP status code and the provider label are included in ToolError.
"""

from __future__ import annotations

import os
from typing import Any

import httpx


class ToolError(Exception):
    """User-visible error raised by MCP tools (surfaced to the LLM/caller)."""


class MissingKeyError(ToolError):
    """Raised when one or more required environment variables are absent."""

    def __init__(self, *names: str) -> None:
        missing = [n for n in names if not os.environ.get(n)]
        self.missing = missing
        super().__init__(
            f"Required environment variable(s) not set: {', '.join(missing)}. "
            "Set them in your environment before calling this provider."
        )


def env_key(*names: str) -> dict[str, str] | None:
    """Return a ``{name: value}`` dict if ALL named env-vars are set, else ``None``.

    This is a *soft* check — it does **not** raise.  Use ``require_env`` when you
    want to fail hard with a ToolError.
    """
    result: dict[str, str] = {}
    for name in names:
        val = os.environ.get(name)
        if val is None:
            return None
        result[name] = val
    return result


def require_env(*names: str) -> dict[str, str]:
    """Return a ``{name: value}`` dict for all named env-vars.

    Raises:
        MissingKeyError (subclass of ToolError): if any variable is absent.
    """
    missing = [n for n in names if not os.environ.get(n)]
    if missing:
        raise MissingKeyError(*names)
    return {n: os.environ[n] for n in names}


async def fetch_json(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    method: str = "GET",
    json_body: Any | None = None,
    timeout: float = 20.0,
    provider: str | None = None,
) -> Any:
    """Fetch a URL and return the parsed JSON body.

    Args:
        url:       Full URL to request.
        params:    Query-string parameters (GET) or None.
        headers:   Extra HTTP headers.
        method:    HTTP method, default ``"GET"``.
        json_body: Body to send as JSON (for POST/PUT).
        timeout:   Request timeout in seconds, default 20.
        provider:  Optional human-readable provider name for error messages.
                   When set, it is included in ToolError but the URL is NEVER
                   included (it may contain API keys in path or query params).

    Returns:
        Parsed JSON (dict, list, or scalar).

    Raises:
        ToolError: on 4xx/5xx HTTP responses or network/timeout errors.
                   The error message contains ONLY the status code and provider
                   label — never the full URL or any secrets.
    """
    label = provider or "http"
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.request(
                method,
                url,
                params=params,
                headers=headers,
                json=json_body,
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        raise ToolError(f"{label}: HTTP {status} error from upstream API.") from None
    except httpx.RequestError as exc:
        raise ToolError(f"{label}: network error — {type(exc).__name__}.") from None
