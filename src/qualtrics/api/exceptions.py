class QualtricsError(RuntimeError):
    """Base error for Qualtrics API and export failures."""


class QualtricsAPIError(QualtricsError):
    def __init__(self, message: str, *, status_code: int | None = None, request_id: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.request_id = request_id


class QualtricsExportError(QualtricsError):
    """Raised when an asynchronous response export fails or times out."""
