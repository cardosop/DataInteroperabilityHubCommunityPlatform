"""
Phase 260.2.F — ``GET /api/v1/files/{id}/`` emits ``FILE_METADATA_VIEWED`` under sampling.

- Default: deterministic ~10% per ``(owner_tenant, file_id, user)``.
- ``Tenant.compliance_audit_full_sampling``: 100% of successful retrieves.
- No audit on 404.

Real ``APIClient``, ``AuditEvent`` rows — no mocks.
"""

from __future__ import annotations
import pytest
import pytest

import uuid

from django.test import TestCase, override_settings
from rest_framework import status

from hub.apps.audit import event_types
from hub.apps.audit.models import AuditEvent
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.files.metadata_view_audit import file_metadata_view_should_emit
from hub.apps.files.models import File, FileScanStatus, FileStatus
from hub.apps.files.tests.test_base import FilesAPITestBase, _ensure_tenant_has_active_subscription
from hub.apps.marketplace.models import Entitlement, EntitlementStatus, Listing, ListingStatus
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from tests.security.base_idor import IDORTestBase

pytestmark = pytest.mark.django_db(transaction=True)


def _find_file_id_for_sample(
    tenant: Tenant, user_id, *, want_emit: bool, max_trials: int = 2000
) -> uuid.UUID:
    for _ in range(max_trials):
        fid = uuid.uuid4()
        if (
            file_metadata_view_should_emit(
                file_tenant=tenant, file_id=fid, user_id=user_id
            )
            == want_emit
        ):
            return fid
    raise AssertionError("could not find file_id for sample bucket (increase max_trials)")


class FileMetadataViewAuditSamplingTest(TestCase):
    """Unit tests for deterministic sampling (no HTTP)."""

    @pytest.mark.integration
    def test_full_sampling_always_true(self):
        t = Tenant(
            id=uuid.uuid4(),
            name="u",
            slug="u-slug",
            status=TenantStatus.ACTIVE,
            compliance_audit_full_sampling=True,
        )
        fid = uuid.uuid4()
        self.assertTrue(
            file_metadata_view_should_emit(file_tenant=t, file_id=fid, user_id=1)
        )

    @pytest.mark.integration
    def test_deterministic_stable_for_same_tuple(self):
        t = Tenant(
            id=uuid.uuid4(),
            name="u2",
            slug="u2-slug",
            status=TenantStatus.ACTIVE,
            compliance_audit_full_sampling=False,
        )
        fid = uuid.uuid4()
        uid = uuid.uuid4()
        a = file_metadata_view_should_emit(file_tenant=t, file_id=fid, user_id=uid)
        b = file_metadata_view_should_emit(file_tenant=t, file_id=fid, user_id=uid)
        self.assertEqual(a, b)


@override_settings(
    EVENT_BUS_ASYNC_PERSISTENCE=False,
    EVENT_BUS_WRITE_BEHIND_ENABLED=False,
    RATE_LIMIT_ENABLED=False,
)
class FileMetadataViewAuditHTTPTest(FilesAPITestBase):
    """Integration: retrieve + AuditEvent counts."""

    @pytest.mark.integration
    def test_full_sampling_records_audit_on_every_successful_retrieve(self):
        self.tenant.compliance_audit_full_sampling = True
        self.tenant.save(update_fields=["compliance_audit_full_sampling"])

        key = {"action": event_types.FILE_METADATA_VIEWED, "resource_id": str(self.file.id)}
        before = AuditEvent.objects.filter(**key).count()
        r1 = self.client.get(f"/api/v1/files/{self.file.id}/")
        r2 = self.client.get(f"/api/v1/files/{self.file.id}/")
        self.assertEqual(r1.status_code, status.HTTP_200_OK)
        self.assertEqual(r2.status_code, status.HTTP_200_OK)
        self.assertEqual(AuditEvent.objects.filter(**key).count(), before + 2)

        row = AuditEvent.objects.filter(**key).order_by("-timestamp").first()
        self.assertIsNotNone(row)
        d = row.details_json or {}
        self.assertEqual(d.get("sampling"), "full")

    @pytest.mark.integration
    def test_ten_percent_bucket_in_samples_emit(self):
        self.tenant.compliance_audit_full_sampling = False
        self.tenant.save(update_fields=["compliance_audit_full_sampling"])

        fid = _find_file_id_for_sample(self.tenant, self.user.id, want_emit=True)
        f = File.objects.create(
            id=fid,
            tenant=self.tenant,
            name="sampled.csv",
            content_type="text/csv",
            size=100,
            status=FileStatus.ACTIVE,
            scan_status=FileScanStatus.CLEAN,
            storage_path=f"{self.tenant.id}/{fid}/sampled.csv",
            created_by=self.user,
        )

        key = {"action": event_types.FILE_METADATA_VIEWED, "resource_id": str(f.id)}
        before = AuditEvent.objects.filter(**key).count()
        resp = self.client.get(f"/api/v1/files/{f.id}/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(AuditEvent.objects.filter(**key).count(), before + 1)
        row = AuditEvent.objects.filter(**key).order_by("-timestamp").first()
        d = row.details_json or {}
        self.assertEqual(d.get("sampling"), "ten_percent")

    @pytest.mark.integration
    def test_ten_percent_bucket_out_does_not_emit(self):
        self.tenant.compliance_audit_full_sampling = False
        self.tenant.save(update_fields=["compliance_audit_full_sampling"])

        fid = _find_file_id_for_sample(self.tenant, self.user.id, want_emit=False)
        f = File.objects.create(
            id=fid,
            tenant=self.tenant,
            name="not-sampled.csv",
            content_type="text/csv",
            size=100,
            status=FileStatus.ACTIVE,
            scan_status=FileScanStatus.CLEAN,
            storage_path=f"{self.tenant.id}/{fid}/not-sampled.csv",
            created_by=self.user,
        )

        key = {"action": event_types.FILE_METADATA_VIEWED, "resource_id": str(f.id)}
        before = AuditEvent.objects.filter(action=event_types.FILE_METADATA_VIEWED).count()
        resp = self.client.get(f"/api/v1/files/{f.id}/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(
            AuditEvent.objects.filter(action=event_types.FILE_METADATA_VIEWED).count(),
            before,
        )

    @pytest.mark.integration
    def test_404_does_not_emit_metadata_viewed(self):
        self.tenant.compliance_audit_full_sampling = True
        self.tenant.save(update_fields=["compliance_audit_full_sampling"])

        missing = uuid.uuid4()
        before = AuditEvent.objects.filter(action=event_types.FILE_METADATA_VIEWED).count()
        resp = self.client.get(f"/api/v1/files/{missing}/")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            AuditEvent.objects.filter(action=event_types.FILE_METADATA_VIEWED).count(),
            before,
        )


@override_settings(
    EVENT_BUS_ASYNC_PERSISTENCE=False,
    EVENT_BUS_WRITE_BEHIND_ENABLED=False,
    RATE_LIMIT_ENABLED=False,
)
class FileMetadataViewAuditCrossTenantEntitlementTest(IDORTestBase):
    """Entitled cross-tenant GET /files/{id}/: audit row on file owner tenant + consumer id."""

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
            name="entitled-cross.csv",
            content_type="text/csv",
            size=256,
            status=FileStatus.ACTIVE,
            scan_status=FileScanStatus.CLEAN,
            storage_path=f"{self.tenant_b.id}/{fid}/entitled-cross.csv",
            created_by=self.user_b,
        )
        self.asset = Asset.objects.create(
            tenant=self.tenant_b,
            key=f"meta-audit-asset-{uuid.uuid4().hex[:8]}",
            name="Meta Audit Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user_b,
        )
        self.listing = Listing.objects.create(
            tenant=self.tenant_b,
            asset=self.asset,
            status=ListingStatus.PUBLISHED,
            metadata_json={"title": "Offer"},
        )
        Dataset.objects.create(
            tenant=self.tenant_b,
            asset=self.asset,
            file=self.file_b,
            format="CSV",
            created_by=self.user_b,
        )
        Entitlement.objects.create(
            tenant=self.tenant_a,
            listing=self.listing,
            asset=self.asset,
            status=EntitlementStatus.ACTIVE,
        )
        self.tenant_b.compliance_audit_full_sampling = True
        self.tenant_b.save(update_fields=["compliance_audit_full_sampling"])

    @pytest.mark.integration
    def test_entitled_cross_tenant_retrieve_emits_metadata_viewed_with_consumer_tenant_id(self):
        self.client.force_authenticate(user=self.user_a)
        key = {
            "action": event_types.FILE_METADATA_VIEWED,
            "resource_id": str(self.file_b.id),
        }
        before = AuditEvent.objects.filter(**key).count()
        resp = self.client.get(f"/api/v1/files/{self.file_b.id}/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        self.assertEqual(AuditEvent.objects.filter(**key).count(), before + 1)
        row = AuditEvent.objects.filter(**key).order_by("-timestamp").first()
        self.assertIsNotNone(row)
        self.assertEqual(row.tenant_id, self.tenant_b.id)
        d = row.details_json or {}
        self.assertEqual(d.get("consumer_tenant_id"), str(self.tenant_a.id))
        self.assertEqual(d.get("sampling"), "full")
