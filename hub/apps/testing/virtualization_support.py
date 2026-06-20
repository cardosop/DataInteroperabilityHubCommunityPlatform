"""
Test support helpers for virtualization integration tests.

Shared utilities used across virtualization test files to avoid duplication.
"""

from django.conf import settings


def get_test_db_source():
    """Get source config pointing to the actual test database."""
    db = settings.DATABASES["default"]
    return {
        "type": "postgresql",
        "host": db.get("HOST", "localhost"),
        "port": int(db.get("PORT", 5432)),
        "database": db.get("NAME"),
        "username": db.get("USER"),
        "password": db.get("PASSWORD"),
    }
