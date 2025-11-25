"""
Data export tools for the PostgreSQL MCP server.

This module provides tools for exporting query results to various formats
including CSV and JSON.
"""

import csv
import io
import json
from typing import Any, Dict, Literal

from src.config import get_settings
from src.database.connection import get_db_pool
from src.database.validators import validate_export_limit, validate_query_is_select
from src.utils.errors import ValidationError
from src.utils.logging import get_logger
from src.utils.rate_limiter import get_rate_limiter

logger = get_logger(__name__)


def export_data(
    query: str,
    format: Literal["csv", "json"] = "json",
    limit: int = 1000,
) -> Dict[str, Any]:
    """
    Export query results to CSV or JSON format.

    This tool executes a SELECT query and exports the results in the specified
    format. Useful for data analysis, reporting, or integration with other tools.

    Args:
        query: SQL SELECT query to execute. Must be a valid SELECT statement.
               Multi-statement queries are not allowed.
        format: Export format - either "csv" or "json" (default: "json")
        limit: Maximum number of rows to export (1-50000, default: 1000).
               Higher limits are allowed for exports than regular queries.

    Returns:
        dict: Export results with structure:
            {
                "format": str,          # Export format used
                "data": str,            # Exported data as string
                "row_count": int,       # Number of rows exported
                "size_bytes": int,      # Size of exported data in bytes
                "query": str            # Sanitized query that was executed
            }

        For JSON format:
            - data is a JSON string containing an array of objects
            - Each object represents one row with column names as keys

        For CSV format:
            - data is a CSV string with headers
            - First row contains column names
            - Subsequent rows contain data values

    Raises:
        ValidationError: If query is invalid, format is unsupported, or limit out of range
        SecurityError: If query contains dangerous operations
        DatabaseError: If query execution fails
        RateLimitError: If rate limit exceeded

    Examples:
        >>> export_data("SELECT id, name FROM users LIMIT 3", format="json")
        {
            "format": "json",
            "data": '[{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]',
            "row_count": 2,
            "size_bytes": 58,
            "query": "SELECT id, name FROM users LIMIT 3"
        }

        >>> export_data("SELECT * FROM orders WHERE status = 'completed'", format="csv", limit=100)
        {
            "format": "csv",
            "data": "id,customer_id,total,status\\n1,101,99.99,completed\\n2,102,149.50,completed\\n",
            "row_count": 2,
            "size_bytes": 75,
            "query": "SELECT * FROM orders WHERE status = 'completed'"
        }

    Note:
        - NULL values in CSV are exported as empty strings
        - NULL values in JSON are exported as null
        - Timestamps are converted to ISO format strings
        - Binary data is hex-encoded in both formats
        - Export limits are higher than query limits (configurable)
    """
    # Check if export feature is enabled
    settings = get_settings()
    if not settings.enable_export:
        logger.warning("Export feature is disabled")
        raise ValidationError(
            "Export functionality is disabled in configuration",
            details={"enable_export": False},
        )

    # Rate limiting
    rate_limiter = get_rate_limiter()
    rate_limiter.check_rate_limit("export_data")

    # Validate inputs
    if format not in ["csv", "json"]:
        raise ValidationError(
            f"Unsupported export format: {format}",
            details={"format": format, "supported_formats": ["csv", "json"]},
        )

    validated_query = validate_query_is_select(query)
    validated_limit = validate_export_limit(limit)

    logger.info(
        "Exporting data",
        format=format,
        limit=validated_limit,
        query_start=validated_query[:100],
    )

    # Add LIMIT to query if not present
    query_upper = validated_query.upper()
    if "LIMIT" not in query_upper:
        limited_query = f"{validated_query} LIMIT {validated_limit}"
    else:
        limited_query = validated_query

    # Execute query
    db_pool = get_db_pool()
    results = db_pool.execute_query(limited_query)

    # Export based on format
    if format == "json":
        exported_data = _export_json(results)
    else:  # csv
        exported_data = _export_csv(results)

    size_bytes = len(exported_data.encode('utf-8'))

    logger.info(
        "Data exported successfully",
        format=format,
        row_count=len(results),
        size_bytes=size_bytes,
    )

    return {
        "format": format,
        "data": exported_data,
        "row_count": len(results),
        "size_bytes": size_bytes,
        "query": validated_query,
    }


def _export_json(results: list[Dict[str, Any]]) -> str:
    """
    Export results as JSON.

    Args:
        results: Query results as list of dictionaries

    Returns:
        JSON string representation of results
    """
    # Custom JSON encoder to handle special types
    def json_encoder(obj: Any) -> str:
        """Handle special types in JSON encoding."""
        # Handle bytes (binary data)
        if isinstance(obj, bytes):
            return obj.hex()

        # Handle other non-serializable types
        if hasattr(obj, 'isoformat'):
            return obj.isoformat()

        raise TypeError(f"Type {type(obj)} not JSON serializable")

    return json.dumps(results, default=json_encoder, indent=2)


def _export_csv(results: list[Dict[str, Any]]) -> str:
    """
    Export results as CSV.

    Args:
        results: Query results as list of dictionaries

    Returns:
        CSV string representation of results
    """
    if not results:
        return ""

    # Get column names from first row
    columns = list(results[0].keys())

    # Create CSV in memory
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=columns)

    # Write header
    writer.writeheader()

    # Write rows, converting special types
    for row in results:
        converted_row = {}
        for key, value in row.items():
            if value is None:
                converted_row[key] = ""
            elif isinstance(value, bytes):
                converted_row[key] = value.hex()
            elif hasattr(value, 'isoformat'):
                converted_row[key] = value.isoformat()
            else:
                converted_row[key] = str(value)
        writer.writerow(converted_row)

    return output.getvalue()
