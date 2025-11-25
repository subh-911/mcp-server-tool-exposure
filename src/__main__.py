"""
Main entry point for the PostgreSQL MCP server.

This module provides the CLI entry point for running the MCP server.
"""

import sys

from src.server import mcp
from src.utils.logging import get_logger

logger = get_logger(__name__)


def main() -> None:
    """
    Main entry point for the PostgreSQL MCP server.

    This function starts the FastMCP server using stdio transport.
    """
    try:
        logger.info("Starting PostgreSQL MCP server")

        # Run the FastMCP server
        # FastMCP handles stdio transport automatically
        mcp.run()

    except KeyboardInterrupt:
        logger.info("Server stopped by user")
        sys.exit(0)

    except Exception as e:
        logger.error("Server error", error=str(e), exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
