from __future__ import annotations

import logging
from typing import Any

from ._http import HttpClient
from .resources.jobs import JobsResource

logger = logging.getLogger("getmotion")

_DEFAULT_BASE_URL = "https://api.getmotion.io"


class GetMotion:
    """Top-level GetMotion API client.

    Create a single instance and reuse it across your application.  The
    client manages an underlying HTTP connection pool; always close it when
    you are done, either by calling :meth:`close` explicitly or by using the
    client as a context manager::

        # Context manager (recommended)
        with GetMotion(api_key="gm-...") as client:
            job = client.jobs.create(title="my-video")
            ...

        # Manual close
        client = GetMotion(api_key="gm-...")
        try:
            job = client.jobs.create(title="my-video")
            ...
        finally:
            client.close()
    """

    jobs: JobsResource
    """Entry point for all job operations.

    Use ``client.jobs.create()`` to start a new job or
    ``client.jobs.get(job_id)`` to resume an existing one.
    See :class:`JobsResource` for the full API.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = _DEFAULT_BASE_URL,
        timeout: float = 60.0,
        debug: bool = False,
    ):
        """
        Args:
            api_key: Your GetMotion API key (starts with ``gm-``).
            base_url: Override the API base URL. Useful for self-hosted
                instances or staging environments.
                Defaults to ``https://api.getmotion.io``.
            timeout: HTTP request timeout in seconds. Applies to every
                request except storyboard chat (which is LLM-backed and
                has no timeout). Defaults to 60.
            debug: Set to ``True`` to enable verbose request/response
                logging via the ``getmotion`` logger.
        """
        if debug:
            logging.getLogger("getmotion").setLevel(logging.DEBUG)
            if not logging.getLogger("getmotion").handlers:
                logging.getLogger("getmotion").addHandler(logging.StreamHandler())

        self._http = HttpClient(api_key=api_key, base_url=base_url, timeout=timeout)
        self.jobs = JobsResource(self._http)

    def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        self._http.close()

    def __enter__(self) -> "GetMotion":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()
