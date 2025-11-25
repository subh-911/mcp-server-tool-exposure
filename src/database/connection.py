"""
PostgreSQL connection pool management.

This module handles database connections with security measures including
forced connection closure to prevent session hijacking attacks.

SECURITY: Connections are never reused in the pool to prevent session
variable manipulation across requests.
"""

from contextlib import contextmanager
from typing import Any, Dict, Generator, List, Tuple

import psycopg2
import psycopg2.extras
import psycopg2.pool
from psycopg2.extensions import connection as PgConnection
from psycopg2.extras import RealDictCursor

from src.config import get_settings
from src.utils.errors import ConfigurationError, DatabaseError, QueryTimeoutError
from src.utils.logging import get_logger

logger = get_logger(__name__)


class DatabasePool:
    """
    PostgreSQL connection pool with security-enhanced connection management.

    This class manages a pool of database connections with the following
    security features:
    - Forced connection closure after each use (no reuse)
    - Query timeout enforcement
    - Read-only transaction mode
    - Connection health checks
    """

    def __init__(self) -> None:
        """Initialize the database connection pool."""
        self.pool: psycopg2.pool.SimpleConnectionPool | None = None
        self.settings = get_settings()
        self._initialize_pool()

    def _initialize_pool(self) -> None:
        """
        Create and initialize the connection pool.

        Raises:
            ConfigurationError: If pool creation fails
        """
        try:
            # Extract connection parameters from DSN
            dsn = str(self.settings.database_url)

            logger.info(
                "Initializing database connection pool",
                min_connections=self.settings.db_pool_min,
                max_connections=self.settings.db_pool_max,
            )

            self.pool = psycopg2.pool.SimpleConnectionPool(
                self.settings.db_pool_min,
                self.settings.db_pool_max,
                dsn,
                connect_timeout=self.settings.db_timeout,
            )

            # Test the connection
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT version()")
                    version = cursor.fetchone()
                    logger.info(
                        "Database connection successful",
                        postgres_version=version[0] if version else "unknown",
                    )

        except psycopg2.Error as e:
            logger.error("Failed to initialize database pool", error=str(e))
            raise ConfigurationError(
                "Failed to connect to database. Check DATABASE_URL configuration.",
                details={"error": str(e)},
            )

    @contextmanager
    def get_connection(self) -> Generator[PgConnection, None, None]:
        """
        Get a database connection from the pool.

        SECURITY: This context manager ensures connections are NEVER reused
        by closing them after use. This prevents session variable manipulation.

        Yields:
            Database connection

        Raises:
            DatabaseError: If unable to get a connection

        Example:
            >>> with pool.get_connection() as conn:
            ...     with conn.cursor() as cursor:
            ...         cursor.execute("SELECT 1")
        """
        if not self.pool:
            raise DatabaseError(
                "Database pool not initialized",
                recoverable=False,
            )

        conn = None
        try:
            # Get connection from pool
            conn = self.pool.getconn()

            if conn is None:
                raise DatabaseError(
                    "Unable to get database connection from pool",
                    recoverable=True,
                )

            # Set connection to read-only mode
            conn.set_session(readonly=True, autocommit=False)

            logger.debug("Database connection acquired")

            yield conn

        except psycopg2.Error as e:
            logger.error("Database connection error", error=str(e))
            raise DatabaseError(
                f"Database connection error: {str(e)}",
                details={"error": str(e)},
                recoverable=True,
            )

        finally:
            if conn is not None:
                try:
                    # SECURITY: Always close the connection instead of returning it
                    # to the pool. This prevents session hijacking attacks.
                    conn.close()
                    logger.debug("Database connection closed (forced)")

                    # Return the closed connection to pool so it creates a new one
                    self.pool.putconn(conn, close=True)

                except Exception as e:
                    logger.error("Error closing database connection", error=str(e))

    def execute_query(
        self,
        query: str,
        params: Tuple[Any, ...] | None = None,
        timeout: int | None = None,
    ) -> List[Dict[str, Any]]:
        """
        Execute a SELECT query and return results as dictionaries.

        Args:
            query: SQL query to execute (must be validated before calling)
            params: Query parameters for parameterized queries
            timeout: Query timeout in seconds (uses config default if None)

        Returns:
            List of result rows as dictionaries

        Raises:
            QueryTimeoutError: If query exceeds timeout
            DatabaseError: If query execution fails
        """
        timeout_seconds = timeout or self.settings.query_timeout

        with self.get_connection() as conn:
            try:
                # Set statement timeout for this connection
                with conn.cursor() as setup_cursor:
                    setup_cursor.execute(
                        f"SET statement_timeout = {timeout_seconds * 1000}"
                    )

                # Execute query with RealDictCursor for dictionary results
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    logger.debug(
                        "Executing query",
                        query_start=query[:100],
                        params_count=len(params) if params else 0,
                        timeout=timeout_seconds,
                    )

                    cursor.execute(query, params)
                    results = cursor.fetchall()

                    logger.info(
                        "Query executed successfully",
                        row_count=len(results),
                        query_start=query[:50],
                    )

                    # Convert RealDictRow to regular dicts
                    return [dict(row) for row in results]

            except psycopg2.extensions.QueryCanceledError:
                logger.warning(
                    "Query timeout exceeded",
                    timeout=timeout_seconds,
                    query_start=query[:100],
                )
                raise QueryTimeoutError(
                    f"Query execution exceeded {timeout_seconds} second timeout",
                    timeout=timeout_seconds,
                )

            except psycopg2.Error as e:
                logger.error(
                    "Query execution failed",
                    error=str(e),
                    query_start=query[:100],
                )
                raise DatabaseError(
                    f"Query execution failed: {str(e)}",
                    details={"error": str(e)},
                    recoverable=True,
                )

    def execute_query_single(
        self,
        query: str,
        params: Tuple[Any, ...] | None = None,
        timeout: int | None = None,
    ) -> Dict[str, Any] | None:
        """
        Execute a query and return a single result row.

        Args:
            query: SQL query to execute
            params: Query parameters
            timeout: Query timeout in seconds

        Returns:
            Single result row as dictionary, or None if no results
        """
        results = self.execute_query(query, params, timeout)
        return results[0] if results else None

    def test_connection(self) -> bool:
        """
        Test if database connection is working.

        Returns:
            True if connection is successful, False otherwise
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    cursor.fetchone()
            return True
        except Exception as e:
            logger.error("Database connection test failed", error=str(e))
            return False

    def close(self) -> None:
        """Close all connections in the pool."""
        if self.pool:
            logger.info("Closing database connection pool")
            self.pool.closeall()
            self.pool = None


# Global database pool instance
_db_pool: DatabasePool | None = None


def get_db_pool() -> DatabasePool:
    """
    Get the global database pool instance.

    Returns:
        DatabasePool instance
    """
    global _db_pool
    if _db_pool is None:
        _db_pool = DatabasePool()
    return _db_pool


def close_db_pool() -> None:
    """Close the global database pool."""
    global _db_pool
    if _db_pool is not None:
        _db_pool.close()
        _db_pool = None
