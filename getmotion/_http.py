"""Internal HTTP client — not part of the public API."""
from __future__ import annotations

import logging
from typing import Any

import httpx

from .exceptions import (
    AuthenticationError,
    ConflictError,
    GetMotionError,
    NotFoundError,
)

logger = logging.getLogger("getmotion")


class HttpClient:
    def __init__(self, api_key: str, base_url: str, timeout: float = 60.0):
        self._base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            headers={"X-API-Key": api_key, "Accept": "application/json"},
            timeout=timeout,
        )

    def get(self, path: str, timeout: float | None = None, **params: Any) -> Any:
        return self._request("GET", path, params=params or None, timeout=timeout)

    def post(self, path: str, json: Any = None, timeout: float | None = None, **params: Any) -> Any:
        return self._request("POST", path, json=json, params=params or None, timeout=timeout)

    def _request(self, method: str, path: str, timeout: float | None = None, **kwargs: Any) -> Any:
        url = f"{self._base_url}{path}"
        logger.debug("%s %s  body=%s", method, url, kwargs.get("json"))

        response = self._client.request(method, url, timeout=timeout, **kwargs)

        logger.debug("← %s %s", response.status_code, url)

        self._raise_for_status(response)
        return response.json()

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if response.is_success:
            return
        try:
            detail = response.json().get("detail", response.text)
        except Exception:
            detail = response.text

        status = response.status_code
        if status == 401:
            raise AuthenticationError("Invalid or missing API key.", status_code=status, detail=detail)
        if status == 404:
            raise NotFoundError(detail or "Resource not found.", status_code=status)
        if status == 409:
            raise ConflictError(detail or "Conflict.", status_code=status)
        raise GetMotionError(detail or f"HTTP {status}", status_code=status, detail=detail)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "HttpClient":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()
