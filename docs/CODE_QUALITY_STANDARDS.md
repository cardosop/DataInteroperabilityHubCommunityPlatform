# Code Quality Standards

Comprehensive guide for maintaining code quality in the Data Interoperability Hub project.

## Table of Contents

1. [Overview](#overview)
2. [Linting (Ruff)](#linting-ruff)
3. [Code Formatting (Black)](#code-formatting-black)
4. [Type Checking (MyPy)](#type-checking-mypy)
5. [Security Scanning](#security-scanning)
6. [Dependency Scanning](#dependency-scanning)
7. [Pre-commit Hooks](#pre-commit-hooks)
8. [CI/CD Integration](#cicd-integration)
9. [Quality Gates](#quality-gates)
10. [Best Practices](#best-practices)

---

## Overview

The Data Interoperability Hub project uses a comprehensive set of code quality tools to ensure high standards, maintainability, and security:

- **Ruff**: Fast Python linter and formatter
- **Black**: Uncompromising code formatter
- **MyPy**: Static type checker
- **Bandit**: Security linter for Python code
- **Safety**: Dependency vulnerability scanner
- **pip-audit**: Python dependency vulnerability scanner
- **Trivy**: Container security scanner
- **CodeQL**: Security analysis

### Quality Thresholds

- **Code Quality Score**: Minimum 80/100
- **Test Coverage**: Minimum 90%
- **Linting Errors**: Zero critical errors
- **Security Issues**: Zero high/critical severity issues
- **Type Coverage**: Gradual improvement (not enforced yet)

---

## Linting (Ruff)

### Configuration

Ruff is configured in `pyproject.toml`:

```toml
[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = [
    "E",   # pycodestyle errors
    "W",   # pycodestyle warnings
    "F",   # pyflakes
    "I",   # isort
    "B",   # flake8-bugbear
    "C4",  # flake8-comprehensions
    "UP",  # pyupgrade
    "ARG", # flake8-unused-arguments
    "SIM", # flake8-simplify
    "TCH", # flake8-type-checking
    "PIE", # flake8-pie
    "PL",  # Pylint
    "TRY", # tryceratops
    "RUF", # Ruff-specific rules
]
```

### Usage

**Check for issues:**
```bash
ruff check .
```

**Fix auto-fixable issues:**
```bash
ruff check . --fix
```

**Format code:**
```bash
ruff format .
```

**Check formatting:**
```bash
ruff format --check .
```

### Common Rules

- **E501**: Line too long (handled by Black)
- **F401**: Unused imports
- **B008**: Function calls in argument defaults
- **PLR0913**: Too many arguments (allowed in some cases)

### Ignoring Rules

```python
# Ignore specific rule for a line
result = process()  # noqa: PLR2004

# Ignore multiple rules
data = get_data()  # noqa: F401, B008

# Ignore for entire file (at top)
# ruff: noqa
```

---

## Code Formatting (Black)

### Configuration

Black is configured in `pyproject.toml`:

```toml
[tool.black]
line-length = 100
target-version = ['py312']
```

### Usage

**Format code:**
```bash
black .
```

**Check formatting:**
```bash
black --check .
```

**Show diff:**
```bash
black --diff .
```

### Black Rules

- **Line length**: 100 characters
- **String quotes**: Prefer double quotes
- **Trailing commas**: Always use when possible
- **Line breaks**: Automatic based on complexity

### Exclusions

Black automatically excludes:
- Migrations (`migrations/`)
- Virtual environments (`venv/`, `.venv/`)
- Build directories (`build/`, `dist/`)

---

## Type Checking (MyPy)

### Configuration

MyPy is configured in `pyproject.toml`:

```toml
[tool.mypy]
python_version = "3.12"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = false
disallow_incomplete_defs = false
check_untyped_defs = true
no_implicit_optional = true
strict_equality = true
show_error_codes = true
```

### Usage

**Type check code:**
```bash
mypy .
```

**Type check specific module:**
```bash
mypy hub/apps/contracts/
```

**Generate JSON report:**
```bash
mypy . --json-report .mypy-report
```

### Type Hints

**Function annotations:**
```python
def process_data(data: dict[str, Any]) -> list[str]:
    """Process data and return list of strings."""
    return [str(item) for item in data.values()]
```

**Variable annotations:**
```python
from typing import Optional

user_id: Optional[str] = None
count: int = 0
```

**Class annotations:**
```python
class User:
    def __init__(self, name: str, email: str) -> None:
        self.name: str = name
        self.email: str = email
```

### Ignoring Type Errors

```python
# Ignore specific line
result = get_data()  # type: ignore

# Ignore specific error code
value = process()  # type: ignore[assignment]

# Ignore for entire file (at top)
# mypy: ignore-errors
```

### Django Stubs

Django-specific type stubs are provided by `django-stubs`:

```python
from django.db import models

class Contract(models.Model):
    name = models.CharField(max_length=255)  # Properly typed
    status = models.CharField(max_length=50)  # Properly typed
```

---

## Security Scanning

### Bandit

**Configuration**: `.bandit` or `.bandit.yaml`

**Usage:**
```bash
# Scan code
bandit -r hub/ services/ -c .bandit

# JSON output
bandit -r hub/ services/ -f json -o bandit-report.json

# Text output
bandit -r hub/ services/ -f txt -o bandit-report.txt

# Specific severity
bandit -r hub/ services/ --severity-level high
```

**Common Issues:**
- **B101**: `assert` used (allowed in tests)
- **B601**: Shell injection in subprocess (review case-by-case)
- **B506**: Use of `yaml.load()` (use `yaml.safe_load()`)

**Fixing Issues:**
```python
# BAD: Using yaml.load()
import yaml
data = yaml.load(file_content)  # noqa: B506

# GOOD: Using yaml.safe_load()
import yaml
data = yaml.safe_load(file_content)
```

### Trivy (Container Scanning)

**Usage:**
```bash
# Scan Docker image
trivy image hub/api-service:latest

# Scan with severity filter
trivy image --severity HIGH,CRITICAL hub/api-service:latest

# JSON output
trivy image --format json --output trivy-report.json hub/api-service:latest

# Exit on vulnerabilities
trivy image --exit-code 1 --severity HIGH,CRITICAL hub/api-service:latest
```

---

## Dependency Scanning

### Safety

**Usage:**
```bash
# Check dependencies
safety check

# JSON output
safety check --json

# Full report
safety check --full-report
```

**Output:**
```
+==============================================================================+
| REPORT                                                                       |
+==============================================================================+
| Safety found 2 known security vulnerabilities.
| Vulnerability ID: 12345
| Affected package: requests
| Installed version: 2.28.0
| Vulnerability: CVE-2023-12345
| More info: https://pyup.io/vulnerabilities/CVE-2023-12345/
+==============================================================================+
```

### pip-audit

**Usage:**
```bash
# Audit dependencies
pip-audit

# JSON output
pip-audit --format json --output pip-audit-report.json

# Desc format
pip-audit --desc
```

**Output:**
```
Found 3 known vulnerabilities in 2 packages
Package: requests
  Vulnerability ID: CVE-2023-12345
  Severity: HIGH
  Description: Security vulnerability in requests
  Fix: Upgrade to requests>=2.31.0
```

### Fixing Vulnerabilities

1. **Identify vulnerable package:**
   ```bash
   pip-audit
   ```

2. **Check available versions:**
   ```bash
   pip index versions package-name
   ```

3. **Update requirements.txt:**
   ```txt
   # OLD
   requests>=2.28.0
   
   # NEW
   requests>=2.31.0
   ```

4. **Test and verify:**
   ```bash
   pip install -r requirements.txt
   pip-audit  # Verify no vulnerabilities
   ```

---

## Pre-commit Hooks

### Installation

```bash
# Install pre-commit
pip install pre-commit

# Install hooks
pre-commit install

# Install hooks for all environments
pre-commit install --hook-type pre-push --hook-type commit-msg
```

### Configuration

Pre-commit hooks are configured in `.pre-commit-config.yaml`:

- **Trailing whitespace**: Removed automatically
- **End of file**: Newline added automatically
- **YAML/JSON/TOML**: Syntax checked
- **Large files**: Prevented from committing
- **Merge conflicts**: Detected
- **Debug statements**: Detected
- **Black**: Code formatted
- **Ruff**: Linting and formatting
- **MyPy**: Type checking
- **Bandit**: Security scanning

### Usage

**Run on all files:**
```bash
pre-commit run --all-files
```

**Run specific hook:**
```bash
pre-commit run ruff --all-files
pre-commit run black --all-files
```

**Skip hooks (not recommended):**
```bash
git commit --no-verify -m "message"
```

### Bypassing Hooks

Only bypass hooks in emergencies. Always fix issues properly:

```bash
# Skip pre-commit hooks (use with caution)
SKIP=ruff,black git commit -m "message"
```

---

## CI/CD Integration

### GitHub Actions Workflows

**1. CI Workflow** (`.github/workflows/ci.yml`):
- Runs Ruff linting
- Checks Black formatting
- Runs MyPy type checking
- Runs tests with coverage

**2. Security Scan Workflow** (`.github/workflows/security-scan.yml`):
- Dependency scanning (Safety, pip-audit)
- Code security scanning (Bandit)
- Container scanning (Trivy)

**3. Code Quality Workflow** (`.github/workflows/code-quality.yml`):
- Comprehensive quality analysis
- Quality score calculation
- CodeQL security analysis
- PR comments with metrics

### Quality Gates

Quality gates are enforced in CI:

1. **Linting**: Must pass Ruff checks
2. **Formatting**: Must pass Black checks
3. **Security**: No high/critical Bandit issues
4. **Dependencies**: No known vulnerabilities
5. **Quality Score**: Minimum 80/100

### Local Testing

Test CI checks locally:

```bash
# Run all checks
ruff check .
black --check .
mypy .
bandit -r hub/ services/ -c .bandit
safety check
pip-audit

# Or use pre-commit
pre-commit run --all-files
```

---

## Quality Gates

### Quality Score Calculation

Quality score is calculated based on:

- **Ruff Errors**: -2 points each
- **Ruff Warnings**: -0.5 points each
- **MyPy Errors**: -1 point each
- **Bandit Issues**: -1 point each

**Formula:**
```
Quality Score = max(0, 100 - (ruff_errors * 2 + ruff_warnings * 0.5 + mypy_errors * 1 + bandit_issues * 1))
```

### Thresholds

- **Minimum Quality Score**: 80/100
- **Test Coverage**: 90%
- **Security Issues**: Zero high/critical
- **Dependency Vulnerabilities**: Zero high/critical

### Failing Quality Gates

If quality gates fail:

1. **Review the report**: Check CI artifacts
2. **Fix issues**: Address all errors
3. **Re-run checks**: Verify locally
4. **Re-push**: Trigger CI again

---

## Best Practices

### 1. Code Style

- **Follow PEP 8**: Use Ruff/Black to enforce
- **Type hints**: Add type hints to all functions
- **Docstrings**: Document all public functions/classes
- **Naming**: Use descriptive names, follow conventions

### 2. Security

- **Never commit secrets**: Use environment variables
- **Sanitize input**: Always validate and sanitize user input
- **Use parameterized queries**: Prevent SQL injection
- **Review security scans**: Address all high/critical issues

### 3. Dependencies

- **Pin versions**: Use `>=` for minimum versions
- **Regular updates**: Update dependencies regularly
- **Audit regularly**: Run `pip-audit` weekly
- **Review vulnerabilities**: Address security issues promptly

### 4. Testing

- **Write tests**: Test all new code
- **Maintain coverage**: Keep coverage above 90%
- **Test edge cases**: Test error scenarios
- **Integration tests**: Test service interactions

### 5. Documentation

- **Docstrings**: Document all public APIs
- **Type hints**: Use type hints for clarity
- **Comments**: Explain complex logic
- **README**: Keep README updated

### 6. Git Workflow

- **Pre-commit hooks**: Always run before committing
- **Small commits**: Make focused, atomic commits
- **Clear messages**: Write descriptive commit messages
- **Review PRs**: Review code before merging

---

## Troubleshooting

### Common Issues

**1. Ruff/Black conflicts:**
```bash
# Run Black first, then Ruff
black .
ruff check . --fix
```

**2. MyPy import errors:**
```python
# Add to pyproject.toml
[[tool.mypy.overrides]]
module = "problematic.module"
ignore_missing_imports = true
```

**3. Bandit false positives:**
```python
# Add to .bandit
skips = ["B601"]  # Shell injection false positive
```

**4. Pre-commit hooks failing:**
```bash
# Update hooks
pre-commit autoupdate

# Clear cache
pre-commit clean
```

### Getting Help

- **Ruff**: https://docs.astral.sh/ruff/
- **Black**: https://black.readthedocs.io/
- **MyPy**: https://mypy.readthedocs.io/
- **Bandit**: https://bandit.readthedocs.io/
- **Safety**: https://pyup.io/safety/
- **pip-audit**: https://pypi.org/project/pip-audit/

---

## Additional Resources

- **Python Style Guide**: PEP 8 (https://pep8.org/)
- **Type Hints**: PEP 484 (https://peps.python.org/pep-0484/)
- **Security Best Practices**: OWASP Top 10 (https://owasp.org/www-project-top-ten/)
- **Dependency Management**: pip-tools (https://github.com/jazzband/pip-tools)

---

## Summary

Maintaining code quality requires:

1. ✅ **Automated tools**: Ruff, Black, MyPy, Bandit
2. ✅ **Pre-commit hooks**: Catch issues before commit
3. ✅ **CI/CD integration**: Enforce quality gates
4. ✅ **Regular scanning**: Security and dependency audits
5. ✅ **Documentation**: Clear standards and practices
6. ✅ **Team discipline**: Follow best practices consistently

By following these standards, we ensure:
- **High code quality**: Consistent, maintainable code
- **Security**: Reduced vulnerability surface
- **Reliability**: Fewer bugs and issues
- **Developer experience**: Faster development and debugging

