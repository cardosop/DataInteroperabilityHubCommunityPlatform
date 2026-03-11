"""
Dataset Views

REST API views for dataset creation and retrieval.
All create/update/destroy/version creation delegate to DatasetService,
which invokes DatasetsBusinessRules before mutations.
"""

import uuid

from django.db import transaction
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from hub.apps.audit.utils import create_audit_event
from hub.apps.core.responses import api_error_response, handle_service_exception
from hub.apps.core.services.base import NotFoundError
from hub.apps.core.services.base import ValidationError as ServiceValidationError
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
from .models import Dataset, SchemaVersion
from .serializers import (
    DatasetCreateSerializer,
    DatasetSerializer,
    DatasetVersionCreateSerializer,
    DatasetVersionSerializer,
    SchemaVersionCompareSerializer,
)
from .services import DatasetService


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
        # Avoid N+1: serializer uses asset.name and file for name/size_bytes
        return qs.select_related("asset", "file")

    @transaction.atomic
    def create(self, request):
        """
        Create a dataset from a file with schema inference.

        POST /datasets
        Body: {
            "file_id": "uuid",
            "asset_id": "uuid" (optional)
        }
        """
        serializer = DatasetCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        file_id = serializer.validated_data["file_id"]
        asset_id = serializer.validated_data.get("asset_id")

        # Phase 16: use central helper
        _, tenant = get_request_tenant(request)
        if not tenant:
            return Response(
                {"error": "User must belong to a tenant to create datasets"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            dataset = DatasetService().create_dataset(
                tenant_id=str(tenant.id),
                user_id=str(request.user.id) if request.user else "",
                file_id=str(file_id),
                asset_id=str(asset_id) if asset_id else None,
            )
        except NotFoundError as e:
            return handle_service_exception(e)
        except ServiceValidationError as e:
            return handle_service_exception(e)

        try:
            invalidate_dataset_list_cache(str(tenant.id))
        except Exception as e:
            import logging

            logging.getLogger(__name__).warning(
                "Failed to invalidate cache after dataset creation: %s", e, exc_info=True
            )
        return Response(DatasetSerializer(dataset).data, status=status.HTTP_201_CREATED)

    def list(self, request, *args, **kwargs):
        """
        List datasets (tenant-scoped) with caching.

        GET /api/v1/datasets/
        Query params: page, page_size, ordering, search, asset_id, dataset_format, etc.
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
        """
        dataset_id = str(kwargs.get("id", ""))

        # Try to get from cache
        cached_data = get_cached_dataset_detail(dataset_id)
        if cached_data is not None:
            return Response(cached_data)

        # Cache miss - execute query
        dataset = self.get_object()

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
                )
            except NotFoundError as e:
                return handle_service_exception(e)
            except ServiceValidationError as e:
                return handle_service_exception(e)
                body = {"error": str(e)}
                if getattr(e, "code", None):
                    body["code"] = e.code
                if getattr(e, "details", None):
                    body["details"] = e.details
                return Response(body, status=status.HTTP_400_BAD_REQUEST)
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
            else:
                # If no asset, just return this dataset
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

        # Compare schemas
        from .schema_evolution import SchemaEvolutionTracker

        schema_diff = SchemaEvolutionTracker.calculate_schema_diff(
            version1.schema_json or {}, version2.schema_json or {}
        )

        # Generate change log
        change_log = SchemaEvolutionTracker.generate_change_log(version1, version2)

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
