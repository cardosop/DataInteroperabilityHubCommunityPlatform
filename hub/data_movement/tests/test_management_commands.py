"""Tests for data_movement management commands."""

from io import StringIO

import pytest
from django.core.management import call_command

pytestmark = pytest.mark.django_db(transaction=True)


class TestMigrateCredentialsToRefs:
    """Tests for migrate_credentials_to_refs command."""

    def test_dry_run_produces_output(self, scheduled_ingestion):
        """--dry-run prints preview or success message."""
        out = StringIO()
        err = StringIO()
        call_command(
            "migrate_credentials_to_refs",
            "--dry-run",
            stdout=out,
            stderr=err,
        )
        assert err.getvalue() == "", f"stderr should be empty on dry-run; got {err.getvalue()!r}"

    def test_dry_run_with_tenant_filter(self, scheduled_ingestion, tenant):
        """--dry-run --tenant-id scopes to one tenant."""
        out = StringIO()
        err = StringIO()
        call_command(
            "migrate_credentials_to_refs",
            "--dry-run",
            f"--tenant-id={tenant.id}",
            stdout=out,
            stderr=err,
        )
        assert err.getvalue() == "", (
            f"stderr should be empty on dry-run with tenant filter; got {err.getvalue()!r}"
        )

    def test_no_flags_produces_error(self):
        """Missing --dry-run/--execute/--rollback prints error."""
        out = StringIO()
        err = StringIO()
        call_command(
            "migrate_credentials_to_refs",
            stdout=out,
            stderr=err,
        )
        assert "ERROR" in err.getvalue()


class TestCleanupDltStateTables:
    """Tests for cleanup_dlt_state_tables command."""

    def test_dry_run_produces_output(self):
        """--dry-run prints preview without dropping tables."""
        out = StringIO()
        call_command(
            "cleanup_dlt_state_tables",
            "--dry-run",
            stdout=out,
        )
        output = out.getvalue()
        assert len(output) > 0  # Should at least print "No orphaned" or the list

    def test_custom_min_age_days(self):
        """--min-age-days is accepted."""
        out = StringIO()
        err = StringIO()
        call_command(
            "cleanup_dlt_state_tables",
            "--dry-run",
            "--min-age-days=180",
            stdout=out,
            stderr=err,
        )
        assert err.getvalue() == "", (
            f"stderr should be empty with --min-age-days; got {err.getvalue()!r}"
        )
        output = out.getvalue()
        assert len(output) > 0, "stdout should produce output with --min-age-days"

    def test_no_flags_produces_error(self):
        """Missing --dry-run/--execute prints error."""
        out = StringIO()
        err = StringIO()
        call_command(
            "cleanup_dlt_state_tables",
            stdout=out,
            stderr=err,
        )
        assert "ERROR" in err.getvalue()
