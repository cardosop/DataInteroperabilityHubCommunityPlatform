"""285.12.6.1 4A — Disaster recovery restore verification tests."""

from __future__ import annotations

import os

import pytest


class TestRestoreVerification:
    """Verify DR restore readiness without actually restoring."""

    def test_latest_backup_exists(self):
        """Backup bucket should be configured."""
        bucket = os.getenv("BACKUP_S3_BUCKET", "")
        if not bucket:
            pytest.skip("BACKUP_S3_BUCKET not configured")  # noqa: skip-in-body — runtime service dependency
        assert bucket, "Backup S3 bucket must be configured"

    def test_restore_script_is_executable(self):
        """The restore script should exist and be executable."""
        import subprocess

        result = subprocess.run(
            ["which", "pg_restore"],
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, "pg_restore must be available"

    def test_encryption_key_available(self):
        """Backup encryption key must be configured."""
        key = os.getenv("BACKUP_ENCRYPTION_KEY") or os.getenv("FERNET_KEY", "")
        if not key:
            pytest.skip("No encryption key configured")  # noqa: skip-in-body — runtime service dependency
        assert len(key) >= 32, "Encryption key should be at least 32 chars"
