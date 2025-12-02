# Code Quality Guide

This document describes the code quality tools and standards used in the Interoperable Data Hub MVP project.

## Tools

### Ruff (Linting)

**Ruff** is a fast Python linter written in Rust. It replaces multiple tools like flake8, isort, and more.

**Configuration**: `pyproject.toml` and `.ruff.toml`

**Usage**:
```bash
# Check for issues
ruff check .

# Auto-fix issues
ruff check --fix .

# Check specific directory
ruff check hub/apps/
```

**Rules Enabled**:
- `E`, `W`: pycodestyle errors and warnings
- `F`: pyflakes
- `I`: isort (import sorting)
- `B`: flake8-bugbear
- `C4`: flake8-comprehensions
- `UP`: pyupgrade
- `ARG`: flake8-unused-arguments
- `SIM`: flake8-simplify
- `TCH`: flake8-type-checking
- `PIE`: flake8-pie
- `PL`: Pylint
- `TRY`: tryceratops
- `RUF`: Ruff-specific rules

### Black (Code Formatting)

**Black** is the uncompromising Python code formatter.

**Configuration**: `pyproject.toml`

**Usage**:
```bash
# Format all files
black .

# Check formatting without changing files
black --check .

# Format specific directory
black hub/apps/
```

**Settings**:
- Line length: 100 characters
- Target Python version: 3.11+

### Mypy (Type Checking)

**Mypy** is a static type checker for Python.

**Configuration**: `pyproject.toml` and `mypy.ini`

**Usage**:
```bash
# Type check all files
mypy hub/

# Type check specific file
mypy hub/apps/api/views.py

# Show error codes
mypy hub/ --show-error-codes
```

**Settings**:
- Python version: 3.11
- Warn on return any: true
- Check untyped defs: true
- Ignore missing imports for third-party libraries

## Makefile Commands

### Lint
```bash
make lint
```
Runs both ruff and mypy to check code quality.

### Format
```bash
make format
```
Formats code with black and fixes issues with ruff.

## Pre-commit Hooks

Pre-commit hooks automatically run code quality checks before commits.

**Installation**:
```bash
pip install pre-commit
pre-commit install
```

**Manual Run**:
```bash
pre-commit run --all-files
```

**Hooks**:
- Trailing whitespace removal
- End of file fixer
- YAML/JSON/TOML validation
- Black formatting
- Ruff linting and formatting
- Mypy type checking

## CI/CD Integration

Code quality checks should be run in CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
- name: Lint with ruff
  run: ruff check .

- name: Format check with black
  run: black --check .

- name: Type check with mypy
  run: mypy hub/
```

## Configuration Files

- `pyproject.toml`: Main configuration for black, ruff, and mypy
- `.ruff.toml`: Legacy ruff configuration (for backwards compatibility)
- `mypy.ini`: Legacy mypy configuration (for backwards compatibility)
- `.pre-commit-config.yaml`: Pre-commit hooks configuration

## Ignored Files/Directories

The following are excluded from linting/type checking:
- `migrations/`: Django migration files
- `venv/`, `.venv/`: Virtual environments
- `__pycache__/`: Python cache
- `.pytest_cache/`: Pytest cache
- `.mypy_cache/`: Mypy cache
- `.ruff_cache/`: Ruff cache
- `node_modules/`: Node.js dependencies

## Best Practices

1. **Run linting before committing**: Use `make lint` or pre-commit hooks
2. **Format code regularly**: Use `make format` to keep code consistent
3. **Fix type errors**: Address mypy errors to improve code quality
4. **Use type hints**: Add type annotations to function signatures
5. **Follow import order**: Let isort/ruff handle import sorting

## Troubleshooting

### Ruff errors
```bash
# See all errors
ruff check .

# Auto-fix what can be fixed
ruff check --fix .
```

### Mypy errors
```bash
# See all type errors
mypy hub/

# Ignore specific errors (add to mypy.ini)
# [mypy-module.name]
# ignore_errors = true
```

### Black formatting conflicts
```bash
# Format with black
black .

# Then run ruff to fix any remaining issues
ruff check --fix .
```

## Additional Resources

- [Ruff Documentation](https://docs.astral.sh/ruff/)
- [Black Documentation](https://black.readthedocs.io/)
- [Mypy Documentation](https://mypy.readthedocs.io/)
- [Pre-commit Documentation](https://pre-commit.com/)

