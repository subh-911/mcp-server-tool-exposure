# Security Documentation

This document describes the security features, threat model, and best practices for the PostgreSQL MCP Server.

## Security Features

### 1. SQL Injection Prevention

The server implements multiple layers of defense against SQL injection:

#### Parameterized Queries
All database queries use parameterized queries (prepared statements) to prevent SQL injection:

```python
# Safe - parameterized query
cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))

# Never used - string concatenation (vulnerable)
# cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")
```

#### Query Validation
All queries undergo strict validation before execution:

- **SELECT-only enforcement**: Only SELECT queries are allowed
- **Multi-statement blocking**: Semicolons are blocked to prevent query stacking
- **Dangerous keyword detection**: DROP, DELETE, UPDATE, INSERT, ALTER, etc. are blocked
- **Comment removal**: SQL comments are stripped and analyzed separately

#### Input Sanitization
All identifiers (table names, column names, schema names) are validated:

- Must start with letter or underscore
- Can only contain alphanumeric characters and underscores
- Maximum length of 63 characters (PostgreSQL limit)
- No special characters or SQL keywords

### 2. Access Control

#### Read-Only Operations
The server enforces read-only access through multiple mechanisms:

1. **Database connection level**: Connections are set to read-only mode
2. **Query validation**: Only SELECT queries are permitted
3. **Database user**: Recommended to use a database user with only SELECT grants

#### Schema-Level Access Control
Access is restricted to explicitly allowed schemas:

```python
# Configuration
ALLOWED_SCHEMAS=["public", "app"]

# Queries to other schemas are rejected
validate_schema_access("information_schema")  # ✗ Denied
validate_schema_access("public")              # ✓ Allowed
```

#### Connection Isolation
**Critical security feature**: Database connections are NEVER reused:

```python
# After each request, connections are closed
# This prevents session variable manipulation attacks
conn.close()
pool.putconn(conn, close=True)  # Force close
```

This prevents attacks like:
```sql
-- Attacker tries to manipulate session
SELECT 1; SET ROLE admin; -- Prevented by multi-statement blocking

-- Even if they could set a variable, connection is closed after
SET app.user_id = 'admin';  -- Next request gets a fresh connection
```

### 3. Resource Protection

#### Rate Limiting
Protects against abuse and DoS attacks:

- Default: 100 requests per 60 seconds
- Per-identifier tracking (can distinguish between users)
- Configurable limits and windows
- Automatic cleanup of expired entries

#### Query Timeout
Prevents resource exhaustion from long-running queries:

- Default timeout: 30 seconds
- Configurable per-query
- Uses PostgreSQL's `statement_timeout`
- Queries exceeding timeout are automatically canceled

#### Row Limits
Prevents excessive memory usage and response sizes:

- Default query limit: 1,000 rows
- Default export limit: 5,000 rows
- Configurable maximums
- Automatic LIMIT clause injection

#### Connection Pool Management
Prevents connection exhaustion:

- Configurable min/max connections
- Connection timeout settings
- Automatic connection health checks
- Graceful degradation on pool exhaustion

### 4. Audit & Monitoring

#### Structured Logging
All operations are logged in structured JSON format:

```json
{
  "timestamp": "2025-11-25T10:30:00Z",
  "level": "INFO",
  "message": "Query executed successfully",
  "query_start": "SELECT * FROM users",
  "row_count": 42,
  "duration_ms": 15.3
}
```

#### Security Event Logging
Security-relevant events are logged with context:

- SQL injection attempts
- Rate limit violations
- Schema access denials
- Query validation failures
- Authentication errors

#### Error Information
Errors include categorization for monitoring:

- `client_error`: User's fault (invalid input)
- `server_error`: Server fault (bugs, config issues)
- `database_error`: Database issues
- `security_error`: Security violations
- `rate_limit_error`: Rate limiting

## Threat Model

### Threats Mitigated

#### ✓ SQL Injection
**Threat**: Attacker injects malicious SQL to access/modify data

**Mitigations**:
- Parameterized queries
- Query validation
- Multi-statement blocking
- Dangerous keyword detection
- Comment removal

**Residual Risk**: Low

#### ✓ Privilege Escalation
**Threat**: Attacker attempts to gain higher privileges

**Mitigations**:
- Read-only database user
- Read-only connection mode
- Schema access control
- Connection isolation

**Residual Risk**: Very Low

#### ✓ Denial of Service (DoS)
**Threat**: Attacker overwhelms server with requests or expensive queries

**Mitigations**:
- Rate limiting
- Query timeouts
- Row limits
- Connection pool limits

**Residual Risk**: Low (sophisticated DDoS may still impact)

#### ✓ Information Disclosure
**Threat**: Attacker accesses unauthorized data

**Mitigations**:
- Schema whitelist
- Table name validation
- Audit logging
- Read-only access

**Residual Risk**: Low

#### ✓ Session Hijacking
**Threat**: Attacker manipulates session variables across requests

**Mitigations**:
- Connection isolation (no reuse)
- Forced connection closure
- Read-only transactions

**Residual Risk**: Very Low

### Threats NOT Mitigated

#### ⚠ Sensitive Data Exposure
**Threat**: Authorized users can query and export sensitive data

**Mitigation Strategy**:
- Use database-level row/column security (PostgreSQL RLS)
- Encrypt sensitive columns
- Implement application-level access control
- Audit query patterns

**Residual Risk**: Medium (depends on data sensitivity)

#### ⚠ Distributed Denial of Service (DDoS)
**Threat**: Large-scale coordinated attack

**Mitigation Strategy**:
- Deploy behind rate-limiting proxy (Cloudflare, etc.)
- Use network-level DDoS protection
- Implement IP-based rate limiting

**Residual Risk**: Medium (architectural, not application-level)

#### ⚠ Database Server Compromise
**Threat**: Attacker gains access to database server itself

**Mitigation Strategy**:
- Follow PostgreSQL security hardening guide
- Keep PostgreSQL updated
- Use network isolation
- Implement authentication at database level

**Residual Risk**: Low to Medium (depends on infrastructure)

## Best Practices

### Database Configuration

#### Create Read-Only User
```sql
CREATE USER mcp_readonly WITH PASSWORD 'strong_password';
GRANT CONNECT ON DATABASE mydb TO mcp_readonly;
GRANT USAGE ON SCHEMA public TO mcp_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO mcp_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO mcp_readonly;

-- Explicitly deny dangerous privileges
REVOKE CREATE ON SCHEMA public FROM mcp_readonly;
```

#### Enable Connection Limits
```sql
-- Limit connections for the MCP user
ALTER USER mcp_readonly CONNECTION LIMIT 20;
```

#### Enable Statement Timeout
```sql
-- Set default timeout for user
ALTER USER mcp_readonly SET statement_timeout = '30s';
```

### Server Configuration

#### Use Environment Variables
Never hardcode credentials:

```bash
# Good
DATABASE_URL=postgresql://user:pass@host:port/db

# Bad - hardcoded in code
# db_url = "postgresql://user:pass@localhost/db"
```

#### Configure Rate Limiting
Adjust based on expected load:

```bash
# Higher traffic applications
RATE_LIMIT_REQUESTS=1000
RATE_LIMIT_WINDOW=60

# Lower traffic or stricter control
RATE_LIMIT_REQUESTS=50
RATE_LIMIT_WINDOW=60
```

#### Set Appropriate Limits
```bash
# Balance between usability and safety
MAX_QUERY_ROWS=1000      # Typical queries
MAX_EXPORT_ROWS=5000     # Exports can be larger
QUERY_TIMEOUT=30         # 30 seconds is usually sufficient
```

#### Enable Logging
```bash
# Use INFO in production for troubleshooting
LOG_LEVEL=INFO

# Use DEBUG only for development
# LOG_LEVEL=DEBUG
```

### Network Security

#### Use TLS for Database Connections
```bash
DATABASE_URL=postgresql://user:pass@host:port/db?sslmode=require
```

#### Restrict Database Access
In PostgreSQL `pg_hba.conf`:
```
# Allow only from application server
host    mydb    mcp_readonly    10.0.1.0/24    scram-sha-256
```

#### Run Behind Firewall
- Don't expose database directly to internet
- Use application-level firewalls
- Implement IP whitelisting if possible

### Operational Security

#### Rotate Credentials Regularly
```bash
# Change password every 90 days
ALTER USER mcp_readonly WITH PASSWORD 'new_password';

# Update .env file
DATABASE_URL=postgresql://mcp_readonly:new_password@host:port/db
```

#### Monitor Logs
Watch for:
- Repeated validation failures (potential attacks)
- Rate limit violations
- Unusual query patterns
- Error spikes

#### Regular Security Updates
```bash
# Keep dependencies updated
pip install --upgrade -r requirements.txt

# Or with uv
uv sync --upgrade
```

#### Review Access Logs
Periodically review:
- Which tables are being queried
- Which schemas are accessed
- Query patterns and frequencies
- Error rates

## Vulnerability Disclosure

If you discover a security vulnerability:

1. **DO NOT** open a public issue
2. Email security concerns to: [your-security-email]
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

We will respond within 48 hours and work with you to address the issue.

## Security Checklist

Before deploying to production:

- [ ] Created dedicated read-only database user
- [ ] Configured strong database password
- [ ] Enabled TLS for database connections
- [ ] Set appropriate `ALLOWED_SCHEMAS`
- [ ] Configured rate limiting
- [ ] Set up structured logging
- [ ] Configured log monitoring/alerting
- [ ] Restricted network access to database
- [ ] Reviewed and hardened PostgreSQL configuration
- [ ] Tested with MCP Inspector
- [ ] Ran full test suite
- [ ] Documented database schema
- [ ] Set up regular security updates
- [ ] Configured backup and recovery
- [ ] Implemented access control at network level
- [ ] Reviewed application logs for anomalies

## References

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [PostgreSQL Security Best Practices](https://www.postgresql.org/docs/current/security.html)
- [SQL Injection Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html)
- [Model Context Protocol Specification](https://modelcontextprotocol.io/)

## License

This security documentation is part of the PostgreSQL MCP Server project and is licensed under the MIT License.
