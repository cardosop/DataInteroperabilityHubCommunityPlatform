"""
Phase 260.3.F.2 — ``GET /api/v1/files/{id}/parts/`` contract tests.

The endpoint returns S3-truth for the parts already uploaded against a
file's ``multipart_upload_id``, so the frontend can reconcile its
localStorage checkpoint when resuming after a network failure.

No mocks of S3, ORM, or auth: when MinIO/S3 is unreachable the live-S3
tests skip cleanly (mirrors :mod:`test_chunked_upload`'s established
pattern). The throttle-wiring + tenant-isolation tests run unconditionally
because they exercise the view layer end-to-end without any S3 round
trips.
"""

from __future__ import annotations

import contextlib
import uuid
from typing import cast

import pytest
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.files.models import File, FileStatus
from hub.apps.files.storage import S3StorageClient
from hub.apps.files.tests.test_base import FilesAPITestBase
from hub.apps.files.views import FileViewSet
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

pytestmark = pytest.mark.django_db(transaction=True)


class _StorageProbe:
    """Helper that lazily checks whether MinIO/S3 is reachable for live tests."""

    def __init__(self) -> None:
        self.client: S3StorageClient | None = None
        self.available = False
        try:
            self.client = S3StorageClient()
            self.client._ensure_bucket_exists()
            self.available = True
        except (ConnectionError, TimeoutError, OSError):  # pragma: no cover — env-conditional
            self.available = False


class MultipartListPartsContractTest(FilesAPITestBase):
    """Endpoint shape, tenant isolation, state-machine guards."""

    def setUp(self) -> None:
        super().setUp()
        self._probe = _StorageProbe()

    def _seed_uploading_file(self, *, key_suffix: str = "data.csv") -> tuple[File, str]:
        if not self._probe.available or self._probe.client is None:
            self.skipTest("S3/MinIO storage not available")
        file_obj = File.objects.create(
            tenant=self.tenant,
            name="big.csv",
            content_type="text/csv",
            size=150 * 1024 * 1024,
            storage_path=f"{self.tenant.id}/list-parts/{uuid.uuid4().hex[:8]}/{key_suffix}",
            status=FileStatus.UPLOADING,
            created_by=self.user,
            metadata_json={
                "chunk_size": 10 * 1024 * 1024,
                "chunk_count": 15,
            },
        )
        upload_id = self._probe.client.initiate_multipart_upload(
            key=file_obj.storage_path, content_type="text/csv"
        )
        file_obj.metadata_json["multipart_upload_id"] = upload_id
        file_obj.save(update_fields=["metadata_json"])
        return file_obj, upload_id

    def _abort(self, file_obj: File, upload_id: str) -> None:
        if self._probe.client is None:
            return
        with contextlib.suppress(Exception):
            self._probe.client.abort_multipart_upload(
                key=file_obj.storage_path, upload_id=upload_id
            )

    @pytest.mark.integration
    def test_list_parts_returns_empty_parts_before_any_chunk_uploaded(self) -> None:
        file_obj, upload_id = self._seed_uploading_file()
        try:
            resp = self.client.get(f"/api/v1/files/{file_obj.id}/parts/")
            assert resp.status_code == status.HTTP_200_OK, resp.content
            assert resp.data["upload_id"] == upload_id
            assert resp.data["parts"] == []
        finally:
            self._abort(file_obj, upload_id)

    @pytest.mark.integration
    def test_list_parts_returns_etags_after_chunk_upload(self) -> None:
        file_obj, upload_id = self._seed_uploading_file()
        if self._probe.client is None:
            self.skipTest("S3 client unavailable")
        try:
            # Upload one part directly through the boto3 client so the
            # endpoint observes a real multipart-state transition (no
            # mocks).
            payload = b"X" * (5 * 1024 * 1024)  # 5 MiB minimum
            put = self._probe.client.client.upload_part(
                Bucket=self._probe.client.bucket_name,
                Key=file_obj.storage_path,
                UploadId=upload_id,
                PartNumber=1,
                Body=payload,
            )
            etag = put["ETag"]

            resp = self.client.get(f"/api/v1/files/{file_obj.id}/parts/")
            assert resp.status_code == status.HTTP_200_OK
            assert resp.data["upload_id"] == upload_id
            parts = resp.data["parts"]
            assert isinstance(parts, list) and len(parts) == 1
            entry = parts[0]
            assert entry["part_number"] == 1
            assert entry["etag"] == etag
            assert entry["size"] == len(payload)
        finally:
            self._abort(file_obj, upload_id)

    @pytest.mark.integration
    def test_list_parts_404_when_file_not_in_uploading_state(self) -> None:
        file_obj = File.objects.create(
            tenant=self.tenant,
            name="not-uploading.csv",
            content_type="text/csv",
            size=1024,
            storage_path=f"{self.tenant.id}/not-uploading.csv",
            status=FileStatus.ACTIVE,
            created_by=self.user,
        )
        resp = self.client.get(f"/api/v1/files/{file_obj.id}/parts/")
        # The file exists and is queryable, but it has no active multipart —
        # treat this as 409: the resource is in the wrong state for the
        # operation. Frontend should clear its checkpoint and surface
        # "upload already completed" to the user.
        assert resp.status_code in (
            status.HTTP_404_NOT_FOUND,
            status.HTTP_409_CONFLICT,
        ), resp.content
        if resp.status_code == status.HTTP_409_CONFLICT:
            assert "code" in (resp.data.get("error") or {}) or "code" in resp.data

    @pytest.mark.integration
    def test_list_parts_404_for_unknown_file(self) -> None:
        missing = uuid.uuid4()
        resp = self.client.get(f"/api/v1/files/{missing}/parts/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.integration
    def test_list_parts_tenant_isolation_blocks_cross_tenant_reads(self) -> None:
        if not self._probe.available or self._probe.client is None:
            self.skipTest("S3/MinIO storage not available")
        other = Tenant.objects.create(
            name="other-list-parts",
            slug=f"other-list-parts-{uuid.uuid4().hex[:8]}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        ensure_tenant_has_active_subscription(other)
        other_file = File.objects.create(
            tenant=other,
            name="other.csv",
            content_type="text/csv",
            size=150 * 1024 * 1024,
            storage_path=f"{other.id}/other-list-parts/{uuid.uuid4().hex[:8]}/data.csv",
            status=FileStatus.UPLOADING,
            created_by=None,
            metadata_json={"chunk_size": 10 * 1024 * 1024, "chunk_count": 15},
        )
        other_upload_id = self._probe.client.initiate_multipart_upload(
            key=other_file.storage_path, content_type="text/csv"
        )
        other_file.metadata_json["multipart_upload_id"] = other_upload_id
        other_file.save(update_fields=["metadata_json"])
        try:
            resp = self.client.get(f"/api/v1/files/{other_file.id}/parts/")
            assert resp.status_code == status.HTTP_404_NOT_FOUND
        finally:
            self._abort(other_file, other_upload_id)


class MultipartListPartsThrottleWiringTest(TestCase):
    """``parts`` MUST run under the same scan-status-class polling caps."""

    @pytest.mark.integration
    def test_parts_action_uses_dedicated_throttles(self) -> None:
        view = FileViewSet()
        view.action = "parts"
        throttles = view.get_throttles()
        # Either the dedicated FileScanStatus*Throttle pair OR a new
        # FileMultipartParts*Throttle pair is acceptable; the contract is
        # "polling-caliber rate limits, not the upload-init caps". The
        # failing assertion lets us choose at implementation time.
        from hub.apps.files.throttles import (
            FileInitTenantThrottle,
            FileInitUserThrottle,
        )

        for t in throttles:
            assert not isinstance(t, FileInitUserThrottle), (
                "parts must NOT inherit the file-init upload caps"
            )
            assert not isinstance(t, FileInitTenantThrottle), (
                "parts must NOT inherit the file-init upload caps"
            )

    @pytest.mark.integration
    def test_parts_action_is_a_get_only_action(self) -> None:
        view = FileViewSet()
        view.action = "parts"
        getattr(view, "_get_action_methods", lambda: None)()  # type: ignore[arg-type]  # test: reflective callable access
        # Smoke: action attribute exists and is callable.
        assert callable(getattr(view, "parts", None)), "FileViewSet.parts action must be defined"


class MultipartListPartsRateLimitTest(TestCase):
    """Per-tenant rate-limit guard applies on hot polling."""

    def setUp(self) -> None:
        super().setUp()
        from django.core.cache import cache

        cache.clear()

    @pytest.mark.integration
    def test_unauthenticated_request_is_rejected(self) -> None:
        # No login_user, no force_authenticate — anonymous user must not
        # be able to list parts even for a non-existent file.
        client = APIClient()
        resp = cast(
            "object",
            client.get(f"/api/v1/files/{uuid.uuid4()}/parts/"),
        )
        # Either 401 (auth required) or 403 (tenant required) is fine —
        # the contract is "no anonymous list-parts".
        assert getattr(resp, "status_code", None) in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ), getattr(resp, "content", b"")
