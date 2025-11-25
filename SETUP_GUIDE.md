# PostgreSQL MCP Server - Setup Guide

This guide will walk you through setting up the PostgreSQL MCP Server from scratch.

## Prerequisites

Before you begin, ensure you have:

- **Python 3.10 or higher** installed
- **PostgreSQL 12 or higher** installed and running
- **pip** or **uv** package manager
- Basic knowledge of PostgreSQL and command line

## Step 1: Install PostgreSQL (if needed)

### macOS
```bash
brew install postgresql@16
brew services start postgresql@16
```

### Ubuntu/Debian
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
```

### Windows
Download and install from [PostgreSQL Downloads](https://www.postgresql.org/download/windows/)

## Step 2: Set Up Database

### Create a Database

```bash
# Connect to PostgreSQL
psql -U postgres

# Create a database for your application
CREATE DATABASE myapp;

# Exit psql
\q
```

### Create Read-Only User (Recommended)

For security, create a dedicated read-only user:

```sql
-- Connect to your database
psql -U postgres -d myapp

-- Create read-only user
CREATE USER mcp_readonly WITH PASSWORD 'your_secure_password_here';

-- Grant connection privileges
GRANT CONNECT ON DATABASE myapp TO mcp_readonly;
GRANT USAGE ON SCHEMA public TO mcp_readonly;

-- Grant SELECT on all existing tables
GRANT SELECT ON ALL TABLES IN SCHEMA public TO mcp_readonly;

-- Grant SELECT on future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA public
GRANT SELECT ON TABLES TO mcp_readonly;

-- Verify permissions
\du mcp_readonly
```

### Load Sample Data (Optional)

```sql
-- Create a sample table
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert sample data
INSERT INTO users (name, email) VALUES
    ('Alice Smith', 'alice@example.com'),
    ('Bob Jones', 'bob@example.com'),
    ('Charlie Brown', 'charlie@example.com');

-- Verify data
SELECT * FROM users;
```

## Step 3: Install the MCP Server

### Option A: Using pip

```bash
# Clone the repository
git clone <repository-url>
cd postgresql-mcp-server

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e .

# Install development dependencies (optional)
pip install -e ".[dev]"
```

### Option B: Using uv (Recommended)

```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone the repository
git clone <repository-url>
cd postgresql-mcp-server

# Install dependencies
uv sync
```

## Step 4: Configure Environment

### Create .env File

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env with your settings
nano .env  # or use your preferred editor
```

### Update Configuration

Edit `.env` with your database credentials:

```env
# Database Configuration
DATABASE_URL=postgresql://mcp_readonly:your_secure_password_here@localhost:5432/myapp

# Server Configuration
SERVER_NAME=postgresql-mcp-server
LOG_LEVEL=INFO

# Security Settings
MAX_QUERY_ROWS=1000
QUERY_TIMEOUT=30
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW=60
ALLOWED_SCHEMAS=["public"]

# Features
ENABLE_EXPORT=true
MAX_EXPORT_ROWS=5000
```

## Step 5: Test the Server

### Run Basic Tests

```bash
# Activate virtual environment if using pip
source venv/bin/activate  # Skip if using uv

# Run tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html
```

### Test Database Connection

Create a simple test script `test_connection.py`:

```python
from src.config import get_settings
from src.database.connection import get_db_pool

# Load settings
settings = get_settings()
print(f"Connecting to: {settings.database_url}")

# Test connection
pool = get_db_pool()
if pool.test_connection():
    print("✓ Database connection successful!")
else:
    print("✗ Database connection failed!")
```

Run the test:
```bash
python test_connection.py
```

## Step 6: Run the Server

### Start the Server

```bash
# Using Python directly
python -m src

# Using uv
uv run python -m src

# You should see log output like:
# {"timestamp": "2025-11-25T...", "level": "INFO", "message": "MCP server starting up"}
```

### Test with MCP Inspector

```bash
# Install MCP Inspector globally
npm install -g @modelcontextprotocol/inspector

# Run the server with inspector
mcp-inspector python -m src

# This will open a web interface for testing
```

## Step 7: Integration with Claude Desktop

### Configure Claude Desktop

1. **Locate config file:**
   - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - Windows: `%APPDATA%\Claude\claude_desktop_config.json`

2. **Add server configuration:**

```json
{
  "mcpServers": {
    "postgresql": {
      "command": "python",
      "args": ["-m", "src"],
      "cwd": "/absolute/path/to/postgresql-mcp-server",
      "env": {
        "DATABASE_URL": "postgresql://mcp_readonly:password@localhost:5432/myapp",
        "LOG_LEVEL": "INFO"
      }
    }
  }
}
```

3. **Restart Claude Desktop**

4. **Test the connection:**
   - Open Claude Desktop
   - Look for the PostgreSQL server in available tools
   - Try: "List all tables in my database"
   - Try: "Query the users table"

## Step 8: Verify Installation

### Test All Tools

Try these commands in Claude Desktop or MCP Inspector:

1. **List Tables:**
```json
{
  "tool": "list_tables",
  "arguments": {"schema": "public"}
}
```

2. **Describe Table:**
```json
{
  "tool": "describe_table",
  "arguments": {
    "table_name": "users",
    "schema": "public"
  }
}
```

3. **Query Database:**
```json
{
  "tool": "query_database",
  "arguments": {
    "query": "SELECT * FROM users LIMIT 5",
    "limit": 5
  }
}
```

4. **Get Row Count:**
```json
{
  "tool": "get_row_count",
  "arguments": {
    "table_name": "users",
    "schema": "public"
  }
}
```

5. **Export Data:**
```json
{
  "tool": "export_data",
  "arguments": {
    "query": "SELECT * FROM users",
    "format": "json",
    "limit": 10
  }
}
```

## Troubleshooting

### Common Issues

#### 1. Database Connection Failed

**Error:** `Failed to connect to database`

**Solutions:**
- Verify PostgreSQL is running: `pg_isready`
- Check DATABASE_URL format
- Test connection: `psql -d myapp -U mcp_readonly`
- Check firewall settings

#### 2. Permission Denied

**Error:** `Access to schema 'public' is not allowed`

**Solutions:**
- Verify ALLOWED_SCHEMAS includes "public"
- Check database user permissions:
```sql
SELECT * FROM information_schema.role_table_grants
WHERE grantee = 'mcp_readonly';
```

#### 3. Module Import Errors

**Error:** `ModuleNotFoundError: No module named 'src'`

**Solutions:**
- Verify you're in the project directory
- Check virtual environment is activated
- Reinstall: `pip install -e .` or `uv sync`

#### 4. Rate Limit Exceeded

**Error:** `Rate limit exceeded`

**Solutions:**
- Increase RATE_LIMIT_REQUESTS in .env
- Reset rate limiter (restart server)
- Wait for rate limit window to pass

### Getting Help

1. Check the main [README.md](README.md) for detailed documentation
2. Review test files in `tests/` for usage examples
3. Check logs for error details (structured JSON output)
4. Open an issue on GitHub with:
   - Error message
   - Log output
   - Configuration (without sensitive data)

## Next Steps

### Production Deployment

1. **Use environment-specific configuration:**
```bash
# Create separate .env files
.env.development
.env.staging
.env.production
```

2. **Set up monitoring:**
   - Configure log aggregation
   - Set up alerting for errors
   - Monitor rate limiting stats

3. **Security hardening:**
   - Use strong passwords
   - Limit network access to database
   - Rotate credentials regularly
   - Review ALLOWED_SCHEMAS

4. **Performance tuning:**
   - Adjust connection pool settings
   - Monitor query performance
   - Add database indexes
   - Tune rate limits

### Customization

1. **Add custom tools:**
   - Create new tool files in `src/tools/`
   - Register in `src/server.py`
   - Add tests

2. **Extend validation:**
   - Modify `src/database/validators.py`
   - Add custom security rules
   - Update tests

3. **Configure logging:**
   - Adjust LOG_LEVEL
   - Add custom log handlers
   - Integrate with logging platform

## Success!

You should now have a fully functional PostgreSQL MCP Server!

Try asking Claude Desktop:
- "Show me all tables in my database"
- "Describe the structure of the users table"
- "Query the users table and show me the first 10 rows"
- "Count how many active users we have"
- "Export all users to JSON format"

Enjoy secure, read-only database access through MCP!
