# PostgreSQL MCP Server

A production-quality Model Context Protocol (MCP) server for secure PostgreSQL database access. Built with FastMCP and Python, this server provides read-only database operations with comprehensive security validations.

## Features

### Core Capabilities
- **Read-only database access** via SELECT queries
- **Schema introspection** (list tables, describe table structures)
- **Row counting** with optional filtering
- **Data export** to CSV and JSON formats
- **5+ MCP tools** for comprehensive database operations

### Security Features
- SQL injection prevention with parameterized queries
- Multi-statement query blocking
- Dangerous keyword detection (DROP, DELETE, UPDATE, etc.)
- Read-only database user enforcement
- Rate limiting (100 requests/minute default)
- Query timeout protection (30s default)
- Row limit enforcement
- Schema access control
- Comprehensive audit logging

### Production Ready
- Structured JSON logging for observability
- Connection pool with security-enhanced management
- Comprehensive error handling
- Type-safe configuration with Pydantic
- Extensive test coverage (>80%)
- FastMCP framework for MCP protocol compliance

## Installation

### Requirements
- Python 3.10 or higher
- PostgreSQL 12 or higher
- pip or uv package manager

### Quick Start

1. **Clone the repository**
```bash
git clone <repository-url>
cd postgresql-mcp-server
```

2. **Install dependencies**

Using pip:
```bash
pip install -e .
```

Using uv (recommended):
```bash
uv sync
```

3. **Configure environment**
```bash
cp .env.example .env
# Edit .env with your database credentials
```

4. **Set up database user (recommended)**

Create a read-only PostgreSQL user:
```sql
-- Create read-only user
CREATE USER mcp_readonly WITH PASSWORD 'secure_password';

-- Grant connection and schema usage
GRANT CONNECT ON DATABASE your_database TO mcp_readonly;
GRANT USAGE ON SCHEMA public TO mcp_readonly;

-- Grant SELECT on all tables
GRANT SELECT ON ALL TABLES IN SCHEMA public TO mcp_readonly;

-- Grant SELECT on future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA public
GRANT SELECT ON TABLES TO mcp_readonly;
```

5. **Run the server**
```bash
python -m src
# or
uv run python -m src
```

## Configuration

All configuration is done via environment variables or a `.env` file. See `.env.example` for all available options.

### Key Configuration Options

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | (required) | PostgreSQL connection string |
| `MAX_QUERY_ROWS` | 1000 | Maximum rows per query |
| `QUERY_TIMEOUT` | 30 | Query timeout in seconds |
| `RATE_LIMIT_REQUESTS` | 100 | Max requests per time window |
| `RATE_LIMIT_WINDOW` | 60 | Rate limit window in seconds |
| `ALLOWED_SCHEMAS` | ["public"] | Accessible database schemas |
| `LOG_LEVEL` | INFO | Logging level |

## Tools

The server exposes 5 MCP tools for database operations:

### 1. query_database

Execute SELECT queries with security validation.

```json
{
  "name": "query_database",
  "arguments": {
    "query": "SELECT * FROM users WHERE active = true",
    "limit": 100,
    "timeout": 30
  }
}
```

**Returns:**
```json
{
  "rows": [...],
  "count": 42,
  "columns": ["id", "name", "email", "active"],
  "duration_ms": 15.3,
  "limited": false
}
```

### 2. list_tables

List all tables in a schema.

```json
{
  "name": "list_tables",
  "arguments": {
    "schema": "public"
  }
}
```

**Returns:**
```json
{
  "schema": "public",
  "tables": [
    {
      "name": "users",
      "row_count": 1523,
      "size": "128 kB",
      "description": "Application users"
    }
  ],
  "table_count": 1
}
```

### 3. describe_table

Get detailed schema information for a table.

```json
{
  "name": "describe_table",
  "arguments": {
    "table_name": "users",
    "schema": "public"
  }
}
```

**Returns:**
```json
{
  "schema": "public",
  "table": "users",
  "description": "Application users",
  "columns": [
    {
      "name": "id",
      "type": "integer",
      "nullable": false,
      "default": "nextval('users_id_seq'::regclass)"
    }
  ],
  "primary_key": ["id"],
  "indexes": [...]
}
```

### 4. get_row_count

Count rows in a table with optional filtering.

```json
{
  "name": "get_row_count",
  "arguments": {
    "table_name": "orders",
    "schema": "public",
    "where_clause": "status = 'completed' AND created_at > '2024-01-01'"
  }
}
```

**Returns:**
```json
{
  "schema": "public",
  "table": "orders",
  "count": 842,
  "filtered": true
}
```

### 5. export_data

Export query results to CSV or JSON.

```json
{
  "name": "export_data",
  "arguments": {
    "query": "SELECT id, name, email FROM users LIMIT 100",
    "format": "csv",
    "limit": 100
  }
}
```

**Returns:**
```json
{
  "format": "csv",
  "data": "id,name,email\n1,Alice,alice@example.com\n...",
  "row_count": 100,
  "size_bytes": 2048
}
```

## Resources

The server also exposes MCP resources for contextual information:

### postgres://status

Server and database status information.

### postgres://schemas

Available database schemas.

## Security

This server implements multiple layers of security:

### SQL Injection Prevention
- All queries validated before execution
- Parameterized queries used throughout
- Multi-statement queries blocked (no semicolons)
- Dangerous keywords detected (DROP, DELETE, UPDATE, etc.)
- SQL comments removed and analyzed

### Access Control
- Read-only database operations only
- Schema-level access control
- Table and column name validation
- Connection isolation (no connection reuse)

### Resource Protection
- Rate limiting per identifier
- Query timeout enforcement
- Row limit enforcement
- Connection pool management
- Memory usage controls

### Audit & Monitoring
- Structured JSON logging
- All operations logged with context
- Error tracking with categorization
- Security event logging

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run only unit tests
pytest tests/test_validators.py

# Run only integration tests (requires database)
pytest tests/test_integration.py -m integration
```

### Code Quality

```bash
# Format code
black src/ tests/

# Lint
ruff check src/ tests/

# Type check
mypy src/
```

### Project Structure

```
postgresql-mcp-server/
├── src/
│   ├── __init__.py
│   ├── __main__.py          # Entry point
│   ├── server.py            # FastMCP server definition
│   ├── config.py            # Configuration management
│   ├── tools/               # MCP tools implementation
│   │   ├── query.py
│   │   ├── schema.py
│   │   ├── stats.py
│   │   └── export.py
│   ├── database/            # Database layer
│   │   ├── connection.py
│   │   └── validators.py
│   └── utils/               # Utilities
│       ├── errors.py
│       ├── logging.py
│       └── rate_limiter.py
├── tests/                   # Test suite
├── pyproject.toml          # Project configuration
├── .env.example            # Example configuration
└── README.md
```

## Integration with Claude Desktop

To use this server with Claude Desktop, add to your configuration:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "postgresql": {
      "command": "python",
      "args": ["-m", "src"],
      "cwd": "/path/to/postgresql-mcp-server",
      "env": {
        "DATABASE_URL": "postgresql://user:pass@localhost:5432/db"
      }
    }
  }
}
```

## Testing with MCP Inspector

```bash
# Install MCP Inspector
npm install -g @modelcontextprotocol/inspector

# Run the server with inspector
mcp-inspector python -m src
```

## Troubleshooting

### Connection Issues

**Problem:** Cannot connect to database

**Solution:**
- Verify `DATABASE_URL` is correct
- Check PostgreSQL is running
- Verify network connectivity
- Check user permissions

### Performance Issues

**Problem:** Queries are slow

**Solution:**
- Check query timeout settings
- Review database indexes
- Monitor connection pool usage
- Check rate limiting settings

### Permission Errors

**Problem:** "Access denied" errors

**Solution:**
- Verify database user has SELECT permissions
- Check `ALLOWED_SCHEMAS` configuration
- Review table-level permissions

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Run the test suite
6. Submit a pull request

## License

MIT License - see LICENSE file for details

## Acknowledgments

- Built with [FastMCP](https://github.com/modelcontextprotocol/python-sdk)
- Model Context Protocol by [Anthropic](https://www.anthropic.com)
- Security best practices from PostgreSQL and OWASP guidelines

## Support

For issues, questions, or contributions:
- Open an issue on GitHub
- Review existing documentation
- Check the test suite for examples

---

**Version:** 1.0.0
**Author:** Your Name
**Last Updated:** 2025-11-25
