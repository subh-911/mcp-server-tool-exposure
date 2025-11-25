"""
SQL query validation and security checks.

This module implements critical security validations to prevent SQL injection
and other database security vulnerabilities. All database operations MUST
use these validators.

SECURITY WARNING: The research identified a major SQL injection vulnerability
in reference implementations. This module prevents those attacks.
"""

import re
from typing import List

from src.config import get_settings
from src.utils.errors import SecurityError, ValidationError
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Dangerous SQL keywords that should never appear in SELECT queries
DANGEROUS_KEYWORDS = [
    "DROP",
    "DELETE",
    "INSERT",
    "UPDATE",
    "ALTER",
    "CREATE",
    "TRUNCATE",
    "GRANT",
    "REVOKE",
    "COMMIT",
    "ROLLBACK",
    "SAVEPOINT",
    "EXECUTE",
    "EXEC",
    "CALL",
    "SET",
    "DECLARE",
]

# SQL comment patterns to remove
COMMENT_PATTERNS = [
    (re.compile(r'--.*?$', re.MULTILINE), ''),  # Single-line comments
    (re.compile(r'/\*.*?\*/', re.DOTALL), ''),  # Multi-line comments
]


def sanitize_sql(query: str) -> str:
    """
    Remove SQL comments from a query.

    This helps prevent comment-based SQL injection techniques.

    Args:
        query: SQL query to sanitize

    Returns:
        Query with comments removed
    """
    sanitized = query
    for pattern, replacement in COMMENT_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized


def validate_query_is_select(query: str) -> str:
    """
    Validate that a query is a safe SELECT statement.

    This function implements multiple layers of validation:
    1. Removes SQL comments to prevent comment-based injection
    2. Ensures query starts with SELECT
    3. Blocks dangerous SQL keywords
    4. Prevents multi-statement queries (semicolon check)

    Args:
        query: SQL query to validate

    Returns:
        Sanitized query string

    Raises:
        SecurityError: If dangerous SQL operations are detected
        ValidationError: If query format is invalid

    Examples:
        >>> validate_query_is_select("SELECT * FROM users")
        'SELECT * FROM users'

        >>> validate_query_is_select("DROP TABLE users")
        SecurityError: Dangerous keyword detected: DROP

        >>> validate_query_is_select("SELECT * FROM users; DROP TABLE users")
        SecurityError: Multi-statement queries are not allowed
    """
    if not query or not query.strip():
        raise ValidationError(
            "Query cannot be empty",
            details={"query": query},
        )

    # Remove comments
    sanitized = sanitize_sql(query)

    # Normalize whitespace and convert to uppercase for checking
    normalized = ' '.join(sanitized.split()).upper()

    # Must start with SELECT
    if not normalized.startswith('SELECT'):
        logger.warning(
            "Non-SELECT query blocked",
            query_start=normalized[:50],
        )
        raise SecurityError(
            "Only SELECT queries are allowed",
            details={"query_start": query[:100]},
        )

    # Check for semicolons (multi-statement queries)
    # This is CRITICAL - prevents "SELECT 1; DROP TABLE users" attacks
    if ';' in sanitized:
        logger.error(
            "Multi-statement query blocked",
            query=sanitized,
        )
        raise SecurityError(
            "Multi-statement queries are not allowed (no semicolons)",
            details={"query": sanitized[:200]},
        )

    # Check for dangerous keywords
    for keyword in DANGEROUS_KEYWORDS:
        # Use word boundaries to avoid false positives
        pattern = r'\b' + re.escape(keyword) + r'\b'
        if re.search(pattern, normalized):
            logger.error(
                "Dangerous keyword detected",
                keyword=keyword,
                query=sanitized,
            )
            raise SecurityError(
                f"Dangerous keyword detected: {keyword}",
                details={"keyword": keyword, "query": sanitized[:200]},
            )

    logger.debug("Query validation passed", query_length=len(sanitized))
    return sanitized


def validate_identifier(
    identifier: str,
    identifier_type: str = "identifier",
    max_length: int = 63,
) -> str:
    """
    Validate a SQL identifier (table name, schema name, column name).

    PostgreSQL identifiers must follow specific rules. This function
    validates and sanitizes identifiers to prevent SQL injection.

    Args:
        identifier: The identifier to validate (table name, column, etc.)
        identifier_type: Type of identifier for error messages
        max_length: Maximum length (PostgreSQL limit is 63)

    Returns:
        Validated identifier

    Raises:
        ValidationError: If identifier is invalid

    Examples:
        >>> validate_identifier("users")
        'users'

        >>> validate_identifier("my_table_123")
        'my_table_123'

        >>> validate_identifier("Robert'; DROP TABLE users--")
        ValidationError: Invalid identifier
    """
    if not identifier or not identifier.strip():
        raise ValidationError(
            f"{identifier_type} cannot be empty",
            details={"identifier_type": identifier_type},
        )

    identifier = identifier.strip()

    # Check length
    if len(identifier) > max_length:
        raise ValidationError(
            f"{identifier_type} exceeds maximum length of {max_length}",
            details={
                "identifier": identifier[:100],
                "length": len(identifier),
                "max_length": max_length,
            },
        )

    # PostgreSQL identifier rules:
    # - Start with letter or underscore
    # - Contain only letters, digits, underscores
    # - Case-insensitive unless quoted (we don't support quoted identifiers)
    pattern = r'^[a-zA-Z_][a-zA-Z0-9_]*$'

    if not re.match(pattern, identifier):
        logger.warning(
            "Invalid identifier blocked",
            identifier=identifier,
            identifier_type=identifier_type,
        )
        raise ValidationError(
            f"Invalid {identifier_type}: must start with letter/underscore "
            f"and contain only alphanumeric characters and underscores",
            details={
                "identifier": identifier,
                "identifier_type": identifier_type,
            },
        )

    return identifier


def validate_schema_access(schema: str) -> str:
    """
    Validate that a schema is in the allowed list.

    Args:
        schema: Schema name to validate

    Returns:
        Validated schema name

    Raises:
        SecurityError: If schema is not in the allowed list
    """
    settings = get_settings()

    # First validate it's a valid identifier
    validated = validate_identifier(schema, identifier_type="schema")

    # Check against allowed list
    if validated not in settings.allowed_schemas:
        logger.warning(
            "Schema access denied",
            schema=schema,
            allowed_schemas=settings.allowed_schemas,
        )
        raise SecurityError(
            f"Access to schema '{schema}' is not allowed",
            details={
                "schema": schema,
                "allowed_schemas": settings.allowed_schemas,
            },
        )

    return validated


def validate_limit(limit: int) -> int:
    """
    Validate a LIMIT value.

    Args:
        limit: Limit value to validate

    Returns:
        Validated limit value

    Raises:
        ValidationError: If limit is invalid
    """
    settings = get_settings()

    if limit < 1:
        raise ValidationError(
            "Limit must be at least 1",
            details={"limit": limit},
        )

    if limit > settings.max_query_rows:
        raise ValidationError(
            f"Limit exceeds maximum of {settings.max_query_rows}",
            details={
                "limit": limit,
                "max_limit": settings.max_query_rows,
            },
        )

    return limit


def validate_export_limit(limit: int) -> int:
    """
    Validate an export limit value.

    Export operations may have different limits than regular queries.

    Args:
        limit: Limit value to validate

    Returns:
        Validated limit value

    Raises:
        ValidationError: If limit is invalid
    """
    settings = get_settings()

    if limit < 1:
        raise ValidationError(
            "Export limit must be at least 1",
            details={"limit": limit},
        )

    if limit > settings.max_export_rows:
        raise ValidationError(
            f"Export limit exceeds maximum of {settings.max_export_rows}",
            details={
                "limit": limit,
                "max_limit": settings.max_export_rows,
            },
        )

    return limit
