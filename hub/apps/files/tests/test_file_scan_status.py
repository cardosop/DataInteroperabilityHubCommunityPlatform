"""
Phase 260.3.D — ``GET /api/v1/files/{id}/scan-status/`` contract tests.

Lightweight poll endpoint, per-user 30/min and per-tenant 300/min throttles
(pass-2 S2-3). Real ``APIClient``, ORM, and Django cache — no mocks on the
HTTP throttling path.
"""

from __future__ import annotations

import uuid
from typing import Any, cast

import pytest
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.audit import event_types as audit_event_types
from hub.apps.audit.models import AuditEvent
from hub.apps.files.models import File, FileScanStatus, FileStatus
from hub.apps.files.tests.test_base import FilesAPITestBase
from hub.apps.files.throttles import (
    FileScanStatusTenantThrottle,
    FileScanStatusUserThrottle,
)
from hub.apps.files.views import FileViewSet
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


@override_settings(
    EVENT_BUS_ASYNC_PERSISTENCE=False,
    EVENT_BUS_WRITE_BEHIND_ENABLED=False,
    RATE_LIMIT_ENABLED=False,
)
class FileScanStatusEndpointTest(FilesAPITestBase):
    """Happy path, tenant isolation, and terminal transition (polling contract)."""

    @pytest.mark.integration
    def test_scan_status_returns_scan_fields(self):
        self.file.scanned_at = timezone.now()
        self.file.save(update_fields=["scanned_at"])
        resp = self.client.get(f"/api/v1/files/{self.file.id}/scan-status/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["scan_status"], FileScanStatus.CLEAN)
        self.assertIsNotNone(resp.data["scanned_at"])

    @pytest.mark.integration
    def test_scan_status_not_found(self):
        missing = uuid.uuid4()
        resp = self.client.get(f"/api/v1/files/{missing}/scan-status/")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    @pytest.mark.integration
    def test_scan_status_tenant_isolation(self):
        other = Tenant.objects.create(
            name="other-scan",
            slug=f"other-scan-{uuid.uuid4().hex[:8]}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        other_file = File.objects.create(
            id=uuid.uuid4(),
            tenant=other,
            name="x.csv",
            content_type="text/csv",
            size=1,
            status=FileStatus.ACTIVE,
            scan_status=FileScanStatus.CLEAN,
            storage_path=f"{other.id}/x.csv",
        )
        resp = self.client.get(f"/api/v1/files/{other_file.id}/scan-status/")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    @pytest.mark.integration
    def test_scan_status_pending_then_terminal_matches_polling_stop_contract(self):
        """Two polls: PENDING_SCAN then CLEAN — client would stop after the second."""
        self.file.scan_status = FileScanStatus.PENDING_SCAN
        self.file.scanned_at = None
        self.file.save(update_fields=["scan_status", "scanned_at"])

        first = self.client.get(f"/api/v1/files/{self.file.id}/scan-status/")
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(first.data["scan_status"], FileScanStatus.PENDING_SCAN)
        self.assertIsNone(first.data["scanned_at"])

        now = timezone.now()
        self.file.scan_status = FileScanStatus.CLEAN
        self.file.scanned_at = now
        self.file.save(update_fields=["scan_status", "scanned_at"])

        second = self.client.get(f"/api/v1/files/{self.file.id}/scan-status/")
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(second.data["scan_status"], FileScanStatus.CLEAN)
        self.assertIsNotNone(second.data["scanned_at"])

    @pytest.mark.integration
    def test_scan_status_does_not_emit_file_metadata_viewed_audit(self):
        """Poll endpoint must not flood FILE_METADATA_VIEWED (unlike retrieve)."""
        key = {"action": audit_event_types.FILE_METADATA_VIEWED, "resource_id": self.file.id}
        before = AuditEvent.objects.filter(**key).count()
        resp = self.client.get(f"/api/v1/files/{self.file.id}/scan-status/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        after = AuditEvent.objects.filter(**key).count()
        self.assertEqual(after, before)


class FileScanStatusThrottleWiringTest(TestCase):
    @pytest.mark.integration
    def test_default_scan_status_rate_values_match_s23_contract(self):
        user_throttle = FileScanStatusUserThrottle()
        tenant_throttle = FileScanStatusTenantThrottle()
        self.assertEqual(user_throttle.get_rate(), "30/minute")
        self.assertEqual(tenant_throttle.get_rate(), "300/minute")

    @pytest.mark.integration
    def test_scan_status_action_uses_dedicated_throttles(self):
        view = FileViewSet()
        view.action = "scan_status"
        throttles = view.get_throttles()
        self.assertTrue(any(isinstance(t, FileScanStatusUserThrottle) for t in throttles))
        self.assertTrue(any(isinstance(t, FileScanStatusTenantThrottle) for t in throttles))

    @pytest.mark.integration
    def test_list_action_does_not_use_scan_status_throttles(self):
        view = FileViewSet()
        view.action = "list"
        throttles = view.get_throttles()
        self.assertFalse(any(isinstance(t, FileScanStatusUserThrottle) for t in throttles))
        self.assertFalse(any(isinstance(t, FileScanStatusTenantThrottle) for t in throttles))


class FileScanStatusRateLimitQuotaTest(TestCase):
    def setUp(self):
        super().setUp()
        self._orig_user_rates = dict(
            cast("dict[str, str]", FileScanStatusUserThrottle.THROTTLE_RATES or {})
        )
        self._orig_tenant_rates = dict(
            cast("dict[str, str]", FileScanStatusTenantThrottle.THROTTLE_RATES or {})
        )
        cache.clear()

    def tearDown(self):
        FileScanStatusUserThrottle.THROTTLE_RATES = self._orig_user_rates
        FileScanStatusTenantThrottle.THROTTLE_RATES = self._orig_tenant_rates
        cache.clear()

    def _seed_user_client(self):
        uid = uuid.uuid4().hex[:8]
        tenant = Tenant.objects.create(
            name=f"scan-rl-{uid}",
            slug=f"scan-rl-{uid}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        ensure_tenant_has_active_subscription(tenant)
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.create_user(
            email=f"scan-rl-{uid}@example.com",
            password="testpass123",
            tenant=tenant,
            status=UserStatus.ACTIVE,
        )
        fid = uuid.uuid4()
        File.objects.create(
            id=fid,
            tenant=tenant,
            name="poll.csv",
            content_type="text/csv",
            size=8,
            status=FileStatus.ACTIVE,
            scan_status=FileScanStatus.CLEAN,
            storage_path=f"{tenant.id}/{fid}/poll.csv",
            created_by=user,
        )
        client = APIClient()
        client.force_authenticate(user=user)
        return client, fid

    @pytest.mark.integration
    def test_user_throttle_second_scan_status_within_window_returns_429(self):
        client, fid = self._seed_user_client()
        FileScanStatusUserThrottle.THROTTLE_RATES = {
            **self._orig_user_rates,
            "file_scan_status_user": "1/minute",
        }
        FileScanStatusTenantThrottle.THROTTLE_RATES = {
            **self._orig_tenant_rates,
            "file_scan_status_tenant": "1000/minute",
        }

        first = cast(
            "Any",
            client.get(f"/api/v1/files/{fid}/scan-status/"),
        )
        self.assertNotEqual(first.status_code, status.HTTP_429_TOO_MANY_REQUESTS, first.content)

        blocked = cast(
            "Any",
            client.get(f"/api/v1/files/{fid}/scan-status/"),
        )
        self.assertEqual(blocked.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(blocked.data["error"]["code"], "RATE_LIMIT_EXCEEDED")
        details = blocked.data["error"].get("details") or {}
        self.assertIn("retry_after", details)
        self.assertGreaterEqual(int(details["retry_after"]), 1)
        self.assertIn("Retry-After", blocked)
        self.assertGreaterEqual(int(blocked["Retry-After"]), 1)

    @pytest.mark.integration
    def test_tenant_throttle_applies_across_users_in_same_tenant(self):
        uid = uuid.uuid4().hex[:8]
        tenant = Tenant.objects.create(
            name=f"scan-rl-t-{uid}",
            slug=f"scan-rl-t-{uid}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        ensure_tenant_has_active_subscription(tenant)
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user1 = User.objects.create_user(
            email=f"scan-rl-t1-{uid}@example.com",
            password="testpass123",
            tenant=tenant,
            status=UserStatus.ACTIVE,
        )
        user2 = User.objects.create_user(
            email=f"scan-rl-t2-{uid}@example.com",
            password="testpass123",
            tenant=tenant,
            status=UserStatus.ACTIVE,
        )
        fid = uuid.uuid4()
        File.objects.create(
            id=fid,
            tenant=tenant,
            name="poll2.csv",
            content_type="text/csv",
            size=8,
            status=FileStatus.ACTIVE,
            scan_status=FileScanStatus.CLEAN,
            storage_path=f"{tenant.id}/{fid}/poll2.csv",
            created_by=user1,
        )
        client1 = APIClient()
        client1.force_authenticate(user=user1)
        client2 = APIClient()
        client2.force_authenticate(user=user2)

        FileScanStatusUserThrottle.THROTTLE_RATES = {
            **self._orig_user_rates,
            "file_scan_status_user": "1000/minute",
        }
        FileScanStatusTenantThrottle.THROTTLE_RATES = {
            **self._orig_tenant_rates,
            "file_scan_status_tenant": "1/minute",
        }

        first = cast("Any", client1.get(f"/api/v1/files/{fid}/scan-status/"))
        self.assertNotEqual(first.status_code, status.HTTP_429_TOO_MANY_REQUESTS, first.content)

        blocked = cast("Any", client2.get(f"/api/v1/files/{fid}/scan-status/"))
        self.assertEqual(blocked.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(blocked.data["error"]["code"], "RATE_LIMIT_EXCEEDED")
