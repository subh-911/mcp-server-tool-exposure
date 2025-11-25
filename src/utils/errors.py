"""
Custom exception classes for the PostgreSQL MCP server.

This module defines all custom exceptions used throughout the application,
with structured error information for better debugging and user feedback.
"""

from enum import Enum
from typing import Any, Dict, Optional


class ErrorCategory(str, Enum):
    """Categories of errors for classification and handling."""

    CLIENT_ERROR = "client_error"  # 4xx - User's fault (invalid input, etc.)
    SERVER_ERROR = "server_error"  # 5xx - Our fault (bugs, configuration issues)
    DATABASE_ERROR = "database_error"  # Database-specific errors
    SECURITY_ERROR = "security_error"  # Security violations
    RATE_LIMIT_ERROR = "rate_limit_error"  # Rate limiting violations


class MCPError(Exception):
    """
    Base exception for all MCP server errors.

    This exception provides structured error information including
    category, details, and recoverability status.

    Attributes:
        message: Human-readable error message
        category: Error category for classification
        details: Additional error details as a dictionary
        recoverable: Whether the error is recoverable by retrying
    """

    def __init__(
        self,
        message: str,
        category: ErrorCategory,
        details: Optional[Dict[str, Any]] = None,
        recoverable: bool = False,
    ) -> None:
        """
        Initialize the MCP error.

        Args:
            message: Human-readable error message
            category: Error category for classification
            details: Additional error details
            recoverable: Whether retrying might succeed
        """
        self.message = message
        self.category = category
        self.details = details or {}
        self.recoverable = recoverable
        super().__init__(message)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert error to dictionary for JSON serialization.

        Returns:
            Dictionary representation of the error
        """
        return {
            "error": self.message,
            "category": self.category.value,
            "details": self.details,
            "recoverable": self.recoverable,
        }

    def __str__(self) -> str:
        """String representation of the error."""
        base = f"[{self.category.value}] {self.message}"
        if self.details:
            base += f" | Details: {self.details}"
        return base


class ValidationError(MCPError):
    """Raised when input validation fails."""

    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message,
            category=ErrorCategory.CLIENT_ERROR,
            details=details,
            recoverable=False,  # Invalid input won't be fixed by retrying
        )


class SecurityError(MCPError):
    """Raised when a security violation is detected."""

    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message,
            category=ErrorCategory.SECURITY_ERROR,
            details=details,
            recoverable=False,  # Security violations should not be retried
        )


class DatabaseError(MCPError):
    """Raised when a database operation fails."""

    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        recoverable: bool = True,
    ) -> None:
        super().__init__(
            message=message,
            category=ErrorCategory.DATABASE_ERROR,
            details=details,
            recoverable=recoverable,  # Some DB errors are transient
        )


class RateLimitError(MCPError):
    """Raised when rate limit is exceeded."""

    def __init__(
        self,
        message: str = "Rate limit exceeded. Please try again later.",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message,
            category=ErrorCategory.RATE_LIMIT_ERROR,
            details=details,
            recoverable=True,  # Rate limits reset over time
        )


class ConfigurationError(MCPError):
    """Raised when configuration is invalid or missing."""

    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message,
            category=ErrorCategory.SERVER_ERROR,
            details=details,
            recoverable=False,  # Configuration errors need manual fixing
        )


class QueryTimeoutError(MCPError):
    """Raised when a query exceeds the timeout limit."""

    def __init__(
        self,
        message: str = "Query execution timeout exceeded",
        timeout: Optional[int] = None,
    ) -> None:
        details = {"timeout_seconds": timeout} if timeout else {}
        super().__init__(
            message=message,
            category=ErrorCategory.DATABASE_ERROR,
            details=details,
            recoverable=True,  # Query might succeed with different parameters
        )
