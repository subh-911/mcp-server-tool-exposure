"""
Schema introspection tools for the PostgreSQL MCP server.

This module provides tools for exploring database schema information
including listing tables and describing table structures.
"""

from typing import Any, Dict, List

from psycopg2.extensions import AsIs

from src.config import get_settings
from src.database.connection import get_db_pool
from src.database.validators import validate_identifier, validate_schema_access
from src.utils.logging import get_logger
from src.utils.rate_limiter import get_rate_limiter

logger = get_logger(__name__)


def list_tables(schema: str = "public") -> Dict[str, Any]:
    """
    List all tables in a database schema.

    This tool retrieves information about all tables in the specified schema,
    including table names, row counts, and sizes. Only schemas configured in
    the allowed_schemas list can be accessed.

    Args:
        schema: Database schema name (default: "public"). Must be in the
                allowed_schemas configuration list.

    Returns:
        dict: Schema information with structure:
            {
                "schema": str,          # Schema name
                "tables": list[dict],   # List of table information
                "table_count": int      # Total number of tables
            }

            Each table dict contains:
            {
                "name": str,            # Table name
                "row_count": int,       # Approximate row count
                "size": str,            # Human-readable table size
                "description": str|None # Table comment (if any)
            }

    Raises:
        SecurityError: If schema is not in allowed list
        ValidationError: If schema name is invalid
        DatabaseError: If query fails
        RateLimitError: If rate limit exceeded

    Examples:
        >>> list_tables("public")
        {
            "schema": "public",
            "tables": [
                {
                    "name": "users",
                    "row_count": 1523,
                    "size": "128 kB",
                    "description": "Application users"
                },
                {
                    "name": "orders",
                    "row_count": 8421,
                    "size": "1024 kB",
                    "description": null
                }
            ],
            "table_count": 2
        }

    Note:
        - Row counts are approximate (from pg_class.reltuples)
        - Sizes include table data and indexes
        - Tables are sorted alphabetically by name
    """
    # Rate limiting
    rate_limiter = get_rate_limiter()
    rate_limiter.check_rate_limit("list_tables")

    # Validate and check schema access
    validated_schema = validate_schema_access(schema)

    logger.info("Listing tables", schema=validated_schema)

    # Query to get table information
    query = """
        SELECT
            c.relname AS table_name,
            c.reltuples::bigint AS row_count,
            pg_size_pretty(pg_total_relation_size(c.oid)) AS size,
            obj_description(c.oid, 'pg_class') AS description
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relkind = 'r'
            AND n.nspname = %s
            AND c.relname NOT LIKE 'pg_%'
        ORDER BY c.relname
    """

    db_pool = get_db_pool()
    results = db_pool.execute_query(query, (validated_schema,))

    # Format results
    tables = [
        {
            "name": row["table_name"],
            "row_count": row["row_count"],
            "size": row["size"],
            "description": row["description"],
        }
        for row in results
    ]

    logger.info(
        "Tables listed successfully",
        schema=validated_schema,
        table_count=len(tables),
    )

    return {
        "schema": validated_schema,
        "tables": tables,
        "table_count": len(tables),
    }


def describe_table(
    table_name: str,
    schema: str = "public",
) -> Dict[str, Any]:
    """
    Get detailed schema information for a specific table.

    This tool retrieves comprehensive information about a table's structure,
    including columns, data types, constraints, and indexes.

    Args:
        table_name: Name of the table to describe
        schema: Database schema name (default: "public")

    Returns:
        dict: Table information with structure:
            {
                "schema": str,          # Schema name
                "table": str,           # Table name
                "description": str|None,# Table comment
                "columns": list[dict],  # Column information
                "primary_key": list[str],# Primary key column names
                "indexes": list[dict],  # Index information
                "row_count": int        # Approximate row count
            }

            Each column dict contains:
            {
                "name": str,            # Column name
                "type": str,            # Data type
                "nullable": bool,       # Can be NULL
                "default": str|None,    # Default value
                "description": str|None # Column comment
            }

            Each index dict contains:
            {
                "name": str,            # Index name
                "columns": list[str],   # Indexed columns
                "unique": bool,         # Is unique index
                "primary": bool         # Is primary key index
            }

    Raises:
        SecurityError: If schema is not in allowed list
        ValidationError: If table or schema name is invalid
        DatabaseError: If table doesn't exist or query fails
        RateLimitError: If rate limit exceeded

    Examples:
        >>> describe_table("users", "public")
        {
            "schema": "public",
            "table": "users",
            "description": "Application users",
            "columns": [
                {
                    "name": "id",
                    "type": "integer",
                    "nullable": false,
                    "default": "nextval('users_id_seq'::regclass)",
                    "description": "User ID"
                },
                {
                    "name": "email",
                    "type": "character varying(255)",
                    "nullable": false,
                    "default": null,
                    "description": null
                }
            ],
            "primary_key": ["id"],
            "indexes": [
                {
                    "name": "users_pkey",
                    "columns": ["id"],
                    "unique": true,
                    "primary": true
                },
                {
                    "name": "users_email_idx",
                    "columns": ["email"],
                    "unique": true,
                    "primary": false
                }
            ],
            "row_count": 1523
        }
    """
    # Rate limiting
    rate_limiter = get_rate_limiter()
    rate_limiter.check_rate_limit("describe_table")

    # Validate inputs
    validated_schema = validate_schema_access(schema)
    validated_table = validate_identifier(table_name, "table_name")

    logger.info(
        "Describing table",
        schema=validated_schema,
        table=validated_table,
    )

    db_pool = get_db_pool()

    # Query for column information
    columns_query = """
        SELECT
            a.attname AS column_name,
            pg_catalog.format_type(a.atttypid, a.atttypmod) AS data_type,
            NOT a.attnotnull AS nullable,
            pg_get_expr(ad.adbin, ad.adrelid) AS default_value,
            col_description(a.attrelid, a.attnum) AS description
        FROM pg_attribute a
        LEFT JOIN pg_attrdef ad ON a.attrelid = ad.adrelid AND a.attnum = ad.adnum
        JOIN pg_class c ON a.attrelid = c.oid
        JOIN pg_namespace n ON c.relnamespace = n.oid
        WHERE c.relname = %s
            AND n.nspname = %s
            AND a.attnum > 0
            AND NOT a.attisdropped
        ORDER BY a.attnum
    """

    columns_result = db_pool.execute_query(
        columns_query,
        (validated_table, validated_schema),
    )

    columns = [
        {
            "name": row["column_name"],
            "type": row["data_type"],
            "nullable": row["nullable"],
            "default": row["default_value"],
            "description": row["description"],
        }
        for row in columns_result
    ]

    # Query for primary key
    pk_query = """
        SELECT a.attname AS column_name
        FROM pg_index i
        JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
        JOIN pg_class c ON c.oid = i.indrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relname = %s
            AND n.nspname = %s
            AND i.indisprimary
        ORDER BY a.attnum
    """

    pk_result = db_pool.execute_query(pk_query, (validated_table, validated_schema))
    primary_key = [row["column_name"] for row in pk_result]

    # Query for indexes
    indexes_query = """
        SELECT
            i.relname AS index_name,
            ix.indisunique AS is_unique,
            ix.indisprimary AS is_primary,
            ARRAY(
                SELECT a.attname
                FROM pg_attribute a
                WHERE a.attrelid = t.oid
                    AND a.attnum = ANY(ix.indkey)
                ORDER BY a.attnum
            ) AS columns
        FROM pg_class t
        JOIN pg_index ix ON t.oid = ix.indrelid
        JOIN pg_class i ON i.oid = ix.indexrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        WHERE t.relname = %s
            AND n.nspname = %s
        ORDER BY i.relname
    """

    indexes_result = db_pool.execute_query(
        indexes_query,
        (validated_table, validated_schema),
    )

    indexes = [
        {
            "name": row["index_name"],
            "columns": row["columns"],
            "unique": row["is_unique"],
            "primary": row["is_primary"],
        }
        for row in indexes_result
    ]

    # Get table metadata
    metadata_query = """
        SELECT
            c.reltuples::bigint AS row_count,
            obj_description(c.oid, 'pg_class') AS description
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relname = %s AND n.nspname = %s
    """

    metadata = db_pool.execute_query_single(
        metadata_query,
        (validated_table, validated_schema),
    )

    logger.info(
        "Table described successfully",
        schema=validated_schema,
        table=validated_table,
        column_count=len(columns),
    )

    return {
        "schema": validated_schema,
        "table": validated_table,
        "description": metadata["description"] if metadata else None,
        "columns": columns,
        "primary_key": primary_key,
        "indexes": indexes,
        "row_count": metadata["row_count"] if metadata else 0,
    }
