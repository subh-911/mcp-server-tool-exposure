"""
Unit tests for SQL validators.

These tests ensure that the security validations work correctly and
prevent SQL injection and other security vulnerabilities.
"""

import pytest

from src.database.validators import (
    validate_export_limit,
    validate_identifier,
    validate_limit,
    validate_query_is_select,
    validate_schema_access,
)
from src.utils.errors import SecurityError, ValidationError


class TestValidateQueryIsSelect:
    """Tests for SELECT query validation."""

    def test_valid_simple_select(self) -> None:
        """Test that simple SELECT queries pass validation."""
        query = "SELECT * FROM users"
        result = validate_query_is_select(query)
        assert result == query

    def test_valid_select_with_where(self) -> None:
        """Test SELECT with WHERE clause."""
        query = "SELECT id, name FROM users WHERE active = true"
        result = validate_query_is_select(query)
        assert "SELECT" in result

    def test_valid_select_with_join(self) -> None:
        """Test SELECT with JOIN."""
        query = "SELECT u.id, o.total FROM users u JOIN orders o ON u.id = o.user_id"
        result = validate_query_is_select(query)
        assert "SELECT" in result

    def test_valid_select_lowercase(self) -> None:
        """Test that lowercase SELECT is accepted."""
        query = "select * from users"
        result = validate_query_is_select(query)
        assert result == query

    def test_empty_query(self) -> None:
        """Test that empty queries are rejected."""
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_query_is_select("")

    def test_whitespace_only_query(self) -> None:
        """Test that whitespace-only queries are rejected."""
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_query_is_select("   \n\t  ")

    def test_non_select_query_rejected(self) -> None:
        """Test that non-SELECT queries are rejected."""
        with pytest.raises(SecurityError, match="Only SELECT queries"):
            validate_query_is_select("INSERT INTO users VALUES (1, 'test')")

    def test_drop_table_rejected(self) -> None:
        """Test that DROP TABLE is rejected."""
        with pytest.raises(SecurityError, match="Dangerous keyword"):
            validate_query_is_select("DROP TABLE users")

    def test_delete_rejected(self) -> None:
        """Test that DELETE is rejected."""
        with pytest.raises(SecurityError, match="Dangerous keyword"):
            validate_query_is_select("DELETE FROM users WHERE id = 1")

    def test_update_rejected(self) -> None:
        """Test that UPDATE is rejected."""
        with pytest.raises(SecurityError, match="Dangerous keyword"):
            validate_query_is_select("UPDATE users SET name = 'hacker'")

    def test_multi_statement_rejected(self) -> None:
        """Test that multi-statement queries are rejected (SQL injection prevention)."""
        # This is CRITICAL - prevents "SELECT 1; DROP TABLE users" attacks
        with pytest.raises(SecurityError, match="Multi-statement"):
            validate_query_is_select("SELECT * FROM users; DROP TABLE users")

    def test_semicolon_in_string_allowed(self) -> None:
        """Test that semicolons in strings are currently blocked.

        Note: Current implementation blocks all semicolons for security.
        This is intentionally strict.
        """
        # Our implementation is strict and blocks all semicolons
        with pytest.raises(SecurityError, match="Multi-statement"):
            validate_query_is_select("SELECT * FROM users WHERE status = 'active;pending'")

    def test_commit_keyword_rejected(self) -> None:
        """Test that COMMIT keyword is rejected (prevents transaction manipulation)."""
        with pytest.raises(SecurityError, match="Dangerous keyword"):
            validate_query_is_select("SELECT 1; COMMIT")

    def test_rollback_keyword_rejected(self) -> None:
        """Test that ROLLBACK keyword is rejected."""
        with pytest.raises(SecurityError, match="Dangerous keyword"):
            validate_query_is_select("SELECT 1; ROLLBACK")

    def test_comment_removal(self) -> None:
        """Test that SQL comments are removed."""
        query = "SELECT * FROM users -- this is a comment"
        result = validate_query_is_select(query)
        assert "--" not in result

    def test_multi_line_comment_removal(self) -> None:
        """Test that multi-line comments are removed."""
        query = "SELECT /* comment */ * FROM users"
        result = validate_query_is_select(query)
        assert "/*" not in result
        assert "*/" not in result

    def test_comment_based_injection_prevented(self) -> None:
        """Test that comment-based SQL injection is prevented."""
        # Try to use comments to hide dangerous keywords
        query = "SELECT * FROM users WHERE id = 1 /*; DROP TABLE users;*/"
        result = validate_query_is_select(query)
        # Comments removed, but no dangerous keywords in the actual query
        assert "DROP" not in result


class TestValidateIdentifier:
    """Tests for SQL identifier validation."""

    def test_valid_simple_identifier(self) -> None:
        """Test valid simple identifiers."""
        assert validate_identifier("users") == "users"
        assert validate_identifier("my_table") == "my_table"
        assert validate_identifier("table123") == "table123"

    def test_valid_identifier_starting_with_underscore(self) -> None:
        """Test identifiers starting with underscore."""
        assert validate_identifier("_private") == "_private"

    def test_empty_identifier_rejected(self) -> None:
        """Test that empty identifiers are rejected."""
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_identifier("")

    def test_identifier_with_spaces_rejected(self) -> None:
        """Test that identifiers with spaces are rejected."""
        with pytest.raises(ValidationError, match="Invalid"):
            validate_identifier("my table")

    def test_identifier_with_special_chars_rejected(self) -> None:
        """Test that identifiers with special characters are rejected."""
        with pytest.raises(ValidationError, match="Invalid"):
            validate_identifier("users; DROP TABLE")

    def test_identifier_with_quotes_rejected(self) -> None:
        """Test that identifiers with quotes are rejected."""
        with pytest.raises(ValidationError, match="Invalid"):
            validate_identifier("users' --")

    def test_identifier_starting_with_number_rejected(self) -> None:
        """Test that identifiers starting with numbers are rejected."""
        with pytest.raises(ValidationError, match="Invalid"):
            validate_identifier("123table")

    def test_identifier_length_limit(self) -> None:
        """Test that identifiers exceeding max length are rejected."""
        long_name = "a" * 64  # PostgreSQL limit is 63
        with pytest.raises(ValidationError, match="exceeds maximum length"):
            validate_identifier(long_name)

    def test_sql_injection_attempts_rejected(self) -> None:
        """Test various SQL injection attempts in identifiers."""
        injection_attempts = [
            "Robert'; DROP TABLE users--",
            "admin'--",
            "1' OR '1'='1",
            "users; DELETE FROM",
        ]
        for attempt in injection_attempts:
            with pytest.raises(ValidationError):
                validate_identifier(attempt)


class TestValidateSchemaAccess:
    """Tests for schema access validation."""

    def test_allowed_schema_public(self, mock_settings: None) -> None:
        """Test that 'public' schema is allowed."""
        # public is in default allowed_schemas
        assert validate_schema_access("public") == "public"

    def test_disallowed_schema_rejected(self, mock_settings: None) -> None:
        """Test that non-allowed schemas are rejected."""
        with pytest.raises(SecurityError, match="not allowed"):
            validate_schema_access("information_schema")

    def test_invalid_schema_name_rejected(self, mock_settings: None) -> None:
        """Test that invalid schema names are rejected."""
        with pytest.raises(ValidationError, match="Invalid"):
            validate_schema_access("schema'; DROP TABLE users--")


class TestValidateLimit:
    """Tests for LIMIT value validation."""

    def test_valid_limits(self, mock_settings: None) -> None:
        """Test that valid limits are accepted."""
        assert validate_limit(1) == 1
        assert validate_limit(50) == 50
        assert validate_limit(100) == 100

    def test_zero_limit_rejected(self, mock_settings: None) -> None:
        """Test that zero limit is rejected."""
        with pytest.raises(ValidationError, match="at least 1"):
            validate_limit(0)

    def test_negative_limit_rejected(self, mock_settings: None) -> None:
        """Test that negative limits are rejected."""
        with pytest.raises(ValidationError, match="at least 1"):
            validate_limit(-10)

    def test_limit_exceeds_max_rejected(self, mock_settings: None) -> None:
        """Test that limits exceeding max are rejected."""
        # max_query_rows is set to 100 in test settings
        with pytest.raises(ValidationError, match="exceeds maximum"):
            validate_limit(10000)


class TestValidateExportLimit:
    """Tests for export limit validation."""

    def test_valid_export_limits(self, mock_settings: None) -> None:
        """Test that valid export limits are accepted."""
        assert validate_export_limit(100) == 100
        assert validate_export_limit(5000) == 5000

    def test_zero_export_limit_rejected(self, mock_settings: None) -> None:
        """Test that zero export limit is rejected."""
        with pytest.raises(ValidationError, match="at least 1"):
            validate_export_limit(0)

    def test_export_limit_exceeds_max_rejected(self, mock_settings: None) -> None:
        """Test that export limits exceeding max are rejected."""
        with pytest.raises(ValidationError, match="exceeds maximum"):
            validate_export_limit(100000)


class TestSecurityScenarios:
    """Integration tests for security scenarios."""

    def test_bobby_tables_attack(self) -> None:
        """Test the famous 'Bobby Tables' SQL injection attack is prevented."""
        # https://xkcd.com/327/
        table_name = "Robert'); DROP TABLE students;--"
        with pytest.raises(ValidationError):
            validate_identifier(table_name)

    def test_union_injection_in_query(self) -> None:
        """Test UNION-based SQL injection attempt."""
        # UNION attacks try to combine results from multiple queries
        query = "SELECT * FROM users WHERE id = 1 UNION SELECT * FROM passwords"
        # This should pass validation as it's still a SELECT query
        # The security layer is at the application level (what tables exist)
        result = validate_query_is_select(query)
        assert "UNION" in result.upper()

    def test_time_based_blind_injection(self) -> None:
        """Test time-based blind SQL injection attempt."""
        query = "SELECT CASE WHEN (1=1) THEN pg_sleep(10) ELSE 1 END"
        # This is still a SELECT query, but query timeout will prevent abuse
        result = validate_query_is_select(query)
        assert "SELECT" in result

    def test_stacked_query_injection(self) -> None:
        """Test stacked query injection (multiple statements)."""
        query = "SELECT * FROM users WHERE id = 1; DELETE FROM users"
        with pytest.raises(SecurityError, match="Multi-statement"):
            validate_query_is_select(query)
