"""
Dataset Views

REST API views for dataset creation and retrieval.
All create/update/destroy/version creation delegate to DatasetService,
which invokes DatasetsBusinessRules before mutations.
"""

import uuid

from django.db import transaction
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from hub.apps.audit.event_types import (
    DATASET_REFRESH_TRIGGERED,
    DATASET_REFRESHED_FROM_FILE,
    DATASET_RETIRED,
    DATASET_VERSION_COMPARED,
)
from hub.apps.audit.utils import create_audit_event
from hub.apps.api.standards.pagination import StandardCursorPagination
from hub.apps.core.responses import api_error_response, handle_service_exception
from hub.apps.core.services.base import NotFoundError
from hub.apps.core.services.base import ValidationError as ServiceValidationError
from hub.apps.auth.serializers import get_user_permissions
from hub.apps.tenants.kill_switch_gates import ensure_tenant_datasets_api_allowed
from hub.apps.tenants.request_tenant import get_request_tenant, get_request_tenant_id

from .caching import (
    cache_dataset_detail,
    cache_dataset_list,
    get_cached_dataset_detail,
    get_cached_dataset_list,
    get_tenant_id_from_request,
    hash_filters,
    invalidate_dataset_caches,
    invalidate_dataset_detail_cache,
    invalidate_dataset_list_cache,
)
from .models import Dataset, DatasetStatus, SchemaVersion
from .serializers import (
    DatasetCreateSerializer,
    DatasetManualRefreshResponseSerializer,
    DatasetRefreshFromFileResponseSerializer,
    DatasetRefreshFromFileSerializer,
    DatasetSerializer,
    DatasetVersionCreateSerializer,
    DatasetVersionSerializer,
    SchemaVersionCompareSerializer,
)
from .services import DatasetService
from .sample_pii_redaction import redact_sample_rows


def _truthy_query_param(raw: str | None) -> bool:
    if raw is None:
        return False
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _dataset_version_in_anchor_lineage(anchor: Dataset, version: Dataset) -> bool:
    """
    True when ``version`` is included in GET /datasets/{anchor}/versions/.

    Mirrors the branching in ``DatasetViewSet.versions`` so compare and schema-evolution
    cannot compare arbitrary tenant datasets under an unrelated anchor URL.
    """
    if anchor.asset_id is not None:
        return version.asset_id == anchor.asset_id
    if anchor.file_id is not None:
        return version.file_id == anchor.file_id
    return version.id == anchor.id


class DatasetViewSet(viewsets.ModelViewSet):
    """
    ViewSet for dataset management.

    Tenant-scoped: users can only see/manage datasets in their tenant.
    List supports: search (file name, format), filter (asset_id, dataset_format), ordering.
    Uses dataset_format (not format) to avoid conflict with DRF's reserved ?format= for content negotiation.
    """

    queryset = Dataset.objects.all()
    serializer_class = DatasetSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "id"
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["file__name", "format"]
    ordering_fields = ["created_at", "updated_at", "format"]
    ordering = ["-created_at"]

    def initial(self, request, *args, **kwargs):
        ensure_tenant_datasets_api_allowed(request)
        super().initial(request, *args, **kwargs)

    def get_queryset(self):
        """Filter queryset based on user permissions and query params (29.69.2)."""
        user = self.request.user
        if hasattr(user, "is_platform_admin") and user.is_platform_admin:
            qs = Dataset.objects.all()
        else:
            tenant_id_str = get_request_tenant_id(self.request)
            if not tenant_id_str:
                return Dataset.objects.none()
            qs = Dataset.objects.filter(tenant_id=tenant_id_str)
        # Apply asset_id filter (picker support); validate UUID to avoid 500 on invalid input
        asset_id = self.request.query_params.get("asset_id")
        if asset_id:
            try:
                uuid.UUID(str(asset_id))
                qs = qs.filter(asset_id=asset_id)
            except (ValueError, TypeError, AttributeError):
                return Dataset.objects.none()
        # Apply format filter (?dataset_format=CSV/JSON; avoid ?format= which DRF reserves for content negotiation)
        format_val = self.request.query_params.get("dataset_format")
        if format_val:
            qs = qs.filter(format=format_val)
        # Phase 260.4.A.3 — RETIRED datasets are hidden from list responses
        # by default (the customer-facing UI doesn't want to surface
        # tombstoned rows). Opt-in via ``?include_retired=true`` so the
        # frontend "Show retired" toggle and operator audits can still
        # enumerate them. Detail GETs (``retrieve``) and the retire
        # action itself MUST NOT be filtered — those need to load
        # retired rows for the 409-already-retired path to fire and
        # for the detail-page Retired badge to render.
        if self.action == "list":
            include_retired = _truthy_query_param(
                self.request.query_params.get("include_retired")
            )
            if not include_retired:
                qs = qs.exclude(status=DatasetStatus.RETIRED)
        # Avoid N+1: serializer uses asset.name and file for name/size_bytes;
        # latest_compliance_run uses compliance_runs.
        return qs.select_related("asset", "file").prefetch_related("compliance_runs")

    def _get_via_entitlement(self, request, dataset_id):
        """117B.5: Cross-tenant dataset access via entitlement.

        Returns Dataset if consumer has an ACTIVE entitlement
        for the dataset's asset; None otherwise (caller raises 404).
        Raises PermissionDenied only if entitlement is revoked/expired
        (consumer previously had access).
        """
        try:
            dataset = Dataset.objects.select_related(
                "asset", "file",
            ).prefetch_related("compliance_runs").get(id=dataset_id)
        except Dataset.DoesNotExist:
            return None

        if not dataset.asset_id:
            return None

        consumer_tenant_id = get_request_tenant_id(request)
        if not consumer_tenant_id:
            return None

        from django.core.exceptions import PermissionDenied
        from hub.apps.marketplace.entitlement_check import (
            require_entitlement,
        )
        try:
            require_entitlement(
                consumer_tenant_id=consumer_tenant_id,
                asset_id=str(dataset.asset_id),
                provider_tenant_id=str(dataset.tenant_id),
            )
        except PermissionDenied as exc:
            # For ENTITLEMENT_REQUIRED (never had access), return None so
            # the caller raises 404 — don't reveal the resource exists.
            # For revoked/expired entitlements, re-raise 403.
            detail = exc.args[0] if exc.args else {}
            code = detail.get("code", "") if isinstance(detail, dict) else ""
            if code == "ENTITLEMENT_REQUIRED":
                return None
            raise
        return dataset

    @extend_schema(
        request=DatasetCreateSerializer,
        responses={
            201: DatasetSerializer,
            400: OpenApiResponse(
                description=(
                    "Validation failure. Typed codes include "
                    "``FILE_NOT_READY_FOR_DATASET`` (Phase 260.5.B; file "
                    "not in ACTIVE state — Phase 260.6.A retired the "
                    "legacy ``COMPLETED`` value), "
                    "``FILE_ENCODING_UNSUPPORTED`` (Phase 260.5.D; charset "
                    "below confidence floor or BOM-less UTF-16), "
                    "``UNSUPPORTED_FILE_FORMAT`` (Phase 260.5.D.R1), "
                    "``EXTERNAL_REF_NOT_API_SETTABLE`` (Phase 260.6.C / "
                    "OQ260.3 — external clients cannot create "
                    "``kind=EXTERNAL_REF`` datasets; the federation "
                    "pipeline at Asset Phase 250.5 sets that value "
                    "server-side), and the umbrella "
                    "``BUSINESS_RULES_VALIDATION``."
                )
            ),
            413: OpenApiResponse(
                description=(
                    "``FILE_TOO_LARGE_FOR_INFERENCE`` (Phase 260.5.F) — "
                    "``File.size`` exceeds the schema-inference sanity "
                    "cap (``DATASET_INFERENCE_MAX_BYTES``, default 1 GB). "
                    "Files BELOW the cap but above the full-read "
                    "threshold are sample-inferred (text formats only); "
                    "ABOVE the cap, the gate fires before the storage "
                    "GET. ``details`` carries ``file_size``, "
                    "``max_bytes``, ``full_read_bytes``, ``sample_bytes``, "
                    "``file_format``, ``remediation``."
                )
            ),
        },
    )
    @transaction.atomic
    def create(self, request):
        """
        Create a dataset from a file with schema inference.

        POST /datasets
        Body: {
            "file_id": "uuid",
            "asset_id": "uuid" (optional),
            "file_handle_purpose": "primary" | "sample" | "schema_only"
                (optional; defaults to "primary" — Phase 260.5.A)
        }
        """
        serializer = DatasetCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        validated = dict(serializer.validated_data)
        file_id = validated["file_id"]
        asset_id = validated.get("asset_id")
        # Phase 260.5.A — disambiguates concurrent Dataset rows on
        # the same file. Defaults to ``primary`` so existing callers
        # that don't pass the field keep the previous one-File →
        # one-Dataset semantics.
        file_handle_purpose = validated.get("file_handle_purpose", "PRIMARY")

        # Phase 16: use central helper
        _, tenant = get_request_tenant(request)
        if not tenant:
            return Response(
                {"error": "User must belong to a tenant to create datasets"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from django.db import IntegrityError

        try:
            dataset = DatasetService().create_dataset(
                tenant_id=str(tenant.id),
                user_id=str(request.user.id) if request.user else "",
                file_id=str(file_id),
                asset_id=str(asset_id) if asset_id else None,
                file_handle_purpose=file_handle_purpose,
            )
        except NotFoundError as e:
            return handle_service_exception(e)
        except ServiceValidationError as e:
            return handle_service_exception(e)
        except IntegrityError as exc:
            # R1 audit GAP-A — concurrent creators may violate EITHER
            # the (tenant, file, file_handle_purpose) constraint OR
            # the (tenant, asset, version) constraint, depending on
            # which Postgres reports first when both fire on the
            # same INSERT (asset-linked POST with a same-file-and-
            # purpose collision). Both surface as 409 so the FE/SDK
            # gets a deterministic 409 regardless of constraint
            # ordering; the ``code`` field distinguishes the two
            # so consumers can act on either.
            err_str = str(exc)
            # Migration 0110 removed the unique partial index on
            # (tenant, file, file_handle_purpose).  This branch is
            # currently unreachable but retained as a forward-compat
            # guard — when application-level enforcement is re-added
            # (per the migration's stated intent) the handler is
            # already wired and won't need to be re-discovered.
            if "unique_dataset_file_purpose_per_tenant" in err_str:  # pragma: no cover
                return api_error_response(
                    message=(
                        "A dataset already exists for this file with the same "
                        "file_handle_purpose. Use a different purpose "
                        "(``sample`` / ``schema_only``) or update the "
                        "existing dataset."
                    ),
                    status_code=status.HTTP_409_CONFLICT,
                    code="DATASET_FILE_PURPOSE_CONFLICT",
                    details={
                        "file_id": str(file_id),
                        "file_handle_purpose": file_handle_purpose,
                    },
                )
            if "unique_dataset_version_per_asset" in err_str:
                # Concurrent creators racing on the same asset
                # computed the same auto-incremented version. The
                # FE / SDK retries with the new version cleanly.
                return api_error_response(
                    message=(
                        "A dataset already exists for this asset at the "
                        "computed version. Retry the request — the next "
                        "version counter will increment cleanly."
                    ),
                    status_code=status.HTTP_409_CONFLICT,
                    code="DATASET_VERSION_CONFLICT",
                    details={
                        "asset_id": str(asset_id) if asset_id else None,
                        "file_id": str(file_id),
                    },
                )
            raise

        try:
            invalidate_dataset_list_cache(str(tenant.id))
            # When the dataset is linked to an asset at creation time, the
            # asset's serialized `dataset_id` field changes (AssetSerializer
            # resolves it from obj.datasets). The asset detail cache must be
            # invalidated so the next GET /assets/{id}/ returns the new
            # dataset_id — parallel to the invalidation in AssetViewSet.attach_dataset.
            if asset_id:
                from hub.apps.assets.caching import invalidate_asset_detail_cache

                invalidate_asset_detail_cache(str(asset_id))
        except Exception as e:
            import logging

            logging.getLogger(__name__).warning(
                "Failed to invalidate cache after dataset creation: %s", e, exc_info=True
            )
        return Response(DatasetSerializer(dataset).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="include_retired",
                type=bool,
                location=OpenApiParameter.QUERY,
                required=False,
                description=(
                    "Phase 260.4.A.3 — when true, RETIRED datasets are "
                    "included in the response. Default false (retired "
                    "rows are excluded from the list view; the "
                    "frontend 'Show retired' toggle wires this through)."
                ),
            ),
            OpenApiParameter(
                name="asset_id",
                type=str,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Filter datasets by their parent asset UUID.",
            ),
            OpenApiParameter(
                name="dataset_format",
                type=str,
                location=OpenApiParameter.QUERY,
                required=False,
                description=(
                    "Filter by file format (CSV/JSON/PARQUET). The query "
                    "key is intentionally ``dataset_format`` rather than "
                    "``format`` because DRF reserves ``?format=`` for "
                    "content negotiation."
                ),
            ),
        ]
    )
    def list(self, request, *args, **kwargs):
        """
        List datasets (tenant-scoped) with caching.

        GET /api/v1/datasets/
        Query params: page, page_size, ordering, search, asset_id, dataset_format,
        include_retired, etc.
        """
        # Get tenant ID for cache key
        tenant_id = get_tenant_id_from_request(request)
        if not tenant_id:
            # No tenant - return empty result (handled by get_queryset)
            return super().list(request, *args, **kwargs)

        # Build filters hash from query parameters
        query_params = dict(request.query_params)
        # Remove pagination params for cache key (they don't affect the base query)
        query_params.pop("page", None)
        query_params.pop("page_size", None)
        filters_hash = hash_filters(query_params)

        # Try to get from cache
        cached_result = get_cached_dataset_list(tenant_id, filters_hash)
        if cached_result is not None:
            results, total_count = cached_result

            # Apply pagination to cached results
            page = self.paginate_queryset(results)
            if page is not None:
                # Use paginator's response
                response = self.get_paginated_response(page)
                # Update count in response
                if hasattr(response, "data") and isinstance(response.data, dict):
                    response.data["count"] = total_count
                return response

            # No pagination - return all results
            return Response({"results": results, "count": total_count})

        # Cache miss - execute query
        response = super().list(request, *args, **kwargs)

        # Cache the results
        if response.status_code == 200:
            try:
                # Extract results and count from paginated response
                if hasattr(response, "data") and isinstance(response.data, dict):
                    results = response.data.get("results", [])
                    total_count = response.data.get("count", len(results))
                else:
                    # Non-paginated response
                    results = response.data if isinstance(response.data, list) else []
                    total_count = len(results)

                # Cache the results
                cache_dataset_list(tenant_id, filters_hash, results, total_count)
            except Exception as e:
                # Log error but don't fail the request
                import logging

                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to cache dataset list: {e}", exc_info=True)

        return response

    def retrieve(self, request, *args, **kwargs):
        """
        Retrieve dataset by ID with caching.

        GET /api/v1/datasets/{id}/

        117B.5: Cross-tenant access allowed when consumer
        holds an ACTIVE entitlement for the dataset's asset.
        """
        dataset_id = str(kwargs.get("id", ""))

        # Validate UUID format early to return 400 instead of 500
        import uuid as _uuid
        try:
            _uuid.UUID(dataset_id)
        except (ValueError, AttributeError):
            return Response(
                {"detail": f'"{dataset_id}" is not a valid UUID.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Try to get from cache
        cached_data = get_cached_dataset_detail(dataset_id)
        if cached_data is not None:
            return Response(cached_data)

        # Cache miss - try tenant-scoped queryset first
        from django.http import Http404
        from rest_framework.exceptions import NotFound
        try:
            dataset = self.get_object()
        except (Http404, NotFound):
            # 117B.5: Fallback — cross-tenant entitlement
            dataset = self._get_via_entitlement(
                request, dataset_id,
            )
            if dataset is None:
                raise NotFound("Dataset not found.")

        # Set resource instance on request for cache headers middleware
        request._resource_instance = dataset

        response = super().retrieve(request, *args, **kwargs)

        # Cache the result
        if response.status_code == 200:
            try:
                dataset_data = response.data
                cache_dataset_detail(dataset_id, dataset_data)
            except Exception as e:
                # Log error but don't fail the request
                import logging

                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to cache dataset detail: {e}", exc_info=True)

        return response

    @action(detail=True, methods=["get"], url_path="sample")
    def sample(self, request, id=None):
        """
        Return pre-computed sample data rows from the dataset.

        GET /api/v1/datasets/{id}/sample/?limit=50

        Sample data is extracted during dataset creation and cached on the
        model (sample_data_json). No S3 access needed at read time.
        """
        dataset = self.get_object()
        if dataset.file_id is None or dataset.status == DatasetStatus.RETIRED:
            return Response(
                {"error_code": "DATASET_FILE_PURGED"},
                status=status.HTTP_410_GONE,
            )
        sample_data = dataset.sample_data_json or []

        # Optional limit parameter (default: return all stored rows, max 100)
        try:
            limit = int(request.query_params.get("limit", len(sample_data)))
        except (ValueError, TypeError):
            limit = len(sample_data)
        limit = min(limit, 100)  # Hard cap at 100 rows

        sliced = sample_data[:limit]

        tenant = dataset.tenant
        viewer_may_include_pii = False
        if request.user.is_authenticated:
            viewer_may_include_pii = "VIEW_PII" in get_user_permissions(request.user)

        include_pii_requested = _truthy_query_param(request.query_params.get("include_pii"))
        include_pii_effective = include_pii_requested and viewer_may_include_pii

        tenant_redacts_sample_pii = bool(getattr(tenant, "redact_sample_pii_in_ui", False))
        apply_redaction = tenant_redacts_sample_pii and not include_pii_effective

        payload_rows = list(sliced)
        if apply_redaction:
            payload_rows = redact_sample_rows(payload_rows)

        return Response(
            {
                "dataset_id": str(dataset.id),
                "format": dataset.format,
                "row_count": dataset.row_count,
                "sample_size": len(payload_rows),
                "sample_data": payload_rows,
                "tenant_redacts_sample_pii": tenant_redacts_sample_pii,
                "viewer_may_include_pii": viewer_may_include_pii,
                "sample_pii_redaction_applied": apply_redaction,
                "include_pii_effective": include_pii_effective,
            }
        )

    @action(detail=True, methods=["post"], url_path="retire")
    @transaction.atomic
    def retire(self, request, id=None):
        """
        Phase 260.4.A.1 — explicit dataset retirement.

        ``POST /datasets/{id}/retire/``

        State machine
        -------------
        * ``ACTIVE`` → flip to ``RETIRED`` + stamp ``retired_at``;
          emit ``DATASET_RETIRED`` audit; return 200 with the
          updated dataset payload.
        * ``RETIRED`` → 409 with code ``DATASET_ALREADY_RETIRED``
          (idempotent on the wire — repeated calls don't double-
          retire and don't double-audit).

        Concurrency
        -----------
        ``select_for_update`` inside the atomic block makes the read +
        write a single critical section so a second concurrent retire
        sees the row in ``RETIRED`` state and 409s rather than
        racing to a double audit emission.

        Tenant scope
        ------------
        ``self.get_object()`` filters by tenant via the queryset
        filter; cross-tenant calls 404. We deliberately do NOT apply
        the cross-tenant entitlement fallback here — retirement is a
        write-class lifecycle action that only the owner tenant can
        invoke.
        """
        from django.utils import timezone

        self._ensure_detail_lookup_uuid_safe(id)
        # First call resolves + tenant-checks via queryset.
        try:
            dataset = self.get_object()
        except NotFound:
            raise

        # Re-read inside the atomic block under row-level lock to
        # close the read-modify-write window.
        try:
            locked = (
                Dataset.objects.select_for_update()
                .get(id=dataset.id)
            )
        except Dataset.DoesNotExist:  # pragma: no cover — race shouldn't fire after get_object
            raise NotFound("Dataset not found.") from None

        if locked.status == DatasetStatus.RETIRED:
            return api_error_response(
                message="Dataset is already retired",
                status_code=status.HTTP_409_CONFLICT,
                code="DATASET_ALREADY_RETIRED",
                details={"dataset_id": str(locked.id)},
            )

        retired_at = timezone.now()
        locked.status = DatasetStatus.RETIRED
        locked.retired_at = retired_at
        locked.save(update_fields=["status", "retired_at", "updated_at"])

        retain_days = int(
            getattr(locked.tenant, "dataset_retain_after_retire_days", 90) or 90
        )
        from datetime import timedelta as _timedelta

        retain_until = retired_at + _timedelta(days=retain_days)

        audit_details = {
            "dataset_id": str(locked.id),
            "name": locked.file.name if locked.file_id else None,
            "format": locked.format,
            "asset_id": str(locked.asset_id) if locked.asset_id else None,
            "retain_until_at": retain_until.isoformat(),
        }
        create_audit_event(
            resource_type="DATASET",
            action=DATASET_RETIRED,
            actor_user=request.user,
            tenant=locked.tenant,
            resource_id=str(locked.id),
            details=audit_details,
            request=request,
        )

        # Cache invalidation: the list cache may include this row;
        # the detail cache definitely does. Failures here are non-
        # fatal (the data is durable on the row).
        try:
            invalidate_dataset_caches(str(locked.id), str(locked.tenant_id))
        except Exception:
            pass

        # Return the canonical serialised representation so the
        # client doesn't have to re-fetch.
        serializer = self.get_serializer(locked)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def _ensure_detail_lookup_uuid_safe(self, id_value):
        """Phase 260.4.A — defensive UUID validation for detail-class actions.

        Mirrors :meth:`FileViewSet._ensure_detail_lookup_uuid` so a
        malformed ``id`` returns 400 BAD_REQUEST instead of falling
        through to a 500 in the ORM. Local helper because the dataset
        viewset doesn't have its own equivalent yet.
        """
        try:
            uuid.UUID(str(id_value))
        except (ValueError, TypeError, AttributeError):
            raise DRFValidationError(
                {"error": {"code": "INVALID_DATASET_ID", "message": "Malformed dataset id."}}
            )

    @extend_schema(
        request=DatasetRefreshFromFileSerializer,
        responses={
            200: DatasetRefreshFromFileResponseSerializer,
            400: OpenApiResponse(
                description=(
                    "Validation failure: same typed codes the create "
                    "endpoint emits (``FILE_ENCODING_UNSUPPORTED``, "
                    "``UNSUPPORTED_FILE_FORMAT``, "
                    "``DATASET_REFRESH_REQUIRES_ASSET``, "
                    "``BUSINESS_RULES_VALIDATION``)."
                )
            ),
            409: OpenApiResponse(
                description=(
                    "Source dataset RETIRED "
                    "(``DATASET_RETIRED_REFRESH_NOT_ALLOWED``)."
                )
            ),
            413: OpenApiResponse(
                description=(
                    "``FILE_TOO_LARGE_FOR_INFERENCE`` (Phase 260.5.F) — "
                    "new backing file exceeds the schema-inference "
                    "sanity cap. Same shape as the create-endpoint "
                    "413."
                )
            ),
        },
        summary="Refresh dataset from a new file (creates a new version)",
        description=(
            "Phase 260.4.D — replace the bytes backing a dataset by "
            "uploading a new file. The endpoint creates a NEW dataset "
            "version with the same ``asset`` FK, the new ``file`` FK, "
            "and ``parent_version`` linked to the source dataset. Schema "
            "drift against any active contract on the asset is computed "
            "and returned in the response under ``schema_drift``."
        ),
    )
    @action(detail=True, methods=["post"], url_path="refresh-from-file")
    @transaction.atomic
    def refresh_from_file(self, request, id=None):
        """
        Phase 260.4.D — refresh-from-new-file workflow.

        ``POST /datasets/{id}/refresh-from-file/``
        Body: ``{"file_id": "<uploaded-file-uuid>"}``

        Pre-conditions
        --------------
        * Source dataset MUST be ACTIVE (RETIRED → 409
          ``DATASET_RETIRED_REFRESH_NOT_ALLOWED``).
        * Source dataset MUST have an asset link — refresh requires a
          version-chain anchor (no asset → 400
          ``DATASET_REFRESH_REQUIRES_ASSET``).
        * New file MUST live in the same tenant + be ACTIVE +
          have a CLEAN scan status (anything else → 400 with the
          specific reason code).

        Effect
        ------
        * Creates a new ``Dataset`` row via ``DatasetService.create_dataset``
          which auto-increments the per-asset version counter, sets
          ``parent_version`` to the latest existing dataset for the
          asset (= our source), and infers schema from the new file's
          bytes.
        * Computes drift against the asset's active contract (if any)
          via :func:`compute_dataset_contract_drift`.
        * Emits :data:`audit_event_types.DATASET_REFRESHED_FROM_FILE`
          with ``parent_dataset_id``, ``new_dataset_id``, ``new_file_id``,
          ``parent_file_id``, ``new_version``, ``asset_id``, AND a
          ``schema_drift`` summary so audit consumers can replay
          drift incidents without re-running the comparison.

        Response
        --------
        ``200`` with ``{"dataset": <DatasetSerializer>, "schema_drift": <drift>}``.
        """
        from hub.apps.datasets.contract_drift import compute_dataset_contract_drift
        from hub.apps.files.models import File, FileScanStatus, FileStatus

        self._ensure_detail_lookup_uuid_safe(id)

        serializer = DatasetRefreshFromFileSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated = dict(serializer.validated_data)  # narrows for type checker
        new_file_id = str(validated["file_id"])

        # Tenant-scoped lookup. Cross-tenant calls 404. We deliberately
        # do NOT apply the cross-tenant entitlement fallback — refresh
        # is a write-class lifecycle action.
        source = self.get_object()

        # R1 audit GAP-C — re-read the source under a row-level lock
        # so two concurrent refresh-from-file requests on the same
        # source dataset serialise. Without this lock, both threads
        # would read the same ``latest_dataset`` inside
        # ``DatasetService.create_dataset`` and compute the same
        # ``version+1``, then the second ``Dataset.objects.create()``
        # would violate the ``unique_dataset_version_per_asset``
        # constraint and return an unhandled 500. Locking the source
        # forces the second writer to wait until the first commits,
        # then re-read the now-incremented latest version.
        try:
            source = Dataset.objects.select_for_update().get(id=source.id)
        except Dataset.DoesNotExist:  # pragma: no cover — race won't fire after get_object
            raise NotFound("Dataset not found.") from None

        if source.status == DatasetStatus.RETIRED:
            return api_error_response(
                message="Cannot refresh a retired dataset",
                status_code=status.HTTP_409_CONFLICT,
                code="DATASET_RETIRED_REFRESH_NOT_ALLOWED",
                details={"dataset_id": str(source.id)},
            )

        if not source.asset_id:
            return api_error_response(
                message=(
                    "Refresh requires the source dataset to be linked to "
                    "an asset (the version chain anchors on the asset)."
                ),
                status_code=status.HTTP_400_BAD_REQUEST,
                code="DATASET_REFRESH_REQUIRES_ASSET",
                details={"dataset_id": str(source.id)},
            )

        # Validate the new file — same tenant, ACTIVE, scan-clean.
        try:
            new_file = File.objects.get(id=new_file_id, tenant_id=source.tenant_id)
        except File.DoesNotExist:
            return api_error_response(
                message="File not found in this tenant.",
                status_code=status.HTTP_404_NOT_FOUND,
                code="FILE_NOT_FOUND",
                details={"file_id": new_file_id},
            )
        if new_file.status != FileStatus.ACTIVE:
            return api_error_response(
                message=(
                    "File is not ready for use (status="
                    f"{new_file.status}); upload must complete first."
                ),
                status_code=status.HTTP_400_BAD_REQUEST,
                code="FILE_NOT_READY",
                details={"file_id": new_file_id, "status": new_file.status},
            )
        if new_file.scan_status != FileScanStatus.CLEAN:
            return api_error_response(
                message=(
                    "File scan has not cleared (scan_status="
                    f"{new_file.scan_status}); cannot refresh dataset until scan is CLEAN."
                ),
                status_code=status.HTTP_400_BAD_REQUEST,
                code="FILE_SCAN_NOT_CLEAN",
                details={
                    "file_id": new_file_id,
                    "scan_status": new_file.scan_status,
                },
            )
        # Reject reusing the SAME file as the source dataset's backing
        # file — that's a no-op refresh (would create an identical
        # version with no semantic change).
        if source.file_id and str(source.file_id) == new_file_id:
            return api_error_response(
                message=(
                    "New file is the same as the source dataset's current backing file; "
                    "refresh requires a different file to produce a new version."
                ),
                status_code=status.HTTP_400_BAD_REQUEST,
                code="DATASET_REFRESH_SAME_FILE",
                details={"file_id": new_file_id, "dataset_id": str(source.id)},
            )

        parent_file_id_str = str(source.file_id) if source.file_id else None

        # Create the new dataset version. ``DatasetService.create_dataset``
        # auto-versions when ``asset_id`` is supplied (latest dataset
        # for that asset becomes the parent_version).
        try:
            new_dataset = DatasetService(
                tenant_id=str(source.tenant_id),
                user_id=str(request.user.id) if request.user else None,
            ).create_dataset(
                tenant_id=str(source.tenant_id),
                user_id=str(request.user.id) if request.user else None,
                file_id=new_file_id,
                asset_id=str(source.asset_id),
            )
        except NotFoundError as e:
            return handle_service_exception(e)
        except ServiceValidationError as e:
            return handle_service_exception(e)

        # Drift against the active contract. Pure function; no DB writes.
        drift = compute_dataset_contract_drift(new_dataset)

        # Emit durable audit row. ``schema_drift`` in details_json is
        # capped via the comparator's own field-list bounds so a
        # 1000-field contract diff doesn't blow past the audit
        # payload size budget.
        create_audit_event(
            resource_type="DATASET",
            action=DATASET_REFRESHED_FROM_FILE,
            actor_user=request.user,
            tenant=source.tenant,
            resource_id=str(new_dataset.id),
            details={
                "parent_dataset_id": str(source.id),
                "new_dataset_id": str(new_dataset.id),
                "new_file_id": new_file_id,
                "parent_file_id": parent_file_id_str,
                "new_version": new_dataset.version,
                "asset_id": str(source.asset_id),
                "schema_drift": drift,
            },
            request=request,
        )

        # Cache invalidation — best-effort.
        try:
            invalidate_dataset_caches(str(new_dataset.id), str(new_dataset.tenant_id))
            invalidate_dataset_caches(str(source.id), str(source.tenant_id))
        except Exception:
            pass

        return Response(
            {
                "dataset": DatasetSerializer(new_dataset).data,
                "schema_drift": drift,
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=None,
        responses={
            200: DatasetManualRefreshResponseSerializer,
            400: OpenApiResponse(
                description=(
                    "Validation failure: ``FILE_ENCODING_UNSUPPORTED``, "
                    "``UNSUPPORTED_FILE_FORMAT``, or "
                    "``BUSINESS_RULES_VALIDATION`` from the inference "
                    "pipeline."
                )
            ),
            403: OpenApiResponse(
                description="TENANT_ADMIN role required."
            ),
            409: OpenApiResponse(
                description=(
                    "Pre-conditions: source dataset RETIRED "
                    "(``DATASET_RETIRED_REFRESH_NOT_ALLOWED``) or has no "
                    "backing file (``DATASET_REFRESH_NO_FILE``)."
                )
            ),
            413: OpenApiResponse(
                description=(
                    "``FILE_TOO_LARGE_FOR_INFERENCE`` (Phase 260.5.F) — "
                    "the existing backing file's size exceeds the "
                    "inference sanity cap. Same shape as create / "
                    "refresh-from-file 413."
                )
            ),
        },
        summary="Manually refresh a dataset's schema from its existing file",
        description=(
            "Phase 260.4.E — TENANT_ADMIN-only re-inference of the "
            "dataset's schema against its existing backing file. Same "
            "pipeline a scheduled refresh would run; emits "
            "``DATASET_REFRESH_TRIGGERED`` audit. Returns the updated "
            "dataset, drift summary against any active contract, and a "
            "``schema_changed`` flag (True iff the inferred schema "
            "differed from the prior stored value)."
        ),
    )
    @action(detail=True, methods=["post"], url_path="refresh")
    @transaction.atomic
    def refresh(self, request, id=None):
        """
        Phase 260.4.E — manual dataset refresh.

        ``POST /datasets/{id}/refresh/``

        Authorization
        -------------
        TENANT_ADMIN role required (PLATFORM_ADMIN flag bypasses, per
        the standard ``HasAnyRole`` semantics). Regular tenant members
        cannot trigger a refresh — the action churns ``schema_json``,
        appends to the audit log, and consumes S3 read budget; gating
        it on TENANT_ADMIN keeps accidental clicks in low-permission
        seats out of the platform's hot path.

        Pre-conditions
        --------------
        * Source dataset MUST be ACTIVE (RETIRED → 409
          ``DATASET_RETIRED_REFRESH_NOT_ALLOWED``).
        * Source dataset MUST have a backing file (``file_id`` set);
          a refresh on a file-less dataset can't run inference and
          would silently no-op (409 ``DATASET_REFRESH_NO_FILE``).

        Effect
        ------
        * Re-fetches the file bytes from S3 + re-runs the
          format-appropriate schema-inference function.
        * Persists the new schema_json + sample_data + row_count
          ONLY when the canonical schema hash differs from prior
          (no-op refreshes leave ``updated_at`` unchanged so the UI
          doesn't flicker on every Refresh click).
        * Computes drift against any active contract (same helper +
          shape as 260.4.D so audit consumers can dedupe handling).
        * Emits :data:`DATASET_REFRESH_TRIGGERED` audit row INCLUDING
          on no-op refreshes (operator visibility — every refresh
          attempt is auditable, not just the ones that mutated
          state).

        Concurrency
        -----------
        ``select_for_update`` inside the atomic block matches the
        260.4.D / retire / rename pattern. Concurrent refreshes on
        the same row serialize so audit hashes form a clean chain
        rather than racing to overlapping values.

        Tenant scope
        ------------
        ``self.get_object()`` filters by tenant; cross-tenant calls
        404 (no audit emission). The cross-tenant entitlement
        fallback is INTENTIONALLY skipped — refresh is a write-class
        action.
        """
        from hub.apps.datasets.contract_drift import compute_dataset_contract_drift
        from hub.apps.datasets.refresh import (
            apply_refreshed_schema,
            canonical_schema_hash,
            reinfer_dataset_schema,
        )

        self._ensure_detail_lookup_uuid_safe(id)

        # Tenant-scoped resolution. Cross-tenant calls 404.
        source = self.get_object()

        # Lock the row for the duration of the atomic block so two
        # simultaneous refresh requests serialise (matches the 260.4.A
        # / 260.4.C / 260.4.D patterns).
        try:
            locked = Dataset.objects.select_for_update().get(id=source.id)
        except Dataset.DoesNotExist:  # pragma: no cover — race won't fire after get_object
            raise NotFound("Dataset not found.") from None

        if locked.status == DatasetStatus.RETIRED:
            return api_error_response(
                message="Cannot refresh a retired dataset",
                status_code=status.HTTP_409_CONFLICT,
                code="DATASET_RETIRED_REFRESH_NOT_ALLOWED",
                details={"dataset_id": str(locked.id)},
            )

        if not locked.file_id:
            return api_error_response(
                message=(
                    "Dataset has no backing file; cannot re-run schema "
                    "inference. Use refresh-from-file with a new upload."
                ),
                status_code=status.HTTP_409_CONFLICT,
                code="DATASET_REFRESH_NO_FILE",
                details={"dataset_id": str(locked.id)},
            )

        previous_schema = locked.schema_json
        previous_hash = canonical_schema_hash(previous_schema)

        try:
            schema_json, sample_data, row_count = reinfer_dataset_schema(
                locked.file
            )
        except ServiceValidationError as exc:
            return handle_service_exception(exc)

        schema_changed = apply_refreshed_schema(
            locked,
            schema_json=schema_json,
            sample_data=sample_data,
            row_count=row_count,
        )
        new_hash = canonical_schema_hash(locked.schema_json)

        drift = compute_dataset_contract_drift(locked)

        create_audit_event(
            resource_type="DATASET",
            action=DATASET_REFRESH_TRIGGERED,
            actor_user=request.user,
            tenant=locked.tenant,
            resource_id=str(locked.id),
            details={
                "dataset_id": str(locked.id),
                "file_id": str(locked.file_id) if locked.file_id else None,
                "asset_id": str(locked.asset_id) if locked.asset_id else None,
                "previous_schema_hash": previous_hash,
                "new_schema_hash": new_hash,
                "schema_changed": schema_changed,
                "schema_drift": drift,
            },
            request=request,
        )

        # Cache invalidation — best-effort; the row is durable.
        try:
            invalidate_dataset_caches(str(locked.id), str(locked.tenant_id))
        except Exception:
            pass

        return Response(
            {
                "dataset": DatasetSerializer(locked).data,
                "schema_drift": drift,
                "schema_changed": schema_changed,
            },
            status=status.HTTP_200_OK,
        )

    def get_permissions(self):
        """Phase 260.4.E — TENANT_ADMIN gate scoped to the manual-refresh
        action only. Other actions keep the default
        ``permission_classes`` so Phase 260.4.D refresh-from-file (a
        regular write-class action) doesn't suddenly require
        TENANT_ADMIN.
        """
        if getattr(self, "action", None) == "refresh":
            from hub.apps.auth.permissions import HasAnyRole

            return [
                permissions.IsAuthenticated(),
                HasAnyRole(["TENANT_ADMIN"]),
            ]
        return super().get_permissions()

    def get_throttles(self):
        """Phase 260.4.E.R1 GAP-B — manual refresh action gets per-user
        + per-tenant abuse caps. Every refresh downloads the file
        bytes + runs inference + emits an audit row, so a stuck-loop
        bug must not be able to burn S3 read budget OR flood the
        audit log. The caps are deliberately generous for normal
        usage (10/min/user covers the "click, wait, click again"
        retry workflow with headroom) but bound a runaway loop at
        one inference per 6 s.
        """
        if getattr(self, "action", None) == "refresh":
            from hub.apps.datasets.throttles import (
                DatasetRefreshTenantThrottle,
                DatasetRefreshUserThrottle,
            )

            return [
                DatasetRefreshUserThrottle(),
                DatasetRefreshTenantThrottle(),
            ]
        return super().get_throttles()

    @action(detail=True, methods=["get", "post"], url_path="versions")
    def versions(self, request, id=None):
        """
        List or create dataset versions.

        GET /api/v1/datasets/{id}/versions/ - List all versions
        POST /api/v1/datasets/{id}/versions/ - Create a new version
        """
        dataset = self.get_object()

        if request.method == "POST":
            serializer = DatasetVersionCreateSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            tenant_id_str = str(dataset.tenant.id)
            user_id_str = str(request.user.id) if request.user else None
            try:
                new_dataset = DatasetService().create_version_from_dataset(
                    source_dataset_id=str(dataset.id),
                    tenant_id=tenant_id_str,
                    user_id=user_id_str,
                    semantic_version=serializer.validated_data.get("semantic_version"),
                    version_tags=serializer.validated_data.get("version_tags", []),
                    snapshot_metadata=serializer.validated_data.get("schema_changes"),
                    schema_json=serializer.validated_data.get("schema_json"),
                )
            except NotFoundError as e:
                return handle_service_exception(e)
            except ServiceValidationError as e:
                return handle_service_exception(e)
            create_audit_event(
                resource_type="DATASET",
                action="VERSION_CREATED",
                actor_user=request.user,
                tenant=dataset.tenant,
                resource_id=str(new_dataset.id),
                details={
                    "parent_version_id": str(dataset.id),
                    "new_version": new_dataset.version,
                    "semantic_version": new_dataset.semantic_version,
                    "description": serializer.validated_data.get("description", ""),
                },
                request=request,
            )
            try:
                invalidate_dataset_list_cache(tenant_id_str)
                invalidate_dataset_detail_cache(str(dataset.id))
                invalidate_dataset_detail_cache(str(new_dataset.id))
            except Exception as e:
                import logging

                logging.getLogger(__name__).warning(
                    "Failed to invalidate cache after version creation: %s", e, exc_info=True
                )
            return Response(
                DatasetVersionSerializer(new_dataset).data, status=status.HTTP_201_CREATED
            )
        else:
            # GET - List all versions
            # Get all versions for the same asset
            if dataset.asset:
                versions = Dataset.objects.filter(
                    tenant=dataset.tenant, asset=dataset.asset
                ).order_by("-version", "-created_at")
            elif dataset.file_id:
                # Same backing file as lineage created by POST .../versions/ (no asset row).
                versions = Dataset.objects.filter(
                    tenant=dataset.tenant, file_id=dataset.file_id
                ).order_by("-version", "-created_at")
            else:
                versions = Dataset.objects.filter(id=dataset.id)

            serializer = DatasetVersionSerializer(versions, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="versions/compare")
    def compare_versions(self, request, id=None):
        """
        Compare two dataset versions.

        GET /api/v1/datasets/{id}/versions/compare/?version1={uuid}&version2={uuid}
        If version1/version2 not provided, compares parent version with current version.
        """
        dataset = self.get_object()

        serializer = SchemaVersionCompareSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        version1_id = serializer.validated_data.get("version1")
        version2_id = serializer.validated_data.get("version2")

        # Get versions
        if version1_id:
            try:
                version1 = Dataset.objects.get(id=version1_id, tenant=dataset.tenant)
            except Dataset.DoesNotExist:
                return Response(
                    {"error": f"Version {version1_id} not found"}, status=status.HTTP_404_NOT_FOUND
                )
        else:
            # Default to parent version
            version1 = dataset.parent_version
            if not version1:
                return Response(
                    {"error": "No parent version found. Please specify version1."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if version2_id:
            try:
                version2 = Dataset.objects.get(id=version2_id, tenant=dataset.tenant)
            except Dataset.DoesNotExist:
                return Response(
                    {"error": f"Version {version2_id} not found"}, status=status.HTTP_404_NOT_FOUND
                )
        else:
            # Default to current version
            version2 = dataset

        if not (
            _dataset_version_in_anchor_lineage(dataset, version1)
            and _dataset_version_in_anchor_lineage(dataset, version2)
        ):
            return api_error_response(
                "One or both dataset versions are not in this dataset's version lineage.",
                status.HTTP_400_BAD_REQUEST,
                code="VERSION_LINEAGE_MISMATCH",
                details={
                    "anchor_dataset_id": str(dataset.id),
                    "version1_id": str(version1.id),
                    "version2_id": str(version2.id),
                },
            )

        # Compare schemas
        from .schema_evolution import SchemaEvolutionTracker

        schema_diff = SchemaEvolutionTracker.calculate_schema_diff(
            version1.schema_json or {}, version2.schema_json or {}
        )

        # Generate change log
        change_log = SchemaEvolutionTracker.generate_change_log(version1, version2)

        create_audit_event(
            resource_type="DATASET",
            action=DATASET_VERSION_COMPARED,
            actor_user=request.user,
            tenant=dataset.tenant,
            resource_id=str(dataset.id),
            details={
                "anchor_dataset_id": str(dataset.id),
                "version1_id": str(version1.id),
                "version2_id": str(version2.id),
                "change_count": len(schema_diff.changes),
                "compatibility_level": schema_diff.compatibility_level.value,
            },
            request=request,
        )

        return Response(
            {
                "version1": DatasetVersionSerializer(version1).data,
                "version2": DatasetVersionSerializer(version2).data,
                "compatibility_level": schema_diff.compatibility_level.value,
                "summary": schema_diff.summary,
                "changes": [
                    {
                        "type": change.change_type.value,
                        "field_name": change.field_name,
                        "description": change.description,
                        "breaking": change.breaking,
                        "old_value": change.old_value,
                        "new_value": change.new_value,
                    }
                    for change in schema_diff.changes
                ],
                "change_log": change_log,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["get"], url_path="schema-evolution")
    def schema_evolution(self, request, id=None):
        """
        Get schema evolution between dataset versions.

        GET /api/v1/datasets/{id}/schema-evolution/?from_version_id={uuid}&to_version_id={uuid}
        If from_version_id/to_version_id not provided, compares parent version with current version.
        """
        dataset = self.get_object()

        from_version_id = request.query_params.get("from_version_id")
        to_version_id = request.query_params.get("to_version_id")

        # Get versions
        if from_version_id:
            try:
                from_version = Dataset.objects.get(id=from_version_id, tenant=dataset.tenant)
            except Dataset.DoesNotExist:
                return Response(
                    {"error": f"Version {from_version_id} not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )
        else:
            # Default to parent version
            from_version = dataset.parent_version
            if not from_version:
                return Response(
                    {"error": "No parent version found. Please specify from_version_id."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if to_version_id:
            try:
                to_version = Dataset.objects.get(id=to_version_id, tenant=dataset.tenant)
            except Dataset.DoesNotExist:
                return Response(
                    {"error": f"Version {to_version_id} not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )
        else:
            # Default to current version
            to_version = dataset

        if not (
            _dataset_version_in_anchor_lineage(dataset, from_version)
            and _dataset_version_in_anchor_lineage(dataset, to_version)
        ):
            return api_error_response(
                "One or both dataset versions are not in this dataset's version lineage.",
                status.HTTP_400_BAD_REQUEST,
                code="VERSION_LINEAGE_MISMATCH",
                details={
                    "anchor_dataset_id": str(dataset.id),
                    "from_version_id": str(from_version.id),
                    "to_version_id": str(to_version.id),
                },
            )

        # Calculate schema evolution
        from .schema_evolution import SchemaEvolutionTracker

        schema_diff = SchemaEvolutionTracker.calculate_schema_diff(
            from_version.schema_json or {}, to_version.schema_json or {}
        )

        # Generate change log
        change_log = SchemaEvolutionTracker.generate_change_log(from_version, to_version)

        return Response(
            {
                "from_version_id": str(from_version.id),
                "to_version_id": str(to_version.id),
                "compatibility_level": schema_diff.compatibility_level.value,
                "summary": schema_diff.summary,
                "changes": [
                    {
                        "type": change.change_type.value,
                        "field_name": change.field_name,
                        "description": change.description,
                        "breaking": change.breaking,
                        "old_value": change.old_value,
                        "new_value": change.new_value,
                    }
                    for change in schema_diff.changes
                ],
                "change_log": change_log,
            },
            status=status.HTTP_200_OK,
        )

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        """
        Update dataset (full or partial). Delegates to DatasetService; business rules run before update.
        PUT /api/v1/datasets/{id}/ accepts partial data; only provided fields are updated.
        """
        dataset = self.get_object()
        serializer = DatasetSerializer(dataset, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        tenant_id = str(dataset.tenant.id)
        user_id = str(request.user.id) if request.user else None
        try:
            dataset = DatasetService().update_dataset(
                dataset_id=str(dataset.id),
                tenant_id=tenant_id,
                user_id=user_id,
                **{
                    k: v
                    for k, v in serializer.validated_data.items()
                    if k not in serializer.Meta.read_only_fields
                },
            )
        except NotFoundError:
            return api_error_response(
                message="Dataset not found", status_code=status.HTTP_404_NOT_FOUND, code="NOT_FOUND"
            )
        except ServiceValidationError as e:
            body = {"error": str(e)}
            if getattr(e, "code", None):
                body["code"] = e.code
            if getattr(e, "details", None):
                body["details"] = e.details
            return Response(body, status=status.HTTP_400_BAD_REQUEST)
        try:
            invalidate_dataset_caches(str(dataset.id), tenant_id)
        except Exception as e:
            import logging

            logging.getLogger(__name__).warning(
                "Failed to invalidate cache after dataset update: %s", e, exc_info=True
            )
        create_audit_event(
            resource_type="DATASET",
            action="DATASET_UPDATED",
            actor_user=request.user,
            tenant=dataset.tenant,
            resource_id=str(dataset.id),
            details=serializer.validated_data,
            request=request,
        )
        return Response(DatasetSerializer(dataset).data)

    @transaction.atomic
    def partial_update(self, request, *args, **kwargs):
        """
        Update dataset (partial update). Delegates to DatasetService; business rules run before update.
        PATCH /api/v1/datasets/{id}/
        """
        dataset = self.get_object()
        serializer = DatasetSerializer(dataset, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        tenant_id = str(dataset.tenant.id)
        user_id = str(request.user.id) if request.user else None
        update_data = {
            k: v
            for k, v in serializer.validated_data.items()
            if k not in serializer.Meta.read_only_fields
        }
        if not update_data:
            return Response(DatasetSerializer(dataset).data)
        try:
            dataset = DatasetService().update_dataset(
                dataset_id=str(dataset.id), tenant_id=tenant_id, user_id=user_id, **update_data
            )
        except NotFoundError:
            return api_error_response(
                message="Dataset not found", status_code=status.HTTP_404_NOT_FOUND, code="NOT_FOUND"
            )
        except ServiceValidationError as e:
            body = {"error": str(e)}
            if getattr(e, "code", None):
                body["code"] = e.code
            if getattr(e, "details", None):
                body["details"] = e.details
            return Response(body, status=status.HTTP_400_BAD_REQUEST)
        try:
            invalidate_dataset_caches(str(dataset.id), tenant_id)
        except Exception as e:
            import logging

            logging.getLogger(__name__).warning(
                "Failed to invalidate cache after dataset partial update: %s", e, exc_info=True
            )
        create_audit_event(
            resource_type="DATASET",
            action="DATASET_UPDATED",
            actor_user=request.user,
            tenant=dataset.tenant,
            resource_id=str(dataset.id),
            details=serializer.validated_data,
            request=request,
        )
        return Response(DatasetSerializer(dataset).data)

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        """
        Delete a dataset. Delegates to DatasetService; business rules (validate_version_deletion) run before delete.
        DELETE /api/v1/datasets/{id}/
        """
        dataset = self.get_object()
        dataset_id = str(dataset.id)
        tenant_id_str = str(dataset.tenant.id)
        tenant = dataset.tenant
        audit_details = {
            "file_id": str(dataset.file.id) if dataset.file else None,
            "format": dataset.format,
            "version": dataset.version,
        }
        user_id = str(request.user.id) if request.user else None
        try:
            DatasetService().destroy_dataset(
                dataset_id=dataset_id,
                tenant_id=tenant_id_str,
                user_id=user_id,
            )
        except NotFoundError:
            return api_error_response(
                message="Dataset not found", status_code=status.HTTP_404_NOT_FOUND, code="NOT_FOUND"
            )
        except ServiceValidationError as e:
            body = {"error": str(e)}
            if getattr(e, "code", None):
                body["code"] = e.code
            if getattr(e, "details", None):
                body["details"] = e.details
            return Response(body, status=status.HTTP_400_BAD_REQUEST)
        try:
            invalidate_dataset_caches(dataset_id, tenant_id_str)
        except Exception as e:
            import logging

            logging.getLogger(__name__).warning(
                "Failed to invalidate cache before dataset deletion: %s", e, exc_info=True
            )
        create_audit_event(
            resource_type="DATASET",
            action="DATASET_DELETED",
            actor_user=request.user,
            tenant=tenant,
            resource_id=dataset_id,
            details=audit_details,
            request=request,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    # ── Phase 275.D.1 (migrated 277.B.048) — Records API ────────

    @action(detail=True, methods=["get"], url_path="rows")
    def rows(self, request, id=None):
        """
        Phase 275.D.1 / 277.B.048 — Records API for dataset rows.

        GET /api/v1/datasets/{id}/rows/?limit=100&cursor=<encoded>
        Accept: application/json (default) — decimals as strings (RFC 7159)
        Accept: application/vnd.apache.arrow.stream — Arrow IPC stream

        Cursor pagination via StandardCursorPagination (Phase 277.B.048).
        Old plain-value cursors accepted with Deprecation + Sunset headers
        during the 90-day migration window.
        """
        dataset = self.get_object()
        try:
            limit = int(request.query_params.get("limit", 100))
        except (ValueError, TypeError):
            limit = 100
        limit = max(1, min(limit, 100))
        cursor = request.query_params.get("cursor")

        # Check if LIVE_QUERY asset routes through warehouse connector.
        asset = dataset.asset
        if asset and getattr(asset, "data_strategy", None) == "LIVE_QUERY":
            return self._rows_from_live_query(request, dataset, asset, limit, cursor)

        return self._rows_from_file(request, dataset, limit, cursor)

    def _rows_from_live_query(self, request, dataset, asset, limit, cursor):
        """Dispatch to warehouse connector for LIVE_QUERY assets.

        Phase 277.B.048 — cursor pagination via StandardCursorPagination
        with backward-compat for legacy plain-value cursors.
        """
        conn = getattr(asset, "warehouse_connection", None)
        if conn is None:
            return Response(
                {"error": {"code": "NO_WAREHOUSE_CONNECTION", "message": "No warehouse connection configured"}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        config = conn.get_config()
        connector = self._resolve_connector(conn.warehouse_type, config, str(asset.tenant_id), str(asset.id))

        page_size = limit
        is_old_cursor = False
        cursor_value = None

        if cursor:
            cursor_value = self._resolve_cursor(cursor)
            if cursor_value is None:
                # Legacy plain-value cursor
                is_old_cursor = True
                cursor_value = cursor

        try:
            connector.connect()
            table_name = getattr(dataset, "name", None) or asset.key
            sql = f"SELECT * FROM {table_name}"
            if cursor_value:
                sql += f" WHERE id > '{cursor_value}'"
            sql += f" ORDER BY id LIMIT {page_size + 1}"  # fetch one extra to detect has_next

            result = connector.execute_query(sql)

            rows = result.rows if result.rows else []
            has_next = len(rows) > page_size
            if has_next:
                rows = rows[:page_size]

            # Build cursors in StandardCursorPagination format
            paginator = StandardCursorPagination()
            next_cursor = None
            if has_next and rows:
                last_id = rows[-1][0]
                next_cursor = paginator.encode_cursor((last_id, last_id))
            previous_cursor = None
            if cursor and not is_old_cursor:
                previous_cursor = cursor

            accept = request.META.get("HTTP_ACCEPT", "application/json")
            if "arrow" in accept:
                return self._arrow_response(result)

            resp = Response(
                {
                    "results": rows,
                    "columns": result.columns,
                    "count": result.row_count,
                    "next_cursor": next_cursor,
                    "previous_cursor": previous_cursor,
                    "page_size": page_size,
                },
                status=status.HTTP_200_OK,
            )
            if is_old_cursor:
                import datetime as _dt
                sunset_date = (_dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(days=90)).strftime("%a, %d %b %Y %H:%M:%S GMT")
                resp.headers["Deprecation"] = "true"
                resp.headers["Deprecation-Date"] = _dt.datetime.now(_dt.timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
                resp.headers["Sunset"] = sunset_date
                resp.headers["Link"] = '</docs/api/error-codes.md>; rel="deprecation"'
            return resp
        finally:
            connector.close()

    @staticmethod
    def _resolve_cursor(cursor):
        """Decode a StandardCursorPagination cursor; return None if it's a legacy plain-value cursor.

        StandardCursorPagination encodes a JSON list as base64, e.g. ``WyJpZC0wNTAiLCJpZC0wNTAiXQ==``.
        A legacy plain-value cursor like ``"id-050"`` won't decode to a JSON list.
        """
        import base64 as _b64
        import json as _json
        try:
            decoded = _b64.b64decode(cursor.encode("utf-8")).decode("utf-8")
            position = _json.loads(decoded)
            if isinstance(position, list) and len(position) >= 1:
                return position[0]
        except Exception:
            pass
        return None

    def _rows_from_file(self, request, dataset, limit, cursor):
        """Serve rows from file-backed dataset."""
        return Response(
            {"results": [], "columns": [], "count": 0, "next_cursor": None, "previous_cursor": None, "page_size": limit, "message": "File-backed datasets served via existing endpoints"},
            status=status.HTTP_200_OK,
        )

    @staticmethod
    def _arrow_response(result):
        """Convert QueryResult to Arrow IPC stream."""
        import pyarrow as pa
        import io

        arrays = {}
        for i, col in enumerate(result.columns):
            values = [row[i] for row in result.rows]
            arrays[col] = pa.array(values, type=pa.string())

        table = pa.table(arrays)
        sink = io.BytesIO()
        with pa.ipc.new_stream(sink, table.schema) as writer:
            writer.write_table(table)
        return __import__("django.http").HttpResponse(
            sink.getvalue(),
            content_type="application/vnd.apache.arrow.stream",
        )

    @staticmethod
    def _resolve_connector(warehouse_type, config, tenant_id, asset_id):
        """Resolve the appropriate connector for LIVE_QUERY."""
        if warehouse_type == "SNOWFLAKE":
            from hub.apps.warehouses.connectors.snowflake import SnowflakeConnector
            return SnowflakeConnector(config, tenant_id=tenant_id, asset_id=asset_id)
        elif warehouse_type == "BIGQUERY":
            from hub.apps.warehouses.connectors.bigquery import BigQueryConnector
            return BigQueryConnector(config, tenant_id=tenant_id, asset_id=asset_id)
        elif warehouse_type == "DATABRICKS":
            from hub.apps.warehouses.connectors.databricks import DatabricksConnector
            return DatabricksConnector(config, tenant_id=tenant_id, asset_id=asset_id)
        elif warehouse_type == "ATHENA":
            from hub.apps.warehouses.connectors.athena import AthenaConnector
            return AthenaConnector(config, tenant_id=tenant_id, asset_id=asset_id)
        raise ValueError(f"Unknown warehouse type: {warehouse_type}")

    # ── Phase 275.D.3 — Delta Sharing ───────────────────────────────

    @action(detail=True, methods=["get"], url_path="share")
    def share(self, request, id=None):
        """
        Phase 275.D.3 — Delta Sharing endpoint.

        GET /api/v1/datasets/{id}/share/
        Serves the Delta Sharing 1.0 protocol with Hub auth + audit.
        Per-tenant rate limit. WAREHOUSE_SHARE_ACCESSED audit emitted.
        """
        dataset = self.get_object()
        tenant = dataset.tenant

        # Emit audit event.
        try:
            from hub.apps.audit.event_types import WAREHOUSE_SHARE_ACCESSED
            from hub.apps.audit.utils import create_audit_event
            create_audit_event(
                resource_type="DATASET",
                action=WAREHOUSE_SHARE_ACCESSED,
                actor_user=request.user,
                tenant=tenant,
                resource_id=str(dataset.id),
                result="SUCCESS",
                details={"dataset_id": str(dataset.id), "format": "delta-sharing"},
            )
        except Exception:
            pass

        # Delta Sharing protocol response shape.
        return Response({
            "share": {
                "name": getattr(dataset, "name", None) or str(dataset.id),
                "id": str(dataset.id),
                "format": "delta",
            },
            "protocol": {"version": 1},
            "meta": {
                "tenant_id": str(tenant.id),
                "created_at": str(dataset.created_at),
            },
        }, status=status.HTTP_200_OK)
