"""HTTP client with retry, backoff, and User-Agent."""

from __future__ import annotations

import time
from typing import Any, ClassVar

import requests

import corpus


class CorpusHTTPClient:
    """HTTP client with automatic retry on transient errors."""

    RETRYABLE_STATUS_CODES: ClassVar[set[int]] = {429, 500, 502, 503, 504}

    def __init__(
        self,
        *,
        contact_email: str | None = None,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
        timeout: int = 60,
    ) -> None:
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.timeout = timeout
        self.session = requests.Session()

        ua = f"sovereign-prospectus-corpus/{corpus.__version__}"
        if contact_email:
            ua += f" ({contact_email})"
        self.session.headers["User-Agent"] = ua

    def get(self, url: str, **kwargs: Any) -> requests.Response:
        return self._request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> requests.Response:
        return self._request("POST", url, **kwargs)

    def _request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        kwargs.setdefault("timeout", self.timeout)
        last_exc: Exception | None = None

        for attempt in range(self.max_retries + 1):
            resp = self.session.request(method, url, **kwargs)

            if resp.status_code < 400:
                return resp

            if resp.status_code not in self.RETRYABLE_STATUS_CODES:
                resp.raise_for_status()

            if attempt < self.max_retries:
                delay = self.backoff_factor * (2**attempt)
                time.sleep(delay)
            else:
                resp.raise_for_status()

        # Unreachable, but satisfies type checker
        raise last_exc or RuntimeError("request failed")  # pragma: no cover
