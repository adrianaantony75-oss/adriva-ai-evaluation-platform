class DomainError(Exception):
    """Safe error information suitable for API clients."""

    def __init__(self, code: str, message: str, status: int = 422) -> None:
        self.code = code
        self.message = message
        self.status = status
        super().__init__(message)
