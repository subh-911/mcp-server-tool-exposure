"""
Integration tests for the PostgreSQL MCP server.

These tests verify that tools work correctly with a real database.
Note: These tests require a PostgreSQL database to be running.
Use testcontainers for isolated testing or configure a test database.
"""

import pytest

# Note: These tests are placeholders. To run them properly, you need:
# 1. Install testcontainers: pip install testcontainers
# 2. Have Docker running
# 3. Uncomment the implementation below

pytestmark = pytest.mark.integration


class TestDatabaseIntegration:
    """Integration tests with a real PostgreSQL database."""

    @pytest.mark.skip(reason="Requires Docker and testcontainers to be set up")
    def test_connection_pool(self) -> None:
        """Test database connection pool initialization."""
        # Example implementation with testcontainers:
        # from testcontainers.postgres import PostgresContainer
        # with PostgresContainer("postgres:16") as postgres:
        #     os.environ["DATABASE_URL"] = postgres.get_connection_url()
        #     from src.database.connection import get_db_pool
        #     pool = get_db_pool()
        #     assert pool.test_connection()
        pass

    @pytest.mark.skip(reason="Requires test database")
    def test_query_execution(self) -> None:
        """Test actual query execution against database."""
        # from src.tools.query import query_database
        # result = query_database("SELECT 1 as test_value", limit=10)
        # assert result["count"] == 1
        # assert result["rows"][0]["test_value"] == 1
        pass

    @pytest.mark.skip(reason="Requires test database")
    def test_list_tables_integration(self) -> None:
        """Test listing tables from real database."""
        # from src.tools.schema import list_tables
        # result = list_tables("public")
        # assert "tables" in result
        # assert isinstance(result["tables"], list)
        pass


class TestRateLimiting:
    """Tests for rate limiting functionality."""

    def test_rate_limiter_allows_requests_within_limit(
        self,
        rate_limiter_reset: None,
    ) -> None:
        """Test that requests within limit are allowed."""
        from src.utils.rate_limiter import get_rate_limiter

        limiter = get_rate_limiter()

        # Should allow first request
        limiter.check_rate_limit("test_user")

        # Should allow subsequent requests within limit
        for _ in range(10):
            limiter.check_rate_limit("test_user")

    def test_rate_limiter_blocks_requests_exceeding_limit(
        self,
        rate_limiter_reset: None,
    ) -> None:
        """Test that requests exceeding limit are blocked."""
        from src.utils.errors import RateLimitError
        from src.utils.rate_limiter import RateLimiter

        # Create limiter with low limit for testing
        limiter = RateLimiter(max_requests=5, window_seconds=60)

        # Use up the limit
        for _ in range(5):
            limiter.check_rate_limit("test_user")

        # Next request should be blocked
        with pytest.raises(RateLimitError):
            limiter.check_rate_limit("test_user")

    def test_rate_limiter_per_identifier(
        self,
        rate_limiter_reset: None,
    ) -> None:
        """Test that rate limiting is per identifier."""
        from src.utils.rate_limiter import RateLimiter

        limiter = RateLimiter(max_requests=5, window_seconds=60)

        # User 1 uses their limit
        for _ in range(5):
            limiter.check_rate_limit("user1")

        # User 2 should still have their full limit
        limiter.check_rate_limit("user2")
        assert limiter.get_remaining_requests("user2") == 4


class TestErrorHandling:
    """Tests for error handling and logging."""

    def test_validation_error_structure(self) -> None:
        """Test that validation errors have proper structure."""
        from src.utils.errors import ValidationError

        error = ValidationError(
            "Test error message",
            details={"field": "value"},
        )

        assert error.message == "Test error message"
        assert error.details["field"] == "value"
        assert not error.recoverable

        error_dict = error.to_dict()
        assert "error" in error_dict
        assert "category" in error_dict
        assert "details" in error_dict

    def test_security_error_structure(self) -> None:
        """Test that security errors have proper structure."""
        from src.utils.errors import SecurityError

        error = SecurityError(
            "Dangerous operation detected",
            details={"operation": "DROP TABLE"},
        )

        assert error.message == "Dangerous operation detected"
        assert error.category.value == "security_error"
        assert not error.recoverable


class TestExportFunctionality:
    """Tests for data export tools."""

    def test_export_json_format(self) -> None:
        """Test JSON export formatting."""
        from src.tools.export import _export_json

        test_data = [
            {"id": 1, "name": "Alice", "age": 30},
            {"id": 2, "name": "Bob", "age": 25},
        ]

        result = _export_json(test_data)

        # Should be valid JSON
        import json
        parsed = json.loads(result)
        assert len(parsed) == 2
        assert parsed[0]["name"] == "Alice"

    def test_export_csv_format(self) -> None:
        """Test CSV export formatting."""
        from src.tools.export import _export_csv

        test_data = [
            {"id": 1, "name": "Alice", "age": 30},
            {"id": 2, "name": "Bob", "age": 25},
        ]

        result = _export_csv(test_data)

        # Should have headers
        lines = result.strip().split('\n')
        assert "id" in lines[0]
        assert "name" in lines[0]
        assert "age" in lines[0]

        # Should have data rows
        assert "Alice" in result
        assert "Bob" in result

    def test_export_csv_empty_results(self) -> None:
        """Test CSV export with empty results."""
        from src.tools.export import _export_csv

        result = _export_csv([])
        assert result == ""
