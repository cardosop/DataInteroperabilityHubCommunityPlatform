"""
Shared environment-detection utilities.

Use :func:`is_test_environment` instead of ad-hoc ``os.environ`` /
``sys.argv`` / ``sys.modules`` checks so test-mode behaviour is
consistent across views, workflows, and services.
"""

from __future__ import annotations

import os


def is_test_environment() -> bool:
    """Return ``True`` when running in the test Docker Compose stack.

    ``docker-compose.test.yml`` sets ``ENVIRONMENT=test`` on every
    service.  This is the canonical signal — it does not depend on
    how the process was launched (pytest, manage.py, gunicorn, …).
    """
    return os.environ.get("ENVIRONMENT") == "test"
