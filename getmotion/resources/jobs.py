from __future__ import annotations

import logging
import mimetypes
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from ..exceptions import JobFailedError, WaitTimeout
from .storyboard import StoryboardSession, _wait_for_storyboard_session

if TYPE_CHECKING:
    from .._http import HttpClient

logger = logging.getLogger("getmotion")

_FAILED_STATUS = "FAILED"
_TERMINAL_STATUSES = {"COMPLETED", "FAILED", "CANCELLED"}


class Job:
    """
    Represents a GetMotion job.

    Obtain via client.jobs.create() or client.jobs.get().
    """

    def __init__(self, job_id: str, http: "HttpClient", data: dict[str, Any] | None = None):
        self.id = job_id
        self._http = http
        self._data: dict[str, Any] = data or {}

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def status(self) -> dict[str, Any]:
        """Return current job status detail from the API.

        Returns:
            dict with the following keys:

            - ``job_id`` (str): The job identifier.
            - ``status`` (str): Current status value. See
              :meth:`wait_for` for the full list of possible values.
            - ``status_label`` (str): Human-readable label for the
              current status, e.g. ``"Analyzing your audio…"``.
            - ``stage`` (str): High-level pipeline stage. One of:

              - ``"analyze"`` — audio is being transcribed and assets
                gathered (statuses: ``CREATED``, ``QUEUED_COMPOSE_PRE``,
                ``RUNNING_COMPOSE_PRE``).
              - ``"review"`` — AI proposal is ready and waiting for
                user input (statuses: ``STORYBOARD_DRAFT``,
                ``AWAITING_REVIEW``).
              - ``"compose"`` — storyboard is being validated and a
                render blueprint generated (statuses:
                ``QUEUED_COMPOSE_POST``, ``RUNNING_COMPOSE_POST``,
                ``READY_FOR_INJECT``).
              - ``"render"`` — GPU worker is rendering the video
                (statuses: ``QUEUED_INJECT``, ``RUNNING_INJECT``).
              - ``"done"`` — video is complete (status: ``COMPLETED``).
              - ``"error"`` — job stopped with an error or was cancelled
                (statuses: ``FAILED``, ``CANCELLED``).

            - ``progress`` (float | None): Completion estimate from 0.0
              to 1.0, if available.
            - ``step_detail`` (str | None): Human-readable progress
              message, e.g. ``"Rendering: 45%"``.
            - ``created_at`` (str | None): ISO-format creation timestamp.
            - ``updated_at`` (str | None): ISO-format last-update
              timestamp.
            - ``error`` (dict | None): Present on failure. Contains
              ``"code"`` (str | None) and ``"detail"`` (str | None).
            - ``input_s3_key`` (str | None): S3 key of the uploaded audio.
            - ``proposal_s3_key`` (str | None): S3 key of the generated
              proposal.
            - ``current_blueprint_key`` (str | None): S3 key of the
              active blueprint.
            - ``next_action`` (dict | None): Populated when
              ``status == "AWAITING_REVIEW"``; contains ``"kind"``,
              ``"review_token"``, ``"proposal_key"``, and optionally
              ``"proposal_url"``.
            - ``last_transition`` (dict | None): Most recent status
              transition record.
        """
        return self._http.get(f"/jobs/{self.id}/status")

    def wait_for(
        self,
        status: str,
        timeout: int = 300,
        poll_interval: int = 3,
    ) -> dict[str, Any]:
        """Block until the job reaches *status*, then return the status payload.

        Args:
            status: Target status string to wait for. Valid values and
                when to use them:

                +--------------------------+-------------------------------------------+
                | Status                   | Meaning                                   |
                +==========================+===========================================+
                | ``CREATED``              | Job created, not yet started.             |
                +--------------------------+-------------------------------------------+
                | ``QUEUED_COMPOSE_PRE``   | Queued for audio analysis.                |
                +--------------------------+-------------------------------------------+
                | ``RUNNING_COMPOSE_PRE``  | AI is transcribing audio & picking assets.|
                +--------------------------+-------------------------------------------+
                | ``AWAITING_REVIEW``      | Proposal ready — call                     |
                |                          | :meth:`get_proposal` now.                 |
                +--------------------------+-------------------------------------------+
                | ``STORYBOARD_DRAFT``     | Storyboard generation in progress.        |
                +--------------------------+-------------------------------------------+
                | ``QUEUED_COMPOSE_POST``  | Queued for blueprint generation.          |
                +--------------------------+-------------------------------------------+
                | ``RUNNING_COMPOSE_POST`` | Blueprint being compiled.                 |
                +--------------------------+-------------------------------------------+
                | ``READY_FOR_INJECT``     | Blueprint ready — call :meth:`render` now.|
                +--------------------------+-------------------------------------------+
                | ``QUEUED_INJECT``        | Queued for GPU rendering.                 |
                +--------------------------+-------------------------------------------+
                | ``RUNNING_INJECT``       | GPU worker is rendering the video.        |
                +--------------------------+-------------------------------------------+
                | ``COMPLETED``            | Render done — call :meth:`get_renders`.   |
                +--------------------------+-------------------------------------------+
                | ``FAILED``               | Job failed (triggers :exc:`JobFailedError`|
                |                          | automatically).                           |
                +--------------------------+-------------------------------------------+
                | ``CANCELLED``            | Job was cancelled.                        |
                +--------------------------+-------------------------------------------+

                The two most common values to wait for are
                ``"AWAITING_REVIEW"`` (after :meth:`start`) and
                ``"COMPLETED"`` (after :meth:`render`).
            timeout: Maximum seconds to wait before raising
                :exc:`WaitTimeout`. Defaults to 300.
            poll_interval: Seconds between status polls. Defaults to 3.

        Returns:
            The status dict at the moment the target status was reached.
            Same shape as :meth:`status`.

        Raises:
            JobFailedError: if the job transitions to FAILED before
                reaching *status*.
            WaitTimeout: if *timeout* seconds elapse without reaching
                *status*.

        Example::

            job.wait_for("AWAITING_REVIEW", timeout=600)
        """
        deadline = time.monotonic() + timeout
        logger.debug("waiting for job=%s status=%s (timeout=%ss)", self.id, status, timeout)

        _last_detail: str | None = None
        while True:
            data = self.status()
            current = data.get("status", "")

            detail = data.get("step_detail")
            if detail and detail != _last_detail:
                logger.info("job=%s  %s", self.id, detail)
                _last_detail = detail

            if current == status:
                logger.debug("job=%s reached status=%s", self.id, status)
                return data

            if current == _FAILED_STATUS:
                error = data.get("error") or {}
                raise JobFailedError(
                    f"Job {self.id!r} failed: {error.get('detail', 'unknown error')}",
                    job_id=self.id,
                    code=error.get("code"),
                    detail=error.get("detail"),
                )

            if time.monotonic() >= deadline:
                raise WaitTimeout(self.id, status, timeout)

            time.sleep(poll_interval)

    # ------------------------------------------------------------------
    # Pipeline steps
    # ------------------------------------------------------------------

    def upload_audio(self, path: str | Path, content_type: str | None = None) -> None:
        """Presign and upload an audio file to the job's S3 input folder.

        Supports .mp3, .wav, .m4a and other audio formats.

        Args:
            path: Local path to the audio file.
            content_type: MIME type of the file, e.g. ``"audio/mpeg"``.
                Inferred from the file extension when omitted.

        Raises:
            FileNotFoundError: if *path* does not exist on disk.
            httpx.HTTPStatusError: if the presign request or S3 upload
                fails.
        """
        import httpx

        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Audio file not found: {path}")

        if content_type is None:
            guessed, _ = mimetypes.guess_type(str(path))
            content_type = guessed or "audio/mpeg"

        logger.debug("presigning upload for job=%s file=%s", self.id, path.name)
        presign_data = self._http.post(
            "/presign",
            json={"job_id": self.id, "filename": "audio.mp3", "content_type": content_type},
        )

        # Use the first target (root-level key)
        target = presign_data["targets"][0]
        with open(path, "rb") as f:
            audio_bytes = f.read()

        for target in presign_data["targets"]:
            if target.get("fields"):
                response = httpx.post(
                    target["url"],
                    data=target["fields"],
                    files={"file": (path.name, audio_bytes, content_type)},
                )
            else:
                response = httpx.put(
                    target["url"],
                    content=audio_bytes,
                    headers={"Content-Type": content_type},
                )
            response.raise_for_status()
            logger.debug("audio uploaded job=%s key=%s", self.id, target["key"])

    def start(self, input_s3_key: Optional[str] = None) -> dict[str, Any]:
        """Start processing the job — kicks off transcription and asset gathering.

        Args:
            input_s3_key: Override the S3 key of the audio input. When
                omitted the key set during :meth:`upload_audio` is used.

        Returns:
            dict with:

            - ``job_id`` (str): The job identifier.
            - ``queued`` (str): Present when successfully queued.
              If the job was already processing, ``status`` (str) is
              returned instead.
        """
        params = f"?input_s3_key={input_s3_key}" if input_s3_key else ""
        return self._http.post(f"/jobs/{self.id}/start{params}")

    def get_proposal(self) -> dict[str, Any]:
        """Return the AI-generated asset proposal for this job.

        The proposal is a dict with one key per asset *domain*.  Five domains
        (``footage``, ``icon``, ``person``, ``logo``, ``main_asset``) carry an
        ``available_*`` list — the AI's ranked candidates for that slot.  To
        swap an asset, edit the list in-place (reorder, remove, or replace
        entries) before passing the dict to :meth:`submit_review`.

        The remaining domains (``text``, ``color``, ``pose``, ``sound``,
        ``blur``) carry constraints or palette values rather than candidate
        lists.

        **Domain structures**

        ``footage`` — background video clips::

            {
                "prefix": "footage",
                "description": "Dynamic footage for batch 0",
                "available_footage": [
                    {
                        "id": "W-bd821e79",          # unique asset ID
                        "description": "person walking through office",
                        "path": "s3://bucket/.../clip.mp4"
                    },
                    ...
                ]
            }

        ``icon`` — icons and emoji::

            {
                "prefix": "icon",
                "default_domain": "Emoji Unicode code point",
                "default_format": "U+{hex_sequence}",
                "description": "Dynamic icons for batch 1",
                "available_icons": [
                    {
                        "id": "U+1F3E6",             # Unicode emoji: U+XXXX
                        "description": "bank building",
                        "path": "s3://bucket/.../emoji_1F3E6_.png",
                        "source": "local_emoji",     # "local_emoji" | "freepik"
                        "query": "U+1F3E6",
                        "format": "png"
                    },
                    {
                        "id": "ICON-7380091",         # Freepik icon: ICON-NNNNNNN
                        "description": "bank building collapsing",
                        "path": "s3://bucket/.../7380091_bankruptcy.png",
                        "source": "freepik"
                    },
                    ...
                ]
            }

        ``person`` — on-screen person / avatar::

            {
                "prefix": "person",
                "available_persons": [
                    {
                        "id": "P-LIB-001",
                        "description": "man in business suit",
                        "path": "s3://bucket/.../person_001.png",
                        "source": "library"
                    },
                    ...
                ]
            }

        ``logo`` — brand logo::

            {
                "prefix": "logo",
                "description": "Job-level logos (local-first)",
                "available_logos": [
                    {
                        "id": "L-LOCAL-company-logo",   # L-LOCAL-{slug}
                        "description": "company logo",
                        "path": "s3://bucket/.../company_logo.png"
                    },
                    ...
                ]
            }

        ``main_asset`` — primary hero image::

            {
                "prefix": "main_asset",
                "description": "Main assets (LLM-selected from library + job-local)",
                "available_main_assets": [
                    {
                        "id": "A-LIB-BLA-man-running-clock",  # A-LIB-{source}-{slug}
                        "description": "man running with a big clock in hands",
                        "path": "s3://bucket/.../man_running_clock.png",
                        "source": "black-and-white"   # "black-and-white" | "pinterest"
                                                      # | "freepik" | "local"
                    },
                    ...
                ]
            }

        ``color`` — RGBA design-token palette (values are floats 0.0–1.0, **not** 0–255)::

            {
                "prefix": "color",
                "description": "Color palette for design tokens",
                "palette": {
                    "Ink":     {"r": 0.0,  "g": 0.0,  "b": 0.0,  "a": 1.0},
                    "Ink2":    {"r": 1.0,  "g": 1.0,  "b": 1.0,  "a": 1.0},
                    "Accent":  {"r": 0.6,  "g": 0.04, "b": 0.016,"a": 1.0},
                    "Accent2": {"r": 0.5,  "g": 0.5,  "b": 0.5,  "a": 1.0},
                    "Surface": {"r": 1.0,  "g": 1.0,  "b": 1.0,  "a": 1.0}
                }
            }

        ``text`` — transcript-derived text constraint (no candidate list)::

            {
                "prefix": "text",
                "default_domain": "short text (1 up to 6 words MAXIMUM) with timestamps",
                "default_format_example": "Plus(1.5, 2.38) Jamais(2.38, 2.48) de(3.1, 3.2)",
                "forbidden": "A value of more than 6 words"
            }

        ``pose`` — static point-of-interest marker (value is always ``null``)::

            {
                "default_domain": null,
                "description": "Represent just static point of interest with a key value of null"
            }

        ``sound`` — background music / SFX (minimal, no candidate list yet)::

            {"prefix": "sound"}

        ``blur`` — blur / overlay effect (minimal, no candidate list yet)::

            {
                "prefix": "blur",
                "default_domain": "Blur effect parameters",
                "description": "Blur effects with intensity and type parameters"
            }

        Returns:
            The full domain mapping dict described above.
        """
        data = self._http.get(f"/jobs/{self.id}/review/domain_mapping")
        return data["domain_mapping"]

    def submit_review(
        self,
        decisions: dict[str, Any],
        review_token: Optional[str] = None,
    ) -> dict[str, Any]:
        """Save the domain mapping review decisions.

        This is called after the user inspects and edits the proposal
        returned by :meth:`get_proposal`. It does NOT trigger rendering
        — call :meth:`init_storyboard` next.

        Args:
            decisions: The domain mapping dict to submit (typically the
                object returned by :meth:`get_proposal`, optionally
                modified).
            review_token: Optional token from the job's ``next_action``
                payload. Not required in most integrations.

        Returns:
            dict with:

            - ``ok`` (bool): ``True`` on success.
            - ``submitted_key`` (str): S3 key where the submission was
              persisted.
        """
        body: dict[str, Any] = {"decisions_json": decisions}
        if review_token:
            body["review_token"] = review_token
        return self._http.post(f"/jobs/{self.id}/review", json=body)

    # ------------------------------------------------------------------
    # Storyboard
    # ------------------------------------------------------------------

    def init_storyboard(
        self,
        style: str = "default",
        force: bool = False,
        timeout: int = 600,
        poll_interval: int = 3,
    ) -> StoryboardSession:
        """Initialise (or resume) a storyboard editing session.

        If a session already exists for this job it is returned as-is.
        Pass ``force=True`` to discard the existing session and generate
        a new one.

        Generation is async server-side: the call blocks locally,
        polling until the storyboard is ready (up to *timeout* seconds).

        Args:
            style: Storyboard generation style. Defaults to
                ``"default"``.
            force: Discard any existing session and generate a new
                storyboard from scratch.
            timeout: Maximum seconds to wait for generation to complete.
                Defaults to 600.
            poll_interval: Seconds between readiness polls. Defaults
                to 3.

        Returns:
            A :class:`StoryboardSession` with the following attributes:

            - ``session_id`` (str)
            - ``job_id`` (str)
            - ``storyboard_key`` (str): S3 key of the storyboard JSON.
            - ``version`` (int): Current revision number.
            - ``high_level_summary`` (dict): Segment/macro overview —
              ``{"segments": [...], "stats": {"total_segments": int,
              "total_macros": int}}``.

        Raises:
            JobFailedError: if the job fails while waiting for the
                storyboard to be ready.
            WaitTimeout: if *timeout* seconds elapse before the
                storyboard becomes available.
        """
        logger.debug("init storyboard job=%s style=%s force=%s", self.id, style, force)
        data = self._http.post(
            "/storyboard/init",
            json={"job_id": self.id, "style": style, "force": force},
        )

        # API returns 202 when a new storyboard needs to be generated — poll until ready.
        if "session_id" not in data:
            logger.info("job=%s  Storyboard generation queued, waiting…", self.id)
            data = _wait_for_storyboard_session(
                self._http, self.id, timeout=timeout, poll_interval=poll_interval
            )

        return StoryboardSession(
            session_id=data["session_id"],
            job_id=data["job_id"],
            storyboard_key=data["storyboard_key"],
            version=data["version"],
            high_level_summary=data["high_level_summary"],
            http=self._http,
        )

    # ------------------------------------------------------------------
    # Render
    # ------------------------------------------------------------------

    def render(self, force: bool = False, keep_bin: bool = False) -> dict[str, Any]:
        """Queue the job for rendering on the GPU worker.

        The job must be in ``READY_FOR_INJECT`` status (i.e. storyboard
        must be finalized first via :meth:`session.finalize()
        <StoryboardSession.finalize>`).

        Args:
            force: Re-render even if renders already exist.
            keep_bin: Skip DaVinci bin cleanup after render (advanced).

        Returns:
            dict with:

            - ``job_id`` (str): The job identifier.
            - ``status`` (str): ``"QUEUED_INJECT"`` when successfully
              queued, or the current status string if a render was
              already in progress.
            - ``message`` (str): Human-readable confirmation, e.g.
              ``"Render queued"`` or ``"Already rendering"``.
        """
        params: list[str] = []
        if force:
            params.append("force=true")
        if keep_bin:
            params.append("keep_bin=true")
        qs = ("?" + "&".join(params)) if params else ""
        return self._http.post(f"/jobs/{self.id}/render{qs}")

    def get_renders(self, version: Optional[str] = None) -> dict[str, Any]:
        """Return renders for this job.

        Fetches the latest render version by default. Use
        :meth:`list_render_versions` to enumerate all available
        versions.

        Args:
            version: Blueprint version to fetch (e.g. ``"v2"``).
                Defaults to the latest available version.

        Returns:
            dict with:

            - ``renders`` (list[dict]): List of render entries, each
              containing:

              - ``s3_key`` (str): S3 object key of the render file.
              - ``url`` (str | None): Presigned download URL (if
                available).
              - ``etag`` (str | None): S3 ETag.
              - ``bytes`` (int | None): File size in bytes.
        """
        if version:
            return self._http.get(f"/jobs/{self.id}/renders/versions/{version}")
        versions = self.list_render_versions()
        if not versions:
            return {"renders": []}
        # Versions are returned oldest-first; take the last one
        latest = versions[-1]
        return self._http.get(f"/jobs/{self.id}/renders/versions/{latest['version']}")

    def list_render_versions(self) -> list[dict[str, Any]]:
        """Return all available render versions for this job.

        Returns:
            list of version dicts, ordered oldest-first. Each dict
            contains at minimum:

            - ``version`` (str): Version identifier used with
              :meth:`get_renders`.
        """
        data = self._http.get(f"/jobs/{self.id}/renders/versions")
        return data.get("versions", [])

    def __repr__(self) -> str:
        return f"<Job id={self.id!r}>"


class JobsResource:
    """Accessed via client.jobs — entry point for job operations."""

    def __init__(self, http: "HttpClient"):
        self._http = http

    def create(
        self,
        title: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        want_upload_url: bool = False,
    ) -> Job:
        """Create a new job.

        Args:
            title: Human-readable name, also used as the job ID
                (alphanumeric and hyphens only). A UUID is generated
                when omitted.
            idempotency_key: Re-using the same key returns the existing
                job instead of creating a new one.
            want_upload_url: Request a presigned S3 upload URL in the
                response (accessible via ``job._data["upload_url"]``).

        Returns:
            A :class:`Job` instance with ``job.id`` populated.
        """
        body: dict[str, Any] = {"want_upload_url": want_upload_url}
        if title:
            body["title"] = title
        if idempotency_key:
            body["idempotency_key"] = idempotency_key

        data = self._http.post("/jobs", json=body)
        return Job(job_id=data["job_id"], http=self._http, data=data)

    def get(self, job_id: str) -> Job:
        """Fetch an existing job by ID.

        Args:
            job_id: The job identifier to look up.

        Returns:
            A :class:`Job` instance for the given *job_id*.

        Raises:
            NotFoundError: if no job with *job_id* exists.
        """
        data = self._http.get(f"/jobs/{job_id}")
        return Job(job_id=data["job_id"], http=self._http, data=data)
