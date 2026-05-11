class DomainError(Exception):
    """Base class for domain-layer errors."""


class ValidationError(DomainError):
    """Raised when user-submitted data fails validation."""


class NotFoundError(DomainError):
    """Raised when a requested domain object does not exist."""


class ForbiddenError(DomainError):
    """Raised when an operation is not allowed for current user."""
