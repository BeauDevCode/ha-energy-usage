"""Stable, value-free failures at the utility boundary."""

from __future__ import annotations

from enum import StrEnum


class ErrorCategory(StrEnum):
    """Safe categories for diagnostics and repair handling."""

    AUTH = "auth"
    CHALLENGE = "challenge"
    RATE_LIMIT = "rate_limit"
    PAYLOAD = "payload"
    POLICY = "policy"
    LEDGER = "ledger"
    TRANSIENT = "transient"


class EnergyUsageError(Exception):
    """An error with no response body or user-provided value in its text."""

    def __init__(
        self,
        category: ErrorCategory,
        status: int | None = None,
        retry_after: float | None = None,
    ) -> None:
        self.category = category
        self.status = status
        self.retry_after = retry_after
        super().__init__(category.value)

    def __repr__(self) -> str:
        return f"{type(self).__name__}(category={self.category.value!r})"


class AuthError(EnergyUsageError):
    """Authentication is missing or expired."""

    def __init__(self, status: int | None = None) -> None:
        super().__init__(ErrorCategory.AUTH, status)


class ChallengeError(EnergyUsageError):
    """An unsupported interactive challenge was requested."""

    def __init__(self, status: int | None = None) -> None:
        super().__init__(ErrorCategory.CHALLENGE, status)


class RateLimitError(EnergyUsageError):
    """The utility requested a delay before retrying."""

    def __init__(self, status: int | None = None, retry_after: float | None = None) -> None:
        super().__init__(ErrorCategory.RATE_LIMIT, status, retry_after)


class PayloadError(EnergyUsageError):
    """A response failed the reviewed schema or safety limits."""

    def __init__(self) -> None:
        super().__init__(ErrorCategory.PAYLOAD)


class PolicyError(EnergyUsageError):
    """A configured or remote operation violated integration policy."""

    def __init__(self) -> None:
        super().__init__(ErrorCategory.POLICY)


class NoExportConfirmationError(PolicyError):
    """The location's no-export requirement was not confirmed."""


class LedgerError(EnergyUsageError):
    """Persisted ledger data failed validation."""

    def __init__(self) -> None:
        super().__init__(ErrorCategory.LEDGER)


class UnknownProviderError(EnergyUsageError):
    """A provider key is not in the reviewed registry."""

    def __init__(self) -> None:
        super().__init__(ErrorCategory.POLICY)
