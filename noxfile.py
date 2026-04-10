"""
Phase 216.8.1 — Compatibility matrix.

Runs SDK tests on Python 3.9/3.10/3.11/3.12 and CLI tests on the
current platform. Invoke with:

    nox -s sdk_compat       # SDK across Python versions
    nox -s cli_compat       # CLI on current platform
    nox                     # all sessions

Requires nox: pip install nox
"""
import nox

# Python versions to test SDK against
SDK_PYTHON_VERSIONS = ["3.9", "3.10", "3.11", "3.12"]

# CLI only runs on the current interpreter (platform compat is tested
# via the GitHub Actions matrix in ci.yml, not via nox)
CLI_PYTHON_VERSIONS = ["3.12"]


@nox.session(python=SDK_PYTHON_VERSIONS)
def sdk_compat(session):
    """Run SDK tests across Python 3.9–3.12."""
    session.install("-e", "sdk/python/")
    session.install("pytest", "pytest-timeout", "requests", "filelock")
    session.run(
        "python", "-m", "pytest",
        "sdk/python/tests/",
        "-m", "mvp",
        "--strict-markers",
        "-v", "--tb=short",
        "--timeout=60",
        "-x",  # stop on first failure for compat matrix (fast feedback)
        env={"MVP_MODE": "true"},
    )


@nox.session(python=CLI_PYTHON_VERSIONS)
def cli_compat(session):
    """Run CLI tests on the current platform."""
    session.install("-e", "cli/")
    session.install("pytest", "pytest-timeout", "requests", "filelock")
    session.run(
        "python", "-m", "pytest",
        "cli/tests/",
        "-m", "mvp",
        "--strict-markers",
        "-v", "--tb=short",
        "--timeout=60",
        "-x",
        env={"MVP_MODE": "true"},
    )
