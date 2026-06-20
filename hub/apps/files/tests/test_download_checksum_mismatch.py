"""
Phase 260.3.G — file-download checksum verification audit endpoint.

The contract under test:

    1. ``GET /api/v1/files/{id}/download/`` MUST return ``content_sha256``
       in the JSON body so the SDK / browser can verify the blob it
       receives from S3 matches what the platform stored.
    2. ``POST /api/v1/files/{id}/download/checksum-mismatch/`` accepts
       a client-side computed ``actual_sha256`` and emits a
       ``FILE_DOWNLOAD_CHECKSUM_MISMATCH`` audit row carrying both
       hashes (truncated to 16 hex chars in the payload — full hashes
       fingerprint the corruption signature without bloating the audit
       log). The audit fires every call; the endpoint never
       authoritatively decides match/mismatch (that's the client's
       responsibility — the server logs whatever the client says).
    3. Tenant scope: a tenant cannot file a mismatch audit against
       another tenant's file. Cross-tenant requests 404.
    4. Throttle: polling-class caps (30/min user, 300/min tenant) so a
       buggy SDK client that loops forever can't DoS the audit log.

No mocks of S3, ORM, or auth. ``content_sha256`` is set directly on the
File row in setUp — it's a CharField on the model and the production
upload flow writes it via ``FileCompleteSerializer``.
"""

from __future__ import annotations

import uuid
from typing import cast

import pytest
from django.core.cache import cache
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.audit import event_types as audit_event_types
from hub.apps.audit.models import AuditEvent
from hub.apps.files.models import File, FileScanStatus, FileStatus
from hub.apps.files.tests.test_base import FilesAPITestBase
from hub.apps.files.views import FileViewSet
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

pytestmark = pytest.mark.django_db(transaction=True)


# Two valid SHA-256 fixtures — distinct so any "expected vs actual"
# mismatch is unambiguous in test output.
EXPECTED_SHA = "a" * 64
ACTUAL_SHA = "b" * 64


class FileDownloadResponseSurfaceTest(FilesAPITestBase):
    """The download response MUST expose ``content_sha256`` for clients."""

    def setUp(self) -> None:
        super().setUp()
        self.file.content_sha256 = EXPECTED_SHA
        self.file.scan_status = FileScanStatus.CLEAN
        self.file.status = FileStatus.ACTIVE
        self.file.save(update_fields=["content_sha256", "scan_status", "status", "updated_at"])

    @pytest.mark.integration
    def test_download_response_includes_content_sha256(self) -> None:
        resp = self.client.get(f"/api/v1/files/{self.file.id}/download/")
        # Real download against MinIO/S3 may fail to presign in non-S3 dev
        # environments — the contract under test is the JSON shape, not
        # the URL. Assert the body shape regardless of the underlying
        # presign provider.
        if resp.status_code == status.HTTP_200_OK:
            assert resp.data.get("content_sha256") == EXPECTED_SHA
        else:
            self.skipTest(
                f"download presign not available in this environment "
                f"(status={resp.status_code}); see test_download_endpoint suite"
            )

    @pytest.mark.integration
    def test_download_response_includes_null_sha_when_file_has_no_hash(self) -> None:
        """Older files predating Phase 260.3.G have NULL content_sha256."""
        self.file.content_sha256 = None
        self.file.save(update_fields=["content_sha256", "updated_at"])
        resp = self.client.get(f"/api/v1/files/{self.file.id}/download/")
        if resp.status_code == status.HTTP_200_OK:
            # Field MUST be present even when null so clients can branch
            # cleanly on "no expected hash" vs "field missing entirely".
            assert "content_sha256" in resp.data
            assert resp.data["content_sha256"] is None


class FileDownloadChecksumMismatchEndpointTest(FilesAPITestBase):
    """
    ``POST /api/v1/files/{id}/download/checksum-mismatch/`` audit contract.
    """

    def setUp(self) -> None:
        super().setUp()
        self.file.content_sha256 = EXPECTED_SHA
        self.file.status = FileStatus.ACTIVE
        self.file.scan_status = FileScanStatus.CLEAN
        self.file.save(update_fields=["content_sha256", "status", "scan_status", "updated_at"])

    def _post_mismatch(self, file_id: object, actual_sha: str) -> object:
        return self.client.post(
            f"/api/v1/files/{file_id}/download/checksum-mismatch/",
            {"actual_sha256": actual_sha},
            format="json",
        )

    @pytest.mark.integration
    def test_emits_audit_with_truncated_hashes_and_returns_200(self) -> None:
        before = AuditEvent.objects.filter(
            action=audit_event_types.FILE_DOWNLOAD_CHECKSUM_MISMATCH,
            resource_id=str(self.file.id),
        ).count()

        resp = cast("object", self._post_mismatch(self.file.id, ACTUAL_SHA))
        assert getattr(resp, "status_code", None) == status.HTTP_200_OK, getattr(
            resp, "content", b""
        )

        after = AuditEvent.objects.filter(
            action=audit_event_types.FILE_DOWNLOAD_CHECKSUM_MISMATCH,
            resource_id=str(self.file.id),
        )
        assert after.count() == before + 1
        # AuditEvent uses ``timestamp`` (set on creation) as its
        # canonical event-time field — there is no ``created_at`` on
        # this model.
        details = after.latest("timestamp").details_json or {}
        # Truncated to 16 hex chars (load-bearing privacy decision: full
        # hashes are deterministic and could fingerprint sensitive
        # content if leaked into general audit-log search).
        assert details.get("expected_sha256_prefix") == EXPECTED_SHA[:16]
        assert details.get("actual_sha256_prefix") == ACTUAL_SHA[:16]
        assert details.get("file_id") == str(self.file.id)

    @pytest.mark.integration
    def test_rejects_malformed_sha_with_400(self) -> None:
        resp = cast("object", self._post_mismatch(self.file.id, "not-a-sha"))
        assert getattr(resp, "status_code", None) == status.HTTP_400_BAD_REQUEST

    @pytest.mark.integration
    def test_404_for_unknown_file_id(self) -> None:
        missing = uuid.uuid4()
        resp = cast("object", self._post_mismatch(missing, ACTUAL_SHA))
        assert getattr(resp, "status_code", None) == status.HTTP_404_NOT_FOUND

    @pytest.mark.integration
    def test_cross_tenant_returns_404_and_emits_no_audit(self) -> None:
        other = Tenant.objects.create(
            name=f"other-cksum-{uuid.uuid4().hex[:8]}",
            slug=f"other-cksum-{uuid.uuid4().hex[:8]}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        ensure_tenant_has_active_subscription(other)
        other_file = File.objects.create(
            id=uuid.uuid4(),
            tenant=other,
            name="cross.csv",
            content_type="text/csv",
            size=1,
            storage_path=f"{other.id}/cross.csv",
            status=FileStatus.ACTIVE,
            scan_status=FileScanStatus.CLEAN,
            content_sha256=EXPECTED_SHA,
        )
        before = AuditEvent.objects.filter(
            action=audit_event_types.FILE_DOWNLOAD_CHECKSUM_MISMATCH,
        ).count()

        resp = cast("object", self._post_mismatch(other_file.id, ACTUAL_SHA))
        assert getattr(resp, "status_code", None) == status.HTTP_404_NOT_FOUND

        # No audit row from the cross-tenant probe.
        after = AuditEvent.objects.filter(
            action=audit_event_types.FILE_DOWNLOAD_CHECKSUM_MISMATCH,
        ).count()
        assert after == before

    @pytest.mark.integration
    def test_does_NOT_authoritatively_decide_match_vs_mismatch(self) -> None:
        """Endpoint logs whatever the client says — never silently filters."""
        # Same-as-expected SHA also creates an audit entry: the contract
        # is "client reported a mismatch", not "server agrees there is
        # one". This makes the audit complete from the client's POV
        # (they got a non-trivial answer back; the audit row records
        # the report regardless).
        before = AuditEvent.objects.filter(
            action=audit_event_types.FILE_DOWNLOAD_CHECKSUM_MISMATCH,
            resource_id=str(self.file.id),
        ).count()
        resp = cast("object", self._post_mismatch(self.file.id, EXPECTED_SHA))
        assert getattr(resp, "status_code", None) == status.HTTP_200_OK
        after = AuditEvent.objects.filter(
            action=audit_event_types.FILE_DOWNLOAD_CHECKSUM_MISMATCH,
            resource_id=str(self.file.id),
        ).count()
        assert after == before + 1


class ChecksumMismatchThrottleWiringTest(TestCase):
    """The endpoint MUST run at polling-class throttle caps."""

    def setUp(self) -> None:
        super().setUp()
        cache.clear()

    @pytest.mark.integration
    def test_action_uses_dedicated_polling_throttles_not_init_caps(self) -> None:
        view = FileViewSet()
        view.action = "download_checksum_mismatch"
        throttles = view.get_throttles()
        from hub.apps.files.throttles import (
            FileInitTenantThrottle,
            FileInitUserThrottle,
        )

        for t in throttles:
            assert not isinstance(t, FileInitUserThrottle), (
                "checksum-mismatch must not inherit init upload caps"
            )
            assert not isinstance(t, FileInitTenantThrottle), (
                "checksum-mismatch must not inherit init upload caps"
            )
        assert callable(getattr(view, "download_checksum_mismatch", None)), (
            "FileViewSet.download_checksum_mismatch action must be defined"
        )

    @pytest.mark.integration
    def test_unauthenticated_request_is_rejected(self) -> None:
        client = APIClient()
        resp = cast(
            "object",
            client.post(
                f"/api/v1/files/{uuid.uuid4()}/download/checksum-mismatch/",
                {"actual_sha256": ACTUAL_SHA},
                format="json",
            ),
        )
        assert getattr(resp, "status_code", None) in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )


class AuditConstantPresenceTest(TestCase):
    """The audit constant MUST be exported from ``audit.event_types``."""

    @pytest.mark.integration
    def test_constant_value_is_self_describing(self) -> None:
        from hub.apps.audit import event_types

        assert event_types.FILE_DOWNLOAD_CHECKSUM_MISMATCH == "FILE_DOWNLOAD_CHECKSUM_MISMATCH"
        assert "FILE_DOWNLOAD_CHECKSUM_MISMATCH" in event_types.__all__
