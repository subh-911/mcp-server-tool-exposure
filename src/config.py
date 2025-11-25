"""
Configuration management using Pydantic Settings.

This module handles all configuration for the PostgreSQL MCP server,
including database connection, security settings, and feature flags.
"""

from typing import List

from pydantic import Field, PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    All settings can be configured via environment variables or .env file.
    See .env.example for all available options.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database Configuration
    database_url: PostgresDsn = Field(
        ...,  # Required field
        description="PostgreSQL connection string (postgresql://user:pass@host:port/db)",
    )
    db_pool_min: int = Field(
        default=1,
        ge=1,
        description="Minimum number of connections in the pool",
    )
    db_pool_max: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of connections in the pool",
    )
    db_timeout: int = Field(
        default=30,
        ge=5,
        le=300,
        description="Database connection timeout in seconds",
    )

    # Server Configuration
    server_name: str = Field(
        default="postgresql-mcp-server",
        description="MCP server name",
    )
    server_version: str = Field(
        default="1.0.0",
        description="MCP server version",
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level is one of the standard logging levels."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"log_level must be one of {valid_levels}")
        return v_upper

    # Security Settings
    max_query_rows: int = Field(
        default=1000,
        ge=1,
        le=10000,
        description="Maximum number of rows to return from a query",
    )
    query_timeout: int = Field(
        default=30,
        ge=1,
        le=300,
        description="Maximum query execution time in seconds",
    )
    rate_limit_requests: int = Field(
        default=100,
        ge=1,
        le=10000,
        description="Maximum number of requests per time window",
    )
    rate_limit_window: int = Field(
        default=60,
        ge=1,
        le=3600,
        description="Rate limit time window in seconds",
    )
    allowed_schemas: List[str] = Field(
        default=["public"],
        description="List of database schemas accessible by the server",
    )

    @field_validator("allowed_schemas")
    @classmethod
    def validate_schemas(cls, v: List[str]) -> List[str]:
        """Validate schema names contain only safe characters."""
        import re
        for schema in v:
            if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]{0,62}$', schema):
                raise ValueError(f"Invalid schema name: {schema}")
        return v

    # Feature Flags
    enable_export: bool = Field(
        default=True,
        description="Enable data export functionality (CSV/JSON)",
    )
    enable_caching: bool = Field(
        default=True,
        description="Enable caching for schema information",
    )
    cache_ttl: int = Field(
        default=300,
        ge=0,
        le=3600,
        description="Cache time-to-live in seconds",
    )

    # Export Settings
    max_export_rows: int = Field(
        default=5000,
        ge=1,
        le=50000,
        description="Maximum rows for data export operations",
    )


# Global settings instance
_settings: Settings | None = None


def get_settings() -> Settings:
    """
    Get the global settings instance.

    This function implements lazy loading of settings and ensures
    a single instance is used throughout the application.

    Returns:
        Settings: The application settings instance
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    """
    Reload settings from environment variables.

    Useful for testing or when environment variables change.

    Returns:
        Settings: The newly loaded settings instance
    """
    global _settings
    _settings = Settings()
    return _settings
