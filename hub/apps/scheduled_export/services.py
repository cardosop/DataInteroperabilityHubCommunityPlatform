"""
Scheduled Export Service

Service layer for scheduled export operations.
All create/update paths call ScheduledExportBusinessRules before mutation.
"""

import logging
from typing import Any, Dict, Optional

from django.db import transaction

from hub.apps.audit.utils import create_audit_event
from hub.apps.core.services.base import BaseService, NotFoundError, ValidationError
from hub.apps.scheduled_export.business_rules import ScheduledExportBusinessRules
from hub.apps.scheduled_export.models import (
    DestinationType,
    ScheduledExport,
    ScheduledExportRun,
    ScheduledExportRunStatus,
    ScheduledExportStatus,
)

logger = logging.getLogger(__name__)


class ScheduledExportService(BaseService):
    """
    Service for scheduled export operations.

    Provides business logic for:
    - Scheduled export execution
    - Export status monitoring
    - Export configuration management
    - Export item processing
    """

    service_name = "scheduled_export_service"

    def __init__(self, tenant_id: Optional[str] = None, user_id: Optional[str] = None):
        """
        Initialize ScheduledExportService.

        Args:
            tenant_id: Optional tenant ID
            user_id: Optional user ID
        """
        self.tenant_id = tenant_id
        self.user_id = user_id
        super().__init__()

    def process_export_item(
        self,
        run_id: str,
        dataset_id: Optional[str] = None,
        file_id: Optional[str] = None,
        destination_path: Optional[str] = None,
        destination_options: Optional[Dict[str, Any]] = None,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Process a single export item (dataset or file) for a scheduled export run.

        Validates:
        - Run exists and belongs to tenant
        - Scheduled export is active
        - Item (dataset/file) is in source_scope
        - User has access to the item
        - Destination configuration is valid

        Prepares:
        - Export payload or signed URL
        - Upload instructions

        Args:
            run_id: Export run ID
            dataset_id: Optional dataset ID to export
            file_id: Optional file ID to export
            destination_path: Optional destination path override
            destination_options: Optional destination-specific options
            tenant_id: Optional tenant ID (uses service tenant_id if not provided)
            user_id: Optional user ID (uses service user_id if not provided)

        Returns:
            Dictionary with export instructions:
            {
                "success": True,
                "item_id": "...",
                "item_type": "dataset" | "file",
                "upload_url": "...",  # For signed URL uploads
                "upload_method": "PUT" | "POST",
                "upload_headers": {...},
                "payload": {...},  # For direct payload uploads
                "destination_path": "...",
            }

        Raises:
            NotFoundError: If run, dataset, or file not found
            ValidationError: If validation fails
        """
        tenant_id = tenant_id or self.tenant_id
        user_id = user_id or self.user_id

        if not tenant_id:
            raise ValidationError(
                "Tenant ID is required",
                code="TENANT_REQUIRED",
                details={},
            )

        # Get export run
        try:
            export_run = ScheduledExportRun.objects.select_related(
                "scheduled_export", "tenant"
            ).get(id=run_id, tenant_id=tenant_id)
        except ScheduledExportRun.DoesNotExist:
            raise NotFoundError(
                f"Export run {run_id} not found",
                details={"resource_type": "SCHEDULED_EXPORT_RUN", "resource_id": run_id},
            )

        scheduled_export = export_run.scheduled_export

        # Validate scheduled export is active
        if scheduled_export.status != ScheduledExportStatus.ACTIVE:
            raise ValidationError(
                f"Scheduled export {scheduled_export.id} is not active (status: {scheduled_export.status})",
                code="EXPORT_NOT_ACTIVE",
                details={
                    "scheduled_export_id": str(scheduled_export.id),
                    "status": scheduled_export.status,
                },
            )

        # Validate exactly one item is provided
        if not dataset_id and not file_id:
            raise ValidationError(
                "Either dataset_id or file_id must be provided",
                code="ITEM_REQUIRED",
                details={},
            )
        if dataset_id and file_id:
            raise ValidationError(
                "Only one of dataset_id or file_id can be provided",
                code="MULTIPLE_ITEMS",
                details={},
            )

        # Get user if provided (worker API may not have user)
        user = None
        if user_id:
            from hub.apps.users.models import User

            try:
                user = User.objects.get(id=user_id, tenant_id=tenant_id)
            except User.DoesNotExist:
                # User not found - this is OK for worker API
                pass

        # Resolve item first so "not found" yields NotFoundError before scope check
        source_scope = scheduled_export.source_scope
        item_id = dataset_id or file_id
        item_type = "dataset" if dataset_id else "file"

        if dataset_id:
            from hub.apps.datasets.models import Dataset

            try:
                item = Dataset.objects.select_related("asset").get(
                    id=dataset_id, tenant_id=tenant_id
                )
            except Dataset.DoesNotExist:
                raise NotFoundError(
                    f"Dataset {dataset_id} not found",
                    details={"resource_type": "DATASET", "resource_id": dataset_id},
                )
        else:
            from hub.apps.files.models import File

            try:
                item = File.objects.get(id=file_id, tenant_id=tenant_id)
            except File.DoesNotExist:
                raise NotFoundError(
                    f"File {file_id} not found",
                    details={"resource_type": "FILE", "resource_id": file_id},
                )

        # Validate item is in source_scope
        in_scope = False
        if dataset_id:
            dataset_ids = source_scope.get("dataset_ids", [])
            in_scope = str(dataset_id) in [str(did) for did in dataset_ids]
        elif file_id:
            file_ids = source_scope.get("file_ids", [])
            in_scope = str(file_id) in [str(fid) for fid in file_ids]

        if not in_scope and source_scope.get("contract_id"):
            contract_id = source_scope.get("contract_id")
            from hub.apps.contracts.models import Contract

            if dataset_id and getattr(item, "asset", None):
                contracts = Contract.objects.filter(
                    asset=item.asset, tenant_id=tenant_id, id=contract_id
                )
                if contracts.exists():
                    in_scope = True
            elif file_id:
                from hub.apps.datasets.models import Dataset

                for dataset in Dataset.objects.filter(
                    file=item, tenant_id=tenant_id
                ).select_related("asset"):
                    if dataset.asset:
                        contracts = Contract.objects.filter(
                            asset=dataset.asset, tenant_id=tenant_id, id=contract_id
                        )
                        if contracts.exists():
                            in_scope = True
                            break

        if not in_scope:
            raise ValidationError(
                f"{item_type.capitalize()} {item_id} is not in scheduled export source_scope",
                code="ITEM_NOT_IN_SCOPE",
                details={"item_id": item_id, "item_type": item_type, "source_scope": source_scope},
            )

        # Apply business rules validation
        rules = ScheduledExportBusinessRules(tenant_id=tenant_id, user_id=user_id)

        # Validate access (only if user provided - worker API may not have user)
        if user:
            access_result = rules.validate(
                scheduled_export=scheduled_export,
                tenant=export_run.tenant,
                user=user,
                validation_type="access",
            )
            if not access_result.is_valid:
                raise ValidationError(
                    f"Access denied to {item_type} {item_id}: {', '.join(access_result.errors)}",
                    code="ACCESS_DENIED",
                    details=access_result.details,
                )

        # Prepare export payload/URL based on destination type
        destination_type = scheduled_export.destination_type
        destination_config = scheduled_export.destination_config.copy()
        destination_path = destination_path or destination_config.get("prefix", "")

        # For now, return structured response with upload instructions
        # In production, this would generate signed URLs or prepare payloads
        result = {
            "success": True,
            "item_id": item_id,
            "item_type": item_type,
            "destination_type": destination_type,
            "destination_path": destination_path,
            "upload_method": "PUT",  # Default for S3/GCS/Azure
        }

        # Add item-specific data
        if item_type == "dataset":
            result["dataset_id"] = dataset_id
            # Dataset doesn't have a name field - use file name or asset name
            if hasattr(item, "file") and item.file:
                result["file_id"] = str(item.file.id)
                result["file_size"] = item.file.size
                result["file_content_type"] = item.file.content_type
                result["file_name"] = getattr(item.file, "name", None)
            if hasattr(item, "asset") and item.asset:
                result["asset_name"] = getattr(item.asset, "name", None)
        else:
            result["file_id"] = file_id
            result["file_name"] = getattr(item, "name", None)
            result["file_size"] = getattr(item, "size", None)
            result["file_content_type"] = getattr(item, "content_type", None)

        # Generate upload instructions based on destination type
        # Note: In production, this would generate actual signed URLs
        # For now, return instructions for worker to generate URLs
        if destination_type == DestinationType.S3:
            bucket = destination_config.get("bucket")
            result["upload_url"] = f"s3://{bucket}/{destination_path}"
            result["upload_headers"] = {
                "Content-Type": result.get("file_content_type", "application/octet-stream"),
            }
        elif destination_type == DestinationType.GCS:
            bucket = destination_config.get("bucket")
            result["upload_url"] = f"gs://{bucket}/{destination_path}"
            result["upload_headers"] = {
                "Content-Type": result.get("file_content_type", "application/octet-stream"),
            }
        elif destination_type == DestinationType.AZURE_BLOB:
            container = destination_config.get("container")
            account_name = destination_config.get("account_name")
            result["upload_url"] = (
                f"https://{account_name}.blob.core.windows.net/{container}/{destination_path}"
            )
            result["upload_headers"] = {
                "Content-Type": result.get("file_content_type", "application/octet-stream"),
            }

        # Add destination options
        if destination_options:
            result["destination_options"] = destination_options

        return result

    @transaction.atomic
    def create_scheduled_export(
        self,
        tenant,
        created_by,
        name: str,
        destination_type: str,
        destination_config: Dict[str, Any],
        schedule_config: Dict[str, Any],
        source_scope: Dict[str, Any],
        **kwargs,
    ) -> ScheduledExport:
        """
        Create a scheduled export. Validates via ScheduledExportBusinessRules before mutation.

        Returns:
            Created ScheduledExport instance.

        Raises:
            ValidationError: If ScheduledExportBusinessRules reject.
        """
        # Create payload for validation
        payload = ScheduledExport(
            tenant=tenant,
            name=name,
            destination_type=destination_type,
            destination_config=destination_config,
            schedule_config=schedule_config,
            source_scope=source_scope,
            status=ScheduledExportStatus.ACTIVE,
        )

        # Validate via business rules
        rules = ScheduledExportBusinessRules(
            tenant_id=str(tenant.id),
            user_id=str(created_by.id) if created_by else None,
        )
        result = rules.validate(
            scheduled_export=payload,
            tenant=tenant,
            user=created_by,
            validation_type="all",
        )
        if not result.is_valid:
            raise ValidationError(
                "; ".join(result.errors),
                code="BUSINESS_RULES_VALIDATION",
                details=result.details,
            )

        # Check plan limit (Phase 25.4.1)
        from hub.apps.tenants.services import PlanLimitService

        current_scheduled_export_count = ScheduledExport.objects.filter(tenant=tenant).count()
        plan_limit_service = PlanLimitService(
            tenant_id=str(tenant.id), user_id=str(created_by.id) if created_by else None
        )
        plan_limit_service.check_limit(
            tenant_id=str(tenant.id),
            limit_key="max_scheduled_exports",
            current_usage=current_scheduled_export_count,
            delta=1,
        )

        # Create scheduled export
        create_kw = dict(
            tenant=tenant,
            name=name,
            destination_type=destination_type,
            destination_config=destination_config,
            schedule_config=schedule_config,
            source_scope=source_scope,
            status=ScheduledExportStatus.ACTIVE,
        )
        scheduled_export = ScheduledExport.objects.create(**create_kw)

        # Emit audit event
        try:
            create_audit_event(
                resource_type="SCHEDULED_EXPORT",
                action="CREATED",
                actor_user=created_by,
                tenant=tenant,
                resource_id=str(scheduled_export.id),
                details={
                    "scheduled_export_id": str(scheduled_export.id),
                    "name": scheduled_export.name,
                    "destination_type": scheduled_export.destination_type,
                    "status": scheduled_export.status,
                },
            )
        except Exception as e:
            logger.warning(
                "Failed to create audit event for scheduled export creation %s: %s",
                str(scheduled_export.id),
                str(e),
            )

        return scheduled_export

    @transaction.atomic
    def update_scheduled_export(
        self,
        scheduled_export_id: str,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        name: Optional[str] = None,
        destination_type: Optional[str] = None,
        destination_config: Optional[Dict[str, Any]] = None,
        schedule_config: Optional[Dict[str, Any]] = None,
        source_scope: Optional[Dict[str, Any]] = None,
        status: Optional[str] = None,
        **kwargs,
    ) -> ScheduledExport:
        """
        Update a scheduled export. Validates via ScheduledExportBusinessRules before mutation.

        Args:
            scheduled_export_id: Scheduled export ID
            tenant_id: Optional tenant ID for filtering
            user_id: Optional user ID
            name: Optional name to update
            destination_type: Optional destination type to update
            destination_config: Optional destination config to update
            schedule_config: Optional schedule config to update
            source_scope: Optional source scope to update
            status: Optional status to update
            description: Optional description to update
            **kwargs: Additional fields to update

        Returns:
            Updated ScheduledExport instance.

        Raises:
            NotFoundError: If scheduled export not found
            ValidationError: If ScheduledExportBusinessRules reject.
        """
        effective_tenant_id = tenant_id or self.tenant_id
        if not effective_tenant_id:
            raise ValidationError("tenant_id is required", code="TENANT_REQUIRED", details={})

        # Get scheduled export
        scheduled_export = self.get_resource_or_raise(
            ScheduledExport,
            scheduled_export_id,
            tenant_id=effective_tenant_id,
        )

        # Get user if provided
        user = None
        if user_id:
            from hub.apps.users.models import User

            try:
                user = User.objects.get(id=user_id, tenant_id=effective_tenant_id)
            except User.DoesNotExist:
                pass

        # Get tenant
        from hub.apps.tenants.models import Tenant

        tenant = Tenant.objects.get(id=effective_tenant_id)

        # Prepare update payload
        update_fields = []
        if name is not None:
            scheduled_export.name = name
            update_fields.append("name")
        if destination_type is not None:
            scheduled_export.destination_type = destination_type
            update_fields.append("destination_type")
        if destination_config is not None:
            scheduled_export.destination_config = destination_config
            update_fields.append("destination_config")
        if schedule_config is not None:
            scheduled_export.schedule_config = schedule_config
            update_fields.append("schedule_config")
            # Recalculate next_run_at if schedule changed
            scheduled_export.next_run_at = scheduled_export._calculate_next_run_at()
            update_fields.append("next_run_at")
        if source_scope is not None:
            scheduled_export.source_scope = source_scope
            update_fields.append("source_scope")
        if status is not None:
            scheduled_export.status = status
            update_fields.append("status")

        # Validate via business rules before saving
        rules = ScheduledExportBusinessRules(
            tenant_id=effective_tenant_id,
            user_id=user_id,
        )
        result = rules.validate(
            scheduled_export=scheduled_export,
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

        # Save updates
        if update_fields:
            update_fields.append("updated_at")
            scheduled_export.save(update_fields=update_fields)

        # Emit audit event
        try:
            create_audit_event(
                resource_type="SCHEDULED_EXPORT",
                action="UPDATED",
                actor_user=user,
                tenant=tenant,
                resource_id=str(scheduled_export.id),
                details={
                    "scheduled_export_id": str(scheduled_export.id),
                    "updated_fields": update_fields,
                    "status": scheduled_export.status,
                },
            )
        except Exception as e:
            logger.warning(
                "Failed to create audit event for scheduled export update %s: %s",
                str(scheduled_export.id),
                str(e),
            )

        return scheduled_export

    @transaction.atomic
    def delete_scheduled_export(
        self,
        scheduled_export_id: str,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> None:
        """
        Delete a scheduled export.

        Args:
            scheduled_export_id: Scheduled export ID
            tenant_id: Optional tenant ID for filtering
            user_id: Optional user ID

        Raises:
            NotFoundError: If scheduled export not found
        """
        effective_tenant_id = tenant_id or self.tenant_id
        if not effective_tenant_id:
            raise ValidationError("tenant_id is required", code="TENANT_REQUIRED", details={})

        # Get scheduled export
        scheduled_export = self.get_resource_or_raise(
            ScheduledExport,
            scheduled_export_id,
            tenant_id=effective_tenant_id,
        )

        # Get user if provided
        user = None
        if user_id:
            from hub.apps.users.models import User

            try:
                user = User.objects.get(id=user_id, tenant_id=effective_tenant_id)
            except User.DoesNotExist:
                pass

        # Get tenant
        from hub.apps.tenants.models import Tenant

        tenant = Tenant.objects.get(id=effective_tenant_id)

        # Emit audit event before deletion
        try:
            create_audit_event(
                resource_type="SCHEDULED_EXPORT",
                action="DELETED",
                actor_user=user,
                tenant=tenant,
                resource_id=str(scheduled_export.id),
                details={
                    "scheduled_export_id": str(scheduled_export.id),
                    "name": scheduled_export.name,
                },
            )
        except Exception as e:
            logger.warning(
                "Failed to create audit event for scheduled export deletion %s: %s",
                str(scheduled_export.id),
                str(e),
            )

        # Delete scheduled export
        scheduled_export.delete()

    def create_export_run(
        self,
        scheduled_export_id: str,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        prefect_flow_run_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> ScheduledExportRun:
        """
        Create a scheduled export run. Used by internal API.

        Args:
            scheduled_export_id: Scheduled export ID
            tenant_id: Optional tenant ID
            user_id: Optional user ID
            prefect_flow_run_id: Optional Prefect flow run ID
            idempotency_key: Optional idempotency key

        Returns:
            Created ScheduledExportRun instance.

        Raises:
            NotFoundError: If scheduled export not found
            ValidationError: If validation fails
        """
        effective_tenant_id = tenant_id or self.tenant_id
        effective_user_id = user_id or self.user_id
        if not effective_tenant_id:
            raise ValidationError("tenant_id is required", code="TENANT_REQUIRED", details={})

        # Get scheduled export
        scheduled_export = self.get_resource_or_raise(
            ScheduledExport,
            scheduled_export_id,
            tenant_id=effective_tenant_id,
        )

        # Check idempotency by prefect_flow_run_id
        if prefect_flow_run_id:
            existing = ScheduledExportRun.objects.filter(
                scheduled_export=scheduled_export,
                prefect_flow_run_id=prefect_flow_run_id,
            ).first()
            if existing:
                return existing

        # Check idempotency by idempotency_key
        if idempotency_key:
            for r in ScheduledExportRun.objects.filter(scheduled_export=scheduled_export).order_by(
                "-created_at"
            )[:100]:
                if (r.result_json or {}).get("idempotency_key") == idempotency_key:
                    return r

        # Check plan limit for export runs per month (Phase 25.4.1)
        from datetime import datetime, timedelta

        from django.utils import timezone

        from hub.apps.tenants.services import PlanLimitService

        now = timezone.now()
        month_start = datetime(now.year, now.month, 1, tzinfo=now.tzinfo)
        current_month_runs_count = ScheduledExportRun.objects.filter(
            scheduled_export__tenant_id=effective_tenant_id, created_at__gte=month_start
        ).count()
        plan_limit_service = PlanLimitService(
            tenant_id=effective_tenant_id, user_id=effective_user_id
        )
        plan_limit_service.check_limit(
            tenant_id=effective_tenant_id,
            limit_key="max_export_runs_per_month",
            current_usage=current_month_runs_count,
            delta=1,
        )

        # Create run
        run = ScheduledExportRun.objects.create(
            scheduled_export=scheduled_export,
            tenant=scheduled_export.tenant,
            status=ScheduledExportRunStatus.RUNNING,
            prefect_flow_run_id=prefect_flow_run_id or None,
            result_json={"idempotency_key": idempotency_key} if idempotency_key else {},
        )

        return run

    def update_export_run(
        self,
        run_id: str,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        status: Optional[str] = None,
        items_found: Optional[int] = None,
        items_exported: Optional[int] = None,
        items_failed: Optional[int] = None,
        result_json: Optional[Dict[str, Any]] = None,
        completed_at: Optional[str] = None,
        prefect_flow_run_id: Optional[str] = None,
    ) -> ScheduledExportRun:
        """
        Update a scheduled export run. Used by internal API.

        Args:
            run_id: Export run ID
            tenant_id: Optional tenant ID
            user_id: Optional user ID
            status: Optional status to update
            items_found: Optional items_found to update
            items_exported: Optional items_exported to update
            items_failed: Optional items_failed to update
            result_json: Optional result_json to update
            completed_at: Optional completed_at (ISO format string)
            prefect_flow_run_id: Optional prefect_flow_run_id to update

        Returns:
            Updated ScheduledExportRun instance.

        Raises:
            NotFoundError: If run not found
            ValidationError: If validation fails
        """
        effective_tenant_id = tenant_id or self.tenant_id
        if not effective_tenant_id:
            raise ValidationError("tenant_id is required", code="TENANT_REQUIRED", details={})

        # Get run
        try:
            run = ScheduledExportRun.objects.select_related("scheduled_export", "tenant").get(
                id=run_id, tenant_id=effective_tenant_id
            )
        except ScheduledExportRun.DoesNotExist:
            raise NotFoundError(
                f"Export run {run_id} not found",
                details={"resource_type": "SCHEDULED_EXPORT_RUN", "resource_id": run_id},
            )

        # Update fields
        update_fields = []
        if status is not None:
            run.status = status
            update_fields.append("status")
        if items_found is not None:
            run.items_found = items_found
            update_fields.append("items_found")
        if items_exported is not None:
            run.items_exported = items_exported
            update_fields.append("items_exported")
        if items_failed is not None:
            run.items_failed = items_failed
            update_fields.append("items_failed")
        if result_json is not None:
            run.result_json = result_json
            update_fields.append("result_json")
        if completed_at is not None:
            from django.utils.dateparse import parse_datetime

            parsed_completed_at = parse_datetime(completed_at)
            if parsed_completed_at:
                run.completed_at = parsed_completed_at
                update_fields.append("completed_at")
        if prefect_flow_run_id is not None:
            run.prefect_flow_run_id = prefect_flow_run_id
            update_fields.append("prefect_flow_run_id")

        # Save updates
        if update_fields:
            update_fields.append("updated_at")
            run.save(update_fields=update_fields)

        return run
