"""
Unit tests for tenant signals (Phase 93).
"""
import re
import uuid

from django.db import connection, transaction
from django.test import TestCase

from hub.apps.tenants.models import KYCStatus, Tenant


class TenantSignalsTest(TestCase):
    """Test tenant signal behaviour.

    NOTE: The ``create_default_roles`` signal is intentionally skipped in
    test mode (pytest/unittest detection) to prevent 6-8 s blocking per
    tenant creation.  Tests that need roles should create them explicitly
    via ``Role.objects.get_or_create()``.

    This test verifies the SIGNAL SKIP BEHAVIOUR, not role creation itself.
    """

    def test_signal_skips_role_creation_in_test_mode(self):
        """In test mode, the signal should NOT create roles (by design)."""
        from hub.apps.users.models import Role

        uid = uuid.uuid4().hex[:8]
        tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}"
        )

        roles = Role.objects.filter(tenant=tenant)
        self.assertEqual(
            roles.count(), 0,
            "Signal should skip role creation in test mode",
        )

    def test_thread_local_kyc_does_not_leak(self):
        """KYC status tracking uses threading.local, not module-level dict."""
        from hub.apps.tenants.signals import _thread_local

        uid = uuid.uuid4().hex[:8]
        tenant = Tenant.objects.create(
            name=f"KYC Test {uid}", slug=f"kyc-test-{uid}"
        )

        # After save, there should be no lingering state in thread-local
        kyc_store = getattr(_thread_local, "kyc_before_save", {})
        self.assertNotIn(
            tenant.pk, kyc_store,
            "KYC state should be cleaned up after post_save",
        )

    def test_kyc_pre_save_short_timeout_scoped_to_savepoint(self):
        """KYC pre_save uses SET LOCAL 2s; must not poison the outer transaction.

        Without a nested transaction.atomic(), PostgreSQL keeps statement_timeout
        at 2s for the rest of the outer transaction, breaking long statements
        (e.g. Contract.objects.create in product_creation workflows).
        """
        uid = uuid.uuid4().hex[:8]
        tenant = Tenant.objects.create(
            name=f"Timeout scope {uid}",
            slug=f"timeout-scope-{uid}",
            kyc_status=KYCStatus.UNVERIFIED,
        )

        def _timeout_to_seconds(raw):
            s = str(raw).strip().lower()
            m = re.match(r"^(\d+(?:\.\d+)?)\s*ms$", s)
            if m:
                return float(m.group(1)) / 1000.0
            m = re.match(r"^(\d+(?:\.\d+)?)\s*min$", s)
            if m:
                return float(m.group(1)) * 60.0
            m = re.match(r"^(\d+(?:\.\d+)?)\s*s$", s)
            if m:
                return float(m.group(1))
            return float(s) / 1000.0

        with transaction.atomic():
            tenant.kyc_status = KYCStatus.PENDING_REVIEW
            tenant.save(update_fields=["kyc_status", "updated_at"])
            with connection.cursor() as cur:
                cur.execute("SHOW statement_timeout")
                shown = cur.fetchone()[0]
            secs = _timeout_to_seconds(shown)
            self.assertGreater(
                secs,
                30.0,
                "Outer txn must keep normal statement_timeout after KYC pre_save; "
                f"got {shown!r} (~{secs}s)",
            )
