from __future__ import annotations

import logging
from typing import Any

from ._http import HttpClient
from .resources.jobs import JobsResource

logger = logging.getLogger("getmotion")

_DEFAULT_BASE_URL = "https://api.getmotion.io"


class GetMotion:
    """
    GetMotion API client.

    Usage::

        from getmotion import GetMotion

        client = GetMotion(api_key="gm-...")
        job = client.jobs.create(title="my-video")
        job.upload_audio("voiceover.mp3")
        job.start()

        job.wait_for("AWAITING_REVIEW")
        proposal = job.get_proposal()
        job.submit_review(proposal)

        session = job.init_storyboard()
        session.chat("make the transitions snappier")
        session.finalize()

        job.render()
        job.wait_for("DONE")
        renders = job.get_renders()
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
            api_key:  Your GetMotion API key.
            base_url: Override the API base URL (useful for self-hosted or staging).
            timeout:  HTTP request timeout in seconds.
            debug:    Enable verbose request/response logging.
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
