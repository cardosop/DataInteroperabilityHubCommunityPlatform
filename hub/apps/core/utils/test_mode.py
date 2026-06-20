"""
Utility to detect if Django is running in test mode.

This helps optimize app initialization by deferring non-critical operations
during test execution.
"""

import os
import sys


def is_test_mode() -> bool:
    """
    Detect if Django is running in test mode.

    Checks multiple indicators:
    - pytest is in sys.modules
    - 'test' in sys.argv (Django test runner)
    - 'pytest' in sys.argv (pytest runner)
    - PYTEST_CURRENT_TEST environment variable is set
    - TESTING environment variable is set
    - Django's TESTING setting is True

    Returns:
        True if running in test mode, False otherwise
    """
    # Check if pytest is loaded
    if "pytest" in sys.modules:
        return True

    # Check if unittest is loaded (Django test runner uses unittest)
    if "unittest" in sys.modules:
        # Check if we're actually running tests (not just importing unittest)
        if any("test" in arg.lower() or "pytest" in arg.lower() for arg in sys.argv):
            return True

    # Check command line arguments
    if any(arg in sys.argv for arg in ["test", "pytest"]):
        return True

    # Check pytest environment variable (set by pytest)
    if os.getenv("PYTEST_CURRENT_TEST"):
        return True

    # Check environment variable
    if os.getenv("TESTING", "").lower() in ("1", "true", "yes"):
        return True

    # Check Django's TESTING setting if available
    try:
        from django.conf import settings

        if getattr(settings, "TESTING", False):
            return True
    except (ImportError, RuntimeError):
        # Django not configured yet or settings not loaded
        pass

    return False


def should_skip_initialization() -> bool:
    """
    Determine if app initialization should be skipped.

    Skips initialization during:
    - Test mode
    - Migration commands
    - Management commands that don't need full initialization

    Returns:
        True if initialization should be skipped, False otherwise
    """
    # Skip during migrations
    if any(
        cmd in sys.argv for cmd in ["migrate", "makemigrations", "sqlmigrate", "showmigrations"]
    ):
        return True

    # Skip during test mode
    if is_test_mode():
        return True

    # Skip during collectstatic
    if "collectstatic" in sys.argv:
        return True

    return False
