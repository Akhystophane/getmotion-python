from .client import GetMotion
from .exceptions import (
    AuthenticationError,
    ConflictError,
    GetMotionError,
    JobFailedError,
    NotFoundError,
    WaitTimeout,
)

__version__ = "0.1.0"
__all__ = [
    "GetMotion",
    # Exceptions — exported so users can catch them cleanly:
    # except getmotion.JobFailedError
    "GetMotionError",
    "AuthenticationError",
    "NotFoundError",
    "ConflictError",
    "JobFailedError",
    "WaitTimeout",
]
