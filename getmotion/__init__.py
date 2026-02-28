"""GetMotion Python SDK
======================

The GetMotion SDK lets you drive the full AI video-generation pipeline from
Python.  A job moves through five stages in order:

1. **Analyze** — upload a voice-over audio file and let the AI transcribe it,
   pick matching footage, icons, music, and text overlays.
2. **Review** — inspect the AI's asset choices (the "proposal") and optionally
   edit them before committing.
3. **Storyboard** — chat with the AI to adjust cuts, transitions, pacing, and
   layout in a round-trip editing session.
4. **Compose** — the storyboard is validated and a render blueprint is
   generated automatically when you call :meth:`~getmotion.StoryboardSession.finalize`.
5. **Render** — a GPU worker produces the final video file(s).

Quick start::

    from getmotion import GetMotion, JobFailedError, WaitTimeout

    with GetMotion(api_key="gm-...") as client:

        # 1. Create & upload
        job = client.jobs.create(title="my-video")
        job.upload_audio("voiceover.mp3")
        job.start()

        # 2. Review the AI proposal
        job.wait_for("AWAITING_REVIEW", timeout=600)
        proposal = job.get_proposal()
        job.submit_review(proposal)          # accept as-is, or edit first

        # 3. Edit the storyboard
        session = job.init_storyboard()
        session.chat("Make the transitions snappier.")
        session.finalize()

        # 4. Render
        job.render()
        job.wait_for("COMPLETED", timeout=1800)
        renders = job.get_renders()
        print(renders)

Main classes
------------

:class:`GetMotion`
    The top-level API client.  Create one instance per application and reuse
    it.  Can be used as a context manager (``with GetMotion(...) as client``).

:class:`JobsResource` — ``client.jobs``
    Factory for :class:`Job` objects.  Use ``client.jobs.create()`` to start
    a new job or ``client.jobs.get(job_id)`` to resume an existing one.

:class:`Job`
    Represents a single video-generation job.  Every pipeline action —
    uploading audio, polling status, reviewing the proposal, editing the
    storyboard, rendering — is a method on this object.

:class:`StoryboardSession`
    An interactive editing session for a job's storyboard.  Obtained via
    :meth:`Job.init_storyboard`.  Use :meth:`~StoryboardSession.chat` to give
    the AI natural-language instructions, then call
    :meth:`~StoryboardSession.finalize` to lock in your changes and trigger
    blueprint generation.

Exceptions
----------

All SDK exceptions inherit from :class:`GetMotionError`.

:class:`JobFailedError`
    The job transitioned to ``FAILED`` status.  Contains ``code`` and
    ``detail`` from the server.

:class:`WaitTimeout`
    :meth:`Job.wait_for` or :meth:`Job.init_storyboard` exceeded *timeout*
    without the job reaching the target status.

:class:`AuthenticationError`, :class:`NotFoundError`, :class:`ConflictError`
    HTTP-level errors (401, 404, 409).
"""

from .client import GetMotion
from .exceptions import (
    AuthenticationError,
    ConflictError,
    GetMotionError,
    JobFailedError,
    NotFoundError,
    WaitTimeout,
)
from .resources import Job, JobsResource, StoryboardSession

__version__ = "0.1.0"
__all__ = [
    "GetMotion",
    "Job",
    "JobsResource",
    "StoryboardSession",
    "GetMotionError",
    "AuthenticationError",
    "NotFoundError",
    "ConflictError",
    "JobFailedError",
    "WaitTimeout",
]
