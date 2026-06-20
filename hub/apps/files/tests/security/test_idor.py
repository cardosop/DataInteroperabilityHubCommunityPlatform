"""
Phase 260.2.A — Files API IDOR and authorization contract tests.

Pins ``GET /api/v1/files/{id}/``, ``GET /api/v1/files/{id}/download/``,
``GET /api/v1/files/{id}/scan-status/``,
and ``DELETE /api/v1/files/{id}/`` against:

1. Cross-tenant access without entitlement → **404** (no existence leak).
2. AUDITOR → **403** on mutating endpoints (DESTROY), even in-home tenant.
3. **401** when ``X-Tenant-Id`` is set but there is no valid bearer
   (``TenantScopingMiddleware``); unauthenticated calls without that header
   also **401** via ``IsAuthenticated``.
4. Malformed UUID in path → **400** (early UUID validation).

``FILE_IDOR_ATTEMPT_BLOCKED`` is asserted for cross-tenant **read** probes
that run the entitlement path (retrieve, download, and scan-status), including
``ENTITLEMENT_DENIED`` when an asset link exists but no entitlement does.

Real ``APIClient``, ORM fixtures, JWT-free ``force_authenticate`` — same
patterns as ``tests/security/base_idor.py`` and DQ IDOR suites. No mocks.
"""

from __future__ import annotations

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.test.client import Client
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset
from hub.apps.audit import event_types
from hub.apps.audit.models import AuditEvent
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileScanStatus, FileStatus
from hub.apps.files.tests.test_base import _ensure_tenant_has_active_subscription
from hub.apps.tenants.models import KYCStatus
from hub.apps.users.models import Role, UserRole, UserStatus, UserTenantMembership
from tests.security.base_idor import IDORTestBase

pytestmark = pytest.mark.django_db(transaction=True)

User = get_user_model()


@override_settings(
    EVENT_BUS_ASYNC_PERSISTENCE=False,
    EVENT_BUS_WRITE_BEHIND_ENABLED=False,
    RATE_LIMIT_ENABLED=False,
)
class FileEndpointIDORSuite(IDORTestBase):
    """Two tenants; target file always lives in tenant B."""

    def setUp(self):
        super().setUp()
        _ensure_tenant_has_active_subscription(self.tenant_a)
        _ensure_tenant_has_active_subscription(self.tenant_b)
        self.tenant_a.kyc_status = KYCStatus.VERIFIED
        self.tenant_a.save(update_fields=["kyc_status"])
        self.tenant_b.kyc_status = KYCStatus.VERIFIED
        self.tenant_b.save(update_fields=["kyc_status"])
        fid = uuid.uuid4()
        self.file_b = File.objects.create(
            id=fid,
            tenant=self.tenant_b,
            name="idor-target.csv",
            content_type="text/csv",
            size=512,
            status=FileStatus.ACTIVE,
            scan_status=FileScanStatus.CLEAN,
            storage_path=f"{self.tenant_b.id}/{fid}/idor-target.csv",
            created_by=self.user_b,
        )

    # --- parameterized shape (urlpatterns trailing slash matches project)

    _CROSS_TENANT_CALLS = (
        ("retrieve", "GET"),
        ("download", "GET"),
        ("scan_status", "GET"),
        ("destroy", "DELETE"),
    )

    def _call_files_endpoint(self, verb: str, name: str) -> tuple[Client | APIClient, object]:
        self.client.force_authenticate(user=self.user_a)
        base = "/api/v1/files/"
        fid = self.file_b.id
        if name == "retrieve":
            return self.client, getattr(self.client, verb.lower())(f"{base}{fid}/")
        if name == "download":
            return self.client, getattr(self.client, verb.lower())(f"{base}{fid}/download/")
        if name == "scan_status":
            return self.client, getattr(self.client, verb.lower())(f"{base}{fid}/scan-status/")
        if name == "destroy":
            return self.client, getattr(self.client, verb.lower())(f"{base}{fid}/")
        raise AssertionError(f"unknown fixture name {name}")

    @pytest.mark.integration
    def test_cross_tenant_file_access_returns_404_parameterized(self):
        """Across detail GET, download, scan-status GET, and DELETE — no existence leak."""
        for endpoint_name, verb in self._CROSS_TENANT_CALLS:
            with self.subTest(endpoint=f"{verb} /files/{{id}}/… ({endpoint_name})"):
                _, response = self._call_files_endpoint(verb, endpoint_name)
                self.assertEqual(
                    response.status_code,
                    status.HTTP_404_NOT_FOUND,
                    f"Expected 404 for cross-tenant {endpoint_name}, "
                    f"got {response.status_code}: {response.data!r}",
                )

    @pytest.mark.integration
    def test_file_idor_audit_emitted_for_cross_tenant_read_probes(self):
        """retrieve + download + scan-status must emit ONE FILE_IDOR_ATTEMPT_BLOCKED audit each."""
        key = {"action": event_types.FILE_IDOR_ATTEMPT_BLOCKED}
        before = AuditEvent.objects.filter(**key).count()
        for endpoint_name, verb in (
            ("retrieve", "GET"),
            ("download", "GET"),
            ("scan_status", "GET"),
        ):
            self._call_files_endpoint(verb, endpoint_name)
        delta = AuditEvent.objects.filter(**key).count() - before
        self.assertEqual(
            delta,
            3,
            "retrieve, download, and scan-status entitlement fallback must audit",
        )

        row = AuditEvent.objects.filter(**key).order_by("-timestamp").first()
        assert row is not None
        details = row.details_json or {}
        self.assertIn("reason", details)
        self.assertEqual(details["file_owner_tenant_id"], str(self.tenant_b.id))
        self.assertEqual(details["consumer_tenant_id"], str(self.tenant_a.id))

    @pytest.mark.integration
    def test_cross_tenant_read_entitlement_denied_audits_reason_and_error_code(self):
        """Asset-linked file without marketplace entitlement → ENTITLEMENT_DENIED audit detail."""
        asset = Asset.objects.create(
            tenant=self.tenant_b,
            key=f"idor-asset-{uuid.uuid4().hex[:8]}",
            name="IDOR Asset",
            created_by=self.user_b,
        )
        Dataset.objects.create(
            tenant=self.tenant_b,
            asset=asset,
            file=self.file_b,
            format="CSV",
            created_by=self.user_b,
        )
        key = {"action": event_types.FILE_IDOR_ATTEMPT_BLOCKED}
        before = AuditEvent.objects.filter(**key).count()
        self.client.force_authenticate(user=self.user_a)
        resp = self.client.get(f"/api/v1/files/{self.file_b.id}/")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(AuditEvent.objects.filter(**key).count(), before + 1)
        row = AuditEvent.objects.filter(**key).order_by("-timestamp").first()
        assert row is not None
        details = row.details_json or {}
        self.assertEqual(details.get("reason"), "ENTITLEMENT_DENIED")
        self.assertEqual(details.get("entitlement_error"), "ENTITLEMENT_REQUIRED")

    @pytest.mark.integration
    def test_auditor_cannot_destroy_file_home_tenant(self):
        """AUDITOR must not DELETE even when the row is in their tenant."""
        uid = uuid.uuid4().hex[:8]
        auditor_user = User.objects.create_user(
            email=f"auditor-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant_b,
            status=UserStatus.ACTIVE,
        )
        UserTenantMembership.objects.get_or_create(
            user=auditor_user,
            tenant=self.tenant_b,
        )
        auditor_role, _ = Role.objects.get_or_create(
            tenant=self.tenant_b,
            name="AUDITOR",
            defaults={"description": "read-only auditor"},
        )
        UserRole.objects.create(user=auditor_user, role=auditor_role)

        self.client.force_authenticate(user=auditor_user)
        resp = self.client.delete(f"/api/v1/files/{self.file_b.id}/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    @pytest.mark.integration
    def test_malformed_uuid_returns_400_parameterized(self):
        bad_id = "not-a-uuid"
        self.client.force_authenticate(user=self.user_a)
        valid_sha = "a" * 64
        cases = (
            ("get", f"/api/v1/files/{bad_id}/", None),
            ("get", f"/api/v1/files/{bad_id}/download/", None),
            ("get", f"/api/v1/files/{bad_id}/scan-status/", None),
            ("delete", f"/api/v1/files/{bad_id}/", None),
            (
                "post",
                f"/api/v1/files/{bad_id}/complete/",
                {"content_sha256": valid_sha},
            ),
            (
                "post",
                f"/api/v1/files/{bad_id}/chunks/init/",
                {"chunk_number": 1, "chunk_size": 5242880},
            ),
        )
        for verb, path, data in cases:
            with self.subTest(path=path, verb=verb):
                caller = getattr(self.client, verb)
                if data is not None:
                    response = caller(path, data=data, format="json")
                else:
                    response = caller(path)
                self.assertEqual(
                    response.status_code,
                    status.HTTP_400_BAD_REQUEST,
                    f"Malformed UUID path must yield 400, got {response.status_code} for {path}",
                )
                payload = getattr(response, "data", None)
                text = str(payload).lower()
                self.assertTrue(
                    "not a valid uuid" in text or "valid uuid" in text,
                    f"Unexpected 400 body for {path}: {payload!r}",
                )

    @pytest.mark.integration
    def test_missing_auth_returns_401_parameterized(self):
        """Bearer missing while ``X-Tenant-Id`` is set → middleware 401 (DQ contract)."""
        bare = APIClient()
        fid = self.file_b.id
        xt = {"HTTP_X_TENANT_ID": str(self.tenant_a.id)}
        cases = (
            ("get", f"/api/v1/files/{fid}/"),
            ("get", f"/api/v1/files/{fid}/download/"),
            ("get", f"/api/v1/files/{fid}/scan-status/"),
            ("delete", f"/api/v1/files/{fid}/"),
        )
        for verb, path in cases:
            with self.subTest(path=path):
                res = getattr(bare, verb)(path, **xt)
                self.assertEqual(
                    res.status_code,
                    status.HTTP_401_UNAUTHORIZED,
                    f"missing bearer with X-Tenant-Id expects 401, got "
                    f"{res.status_code} for {verb.upper()} {path}",
                )
