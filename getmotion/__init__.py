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
    # Exceptions — exported so users can catch them cleanly:
    # except getmotion.JobFailedError
    "GetMotionError",
    "AuthenticationError",
    "NotFoundError",
    "ConflictError",
    "JobFailedError",
    "WaitTimeout",
]
