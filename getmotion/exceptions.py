class GetMotionError(Exception):
    """Base exception for all GetMotion SDK errors."""

    def __init__(self, message: str, status_code: int | None = None, detail: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail


class AuthenticationError(GetMotionError):
    """Raised when the API key is missing or invalid (401)."""


class NotFoundError(GetMotionError):
    """Raised when the requested resource does not exist (404)."""


class ConflictError(GetMotionError):
    """Raised on state conflicts, e.g. duplicate job id (409)."""


class JobFailedError(GetMotionError):
    """Raised when a job transitions to FAILED status."""

    def __init__(self, message: str, job_id: str, code: str | None = None, detail: str | None = None):
        super().__init__(message, detail=detail)
        self.job_id = job_id
        self.code = code


class WaitTimeout(GetMotionError):
    """Raised when wait_for() exceeds the timeout without reaching the target status."""

    def __init__(self, job_id: str, target_status: str, timeout: int):
        super().__init__(
            f"Job {job_id!r} did not reach status {target_status!r} within {timeout}s"
        )
        self.job_id = job_id
        self.target_status = target_status
        self.timeout = timeout
