"""Tests for HTTP client with retry and backoff."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from corpus.io.http import CorpusHTTPClient


class TestCorpusHTTPClient:
    """Tests for HTTP client configuration and retry behavior."""

    def test_default_user_agent(self) -> None:
        """Client has a User-Agent identifying the project."""
        client = CorpusHTTPClient()
        assert "sovereign-prospectus-corpus" in client.user_agent

    def test_custom_user_agent_from_contact(self) -> None:
        """User-Agent includes contact info when provided."""
        client = CorpusHTTPClient(contact_email="test@example.com")
        assert "test@example.com" in client.user_agent

    def test_get_returns_response(self) -> None:
        """Successful GET returns the response object."""
        client = CorpusHTTPClient()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        with patch.object(client.session, "request", return_value=mock_response):
            resp = client.get("https://example.com/doc.pdf")

        assert resp.status_code == 200

    def test_post_returns_response(self) -> None:
        """Successful POST returns the response object."""
        client = CorpusHTTPClient()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        with patch.object(client.session, "request", return_value=mock_response):
            resp = client.post("https://example.com/api", json={"query": "test"})

        assert resp.status_code == 200

    def test_retries_on_server_error(self) -> None:
        """Retries on 5xx errors up to max_retries."""
        client = CorpusHTTPClient(max_retries=2, backoff_factor=0.0)

        fail_resp = MagicMock()
        fail_resp.status_code = 503
        fail_resp.raise_for_status.side_effect = Exception("503 Server Error")

        ok_resp = MagicMock()
        ok_resp.status_code = 200
        ok_resp.raise_for_status = MagicMock()

        with patch.object(client.session, "request", side_effect=[fail_resp, ok_resp]):
            resp = client.get("https://example.com/doc.pdf")

        assert resp.status_code == 200

    def test_retries_on_429_rate_limit(self) -> None:
        """Retries on 429 Too Many Requests."""
        client = CorpusHTTPClient(max_retries=2, backoff_factor=0.0)

        rate_resp = MagicMock()
        rate_resp.status_code = 429
        rate_resp.raise_for_status.side_effect = Exception("429 Too Many Requests")

        ok_resp = MagicMock()
        ok_resp.status_code = 200
        ok_resp.raise_for_status = MagicMock()

        with patch.object(client.session, "request", side_effect=[rate_resp, ok_resp]):
            resp = client.get("https://example.com/doc.pdf")

        assert resp.status_code == 200

    def test_raises_after_max_retries_exhausted(self) -> None:
        """Raises after all retries are exhausted."""
        client = CorpusHTTPClient(max_retries=2, backoff_factor=0.0)

        fail_resp = MagicMock()
        fail_resp.status_code = 500
        fail_resp.raise_for_status.side_effect = Exception("500 Server Error")

        with (
            patch.object(client.session, "request", return_value=fail_resp),
            pytest.raises(Exception, match="500"),
        ):
            client.get("https://example.com/doc.pdf")

    def test_no_retry_on_client_error(self) -> None:
        """Does NOT retry on 4xx errors (except 429)."""
        client = CorpusHTTPClient(max_retries=3, backoff_factor=0.0)

        fail_resp = MagicMock()
        fail_resp.status_code = 404
        fail_resp.raise_for_status.side_effect = Exception("404 Not Found")

        with (
            patch.object(client.session, "request", return_value=fail_resp) as mock_req,
            pytest.raises(Exception, match="404"),
        ):
            client.get("https://example.com/missing.pdf")

        # Should only be called once — no retries for 404
        assert mock_req.call_count == 1

    def test_retries_on_connection_error(self) -> None:
        """Retries on transport-level ConnectionError."""
        client = CorpusHTTPClient(max_retries=2, backoff_factor=0.0)

        ok_resp = MagicMock()
        ok_resp.status_code = 200
        ok_resp.raise_for_status = MagicMock()

        with patch.object(
            client.session,
            "request",
            side_effect=[requests.ConnectionError("reset"), ok_resp],
        ):
            resp = client.get("https://example.com/doc.pdf")

        assert resp.status_code == 200

    def test_raises_connection_error_after_retries_exhausted(self) -> None:
        """ConnectionError raised after all retries fail."""
        client = CorpusHTTPClient(max_retries=1, backoff_factor=0.0)

        with (
            patch.object(
                client.session,
                "request",
                side_effect=requests.ConnectionError("reset"),
            ),
            pytest.raises(requests.ConnectionError),
        ):
            client.get("https://example.com/doc.pdf")

    def test_timeout_passed_to_request(self) -> None:
        """Timeout is forwarded to the underlying request."""
        client = CorpusHTTPClient(timeout=30)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        with patch.object(client.session, "request", return_value=mock_response) as mock_req:
            client.get("https://example.com/doc.pdf")

        _, kwargs = mock_req.call_args
        assert kwargs["timeout"] == 30
