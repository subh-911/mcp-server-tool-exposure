"""
FastMCP server for PostgreSQL database access.

This is the main server module that defines and exposes all MCP tools
for database operations.
"""

from typing import Literal

from fastmcp import FastMCP

from src.config import get_settings
from src.tools.export import export_data
from src.tools.query import query_database
from src.tools.schema import describe_table, list_tables
from src.tools.stats import get_row_count
from src.utils.logging import get_logger, setup_logging

# Initialize logging
setup_logging()
logger = get_logger(__name__)

# Get settings
settings = get_settings()

# Create FastMCP server instance
mcp = FastMCP(
    name=settings.server_name,
    version=settings.server_version,
)

logger.info(
    "Initializing MCP server",
    server_name=settings.server_name,
    version=settings.server_version,
)


# Register tools
@mcp.tool()
def query_database_tool(
    query: str,
    limit: int = 100,
    timeout: int | None = None,
) -> dict:
    """
    Execute a SELECT query against the PostgreSQL database.

    This tool allows you to run read-only SELECT queries with automatic
    safety validation and result limiting. All queries are validated to
    prevent SQL injection and other security issues.

    Args:
        query: SQL SELECT query to execute. Must be a valid SELECT statement.
        limit: Maximum number of rows to return (1-10000, default: 100)
        timeout: Query timeout in seconds (1-300, optional)

    Returns:
        Query results with rows, columns, count, and execution time
    """
    return query_database(query=query, limit=limit, timeout=timeout)


@mcp.tool()
def list_tables_tool(schema: str = "public") -> dict:
    """
    List all tables in a database schema.

    This tool retrieves information about all tables in the specified schema,
    including table names, row counts, and sizes.

    Args:
        schema: Database schema name (default: "public")

    Returns:
        Schema information with list of tables
    """
    return list_tables(schema=schema)


@mcp.tool()
def describe_table_tool(
    table_name: str,
    schema: str = "public",
) -> dict:
    """
    Get detailed schema information for a specific table.

    This tool retrieves comprehensive information about a table's structure,
    including columns, data types, constraints, and indexes.

    Args:
        table_name: Name of the table to describe
        schema: Database schema name (default: "public")

    Returns:
        Detailed table information including columns, indexes, and constraints
    """
    return describe_table(table_name=table_name, schema=schema)


@mcp.tool()
def get_row_count_tool(
    table_name: str,
    schema: str = "public",
    where_clause: str | None = None,
) -> dict:
    """
    Count rows in a table with optional filtering.

    This tool provides accurate row counts for a table. You can optionally
    provide a WHERE clause to count only rows matching specific criteria.

    Args:
        table_name: Name of the table to count rows in
        schema: Database schema name (default: "public")
        where_clause: Optional WHERE clause for filtering (without WHERE keyword)

    Returns:
        Row count information
    """
    return get_row_count(
        table_name=table_name,
        schema=schema,
        where_clause=where_clause,
    )


@mcp.tool()
def export_data_tool(
    query: str,
    format: Literal["csv", "json"] = "json",
    limit: int = 1000,
) -> dict:
    """
    Export query results to CSV or JSON format.

    This tool executes a SELECT query and exports the results in the specified
    format. Useful for data analysis, reporting, or integration with other tools.

    Args:
        query: SQL SELECT query to execute
        format: Export format - either "csv" or "json" (default: "json")
        limit: Maximum number of rows to export (1-50000, default: 1000)

    Returns:
        Exported data as string with format and metadata
    """
    return export_data(query=query, format=format, limit=limit)


# Register resources
@mcp.resource("postgres://status")
def get_server_status() -> str:
    """
    Get the current server and database connection status.

    This resource provides information about the server configuration,
    rate limiting status, and database connectivity.
    """
    from src.database.connection import get_db_pool
    from src.utils.rate_limiter import get_rate_limiter

    db_pool = get_db_pool()
    rate_limiter = get_rate_limiter()

    status = {
        "server": {
            "name": settings.server_name,
            "version": settings.server_version,
            "log_level": settings.log_level,
        },
        "database": {
            "connected": db_pool.test_connection(),
            "pool_min": settings.db_pool_min,
            "pool_max": settings.db_pool_max,
        },
        "security": {
            "max_query_rows": settings.max_query_rows,
            "query_timeout": settings.query_timeout,
            "allowed_schemas": settings.allowed_schemas,
            "rate_limit": rate_limiter.get_stats(),
        },
        "features": {
            "export_enabled": settings.enable_export,
            "max_export_rows": settings.max_export_rows,
        },
    }

    import json
    return json.dumps(status, indent=2)


@mcp.resource("postgres://schemas")
def get_available_schemas() -> str:
    """
    Get a list of available database schemas.

    This resource returns information about which schemas are
    accessible through this MCP server.
    """
    import json
    return json.dumps(
        {
            "allowed_schemas": settings.allowed_schemas,
            "description": "Database schemas accessible through this MCP server",
        },
        indent=2,
    )


# Startup and shutdown handlers
@mcp.on_startup()
async def startup() -> None:
    """Initialize resources on server startup."""
    logger.info("MCP server starting up")

    # Initialize database pool (already done in get_db_pool)
    from src.database.connection import get_db_pool

    db_pool = get_db_pool()

    if db_pool.test_connection():
        logger.info("Database connection verified")
    else:
        logger.error("Database connection failed")

    logger.info("MCP server ready")


@mcp.on_shutdown()
async def shutdown() -> None:
    """Clean up resources on server shutdown."""
    logger.info("MCP server shutting down")

    # Close database connections
    from src.database.connection import close_db_pool

    close_db_pool()

    logger.info("MCP server shut down complete")
