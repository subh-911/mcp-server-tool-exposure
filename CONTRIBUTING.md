# Contributing to PostgreSQL MCP Server

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing to the project.

## Code of Conduct

- Be respectful and inclusive
- Welcome newcomers and help them learn
- Focus on constructive feedback
- Prioritize security and quality

## Getting Started

### 1. Fork and Clone

```bash
# Fork the repository on GitHub
# Then clone your fork
git clone https://github.com/YOUR_USERNAME/postgresql-mcp-server.git
cd postgresql-mcp-server
```

### 2. Set Up Development Environment

```bash
# Install uv (recommended)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies including dev tools
uv sync

# Or with pip
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
```

### 3. Configure Development Database

```bash
# Copy example environment
cp .env.example .env.development

# Update with your local database
DATABASE_URL=postgresql://user:pass@localhost:5432/testdb
LOG_LEVEL=DEBUG
```

## Development Workflow

### 1. Create a Branch

```bash
# Create a feature branch
git checkout -b feature/my-new-feature

# Or a bugfix branch
git checkout -b fix/issue-123
```

### 2. Make Changes

Follow these guidelines:

- Write clear, self-documenting code
- Add docstrings to all functions and classes
- Follow the existing code style
- Add type hints to all function signatures
- Keep functions focused and small

### 3. Write Tests

All new features and bug fixes must include tests:

```python
# tests/test_my_feature.py
import pytest
from src.my_module import my_function

def test_my_function_basic():
    """Test basic functionality."""
    result = my_function(input_value)
    assert result == expected_value

def test_my_function_edge_case():
    """Test edge cases."""
    with pytest.raises(ValueError):
        my_function(invalid_input)
```

### 4. Run Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_validators.py

# Run tests matching pattern
pytest -k "test_query"
```

### 5. Format and Lint

```bash
# Format code with Black
black src/ tests/

# Check code style with Ruff
ruff check src/ tests/

# Type check with mypy
mypy src/
```

### 6. Commit Changes

Write clear, descriptive commit messages:

```bash
# Good commit messages
git commit -m "Add export to CSV functionality"
git commit -m "Fix SQL injection vulnerability in query validator"
git commit -m "Update README with installation instructions"

# Less helpful
git commit -m "Update code"
git commit -m "Fix bug"
```

### 7. Push and Create Pull Request

```bash
# Push to your fork
git push origin feature/my-new-feature

# Create pull request on GitHub
# Fill in the PR template with details
```

## Contribution Guidelines

### Code Style

- **Python version**: Python 3.10+
- **Formatting**: Black (line length 100)
- **Linting**: Ruff
- **Type checking**: mypy
- **Docstring style**: Google style

Example:
```python
def query_database(query: str, limit: int = 100) -> dict:
    """
    Execute a SELECT query against the database.

    Args:
        query: SQL SELECT query to execute
        limit: Maximum number of rows to return

    Returns:
        dict: Query results with rows and metadata

    Raises:
        ValidationError: If query format is invalid
        SecurityError: If dangerous SQL is detected

    Examples:
        >>> query_database("SELECT * FROM users", limit=10)
        {"rows": [...], "count": 10}
    """
    # Implementation
```

### Testing Requirements

- **Unit tests**: For all business logic
- **Integration tests**: For database operations
- **Test coverage**: Maintain >80% coverage
- **Security tests**: For all validation logic

### Security Considerations

When contributing, always consider security:

1. **Input validation**: Validate all user input
2. **SQL injection**: Use parameterized queries
3. **Error messages**: Don't leak sensitive information
4. **Logging**: Log security events appropriately
5. **Dependencies**: Check for known vulnerabilities

### Documentation

Update documentation for:

- New features: Update README.md
- Configuration changes: Update .env.example
- Security changes: Update SECURITY.md
- Breaking changes: Note in PR description

## Types of Contributions

### Bug Fixes

1. Search existing issues first
2. Create issue if one doesn't exist
3. Reference issue in PR
4. Add test reproducing the bug
5. Fix the bug
6. Verify test now passes

### New Features

1. Discuss in an issue first
2. Get approval before implementing
3. Follow architecture patterns
4. Add comprehensive tests
5. Update documentation
6. Consider backward compatibility

### Documentation

- Fix typos and improve clarity
- Add examples
- Improve setup instructions
- Add troubleshooting guides

### Tests

- Improve test coverage
- Add edge case tests
- Add integration tests
- Add performance tests

## Pull Request Process

### Before Submitting

- [ ] Tests pass: `pytest`
- [ ] Code formatted: `black src/ tests/`
- [ ] Linting passes: `ruff check src/ tests/`
- [ ] Type checking passes: `mypy src/`
- [ ] Documentation updated
- [ ] CHANGELOG updated (for significant changes)

### PR Description Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
How has this been tested?

## Checklist
- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] Code formatted and linted
- [ ] No security vulnerabilities introduced
```

### Review Process

1. **Automated checks**: CI must pass
2. **Code review**: At least one approval required
3. **Security review**: For security-related changes
4. **Testing**: Reviewer may request additional tests
5. **Documentation**: Verify docs are complete

## Project Structure

```
postgresql-mcp-server/
├── src/
│   ├── __init__.py
│   ├── __main__.py          # Entry point
│   ├── server.py            # FastMCP server
│   ├── config.py            # Configuration
│   ├── tools/               # MCP tools
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
│   ├── conftest.py
│   ├── test_validators.py
│   └── test_integration.py
├── docs/                    # Documentation
├── pyproject.toml          # Project config
└── README.md
```

## Adding a New Tool

To add a new MCP tool:

1. **Create tool file**: `src/tools/my_tool.py`

```python
from src.database.connection import get_db_pool
from src.utils.logging import get_logger
from src.utils.rate_limiter import get_rate_limiter

logger = get_logger(__name__)

def my_tool(arg1: str, arg2: int = 10) -> dict:
    """
    Tool description.

    Args:
        arg1: Description of arg1
        arg2: Description of arg2

    Returns:
        Result dictionary

    Raises:
        ValidationError: If input is invalid
    """
    # Rate limiting
    rate_limiter = get_rate_limiter()
    rate_limiter.check_rate_limit("my_tool")

    # Implementation
    logger.info("Tool called", arg1=arg1, arg2=arg2)

    # Return result
    return {"result": "success"}
```

2. **Register in server**: `src/server.py`

```python
from src.tools.my_tool import my_tool

@mcp.tool()
def my_tool_wrapper(arg1: str, arg2: int = 10) -> dict:
    """Tool description for MCP."""
    return my_tool(arg1=arg1, arg2=arg2)
```

3. **Add tests**: `tests/test_my_tool.py`

```python
import pytest
from src.tools.my_tool import my_tool

def test_my_tool_basic():
    """Test basic functionality."""
    result = my_tool("test", 10)
    assert result["result"] == "success"
```

4. **Update documentation**: Add to README.md

## Questions?

- Check existing issues and discussions
- Review documentation
- Ask in discussions tab
- Create an issue for bugs

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

Thank you for contributing to PostgreSQL MCP Server!
