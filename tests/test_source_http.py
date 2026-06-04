"""Tests for source.http — fetch_json error sanitization (review C1).

Ensures that API keys embedded in URLs (path or query params) NEVER leak
through to ToolError messages on HTTP 4xx/5xx responses.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from decroche.source.http import ToolError, fetch_json


def _make_http_status_error(status_code: int, url: str) -> httpx.HTTPStatusError:
    """Build a realistic HTTPStatusError with the given URL and status."""
    request = httpx.Request("GET", url)
    response = httpx.Response(status_code, request=request)
    return httpx.HTTPStatusError(
        f"{status_code} Error",
        request=request,
        response=response,
    )


def _make_request_error(url: str) -> httpx.RequestError:
    """Build a realistic RequestError."""
    request = httpx.Request("GET", url)
    return httpx.ConnectError("connection refused", request=request)


def _patched_async_client(mock_response):
    """Return a context-manager-compatible mock AsyncClient."""
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.request = AsyncMock(return_value=mock_response)
    return mock_client


def _patched_async_client_raises(exc):
    """Return a context-manager-compatible mock AsyncClient that raises on request."""
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.request = AsyncMock(side_effect=exc)
    return mock_client


class TestFetchJsonSecretSanitization:
    """C1 — API keys must never appear in raised ToolError messages."""

    @pytest.mark.asyncio
    async def test_jooble_path_key_not_in_error(self):
        """Jooble puts the key in the URL path: /api/SECRETKEY123.
        On 4xx, the ToolError message must NOT contain the key.
        """
        secret = "SECRETKEY123"
        url = f"https://jooble.org/api/{secret}"
        error = _make_http_status_error(401, url)

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = error
        mock_client = _patched_async_client(mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ToolError) as exc_info:
                await fetch_json(url, provider="jooble")

        error_msg = str(exc_info.value)
        assert secret not in error_msg, f"Secret leaked in ToolError: {error_msg!r}"

    @pytest.mark.asyncio
    async def test_adzuna_query_key_not_in_error(self):
        """Adzuna puts keys in query params: ?app_key=SECRETKEY456.
        On 4xx, the ToolError message must NOT contain the key.
        """
        secret = "SECRETKEY456"
        base_url = "https://api.adzuna.com/v1/api/jobs/fr/search/1"
        error = _make_http_status_error(403, f"{base_url}?app_key={secret}&app_id=myid")

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = error
        mock_client = _patched_async_client(mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ToolError) as exc_info:
                await fetch_json(
                    base_url,
                    params={"app_key": secret, "app_id": "myid"},
                    provider="adzuna",
                )

        error_msg = str(exc_info.value)
        assert secret not in error_msg, f"Secret leaked in ToolError: {error_msg!r}"

    @pytest.mark.asyncio
    async def test_error_contains_status_code(self):
        """ToolError message must include the HTTP status code."""
        url = "https://api.example.com/v1/search"
        error = _make_http_status_error(429, url)

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = error
        mock_client = _patched_async_client(mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ToolError) as exc_info:
                await fetch_json(url, provider="example")

        assert "429" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_error_contains_provider_label(self):
        """ToolError should mention the provider name when given."""
        url = "https://api.example.com/search"
        error = _make_http_status_error(500, url)

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = error
        mock_client = _patched_async_client(mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ToolError) as exc_info:
                await fetch_json(url, provider="myprovider")

        assert "myprovider" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_request_error_raises_tool_error(self):
        """Network errors (RequestError) must also be wrapped as ToolError."""
        url = "https://api.example.com/search"
        net_error = _make_request_error(url)
        mock_client = _patched_async_client_raises(net_error)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ToolError):
                await fetch_json(url, provider="example")

    @pytest.mark.asyncio
    async def test_no_provider_still_sanitizes(self):
        """Without provider label, ToolError still must not contain secret."""
        secret = "MY_SUPER_SECRET"
        url = f"https://api.example.com/api/{secret}"
        error = _make_http_status_error(401, url)

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = error
        mock_client = _patched_async_client(mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ToolError) as exc_info:
                await fetch_json(url)

        assert secret not in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_raw_httpx_error_not_propagated(self):
        """raw httpx.HTTPStatusError must NOT propagate — only ToolError."""
        url = "https://api.example.com/search"
        error = _make_http_status_error(404, url)

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = error
        mock_client = _patched_async_client(mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            try:
                await fetch_json(url)
                pytest.fail("Expected ToolError not raised")
            except httpx.HTTPStatusError:
                pytest.fail("Raw httpx.HTTPStatusError leaked through")
            except ToolError:
                pass  # expected


class TestFetchJsonJoobleProviderIntegration:
    """Verify jooble.fetch wraps errors and never leaks the API key."""

    @pytest.mark.asyncio
    async def test_jooble_fetch_key_not_in_error_on_401(self, monkeypatch):
        """Monkeypatch env + httpx; verify key absent from exception message."""
        from decroche.source.providers import jooble

        secret = "JOOBLE_SECRET_KEY_XYZ"
        monkeypatch.setenv("JOOBLE_KEY", secret)

        url = f"https://jooble.org/api/{secret}"
        error = _make_http_status_error(401, url)

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = error
        mock_client = _patched_async_client(mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ToolError) as exc_info:
                await jooble.fetch("python developer")

        assert secret not in str(exc_info.value), (
            f"Jooble API key leaked in error: {exc_info.value!r}"
        )


class TestFetchJsonAdzunaProviderIntegration:
    """Verify adzuna.fetch wraps errors and never leaks the API keys."""

    @pytest.mark.asyncio
    async def test_adzuna_fetch_key_not_in_error_on_403(self, monkeypatch):
        from decroche.source.providers import adzuna

        secret_id = "MY_APP_ID_123"
        secret_key = "MY_APP_KEY_SECRET_456"
        monkeypatch.setenv("ADZUNA_APP_ID", secret_id)
        monkeypatch.setenv("ADZUNA_APP_KEY", secret_key)

        # The error URL would contain both secrets in query params
        error_url = (
            "https://api.adzuna.com/v1/api/jobs/fr/search/1"
            f"?app_id={secret_id}&app_key={secret_key}"
        )
        error = _make_http_status_error(403, error_url)

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = error
        mock_client = _patched_async_client(mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ToolError) as exc_info:
                await adzuna.fetch("software engineer")

        error_msg = str(exc_info.value)
        assert secret_key not in error_msg, f"app_key leaked: {error_msg!r}"
        assert secret_id not in error_msg, f"app_id leaked: {error_msg!r}"
