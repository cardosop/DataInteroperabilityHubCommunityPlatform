"""
Phase 57.2 — PgBouncer Advisory Lock Guard

Static scan: ensures no production code uses pg_advisory_lock or
pg_advisory_xact_lock, which are incompatible with PgBouncer
transaction pooling mode.

Advisory locks are session-scoped in PostgreSQL. Under PgBouncer
pool_mode=transaction, the "session" is a backend connection that
gets reassigned between requests, causing advisory locks to silently
release mid-transaction or be held by the wrong client.

Alternative: use Redis-based locking via django-rq / redis.lock.
"""

import pathlib

from django.test import TestCase


class AdvisoryLockNotUsedTest(TestCase):
    """Ensure pg_advisory_lock is never used in production code."""

    def test_no_advisory_locks_in_codebase(self):
        """PgBouncer transaction mode is incompatible with pg_advisory_lock."""
        violations = []
        for path in pathlib.Path("hub").rglob("*.py"):
            if "test_" in path.name or "migration" in str(path):
                continue
            text = path.read_text()
            if "pg_advisory_lock" in text or "pg_advisory_xact_lock" in text:
                # Allow the documentation comment in settings.py
                lines = text.split("\n")
                for i, line in enumerate(lines, 1):
                    stripped = line.strip()
                    if ("pg_advisory_lock" in stripped or "pg_advisory_xact_lock" in stripped):
                        # Skip comment lines (documentation)
                        if stripped.startswith("#"):
                            continue
                        violations.append(f"{path}:{i}")
        assert not violations, (
            f"pg_advisory_lock used in: {violations}. "
            "Use Redis locks instead (django-rq is available). "
            "See hub/settings.py PgBouncer documentation."
        )

    def test_pgbouncer_documentation_exists_in_settings(self):
        """hub/settings.py must document PgBouncer constraints."""
        settings_path = pathlib.Path("hub/settings.py")
        text = settings_path.read_text()
        assert "pg_advisory_lock" in text, (
            "hub/settings.py must contain PgBouncer constraint documentation "
            "mentioning pg_advisory_lock"
        )
        assert "LISTEN/NOTIFY" in text, (
            "hub/settings.py must document LISTEN/NOTIFY incompatibility"
        )

    def test_channels_uses_redis_not_postgres(self):
        """CHANNEL_LAYERS must use Redis, not PostgreSQL backend."""
        from django.conf import settings
        backend = settings.CHANNEL_LAYERS.get("default", {}).get("BACKEND", "")
        assert "postgres" not in backend.lower(), (
            f"CHANNEL_LAYERS backend is '{backend}' — must use Redis, not PostgreSQL "
            "(incompatible with PgBouncer transaction pooling)"
        )
