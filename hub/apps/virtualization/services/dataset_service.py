"""Virtual dataset CRUD methods for VirtualizationService."""

import logging
from typing import Any

from django.db import transaction

from hub.apps.core.services.base import (
    ConflictError,
    NotFoundError,
    PermissionError,
    ValidationError,
)
from hub.apps.virtualization.business_rules import (
    VirtualizationBusinessRules,
)
from hub.apps.virtualization.metrics import (
    get_query_type,
    get_tenant_id,
    virtualization_dataset_created_total,
    virtualization_dataset_creation_duration_seconds,
)
from hub.apps.virtualization.models import (
    QueryType,
    VirtualDataset,
    VirtualDatasetStatus,
)

logger = logging.getLogger(__name__)


class DatasetServiceMixin:
    """Mixin providing virtual dataset CRUD operations."""

    def get_virtual_dataset(
        self,
        virtual_dataset_id: str,
        tenant_id: str | None = None,
    ) -> VirtualDataset:
        """
        Get virtual dataset by ID.

        Args:
            virtual_dataset_id: Virtual dataset ID
            tenant_id: Tenant ID (uses service tenant_id if not provided)

        Returns:
            VirtualDataset instance

        Raises:
            NotFoundError: If virtual dataset not found
        """
        effective_tenant_id = tenant_id or self.tenant_id
        if not effective_tenant_id:
            raise ValidationError("tenant_id is required")

        return self.execute_with_metrics(
            operation="get_virtual_dataset",
            tenant_id=effective_tenant_id,
            func=lambda: self.get_resource_or_raise(
                VirtualDataset,
                virtual_dataset_id,
                tenant_id=effective_tenant_id,
            ),
        )

    def get_virtual_datasets(
        self,
        tenant_id: str | None = None,
        status: VirtualDatasetStatus | None = None,
        query_type: QueryType | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[VirtualDataset]:
        """
        Get virtual datasets with optional filtering.

        Args:
            tenant_id: Tenant ID (uses service tenant_id if not provided)
            status: Optional status filter
            query_type: Optional query type filter
            limit: Optional limit on results
            offset: Pagination offset

        Returns:
            List of VirtualDataset instances
        """
        effective_tenant_id = tenant_id or self.tenant_id
        if not effective_tenant_id:
            raise ValidationError("tenant_id is required")

        def _get_virtual_datasets():
            queryset = VirtualDataset.objects.filter(tenant_id=effective_tenant_id)

            if status:
                queryset = queryset.filter(status=status)

            if query_type:
                queryset = queryset.filter(query_type=query_type)

            queryset = queryset.order_by("-created_at")

            if offset:
                queryset = queryset[offset:]

            if limit:
                queryset = queryset[:limit]

            return list(queryset)

        return self.execute_with_metrics(
            operation="get_virtual_datasets",
            tenant_id=effective_tenant_id,
            func=_get_virtual_datasets,
        )

    @transaction.atomic
    def create_virtual_dataset(
        self,
        tenant_id: str,
        user_id: str,
        name: str,
        query: str,
        query_type: QueryType,
        description: str | None = None,
        schema: dict[str, Any] | None = None,
        sources: list[dict[str, Any]] | None = None,
        version: str | None = None,
        status: VirtualDatasetStatus | None = None,
    ) -> VirtualDataset:
        """
        Create a virtual dataset with comprehensive validation.

        This method performs:
        1. Query validation (syntax, schema)
        2. Schema validation
        3. Source connectivity check
        4. User permissions check (role and scope)
        5. Resource quota validation (query quota, storage quota)
        6. ABAC policy checks
        7. Compliance validation for federated sources (via ComplianceService)
        8. Cross-tenant source access permission checks
        9. Query compliance validation
        10. Virtual dataset creation with transaction management
        11. Event publishing (virtualization.dataset.created)
        12. Audit logging

        Args:
            tenant_id: Tenant ID
            user_id: User ID creating the dataset
            name: Dataset name (unique per tenant)
            query: Query definition (SQL, SPARQL, etc.)
            query_type: Type of query (SQL, SPARQL, FEDERATED, etc.)
            description: Optional dataset description
            schema: Optional output schema definition
            sources: Optional list of source system configurations
            version: Optional version string (defaults to "1.0.0")
            status: Optional status (defaults to DRAFT)

        Returns:
            Created VirtualDataset instance

        Raises:
            ValidationError: If validation fails
            PermissionError: If user lacks required permissions or ABAC policy denies access
            ConflictError: If dataset with same name/version already exists
        """
        from django.contrib.auth import get_user_model

        from hub.apps.audit.utils import create_audit_event
        from hub.apps.tenants.models import Tenant

        effective_tenant_id = tenant_id or self.tenant_id
        if not effective_tenant_id:
            raise ValidationError("tenant_id is required")

        effective_user_id = user_id or self.user_id
        if not effective_user_id:
            raise ValidationError("user_id is required")

        # Plan limit enforcement
        from hub.apps.tenants.services import PlanLimitService

        plan_limit_service = PlanLimitService(tenant_id=effective_tenant_id)
        plan_limit_service.check_limit(
            tenant_id=effective_tenant_id,
            limit_key="max_virtual_datasets",
            delta=1,
        )

        # Get tenant and user objects
        try:
            tenant = Tenant.objects.get(id=effective_tenant_id)
        except Tenant.DoesNotExist:
            raise NotFoundError(f"Tenant with id {effective_tenant_id} not found")

        User = get_user_model()
        try:
            user = User.objects.get(id=effective_user_id)
        except User.DoesNotExist:
            raise NotFoundError(f"User with id {effective_user_id} not found")

        # Set defaults
        if version is None:
            version = "1.0.0"
        if status is None:
            status = VirtualDatasetStatus.DRAFT  # type: ignore[assignment]  # enum member assigned to str-typed var

        # Validate via VirtualizationBusinessRules before any mutation
        payload_dataset = VirtualDataset(
            tenant_id=effective_tenant_id,
            name=name,
            query=query,
            query_type=query_type,
            description=description or "",
            schema=schema or {},
            sources=sources or [],
            version=version,
            status=status,
        )
        rules = VirtualizationBusinessRules(
            tenant_id=effective_tenant_id,
            user_id=effective_user_id,
        )
        result = rules.validate(
            virtual_dataset=payload_dataset,
            tenant=tenant,
            user=user,
            query=query,
            validation_type="all",
        )
        if not result.is_valid:
            raise ValidationError(
                "; ".join(result.errors),
                code="BUSINESS_RULES_VALIDATION",
                details=result.details,
            )

        # 1. Check user permissions (role and scope)
        try:
            self._check_user_permissions(effective_user_id, effective_tenant_id)
        except PermissionError as e:
            logger.warning(
                f"User permission check failed for virtual dataset creation: {e!s}",
                extra={"tenant_id": effective_tenant_id, "user_id": effective_user_id},
            )
            raise

        # 2. Validate resource quota
        try:
            self._validate_resource_quota(
                tenant_id=effective_tenant_id,
                query=query,
                query_type=query_type,
                sources=sources,
                schema=schema,
            )
        except ValidationError as e:
            logger.warning(
                f"Resource quota validation failed for virtual dataset creation: {e.message}",
                extra={
                    "tenant_id": effective_tenant_id,
                    "user_id": effective_user_id,
                    "error_code": e.code,
                },
            )
            raise

        # 3. Check ABAC policies
        try:
            self._check_abac_policies(
                user_id=effective_user_id, tenant_id=effective_tenant_id, access_type="WRITE"
            )
        except PermissionError as e:
            logger.warning(
                f"ABAC policy check failed for virtual dataset creation: {e!s}",
                extra={"tenant_id": effective_tenant_id, "user_id": effective_user_id},
            )
            raise

        # 4. Validate query syntax
        try:
            self._validate_query_syntax(query, query_type)
        except ValidationError as e:
            logger.warning(
                f"Query validation failed for virtual dataset creation: {e.message}",
                extra={
                    "tenant_id": effective_tenant_id,
                    "user_id": effective_user_id,
                    "query_type": query_type,
                    "error_code": e.code,
                },
            )
            raise

        # 5. Validate schema
        try:
            self._validate_schema(schema)
        except ValidationError as e:
            logger.warning(
                f"Schema validation failed for virtual dataset creation: {e.message}",
                extra={
                    "tenant_id": effective_tenant_id,
                    "user_id": effective_user_id,
                    "error_code": e.code,
                },
            )
            raise

        # 6. Validate source connectivity
        try:
            self._validate_source_connectivity(sources, effective_tenant_id)
        except ValidationError as e:
            logger.warning(
                f"Source connectivity check failed for virtual dataset creation: {e.message}",
                extra={
                    "tenant_id": effective_tenant_id,
                    "user_id": effective_user_id,
                    "error_code": e.code,
                    "details": e.details,
                },
            )
            raise

        # 7. Validate compliance of federated sources
        try:
            self._validate_compliance_for_sources(sources, effective_tenant_id)
        except ValidationError as e:
            logger.warning(
                f"Compliance validation failed for virtual dataset creation: {e.message}",
                extra={
                    "tenant_id": effective_tenant_id,
                    "user_id": effective_user_id,
                    "error_code": e.code,
                    "details": e.details,
                },
            )
            raise

        # 8. Validate query compliance
        try:
            self._validate_query_compliance(query, query_type, sources, effective_tenant_id)
        except ValidationError as e:
            logger.warning(
                f"Query compliance validation failed for virtual dataset creation: {e.message}",
                extra={
                    "tenant_id": effective_tenant_id,
                    "user_id": effective_user_id,
                    "error_code": e.code,
                    "details": e.details,
                },
            )
            raise

        # 9. Check for duplicate name/version combination
        existing = VirtualDataset.objects.filter(
            tenant_id=effective_tenant_id, name=name, version=version
        ).first()
        if existing:
            raise ConflictError(
                f"Virtual dataset with name '{name}' and version '{version}' already exists"
            )

        # 10. Create virtual dataset
        import time

        creation_start_time = time.time()
        try:
            virtual_dataset = VirtualDataset.objects.create(
                tenant=tenant,
                created_by=user,
                name=name,
                description=description,
                query=query,
                query_type=query_type,
                schema=schema or {},
                sources=sources or [],
                version=version,
                status=status,
            )

            # Track metrics for successful creation
            creation_duration = time.time() - creation_start_time
            tenant_id_str = get_tenant_id(effective_tenant_id)
            query_type_str = get_query_type(query_type)
            status_str = str(status)

            virtualization_dataset_created_total.labels(
                tenant_id=tenant_id_str, query_type=query_type_str, status=status_str
            ).inc()

            virtualization_dataset_creation_duration_seconds.labels(
                tenant_id=tenant_id_str, query_type=query_type_str, status=status_str
            ).observe(creation_duration)

        except Exception as e:
            # Track metrics for failed creation
            creation_duration = time.time() - creation_start_time
            tenant_id_str = get_tenant_id(effective_tenant_id)
            query_type_str = get_query_type(query_type)

            virtualization_dataset_created_total.labels(
                tenant_id=tenant_id_str, query_type=query_type_str, status="FAILED"
            ).inc()

            virtualization_dataset_creation_duration_seconds.labels(
                tenant_id=tenant_id_str, query_type=query_type_str, status="FAILED"
            ).observe(creation_duration)

            logger.error(
                f"Failed to create virtual dataset: {e!s}",
                extra={
                    "tenant_id": effective_tenant_id,
                    "user_id": effective_user_id,
                    "dataset_name": name,  # Use dataset_name instead of name (name is reserved in LogRecord)
                    "query_type": query_type,
                },
                exc_info=True,
            )
            raise ValidationError(
                f"Failed to create virtual dataset: {e!s}", code="DATASET_CREATION_FAILED"
            ) from e

        # 11. Publish event
        try:
            self.publish_virtual_dataset_created(
                virtual_dataset_id=str(virtual_dataset.id),
                name=virtual_dataset.name,
                query_type=virtual_dataset.query_type,
                status=virtual_dataset.status,
                version=virtual_dataset.version,
                tenant_id=effective_tenant_id,
            )
        except Exception as e:
            # Log but don't fail dataset creation if event publishing fails
            logger.warning(
                f"Failed to publish virtualization.dataset.created event for dataset {virtual_dataset.id}: {e}",
                extra={
                    "virtual_dataset_id": str(virtual_dataset.id),
                    "tenant_id": effective_tenant_id,
                    "error": str(e),
                },
                exc_info=True,
            )

        # 9. Index for search
        try:
            from hub.apps.search.indexing import SearchIndexer

            SearchIndexer.index_virtual_dataset(virtual_dataset)
        except Exception as e:
            # Log but don't fail dataset creation if indexing fails
            logger.warning(
                f"Failed to index virtual dataset {virtual_dataset.id} for search: {e}",
                extra={
                    "virtual_dataset_id": str(virtual_dataset.id),
                    "tenant_id": effective_tenant_id,
                    "error": str(e),
                },
                exc_info=True,
            )

        # 10. Create audit log
        try:
            audit_details = {
                "dataset_id": str(virtual_dataset.id),
                "name": virtual_dataset.name,
                "query_type": virtual_dataset.query_type,
                "sources": sources if sources else [],
                "status": virtual_dataset.status,
                "version": virtual_dataset.version,
                "source_count": len(sources) if sources else 0,
                "has_schema": schema is not None and bool(schema),
            }
            create_audit_event(
                resource_type="VIRTUAL_DATASET",
                action="CREATED",
                actor_user=user,
                tenant=tenant,
                resource_id=str(virtual_dataset.id),
                result="SUCCESS",
                details=audit_details,
            )
        except Exception as e:
            # Log but don't fail dataset creation if audit logging fails
            logger.warning(
                f"Failed to create audit log for virtual dataset {virtual_dataset.id}: {e}",
                extra={
                    "virtual_dataset_id": str(virtual_dataset.id),
                    "tenant_id": effective_tenant_id,
                    "error": str(e),
                },
                exc_info=True,
            )

        logger.info(
            f"Virtual dataset created successfully: {virtual_dataset.id}",
            extra={
                "virtual_dataset_id": str(virtual_dataset.id),
                "tenant_id": effective_tenant_id,
                "user_id": effective_user_id,
                "dataset_name": name,  # Use 'dataset_name' instead of 'name' to avoid LogRecord conflict
                "query_type": query_type,
                "status": status,
            },
        )

        return virtual_dataset

    @transaction.atomic
    def update_virtual_dataset(
        self,
        virtual_dataset_id: str,
        tenant_id: str | None = None,
        user_id: str | None = None,
        name: str | None = None,
        query: str | None = None,
        query_type: QueryType | None = None,
        description: str | None = None,
        schema: dict[str, Any] | None = None,
        sources: list[dict[str, Any]] | None = None,
        version: str | None = None,
        status: VirtualDatasetStatus | None = None,
    ) -> VirtualDataset:
        """
        Update a virtual dataset with comprehensive validation and audit logging.

        Args:
            virtual_dataset_id: ID of the virtual dataset to update
            tenant_id: Tenant ID (optional, uses service default if not provided)
            user_id: User ID performing the update (optional, uses service default if not provided)
            name: Optional new name
            query: Optional new query definition
            query_type: Optional new query type
            description: Optional new description
            schema: Optional new schema definition
            sources: Optional new sources list
            version: Optional new version
            status: Optional new status

        Returns:
            Updated VirtualDataset instance

        Raises:
            NotFoundError: If virtual dataset not found
            ValidationError: If validation fails
            PermissionError: If user lacks required permissions
        """
        from django.contrib.auth import get_user_model

        from hub.apps.audit.utils import create_audit_event
        from hub.apps.tenants.models import Tenant

        effective_tenant_id = tenant_id or self.tenant_id
        if not effective_tenant_id:
            raise ValidationError("tenant_id is required")

        effective_user_id = user_id or self.user_id
        if not effective_user_id:
            raise ValidationError("user_id is required")

        # Get tenant and user objects
        try:
            tenant = Tenant.objects.get(id=effective_tenant_id)
        except Tenant.DoesNotExist:
            raise NotFoundError(f"Tenant with id {effective_tenant_id} not found")

        User = get_user_model()
        try:
            user = User.objects.get(id=effective_user_id)
        except User.DoesNotExist:
            raise NotFoundError(f"User with id {effective_user_id} not found")

        # Get virtual dataset
        try:
            virtual_dataset = VirtualDataset.objects.get(
                id=virtual_dataset_id, tenant_id=effective_tenant_id
            )
        except VirtualDataset.DoesNotExist:
            raise NotFoundError(f"Virtual dataset with id {virtual_dataset_id} not found")

        # Store original values for audit log
        original_values = {
            "name": virtual_dataset.name,
            "query": virtual_dataset.query,
            "query_type": virtual_dataset.query_type,
            "description": virtual_dataset.description,
            "schema": virtual_dataset.schema,
            "sources": virtual_dataset.get_sources(),
            "version": virtual_dataset.version,
            "status": virtual_dataset.status,
        }

        # Check user permissions
        try:
            self._check_user_permissions(effective_user_id, effective_tenant_id)
        except PermissionError as e:
            logger.warning(
                f"User permission check failed for virtual dataset update: {e!s}",
                extra={
                    "tenant_id": effective_tenant_id,
                    "user_id": effective_user_id,
                    "virtual_dataset_id": virtual_dataset_id,
                },
            )
            raise

        # Update fields if provided
        if name is not None:
            virtual_dataset.name = name
        if query is not None:
            # Validate query syntax if query is being updated
            self._validate_query_syntax(query, query_type or virtual_dataset.query_type)
            virtual_dataset.query = query
        if query_type is not None:
            virtual_dataset.query_type = query_type
        if description is not None:
            virtual_dataset.description = description
        if schema is not None:
            # Validate schema if provided
            self._validate_schema(schema)
            virtual_dataset.schema = schema
        if sources is not None:
            # Validate source connectivity if sources are being updated
            self._validate_source_connectivity(sources, effective_tenant_id)
            virtual_dataset.sources = sources
        if version is not None:
            virtual_dataset.version = version
        if status is not None:
            virtual_dataset.status = status

        # Validate via VirtualizationBusinessRules before save (updated state)
        rules = VirtualizationBusinessRules(
            tenant_id=effective_tenant_id,
            user_id=effective_user_id,
        )
        result = rules.validate(
            virtual_dataset=virtual_dataset,
            tenant=tenant,
            user=user,
            validation_type="all",
        )
        if not result.is_valid:
            raise ValidationError(
                "; ".join(result.errors),
                code="BUSINESS_RULES_VALIDATION",
                details=result.details,
            )

        # Save the updated dataset
        virtual_dataset.save()

        # Determine what changed (for both event and audit log)
        changes = {}
        if name is not None and name != original_values["name"]:
            changes["name"] = {"old": original_values["name"], "new": name}
        if query is not None and query != original_values["query"]:
            changes["query"] = {
                "old": "***REDACTED***",
                "new": "***REDACTED***",
            }  # Don't log full queries
        if query_type is not None and query_type != original_values["query_type"]:
            changes["query_type"] = {"old": original_values["query_type"], "new": query_type}
        if description is not None and description != original_values["description"]:
            changes["description"] = {"old": original_values["description"], "new": description}
        if schema is not None and schema != original_values["schema"]:
            changes["schema"] = {
                "old": "***REDACTED***",
                "new": "***REDACTED***",
            }  # Don't log full schemas
        if sources is not None and sources != original_values["sources"]:
            changes["sources"] = {
                "old": len(original_values["sources"]) if original_values["sources"] else 0,
                "new": len(sources) if sources else 0,
            }
        if version is not None and version != original_values["version"]:
            changes["version"] = {"old": original_values["version"], "new": version}
        if status is not None and status != original_values["status"]:
            changes["status"] = {"old": original_values["status"], "new": status}

        # Update search index
        self._update_search_index(virtual_dataset)

        # Publish update event
        previous_status = original_values["status"]
        new_status = virtual_dataset.status
        self.publish_virtual_dataset_updated(
            virtual_dataset_id=str(virtual_dataset.id),
            tenant_id=effective_tenant_id,
            user_id=effective_user_id,
            changes=changes,
            previous_status=str(previous_status) if previous_status else None,
            new_status=str(new_status) if new_status else None,
        )

        # Create audit log
        try:
            if name is not None and name != original_values["name"]:
                changes["name"] = {"old": original_values["name"], "new": name}
            if query is not None and query != original_values["query"]:
                changes["query"] = {
                    "old": "***REDACTED***",
                    "new": "***REDACTED***",
                }  # Don't log full queries
            if query_type is not None and query_type != original_values["query_type"]:
                changes["query_type"] = {"old": original_values["query_type"], "new": query_type}
            if description is not None and description != original_values["description"]:
                changes["description"] = {"old": original_values["description"], "new": description}
            if schema is not None and schema != original_values["schema"]:
                changes["schema"] = {
                    "old": "***REDACTED***",
                    "new": "***REDACTED***",
                }  # Don't log full schemas
            if sources is not None and sources != original_values["sources"]:
                changes["sources"] = {
                    "old": len(original_values["sources"]) if original_values["sources"] else 0,
                    "new": len(sources) if sources else 0,
                }
            if version is not None and version != original_values["version"]:
                changes["version"] = {"old": original_values["version"], "new": version}
            if status is not None and status != original_values["status"]:
                changes["status"] = {"old": original_values["status"], "new": status}

            audit_details = {
                "dataset_id": str(virtual_dataset.id),
                "query_type": virtual_dataset.query_type,
                "sources": virtual_dataset.get_sources() or [],
                "changes": changes if changes else {},
                "name": virtual_dataset.name,
                "version": virtual_dataset.version,
                "status": virtual_dataset.status,
            }
            create_audit_event(
                resource_type="VIRTUAL_DATASET",
                action="UPDATED",
                actor_user=user,
                tenant=tenant,
                resource_id=str(virtual_dataset.id),
                result="SUCCESS",
                details=audit_details,
            )
        except Exception as e:
            # Log but don't fail dataset update if audit logging fails
            logger.warning(
                f"Failed to create audit log for virtual dataset update {virtual_dataset.id}: {e}",
                extra={
                    "virtual_dataset_id": str(virtual_dataset.id),
                    "tenant_id": effective_tenant_id,
                    "error": str(e),
                },
                exc_info=True,
            )

        logger.info(
            f"Virtual dataset updated successfully: {virtual_dataset.id}",
            extra={
                "virtual_dataset_id": str(virtual_dataset.id),
                "tenant_id": effective_tenant_id,
                "user_id": effective_user_id,
            },
        )

        return virtual_dataset

    @transaction.atomic
    def delete_virtual_dataset(
        self,
        virtual_dataset_id: str,
        tenant_id: str | None = None,
        user_id: str | None = None,
    ) -> None:
        """
        Delete a virtual dataset with comprehensive audit logging.

        Args:
            virtual_dataset_id: ID of the virtual dataset to delete
            tenant_id: Tenant ID (optional, uses service default if not provided)
            user_id: User ID performing the deletion (optional, uses service default if not provided)

        Raises:
            NotFoundError: If virtual dataset not found
            ValidationError: If validation fails
            PermissionError: If user lacks required permissions
        """
        from django.contrib.auth import get_user_model

        from hub.apps.audit.utils import create_audit_event
        from hub.apps.tenants.models import Tenant

        effective_tenant_id = tenant_id or self.tenant_id
        if not effective_tenant_id:
            raise ValidationError("tenant_id is required")

        effective_user_id = user_id or self.user_id
        if not effective_user_id:
            raise ValidationError("user_id is required")

        # Get tenant and user objects
        try:
            tenant = Tenant.objects.get(id=effective_tenant_id)
        except Tenant.DoesNotExist:
            raise NotFoundError(f"Tenant with id {effective_tenant_id} not found")

        User = get_user_model()
        try:
            user = User.objects.get(id=effective_user_id)
        except User.DoesNotExist:
            raise NotFoundError(f"User with id {effective_user_id} not found")

        # Get virtual dataset
        try:
            virtual_dataset = VirtualDataset.objects.get(
                id=virtual_dataset_id, tenant_id=effective_tenant_id
            )
        except VirtualDataset.DoesNotExist:
            raise NotFoundError(f"Virtual dataset with id {virtual_dataset_id} not found")

        # Store dataset info for audit log before deletion
        dataset_info = {
            "dataset_id": str(virtual_dataset.id),
            "name": virtual_dataset.name,
            "query_type": virtual_dataset.query_type,
            "sources": virtual_dataset.get_sources() or [],
            "version": virtual_dataset.version,
            "status": virtual_dataset.status,
        }

        # Check user permissions
        try:
            self._check_user_permissions(effective_user_id, effective_tenant_id)
        except PermissionError as e:
            logger.warning(
                f"User permission check failed for virtual dataset deletion: {e!s}",
                extra={
                    "tenant_id": effective_tenant_id,
                    "user_id": effective_user_id,
                    "virtual_dataset_id": virtual_dataset_id,
                },
            )
            raise

        # Remove from search index
        self._remove_from_search_index(
            virtual_dataset_id=str(virtual_dataset.id), tenant_id=effective_tenant_id
        )

        # Publish delete event
        self.publish_virtual_dataset_deleted(
            virtual_dataset_id=str(virtual_dataset.id),
            tenant_id=effective_tenant_id,
            user_id=effective_user_id,
            reason="User requested deletion",
        )

        # Create audit log before deletion
        try:
            create_audit_event(
                resource_type="VIRTUAL_DATASET",
                action="DELETED",
                actor_user=user,
                tenant=tenant,
                resource_id=str(virtual_dataset.id),
                result="SUCCESS",
                details=dataset_info,
            )
        except Exception as e:
            # Log but don't fail dataset deletion if audit logging fails
            logger.warning(
                f"Failed to create audit log for virtual dataset deletion {virtual_dataset.id}: {e}",
                extra={
                    "virtual_dataset_id": str(virtual_dataset.id),
                    "tenant_id": effective_tenant_id,
                    "error": str(e),
                },
                exc_info=True,
            )

        # Delete the virtual dataset
        virtual_dataset.delete()

        logger.info(
            f"Virtual dataset deleted successfully: {virtual_dataset_id}",
            extra={
                "virtual_dataset_id": virtual_dataset_id,
                "tenant_id": effective_tenant_id,
                "user_id": effective_user_id,
            },
        )

    def _update_search_index(self, virtual_dataset: VirtualDataset) -> None:
        """
        Update search index for a virtual dataset.

        This is a helper method that can be called from update methods
        to keep the search index in sync with virtual dataset changes.

        Args:
            virtual_dataset: VirtualDataset instance to index
        """
        try:
            from hub.apps.search.indexing import SearchIndexer

            SearchIndexer.index_virtual_dataset(virtual_dataset)
        except Exception as e:
            # Log but don't fail operation if indexing fails
            logger.warning(
                f"Failed to update search index for virtual dataset {virtual_dataset.id}: {e}",
                extra={
                    "virtual_dataset_id": str(virtual_dataset.id),
                    "tenant_id": str(virtual_dataset.tenant_id),
                    "error": str(e),
                },
                exc_info=True,
            )

    def _remove_from_search_index(self, virtual_dataset_id: str, tenant_id: str) -> None:
        """
        Remove virtual dataset from search index.

        This is a helper method that can be called from delete methods
        to remove the virtual dataset from the search index.

        Args:
            virtual_dataset_id: Virtual dataset ID
            tenant_id: Tenant ID
        """
        try:
            from hub.apps.search.indexing import SearchIndexer

            SearchIndexer.delete_index(
                tenant_id=tenant_id, resource_type="VIRTUAL_DATASET", resource_id=virtual_dataset_id
            )
        except Exception as e:
            # Log but don't fail operation if index removal fails
            logger.warning(
                f"Failed to remove virtual dataset {virtual_dataset_id} from search index: {e}",
                extra={
                    "virtual_dataset_id": virtual_dataset_id,
                    "tenant_id": tenant_id,
                    "error": str(e),
                },
                exc_info=True,
            )
