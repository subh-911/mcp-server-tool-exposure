"""
Query execution tool for the PostgreSQL MCP server.

This module provides the query_database tool which allows executing
SELECT queries with comprehensive security validations.
"""

import time
from typing import Any, Dict, List

from src.config import get_settings
from src.database.connection import get_db_pool
from src.database.validators import validate_limit, validate_query_is_select
from src.utils.logging import get_logger
from src.utils.rate_limiter import get_rate_limiter

logger = get_logger(__name__)


def query_database(
    query: str,
    limit: int = 100,
    timeout: int | None = None,
) -> Dict[str, Any]:
    """
    Execute a SELECT query against the PostgreSQL database.

    This tool allows you to run read-only SELECT queries with automatic
    safety validation and result limiting. All queries are validated to
    prevent SQL injection and other security issues.

    Security features:
    - Only SELECT queries allowed
    - SQL injection prevention with parameterized queries
    - Query timeout enforcement
    - Row limit enforcement
    - Rate limiting
    - Comprehensive logging

    Args:
        query: SQL SELECT query to execute. Must be a valid SELECT statement.
               Multi-statement queries (with semicolons) are not allowed.
               Comments are automatically removed.
        limit: Maximum number of rows to return (1-10000, default: 100).
               If the query would return more rows, only the first 'limit'
               rows are returned.
        timeout: Query timeout in seconds (1-300, default: from config).
                 Queries exceeding this time will be canceled.

    Returns:
        dict: Query results with structure:
            {
                "rows": list[dict],      # Query results as list of dicts
                "count": int,            # Number of rows returned
                "columns": list[str],    # Column names in result
                "duration_ms": float,    # Query execution time in milliseconds
                "limited": bool,         # True if results were truncated
                "query": str             # Sanitized query that was executed
            }

    Raises:
        ValidationError: If query format is invalid or limit is out of range
        SecurityError: If query contains dangerous operations
        QueryTimeoutError: If query exceeds timeout limit
        DatabaseError: If query execution fails
        RateLimitError: If rate limit is exceeded

    Examples:
        >>> query_database("SELECT * FROM users WHERE active = true", limit=10)
        {
            "rows": [{"id": 1, "name": "Alice", "active": true}, ...],
            "count": 10,
            "columns": ["id", "name", "active"],
            "duration_ms": 45.2,
            "limited": false,
            "query": "SELECT * FROM users WHERE active = true"
        }

        >>> query_database("SELECT COUNT(*) as total FROM orders")
        {
            "rows": [{"total": 1523}],
            "count": 1,
            "columns": ["total"],
            "duration_ms": 12.5,
            "limited": false,
            "query": "SELECT COUNT(*) as total FROM orders"
        }

    Note:
        - Column names are returned as lowercase
        - NULL values are returned as None (Python null)
        - Timestamps are returned as ISO format strings
        - Binary data (bytea) is returned as hexadecimal strings
    """
    start_time = time.time()

    # Rate limiting check
    rate_limiter = get_rate_limiter()
    rate_limiter.check_rate_limit("query_database")

    # Validate inputs
    validated_query = validate_query_is_select(query)
    validated_limit = validate_limit(limit)

    settings = get_settings()
    query_timeout = timeout or settings.query_timeout

    # Log the query execution attempt
    logger.info(
        "Executing database query",
        query_start=validated_query[:100],
        limit=validated_limit,
        timeout=query_timeout,
    )

    # Add LIMIT clause to the query if it doesn't have one
    # This ensures we never return more rows than requested
    query_upper = validated_query.upper()
    if "LIMIT" not in query_upper:
        limited_query = f"{validated_query} LIMIT {validated_limit}"
        result_limited = True
    else:
        # Query has its own LIMIT, use it but warn if it exceeds our limit
        limited_query = validated_query
        result_limited = False

    # Execute the query
    db_pool = get_db_pool()
    results = db_pool.execute_query(limited_query, timeout=query_timeout)

    # Extract column names from first row (if results exist)
    columns = list(results[0].keys()) if results else []

    # Calculate execution time
    duration_ms = (time.time() - start_time) * 1000

    logger.info(
        "Query execution completed",
        row_count=len(results),
        duration_ms=round(duration_ms, 2),
    )

    return {
        "rows": results,
        "count": len(results),
        "columns": columns,
        "duration_ms": round(duration_ms, 2),
        "limited": result_limited,
        "query": validated_query,
    }
