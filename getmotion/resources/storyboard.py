from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .._http import HttpClient

logger = logging.getLogger("getmotion")


class StoryboardSession:
    """
    Represents an active storyboard editing session for a job.

    Obtain via job.init_storyboard().
    """

    def __init__(
        self,
        session_id: str,
        job_id: str,
        storyboard_key: str,
        version: int,
        high_level_summary: dict[str, Any],
        http: "HttpClient",
    ):
        self.session_id = session_id
        self.job_id = job_id
        self.storyboard_key = storyboard_key
        self.version = version
        self.high_level_summary = high_level_summary
        self._http = http

    def get(self) -> "StoryboardSession":
        """Refresh session state from the API."""
        data = self._http.get(f"/storyboard/{self.session_id}")
        self.storyboard_key = data["storyboard_key"]
        self.version = data["version"]
        self.high_level_summary = data["high_level_summary"]
        return self

    def chat(self, message: str) -> str:
        """
        Send a natural-language instruction to the storyboard LLM.

        Updates the session in place and returns the assistant reply.
        """
        logger.debug("storyboard chat session=%s message=%r", self.session_id, message)
        data = self._http.post(
            f"/storyboard/{self.session_id}/chat",
            json={"message": message},
            timeout=None,  # LLM-backed, no upper bound
        )
        # Update local state if the storyboard changed
        if data.get("high_level_summary"):
            self.high_level_summary = data["high_level_summary"]
        self.storyboard_key = data.get("storyboard_key", self.storyboard_key)
        self.version = data.get("version", self.version)
        return data["reply"]

    def finalize(self) -> None:
        """
        Finalize the storyboard and trigger blueprint generation (compose_post).

        Internally:
          1. POST /storyboard/{session_id}/finalize
          2. POST /jobs/{job_id}/review with the returned storyboard_key
             (this triggers compose_post server-side)

        After this call the job status transitions to READY_FOR_INJECT
        and job.render() can be called.
        """
        logger.debug("finalizing storyboard session=%s", self.session_id)

        finalize_data = self._http.post(f"/storyboard/{self.session_id}/finalize")
        storyboard_key = finalize_data["storyboard_key"]
        self.storyboard_key = storyboard_key

        import datetime
        self._http.post(
            f"/jobs/{self.job_id}/review",
            json={
                "decisions_json": {
                    "storyboard_key": storyboard_key,
                    "submitted_at": datetime.datetime.utcnow().isoformat(),
                }
            },
        )
        logger.debug("storyboard finalized, blueprint generation triggered job=%s", self.job_id)

    def regenerate(self, style: str = "default") -> "StoryboardSession":
        """
        Discard the current storyboard and generate a fresh one.

        Returns a new StoryboardSession — the current session is no longer valid
        after this call.
        """
        logger.debug("regenerating storyboard job=%s", self.job_id)
        data = self._http.post(
            "/storyboard/init",
            json={"job_id": self.job_id, "style": style, "force": True},
        )
        return StoryboardSession(
            session_id=data["session_id"],
            job_id=data["job_id"],
            storyboard_key=data["storyboard_key"],
            version=data["version"],
            high_level_summary=data["high_level_summary"],
            http=self._http,
        )
