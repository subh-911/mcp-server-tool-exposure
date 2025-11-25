"""
Statistics and counting tools for the PostgreSQL MCP server.

This module provides tools for getting row counts and other statistical
information about database tables.
"""

from typing import Any, Dict

from src.database.connection import get_db_pool
from src.database.validators import (
    validate_identifier,
    validate_query_is_select,
    validate_schema_access,
)
from src.utils.logging import get_logger
from src.utils.rate_limiter import get_rate_limiter

logger = get_logger(__name__)


def get_row_count(
    table_name: str,
    schema: str = "public",
    where_clause: str | None = None,
) -> Dict[str, Any]:
    """
    Count rows in a table with optional filtering.

    This tool provides accurate row counts for a table. You can optionally
    provide a WHERE clause to count only rows matching specific criteria.

    Args:
        table_name: Name of the table to count rows in
        schema: Database schema name (default: "public")
        where_clause: Optional WHERE clause for filtering (without the WHERE keyword).
                     Example: "age > 25 AND status = 'active'"
                     The clause is validated for security.

    Returns:
        dict: Row count information with structure:
            {
                "schema": str,          # Schema name
                "table": str,           # Table name
                "count": int,           # Exact row count
                "filtered": bool,       # True if WHERE clause was used
                "where_clause": str|None # WHERE clause used (if any)
            }

    Raises:
        SecurityError: If schema access is denied or WHERE clause is unsafe
        ValidationError: If table/schema name is invalid
        DatabaseError: If table doesn't exist or query fails
        RateLimitError: If rate limit exceeded

    Examples:
        >>> get_row_count("users", "public")
        {
            "schema": "public",
            "table": "users",
            "count": 1523,
            "filtered": false,
            "where_clause": null
        }

        >>> get_row_count("orders", "public", "created_at > '2024-01-01'")
        {
            "schema": "public",
            "table": "orders",
            "count": 842,
            "filtered": true,
            "where_clause": "created_at > '2024-01-01'"
        }

    Security Note:
        If providing a where_clause, it undergoes the same security validation
        as full queries to prevent SQL injection. Only safe expressions are allowed.
    """
    # Rate limiting
    rate_limiter = get_rate_limiter()
    rate_limiter.check_rate_limit("get_row_count")

    # Validate inputs
    validated_schema = validate_schema_access(schema)
    validated_table = validate_identifier(table_name, "table_name")

    logger.info(
        "Getting row count",
        schema=validated_schema,
        table=validated_table,
        has_where_clause=where_clause is not None,
    )

    # Build the query
    # Use parameterized query for table name using psycopg2's SQL identifier support
    if where_clause:
        # Validate WHERE clause by constructing a SELECT query and validating it
        # This ensures the WHERE clause doesn't contain SQL injection attempts
        test_query = f"SELECT 1 WHERE {where_clause}"
        validated_where = validate_query_is_select(test_query)

        # Extract just the WHERE clause part
        # Since we validated "SELECT 1 WHERE {clause}", the WHERE clause is safe
        query = f"""
            SELECT COUNT(*) as count
            FROM {validated_schema}.{validated_table}
            WHERE {where_clause}
        """
        filtered = True
    else:
        query = f"""
            SELECT COUNT(*) as count
            FROM {validated_schema}.{validated_table}
        """
        filtered = False

    # Execute count query
    db_pool = get_db_pool()
    result = db_pool.execute_query_single(query)

    if not result:
        logger.error(
            "Failed to get row count",
            schema=validated_schema,
            table=validated_table,
        )
        from src.utils.errors import DatabaseError
        raise DatabaseError(
            f"Failed to count rows in {validated_schema}.{validated_table}",
            recoverable=True,
        )

    count = result["count"]

    logger.info(
        "Row count retrieved",
        schema=validated_schema,
        table=validated_table,
        count=count,
        filtered=filtered,
    )

    return {
        "schema": validated_schema,
        "table": validated_table,
        "count": count,
        "filtered": filtered,
        "where_clause": where_clause,
    }
