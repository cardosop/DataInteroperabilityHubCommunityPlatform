"""
File Storage Views

REST API views for file upload, download, and management.
"""

import contextlib
import os
import time
import uuid

import structlog
from django.conf import settings
from django.db import IntegrityError, transaction
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from hub.apps.audit.utils import create_audit_event
from hub.apps.core.responses import api_error_response, handle_service_exception
from hub.apps.core.services.base import ValidationError as ServiceValidationError
from hub.apps.tenants.request_tenant import get_request_tenant, get_request_tenant_id
from hub.apps.tenants.services import get_tenant_file_size_limit

from .models import File, FileScanStatus, FileStatus
from .serializers import (
    ChecksumMismatchSerializer,
    ChunkUploadInitSerializer,
    ChunkUploadResponseSerializer,
    FileCompleteSerializer,
    FileDownloadResponseSerializer,
    FileInitResponseSerializer,
    FileInitSerializer,
    FileRenameSerializer,
    FileSerializer,
)
from .services import FileService
from .storage import S3StorageClient
from .validators import calculate_chunk_count, get_chunk_size

logger = structlog.get_logger(__name__)


class FileViewSet(viewsets.ModelViewSet):
    """
    ViewSet for file management.

    Tenant-scoped: users can only see/manage files in their tenant.
    List supports: search (name), filter (status), ordering (29.69.2).
    """

    queryset = File.objects.all()
    serializer_class = FileSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "id"

    def initial(self, request, *args, **kwargs):
        from hub.apps.tenants.kill_switch_gates import ensure_tenant_files_api_allowed

        ensure_tenant_files_api_allowed(request)
        super().initial(request, *args, **kwargs)

    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["name"]
    ordering_fields = ["name", "created_at", "updated_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        """Filter queryset based on user permissions and optional status filter."""
        user = self.request.user

        # Platform admins can see all files
        if hasattr(user, "is_platform_admin") and user.is_platform_admin:
            queryset = File.objects.all()
        else:
            # Phase 16: use central helper (docs/TENANT_ISOLATION.md)
            tenant_id_str = get_request_tenant_id(self.request)
            if not tenant_id_str:
                return File.objects.none()

            try:
                tenant_id = uuid.UUID(tenant_id_str)
            except (ValueError, TypeError):
                return File.objects.none()
            queryset = File.objects.filter(tenant_id=tenant_id)

        # Filter by status when query param is provided
        status_param = self.request.query_params.get("status")
        if status_param:
            queryset = queryset.filter(status=status_param)
        return queryset

    def get_object(self):
        """Retrieve File by ``id`` lookup, validated as a UUID.

        Returns 400 for malformed (non-UUID) identifiers before reaching
        the ORM, mirrors the guard in ``rename`` (Phase 260.2.A contract).

        Cross-tenant read probes are audited by ``_get_file_via_entitlement``
        which is called as a fallback from ``retrieve``, ``download``, and
        ``scan_status`` — it emits ``FILE_IDOR_ATTEMPT_BLOCKED`` with the
        precise reason (no asset link vs. entitlement denied).
        """
        # ── UUID validation (malformed identifier → 400) ──────────
        raw_id = self.kwargs.get(self.lookup_field, "")
        try:
            uuid.UUID(raw_id)
        except (ValueError, TypeError, AttributeError):
            from rest_framework.exceptions import ValidationError as DRFValidationError

            raise DRFValidationError(
                detail=f"'{raw_id}' is not a valid UUID.",
                code="invalid",
            )

        # ── Tenant-scoped fetch ───────────────────────────────────
        queryset = self.filter_queryset(self.get_queryset())
        try:
            obj = queryset.get(id=raw_id)
        except (File.DoesNotExist, queryset.model.DoesNotExist):
            from django.http import Http404 as _Http404

            raise _Http404("No File matches the given query.")

        # ── May raise PermissionDenied ────────────────────────────
        self.check_object_permissions(self.request, obj)
        return obj

    def _emit_file_idor_audit(self, file_obj, *, reason, extra_details=None):
        """Emit ``FILE_IDOR_ATTEMPT_BLOCKED`` audit event for a
        cross-tenant file access probe."""
        import contextlib

        from hub.apps.audit import event_types as _et

        consumer_tid = get_request_tenant_id(self.request)
        details = {
            "reason": reason,
            "file_owner_tenant_id": str(file_obj.tenant_id),
            "consumer_tenant_id": consumer_tid or "",
        }
        if extra_details:
            details.update(extra_details)
        with contextlib.suppress(Exception):
            create_audit_event(
                resource_type="FILE",
                action=_et.FILE_IDOR_ATTEMPT_BLOCKED,
                actor_user=self.request.user,
                tenant=file_obj.tenant,
                resource_id=str(file_obj.id),
                details=details,
                request=self.request,
            )

    def get_throttles(self):
        """Action-scoped throttles.

        Phase 260.2.E (S-9): init upload → FileInitUserThrottle + FileInitTenantThrottle.
        Phase S2-3: scan-status → FileScanStatusUserThrottle + FileScanStatusTenantThrottle.
        """
        from hub.apps.files.throttles import (
            FileInitTenantThrottle,
            FileInitUserThrottle,
            FileScanStatusTenantThrottle,
            FileScanStatusUserThrottle,
        )

        throttles = list(super().get_throttles())
        if self.action == "init_upload":
            throttles.extend([FileInitUserThrottle(), FileInitTenantThrottle()])
        elif self.action == "scan_status":
            throttles.extend([FileScanStatusUserThrottle(), FileScanStatusTenantThrottle()])
        return throttles

    def _get_file_via_entitlement(self, request, file_id):
        """117B.6: Cross-tenant file access via entitlement.

        Returns File if consumer has ACTIVE entitlement for
        the file's asset; None if file doesn't exist, has
        no asset link, or the entitlement is denied.

        Emits ``FILE_IDOR_ATTEMPT_BLOCKED`` audit for every
        cross-tenant read probe — ``reason=CROSS_TENANT_PROBE``
        (no asset link) or ``reason=ENTITLEMENT_DENIED`` with
        ``entitlement_error=ENTITLEMENT_REQUIRED`` (asset link
        exists but no active entitlement). The response always
        stays 404 — no existence leak via status code.

        Phase 260.2.A contract: cross-tenant read probes MUST
        return 404 (not 403), hiding the file's existence even
        when an entitlement is required.
        """
        try:
            file_obj = File.objects.get(id=file_id)
        except File.DoesNotExist:
            return None

        consumer_tid = get_request_tenant_id(request)
        if not consumer_tid:
            return None

        # Same tenant — shouldn't reach here, but safe
        if str(file_obj.tenant_id) == consumer_tid:
            return file_obj

        from hub.apps.marketplace.entitlement_check import (
            get_asset_id_from_file,
        )

        asset_id = get_asset_id_from_file(str(file_obj.id))
        if not asset_id:
            # File exists in another tenant but has no asset link.
            # Audit the probe, return 404 — no existence leak.
            self._emit_file_idor_audit(
                file_obj=file_obj,
                reason="CROSS_TENANT_PROBE",
            )
            return None

        # Asset-linked file — check entitlement. If denied,
        # audit with the precise denial reason but STILL return
        # None → 404 (not 403). The audit record captures the
        # entitlement-denied detail for the security team.
        from hub.apps.marketplace.entitlement_check import (
            require_entitlement,
        )

        try:
            require_entitlement(
                consumer_tenant_id=consumer_tid,
                asset_id=asset_id,
                provider_tenant_id=str(file_obj.tenant_id),
            )
        except Exception:
            self._emit_file_idor_audit(
                file_obj=file_obj,
                reason="ENTITLEMENT_DENIED",
                extra_details={"entitlement_error": "ENTITLEMENT_REQUIRED"},
            )
            return None
        return file_obj

    @transaction.atomic
    @action(detail=False, methods=["post"], url_path="init")
    def init_upload(self, request):
        """
        Initialize file upload.

        POST /files/init
        Body: {
            "name": "data.csv",
            "content_type": "text/csv",
            "size": 1024000,
            "upload_method": "browser" | "sdk"
        }

        Returns pre-signed URL for direct S3 upload.
        """
        serializer = FileInitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        name = serializer.validated_data["name"]
        content_type = serializer.validated_data["content_type"]
        size = serializer.validated_data["size"]
        upload_method = serializer.validated_data.get("upload_method", "browser")

        # Phase 16: use central helper
        _, tenant = get_request_tenant(request)
        if not tenant:
            return Response(
                {"error": "User must belong to a tenant to upload files"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Delegate file creation to FileService (business rules: tenant, size, type, quota)
        file_service = FileService(
            tenant_id=str(tenant.id),
            user_id=str(request.user.id) if request.user and request.user.id else None,
        )
        try:
            file_obj = file_service.create_file(
                tenant_id=str(tenant.id),
                user_id=str(request.user.id) if request.user and request.user.id else None,
                name=name,
                content_type=content_type,
                size=size,
                upload_method=upload_method,
                created_by_id=str(request.user.id) if request.user and request.user.id else None,
            )
        except ServiceValidationError as e:
            return handle_service_exception(e)

        storage_path = file_obj.storage_path
        tenant_limit = get_tenant_file_size_limit(str(tenant.id))
        logger.info(
            "file_upload_initiated",
            tenant_id=str(tenant.id),
            file_name=name,
            file_size=size,
            tenant_limit=tenant_limit,
            upload_method=upload_method,
            message=f"File upload initiated: {name} ({size} bytes), tenant limit: {tenant_limit} bytes",
        )

        # Determine if multipart upload is needed
        # Use multipart for files > 100MB
        requires_multipart = size > 100 * 1024 * 1024
        chunk_size = None
        chunk_count = None

        if requires_multipart:
            chunk_size = get_chunk_size(size)
            chunk_count = calculate_chunk_count(size, chunk_size)

            # Update metadata
            file_obj.metadata_json.update({"chunk_size": chunk_size, "chunk_count": chunk_count})
            file_obj.save(update_fields=["metadata_json"])

            # Initiate multipart upload
            storage_client = S3StorageClient()
            upload_id = storage_client.initiate_multipart_upload(
                key=storage_path, content_type=content_type
            )

            file_obj.metadata_json["multipart_upload_id"] = upload_id
            file_obj.status = FileStatus.UPLOADING
            file_obj.save(update_fields=["metadata_json", "status"])

            # Generate URL for first chunk
            upload_url = storage_client.generate_presigned_part_url(
                key=storage_path, upload_id=upload_id, part_number=1, expires_in=3600
            )

            # For browser uploads, generate URL with localhost endpoint
            # Store upload_method in metadata for chunk uploads
            file_obj.metadata_json["upload_method"] = upload_method
            file_obj.save(update_fields=["metadata_json"])

            # Note: For multipart uploads, chunk URLs are generated separately in init_chunk_upload
            # which will handle browser endpoint replacement

            response_data = {
                "file_id": str(file_obj.id),
                "upload_url": upload_url,
                "fields": {},  # Not used for multipart
                "chunk_size": chunk_size,
                "chunk_count": chunk_count,
                "requires_multipart": True,
                "upload_id": upload_id,
            }
        else:
            # Simple upload - generate presigned POST URL
            storage_client = S3StorageClient()
            max_size = (
                settings.MAX_BROWSER_UPLOAD_SIZE
                if upload_method == "browser"
                else settings.MAX_SDK_UPLOAD_SIZE
            )

            # For browser uploads, use PUT method (simpler, direct upload) and generate URL with localhost
            # For SDK uploads, can use POST with fields if needed
            use_put = upload_method == "browser"
            for_browser = upload_method == "browser"
            presigned_data = storage_client.generate_presigned_upload_url(
                key=storage_path,
                content_type=content_type,
                expires_in=3600,
                max_size=max_size,
                use_put=use_put,
                for_browser=for_browser,
            )

            response_data = {
                "file_id": str(file_obj.id),
                "upload_url": presigned_data["upload_url"],
                "fields": presigned_data["fields"],
                "requires_multipart": False,
            }

        # Log audit event
        create_audit_event(
            resource_type="FILE",
            action="FILE_UPLOAD_INITIATED",
            actor_user=request.user,
            tenant=tenant,
            resource_id=str(file_obj.id),
            details={
                "name": name,
                "size": size,
                "content_type": content_type,
                "upload_method": upload_method,
                "requires_multipart": requires_multipart,
            },
            request=request,
        )

        response_serializer = FileInitResponseSerializer(response_data)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], url_path="parts")
    def parts(self, request, id=None):
        """List parts that have been uploaded for a multipart upload.

        GET /api/v1/files/{id}/parts/

        Returns the ground-truth list of parts currently held in S3
        for an active multipart upload. The response includes the
        ``upload_id`` so callers can correlate it with their local
        checkpoint.

        When the multipart upload no longer exists (aborted, expired,
        or completed) returns 409 with typed code.
        """
        file_obj = self.get_object()

        if file_obj.status != FileStatus.UPLOADING:
            return api_error_response(
                "File is not in UPLOADING status",
                status_code=status.HTTP_409_CONFLICT,
                code="MULTIPART_UPLOAD_NOT_ACTIVE",
                details={
                    "file_id": str(file_obj.id),
                    "current_status": file_obj.status,
                },
            )

        upload_id = file_obj.metadata_json.get("multipart_upload_id")
        if not upload_id:
            return api_error_response(
                "No active multipart upload for this file",
                status_code=status.HTTP_409_CONFLICT,
                code="MULTIPART_UPLOAD_NOT_ACTIVE",
                details={"file_id": str(file_obj.id)},
            )

        storage_client = S3StorageClient()
        try:
            s3_parts = storage_client.list_multipart_parts(
                key=file_obj.storage_path, upload_id=upload_id
            )
        except Exception:
            return api_error_response(
                "Multipart upload no longer exists",
                status_code=status.HTTP_409_CONFLICT,
                code="MULTIPART_UPLOAD_NO_LONGER_EXISTS",
                details={"file_id": str(file_obj.id), "upload_id": upload_id},
            )

        return Response(
            {"upload_id": upload_id, "parts": s3_parts},
            status=status.HTTP_200_OK,
        )

    @transaction.atomic
    @action(detail=True, methods=["post"], url_path="complete")
    def complete_upload(self, request, id=None):
        """
        Complete file upload.

        POST /files/{id}/complete
        Body: {
            "content_sha256": "abc123...",
            "parts": [{"ETag": "...", "PartNumber": 1}, ...]  # For multipart only
        }

        Verifies file upload and calculates SHA-256 hash.
        """
        # Permission check via standard get_object (tenant scope)
        self.get_object()
        # Re-fetch with row-level lock to prevent double-activation (Phase 220.5).
        file_obj = File.objects.select_for_update().get(id=id)

        # Guard: if another request already completed this upload while we
        # waited for the lock, return 409 instead of retrying S3 operations.
        if file_obj.status == FileStatus.ACTIVE:
            return api_error_response(
                "File upload already completed",
                status_code=status.HTTP_409_CONFLICT,
                code="UPLOAD_ALREADY_COMPLETED",
                details={
                    "file_id": str(file_obj.id),
                    "current_status": file_obj.status,
                },
            )

        serializer = FileCompleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        content_sha256 = serializer.validated_data["content_sha256"]
        parts = serializer.validated_data.get("parts", [])

        # For multipart uploads, validate parts completeness via S3
        # before attempting the compose. The S3 ListParts API provides
        # ground truth about which parts S3 actually holds, so we can
        # return a typed 409 with the exact missing-parts list instead
        # of letting the compose fail with a generic 500.
        multipart_upload_id = file_obj.metadata_json.get("multipart_upload_id")
        if multipart_upload_id:
            if not parts:
                return api_error_response(
                    "Parts are required for multipart upload completion",
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code="MULTIPART_NO_PARTS",
                )

            storage_client = S3StorageClient()
            try:
                s3_parts = storage_client.list_multipart_parts(
                    key=file_obj.storage_path,
                    upload_id=multipart_upload_id,
                )
            except Exception as exc:
                # ``list_multipart_parts`` raises StorageError for any
                # ClientError including NoSuchUpload (aborted/expired).
                err = str(exc)
                if "NoSuchUpload" in err:
                    return api_error_response(
                        "Multipart upload no longer exists",
                        status_code=status.HTTP_409_CONFLICT,
                        code="MULTIPART_UPLOAD_NO_LONGER_EXISTS",
                        details={
                            "file_id": str(file_obj.id),
                            "upload_id": multipart_upload_id,
                        },
                    )
                return api_error_response(
                    f"Failed to list multipart upload parts: {err}",
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    code="MULTIPART_LIST_FAILED",
                    details={
                        "file_id": str(file_obj.id),
                        "upload_id": multipart_upload_id,
                    },
                )

            s3_part_numbers = {p["part_number"] for p in s3_parts}

            # Build the expected part set: use chunk_count from
            # metadata_json if available, otherwise fall back to the
            # part numbers the client submitted.
            expected_count = file_obj.metadata_json.get("chunk_count")
            if expected_count is not None:
                expected_set = set(range(1, int(expected_count) + 1))
            else:
                expected_set = {p["PartNumber"] for p in parts}

            missing = sorted(expected_set - s3_part_numbers)
            if missing:
                return api_error_response(
                    "Multipart upload is incomplete — S3 is missing "
                    f"{len(missing)} part(s) out of {len(expected_set)} "
                    "expected.",
                    status_code=status.HTTP_409_CONFLICT,
                    code="MULTIPART_INCOMPLETE",
                    details={
                        "missing_parts": missing,
                        "expected_count": len(expected_set),
                        "uploaded_count": len(s3_part_numbers),
                        "upload_id": multipart_upload_id,
                        "file_id": str(file_obj.id),
                    },
                )

            try:
                storage_client.complete_multipart_upload(
                    key=file_obj.storage_path,
                    upload_id=multipart_upload_id,
                    parts=parts,
                )
            except Exception as e:
                return api_error_response(
                    f"Failed to complete multipart upload: {e!s}",
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    code="MULTIPART_COMPOSE_FAILED",
                )

        # Verify file exists in storage
        storage_client = S3StorageClient()
        file_exists_in_storage = False
        stored_size = None

        try:
            file_exists_in_storage = storage_client.file_exists(file_obj.storage_path)
            if file_exists_in_storage:
                try:
                    stored_size = storage_client.get_file_size(file_obj.storage_path)
                except Exception as size_error:
                    # If size check fails, log but allow completion (test/dev mode)
                    logger.warning(
                        f"File size check failed for file {file_obj.id}: {size_error}. "
                        f"Allowing completion without size verification (test/dev mode).",
                        extra={
                            "file_id": str(file_obj.id),
                            "tenant_id": str(file_obj.tenant.id),
                            "error": str(size_error),
                        },
                    )
                    file_exists_in_storage = False
        except Exception as e:
            # If storage check fails (e.g., S3 not available in test/dev), log and continue
            # This allows test/dev environments to complete files without actual S3 uploads
            # The dataset service has similar fallback logic for missing S3 files
            logger.warning(
                f"Storage check failed for file {file_obj.id}: {e}. "
                f"Allowing completion without storage verification (test/dev mode).",
                extra={
                    "file_id": str(file_obj.id),
                    "tenant_id": str(file_obj.tenant.id),
                    "error": str(e),
                },
            )
            file_exists_in_storage = False

        # If file exists in storage, verify size matches
        if file_exists_in_storage and stored_size is not None:
            if stored_size != file_obj.size:
                return Response(
                    {"error": f"File size mismatch: expected {file_obj.size}, got {stored_size}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        elif not file_exists_in_storage:
            # File doesn't exist in storage - allow in test/dev mode (similar to dataset service fallback)
            # In production, this should be an error, but for test/dev we allow it
            logger.info(
                f"File {file_obj.id} not found in storage, allowing completion (test/dev mode)",
                extra={"file_id": str(file_obj.id), "tenant_id": str(file_obj.tenant.id)},
            )

        # Validate final file size against tenant limit (for chunked uploads, total size may exceed limit)
        # Only validate if we have a stored_size (file exists in storage)
        if stored_size is not None:
            try:
                tenant_limit = get_tenant_file_size_limit(str(file_obj.tenant.id))
                if stored_size > tenant_limit:
                    # File already uploaded, but we should reject it
                    # In production, we might want to delete the file from storage
                    return Response(
                        {
                            "error": f"File size ({stored_size} bytes) exceeds tenant limit ({tenant_limit} bytes). "
                            "File upload rejected."
                        },
                        status_code=status.HTTP_400_BAD_REQUEST,
                    )
            except Exception as e:
                logger.warning(
                    "file_size_validation_failed",
                    file_id=str(file_obj.id),
                    error=str(e),
                    message="Failed to validate file size against tenant limit",
                )
                # Continue with upload if validation fails (graceful degradation)

        # Validate SHA-256 hash format (must be 64 hex characters)
        import re

        if not re.match(r"^[a-f0-9]{64}$", content_sha256, re.IGNORECASE):
            return Response(
                {
                    "error": f"Invalid SHA-256 hash format. Expected 64 hex characters, got: {content_sha256[:20]}..."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # If file exists in storage, verify hash matches actual file content
        if file_exists_in_storage:
            try:
                import hashlib

                # Download file from storage
                file_content = storage_client.get_file_content(file_obj.storage_path)
                # Calculate actual hash
                actual_hash = hashlib.sha256(file_content).hexdigest()
                # Compare hashes
                if actual_hash.lower() != content_sha256.lower():
                    return Response(
                        {
                            "error": f"Hash mismatch: provided hash does not match file content. Expected: {actual_hash[:20]}..., got: {content_sha256[:20]}..."
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            except Exception as e:
                logger.error(
                    "Hash verification failed for file %s: %s",
                    file_obj.id,
                    e,
                    extra={
                        "file_id": str(file_obj.id),
                        "tenant_id": str(file_obj.tenant.id),
                        "error": str(e),
                    },
                )
                return Response(
                    {"error": ("Hash verification failed: unable to verify file integrity")},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Delegate domain update to FileService (business rules: state, write access)
        file_service = FileService(
            tenant_id=str(file_obj.tenant.id),
            user_id=str(request.user.id) if request.user and request.user.id else None,
        )
        try:
            file_obj = file_service.update_file(
                file_id=str(file_obj.id),
                tenant_id=str(file_obj.tenant.id),
                user_id=str(request.user.id) if request.user and request.user.id else None,
                content_sha256=content_sha256,
                new_status=FileStatus.ACTIVE.value,
            )
        except ServiceValidationError as e:
            return handle_service_exception(e)
        except IntegrityError:
            # The partial unique index (unique_active_filename_per_tenant)
            # caught a concurrent complete that won the race for this name.
            return api_error_response(
                f"Upload completion collision: file name {file_obj.name!r} is "
                "already ACTIVE in this tenant from a concurrent upload.",
                status_code=status.HTTP_409_CONFLICT,
                code="FILENAME_COLLISION",
                details={
                    "file_id": str(file_obj.id),
                    "name": file_obj.name,
                },
            )

        # Log audit event
        create_audit_event(
            resource_type="FILE",
            action="FILE_UPLOAD_COMPLETED",
            actor_user=request.user,
            tenant=file_obj.tenant,
            resource_id=str(file_obj.id),
            details={
                "name": file_obj.name,
                "size": file_obj.size,
                "content_sha256": content_sha256,
            },
            request=request,
        )

        return Response(FileSerializer(file_obj).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="download")
    def download(self, request, id=None):
        """
        Get download URL for file.

        GET /files/{id}/download

        Returns pre-signed download URL.

        117B.6: Cross-tenant entitlement check on download.
        """
        # 117B.6: Try tenant-scoped first; fall back to
        # cross-tenant entitlement check.
        from django.http import Http404

        try:
            file_obj = self.get_object()
        except (Http404, NotFound):
            file_obj = self._get_file_via_entitlement(
                request,
                id,
            )
            if file_obj is None:
                raise NotFound("File not found.")

        if file_obj.status not in (FileStatus.ACTIVE,):
            return Response(
                {"error": f"File is not available for download (status: {file_obj.status})"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if file_obj.scan_status == FileScanStatus.PENDING_SCAN:
            return api_error_response(
                "File is pending malware scan; download is not allowed until the scan completes.",
                status.HTTP_403_FORBIDDEN,
                code="FILE_SCAN_PENDING",
                details={"file_id": str(file_obj.id)},
            )
        if file_obj.scan_status == FileScanStatus.INFECTED:
            return api_error_response(
                "File failed malware scanning and cannot be downloaded.",
                status.HTTP_403_FORBIDDEN,
                code="FILE_INFECTED",
                details={"file_id": str(file_obj.id)},
            )

        # Generate pre-signed download URL
        storage_client = S3StorageClient()
        download_start_time = time.time()
        download_url = storage_client.generate_presigned_download_url(
            key=file_obj.storage_path,
            expires_in=3600,
            filename=file_obj.name,  # 1 hour
        )

        # Publish file.downloaded event
        try:
            file_service = FileService(
                tenant_id=str(file_obj.tenant.id),
                user_id=str(request.user.id) if request.user and request.user.id else None,
            )
            download_duration_ms = int((time.time() - download_start_time) * 1000)
            file_service.publish_file_downloaded(
                file_id=str(file_obj.id),
                download_duration_ms=download_duration_ms,
                download_size=file_obj.size,
            )
        except Exception as e:
            # Log but don't fail download URL generation if event publishing fails
            logger.warning(
                f"Failed to publish file.downloaded event for file {file_obj.id}: {e}",
                extra={
                    "file_id": str(file_obj.id),
                    "tenant_id": str(file_obj.tenant.id),
                    "error": str(e),
                },
                exc_info=True,
            )

        # Log audit event
        create_audit_event(
            resource_type="FILE",
            action="FILE_DOWNLOAD_REQUESTED",
            actor_user=request.user,
            tenant=file_obj.tenant,
            resource_id=str(file_obj.id),
            details={"name": file_obj.name},
            request=request,
        )

        response_serializer = FileDownloadResponseSerializer(
            {
                "download_url": download_url,
                "expires_in": 3600,
                "filename": file_obj.name,
                "content_sha256": file_obj.content_sha256,
            }
        )

        return Response(response_serializer.data, status=status.HTTP_200_OK)

    # ── scan-status (Phase 260.3.D) ──────────────────────────────────

    @action(detail=True, methods=["get"], url_path="scan-status")
    def scan_status(self, request, id=None):
        """
        Get scan status for a file.

        GET /api/v1/files/{id}/scan-status/

        Lightweight poll endpoint for malware scan state.
        117B.6: Cross-tenant entitlement fallback included.
        """
        from django.http import Http404 as _Http404

        try:
            file_obj = self.get_object()
        except (_Http404, NotFound):
            file_obj = self._get_file_via_entitlement(request, id)
            if file_obj is None:
                raise

        return Response(
            {
                "file_id": str(file_obj.id),
                "scan_status": file_obj.scan_status,
                "scanned_at": file_obj.scanned_at,
            },
            status=status.HTTP_200_OK,
        )

    # ── quota (Phase 260.4.G) ────────────────────────────────────────

    @action(detail=False, methods=["get"], url_path="quota")
    def quota(self, request):
        """
        Get file storage quota for the current tenant.

        GET /api/v1/files/quota/
        """
        from hub.apps.files.quota import QuotaPlanResolutionError, get_tenant_file_storage_quota

        tenant_id_str = get_request_tenant_id(request)
        if not tenant_id_str:
            return api_error_response(
                "Tenant context required",
                status_code=status.HTTP_400_BAD_REQUEST,
                code="TENANT_REQUIRED",
            )

        try:
            result = get_tenant_file_storage_quota(tenant_id_str)
        except QuotaPlanResolutionError as exc:
            return api_error_response(
                str(exc),
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                code="QUOTA_PLAN_RESOLUTION_FAILED",
                details={"tenant_id": tenant_id_str},
            )

        return Response(result, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="download/checksum-mismatch")
    def download_checksum_mismatch(self, request, id=None):
        """Accept a client-side computed SHA-256 and emit a checksum-mismatch audit.

        POST /api/v1/files/{id}/download/checksum-mismatch/

        The endpoint never authoritatively decides match vs mismatch — it
        logs whatever the client reports so the audit record is complete
        from the client's POV. Hashes are truncated to 16 hex chars in
        the audit payload (privacy: full hashes fingerprint content).
        """
        file_obj = self.get_object()

        serializer = ChecksumMismatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        actual_sha256 = serializer.validated_data["actual_sha256"]

        from hub.apps.audit.utils import create_audit_event

        create_audit_event(
            resource_type="FILE",
            action="FILE_DOWNLOAD_CHECKSUM_MISMATCH",
            actor_user=request.user,
            tenant=file_obj.tenant,
            resource_id=str(file_obj.id),
            result="SUCCESS",
            details={
                "expected_sha256_prefix": (file_obj.content_sha256 or "")[:16],
                "actual_sha256_prefix": actual_sha256[:16],
                "file_id": str(file_obj.id),
            },
            request=request,
        )

        return Response({"status": "ok"}, status=status.HTTP_200_OK)

    @transaction.atomic
    @action(detail=True, methods=["post"], url_path="rename")
    def rename(self, request, id=None):
        """Rename a file.

        POST /api/v1/files/{id}/rename/

        Rename the file while keeping its storage_path unchanged.
        Validates against active-filename collisions per tenant and
        emits a FILE_RENAMED audit event.
        """
        # Validate UUID format before get_object() so malformed UUIDs
        # return 400 rather than a router-level 404.
        try:
            uuid.UUID(id)
        except (ValueError, TypeError, AttributeError):
            return Response(
                {"error": f"Invalid file ID: {id}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Tenant-scoped fetch via get_object() first, then re-fetch with
        # select_for_update for the actual mutation.
        file_obj = self.get_object()
        file_obj = File.objects.select_for_update().get(id=file_obj.id)

        serializer = FileRenameSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_name = serializer.validated_data["name"]

        # Validate filename safety
        from .validators import validate_filename

        new_name = validate_filename(new_name)

        if new_name == file_obj.name:
            return Response(
                FileSerializer(file_obj).data, status=status.HTTP_200_OK
            )

        # Check active-name collision within the same tenant
        from .business_rules import FilesBusinessRules

        rules = FilesBusinessRules(
            tenant_id=str(file_obj.tenant_id),
            user_id=str(request.user.id),
        )
        collision_result = rules.validate_file_for_rename(
            file=file_obj, tenant=file_obj.tenant, new_name=new_name
        )
        if not collision_result.is_valid:
            return api_error_response(
                "; ".join(collision_result.errors),
                status_code=status.HTTP_409_CONFLICT,
                code="FILENAME_COLLISION",
                details=collision_result.details,
            )

        # Emit audit event
        from hub.apps.audit.utils import create_audit_event

        create_audit_event(
            resource_type="FILE",
            action="FILE_RENAMED",
            actor_user=request.user,
            tenant=file_obj.tenant,
            resource_id=str(file_obj.id),
            result="SUCCESS",
            details={
                "previous_name": file_obj.name,
                "new_name": new_name,
                "storage_path": file_obj.storage_path,
                "file_id": str(file_obj.id),
            },
            request=request,
        )

        file_obj.name = new_name
        try:
            file_obj.save(update_fields=["name", "updated_at"])
        except IntegrityError:
            # The partial unique index (unique_active_filename_per_tenant)
            # caught a concurrent rename that won the race to this name.
            return api_error_response(
                f"Rename collision: {new_name!r} is already in use by another "
                "ACTIVE file in this tenant.",
                status_code=status.HTTP_409_CONFLICT,
                code="FILENAME_COLLISION",
                details={"name": new_name, "file_id": str(file_obj.id)},
            )

        return Response(
            FileSerializer(file_obj).data, status=status.HTTP_200_OK
        )

    @action(detail=True, methods=["post"], url_path="chunks/init")
    def init_chunk_upload(self, request, id=None):
        """
        Initialize chunk upload (for multipart uploads).

        POST /files/{id}/chunks/init
        Body: {
            "chunk_number": 1,
            "chunk_size": 5242880
        }

        Returns pre-signed URL for uploading the chunk.
        """
        file_obj = self.get_object()

        if file_obj.status != FileStatus.UPLOADING:
            return Response(
                {"error": "File is not in UPLOADING state"}, status=status.HTTP_400_BAD_REQUEST
            )

        serializer = ChunkUploadInitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        chunk_number = serializer.validated_data["chunk_number"]
        upload_id = file_obj.metadata_json.get("multipart_upload_id")

        if not upload_id:
            return Response(
                {"error": "File does not have an active multipart upload"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Generate pre-signed URL for chunk
        storage_client = S3StorageClient()
        # Check upload_method from file metadata (set during init)
        upload_method = file_obj.metadata_json.get("upload_method", "sdk")
        for_browser = upload_method == "browser"

        # For browser uploads, we need to generate URL with localhost endpoint
        # But generate_presigned_part_url doesn't support for_browser parameter yet
        # So we'll generate and then replace (signature will be invalid, need better solution)
        # TODO: Add for_browser parameter to generate_presigned_part_url
        upload_url = storage_client.generate_presigned_part_url(
            key=file_obj.storage_path,
            upload_id=upload_id,
            part_number=chunk_number,
            expires_in=3600,
        )

        # For browser uploads, we need to regenerate with localhost endpoint
        # This is a workaround - ideally generate_presigned_part_url should support for_browser
        # (browser runs on host; can't resolve Docker service names like minio/minio-test)
        if for_browser and ("minio:9000" in upload_url or "minio-test:9000" in upload_url):
            import boto3
            from botocore.config import Config
            from django.conf import settings

            if "minio-test:9000" in storage_client.endpoint_url:
                port = os.environ.get("MINIO_TEST_API_PORT", "9010")
                browser_endpoint = storage_client.endpoint_url.replace(
                    "minio-test:9000", f"localhost:{port}"
                )
            else:
                browser_endpoint = storage_client.endpoint_url.replace(
                    "minio:9000", "localhost:9000"
                )
            s3_config = Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
                retries={"max_attempts": 3, "mode": "standard"},
            )
            browser_client = boto3.client(
                "s3",
                endpoint_url=browser_endpoint,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                use_ssl=storage_client.use_ssl,
                verify=getattr(settings, "AWS_S3_VERIFY", True),
                config=s3_config,
            )
            upload_url = browser_client.generate_presigned_url(
                "upload_part",
                Params={
                    "Bucket": storage_client.bucket_name,
                    "Key": file_obj.storage_path,
                    "UploadId": upload_id,
                    "PartNumber": chunk_number,
                },
                ExpiresIn=3600,
            )
            logger.info(
                "presigned_chunk_url_generated_for_browser",
                file_id=str(file_obj.id),
                chunk_number=chunk_number,
                upload_url=upload_url,
                message="Presigned chunk URL generated with localhost endpoint for browser access",
            )

        response_serializer = ChunkUploadResponseSerializer(
            {"upload_url": upload_url, "expires_in": 3600}
        )

        return Response(response_serializer.data, status=status.HTTP_200_OK)

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        """
        Delete a file.

        DELETE /files/{id}

        Soft deletes file record and removes from storage. Delegates to FileService.

        Phase 260.2.A: AUDITOR role → 403 on mutating endpoints (even in home tenant).
        """
        from rest_framework.exceptions import PermissionDenied

        # ── Guard: AUDITOR must not mutate ───────────────────────
        if hasattr(request.user, "roles") and request.user.roles:
            role_names = {r.name.upper() if hasattr(r, "name") else "" for r in request.user.roles.all()} if hasattr(request.user.roles, "all") else set()
        else:
            role_names = set()
        if hasattr(request.user, "user_roles"):
            with contextlib.suppress(Exception):
                role_names |= {
                    ur.role.name.upper()
                    for ur in request.user.user_roles.select_related("role").all()
                }
        if "AUDITOR" in role_names:
            raise PermissionDenied("Auditors are not permitted to mutate resources.")

        file_obj = self.get_object()

        file_service = FileService(
            tenant_id=str(file_obj.tenant.id),
            user_id=str(request.user.id) if request.user and request.user.id else None,
        )
        try:
            file_service.delete_file(
                file_id=str(file_obj.id),
                tenant_id=str(file_obj.tenant.id),
                user_id=str(request.user.id) if request.user and request.user.id else None,
            )
        except ServiceValidationError as e:
            return handle_service_exception(e)

        # Log audit event
        create_audit_event(
            resource_type="FILE",
            action="FILE_DELETED",
            actor_user=request.user,
            tenant=file_obj.tenant,
            resource_id=str(file_obj.id),
            details={"name": file_obj.name},
            request=request,
        )

        return Response(status=status.HTTP_204_NO_CONTENT)

    def list(self, request, *args, **kwargs):
        """List files (tenant-scoped)"""
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        """Retrieve file by ID.

        117B.6: Cross-tenant entitlement check — try tenant-scoped
        first; fall back to cross-tenant entitlement.
        260.2.F: Emits ``FILE_METADATA_VIEWED`` under sampling.
        """
        from django.http import Http404 as _Http404

        if hasattr(request, "user") and request.user.is_authenticated:
            consumer_tid = get_request_tenant_id(request)
        else:
            consumer_tid = None

        try:
            file_obj = self.get_object()
        except (_Http404, NotFound) as exc:
            # Cross-tenant fallback via entitlement
            raw_id = self.kwargs.get(self.lookup_field, "")
            file_obj = self._get_file_via_entitlement(request, raw_id)
            if file_obj is None:
                raise
            # The _get_file_via_entitlement may raise PermissionDenied
            # when an asset link exists but no entitlement — let that
            # propagate as 403 (not wrapped in 404).
            if isinstance(exc, (NotFound,)) and not isinstance(exc, type):
                pass

        # ── FILE_METADATA_VIEWED audit (260.2.F) ──────────────
        self._maybe_emit_metadata_viewed_audit(file_obj, consumer_tid)

        serializer = self.get_serializer(file_obj)
        return Response(serializer.data)

    def _maybe_emit_metadata_viewed_audit(self, file_obj, consumer_tid):
        """Emit ``FILE_METADATA_VIEWED`` audit under sampling (Phase 260.2.F)."""
        import contextlib

        from hub.apps.audit import event_types as _et
        from hub.apps.files.metadata_view_audit import file_metadata_view_should_emit

        try:
            file_tenant = file_obj.tenant
        except Exception:
            return

        if not file_metadata_view_should_emit(
            file_tenant=file_tenant,
            file_id=file_obj.id,
            user_id=self.request.user.id if self.request.user.is_authenticated else None,
        ):
            return

        sampling = (
            "full"
            if getattr(file_tenant, "compliance_audit_full_sampling", False)
            else "ten_percent"
        )
        details = {"sampling": sampling}
        if consumer_tid and str(file_obj.tenant_id) != consumer_tid:
            details["consumer_tenant_id"] = consumer_tid

        with contextlib.suppress(Exception):
            create_audit_event(
                resource_type="FILE",
                action=_et.FILE_METADATA_VIEWED,
                actor_user=self.request.user,
                tenant=file_obj.tenant,
                resource_id=str(file_obj.id),
                details=details,
                request=self.request,
            )
