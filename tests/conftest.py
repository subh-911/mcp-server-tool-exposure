"""
Pytest configuration and fixtures for the PostgreSQL MCP server tests.
"""

import os
from typing import Generator

import pytest


@pytest.fixture(scope="session")
def test_env() -> Generator[None, None, None]:
    """
    Set up test environment variables.

    This fixture configures environment variables for testing
    and cleans them up after tests complete.
    """
    # Store original values
    original_values = {}
    test_vars = {
        "DATABASE_URL": "postgresql://test:test@localhost:5432/testdb",
        "LOG_LEVEL": "ERROR",  # Reduce noise in tests
        "RATE_LIMIT_REQUESTS": "1000",  # Higher limit for tests
        "MAX_QUERY_ROWS": "100",
        "ALLOWED_SCHEMAS": '["public", "test"]',
    }

    for key, value in test_vars.items():
        original_values[key] = os.environ.get(key)
        os.environ[key] = value

    yield

    # Restore original values
    for key, original_value in original_values.items():
        if original_value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = original_value


@pytest.fixture
def mock_settings(test_env: None) -> Generator[None, None, None]:
    """
    Provide settings with test configuration.

    This fixture reloads settings to pick up test environment variables.
    """
    from src.config import reload_settings

    reload_settings()
    yield
    reload_settings()


@pytest.fixture
def rate_limiter_reset() -> Generator[None, None, None]:
    """
    Reset rate limiter between tests.

    This ensures rate limiting doesn't affect test independence.
    """
    from src.utils.rate_limiter import get_rate_limiter

    limiter = get_rate_limiter()
    limiter.reset()

    yield

    limiter.reset()
