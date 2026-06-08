"""
Service Event Publishers

Event publisher mixins for each service to enable event publishing.
"""

import time
from typing import Any, Dict, Optional, Callable, List
import structlog

from .publisher import EventPublisher
from .bus import EventBusError, EventPublishError

logger = structlog.get_logger(__name__)


class ContractEventPublisher:
    """Event publisher mixin for ContractService."""

    def __init__(self, *args, **kwargs):
        # Only call super().__init__ if parent class supports it
        # BaseService doesn't have __init__, so we skip calling super
        # The actual service class (ContractService) handles initialization
        try:
            # Check if parent has __init__ that accepts arguments
            parent_init = super().__init__
            if parent_init is not object.__init__:
                parent_init(*args, **kwargs)
        except (TypeError, AttributeError):
            # Parent doesn't support __init__ with arguments, skip
            pass
        self._event_publisher = EventPublisher(
            service_name="contract_service",
            tenant_id=getattr(self, "tenant_id", None),
            user_id=getattr(self, "user_id", None),
        )

    def publish_contract_created(
        self,
        contract_id: str,
        asset_id: Optional[str] = None,
        status: Optional[str] = None,
        original_format: Optional[str] = None,
        original_spec_version: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish contract.created event."""
        return self._event_publisher.publish(
            event_type="contract.created",
            data={
                "contract_id": contract_id,
                "asset_id": asset_id,
                "status": status,
                "original_format": original_format,
                "original_spec_version": original_spec_version,
            },
            **kwargs,
        )

    def publish_contract_updated(
        self,
        contract_id: str,
        changes: Dict[str, Any],
        previous_status: Optional[str] = None,
        new_status: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish contract.updated event."""
        return self._event_publisher.publish(
            event_type="contract.updated",
            data={
                "contract_id": contract_id,
                "changes": changes,
                "previous_status": previous_status,
                "new_status": new_status,
            },
            **kwargs,
        )

    def publish_contract_deleted(
        self, contract_id: str, reason: Optional[str] = None, **kwargs
    ) -> str:
        """Publish contract.deleted event."""
        from django.utils import timezone

        return self._event_publisher.publish(
            event_type="contract.deleted",
            data={
                "contract_id": contract_id,
                "deleted_at": timezone.now().isoformat(),
                "reason": reason,
            },
            **kwargs,
        )

    def publish_contract_validated(
        self,
        contract_id: str,
        validation_result: bool,
        validation_errors: Optional[list] = None,
        validation_warnings: Optional[list] = None,
        **kwargs,
    ) -> str:
        """Publish contract.validated event."""
        return self._event_publisher.publish(
            event_type="contract.validated",
            data={
                "contract_id": contract_id,
                "validation_result": validation_result,
                "validation_errors": validation_errors or [],
                "validation_warnings": validation_warnings or [],
            },
            **kwargs,
        )

    def publish_contract_normalized(
        self,
        contract_id: str,
        normalization_status: str,
        normalization_errors: Optional[list] = None,
        **kwargs,
    ) -> str:
        """Publish contract.normalized event."""
        return self._event_publisher.publish(
            event_type="contract.normalized",
            data={
                "contract_id": contract_id,
                "normalization_status": normalization_status,
                "normalization_errors": normalization_errors,
            },
            **kwargs,
        )


class AssetEventPublisher:
    """Event publisher mixin for AssetService."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._event_publisher = EventPublisher(
            service_name="asset_service",
            tenant_id=getattr(self, "tenant_id", None),
            user_id=getattr(self, "user_id", None),
        )

    def publish_asset_created(
        self,
        asset_id: str,
        name: Optional[str] = None,
        domain: Optional[str] = None,
        status: Optional[str] = None,
        contract_id: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish asset.created event."""
        return self._event_publisher.publish(
            event_type="asset.created",
            data={
                "asset_id": asset_id,
                "name": name,
                "domain": domain,
                "status": status,
                "contract_id": contract_id,
            },
            **kwargs,
        )

    def publish_asset_updated(
        self,
        asset_id: str,
        changes: Dict[str, Any],
        previous_status: Optional[str] = None,
        new_status: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish asset.updated event."""
        return self._event_publisher.publish(
            event_type="asset.updated",
            data={
                "asset_id": asset_id,
                "changes": changes,
                "previous_status": previous_status,
                "new_status": new_status,
            },
            **kwargs,
        )

    def publish_asset_activated(
        self,
        asset_id: str,
        activation_reason: Optional[str] = None,
        dq_status: Optional[str] = None,
        compliance_status: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish asset.activated event."""
        return self._event_publisher.publish(
            event_type="asset.activated",
            data={
                "asset_id": asset_id,
                "activation_reason": activation_reason,
                "dq_status": dq_status,
                "compliance_status": compliance_status,
            },
            **kwargs,
        )

    def publish_asset_published(
        self,
        asset_id: str,
        marketplace_listing_id: str,
        pricing_model: Optional[str] = None,
        license_type: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish asset.published event."""
        from django.utils import timezone

        return self._event_publisher.publish(
            event_type="asset.published",
            data={
                "asset_id": asset_id,
                "marketplace_listing_id": marketplace_listing_id,
                "pricing_model": pricing_model,
                "license_type": license_type,
            },
            **kwargs,
        )

    def publish_asset_retired(
        self, asset_id: str, retirement_reason: Optional[str] = None, **kwargs
    ) -> str:
        """Publish asset.retired event."""
        from django.utils import timezone

        return self._event_publisher.publish(
            event_type="asset.retired",
            data={
                "asset_id": asset_id,
                "retirement_reason": retirement_reason,
                "retired_at": timezone.now().isoformat(),
            },
            **kwargs,
        )


class DatasetEventPublisher:
    """Event publisher mixin for DatasetService."""

    def __init__(self, *args, **kwargs):
        # Only call super().__init__ if parent class supports it
        # BaseService doesn't have __init__, so we skip calling super
        # The actual service class (DatasetService) handles initialization
        try:
            # Check if parent has __init__ that accepts arguments
            parent_init = super().__init__
            if parent_init is not object.__init__:
                parent_init(*args, **kwargs)
        except (TypeError, AttributeError):
            # Parent doesn't support __init__ with arguments, skip
            pass
        # Set tenant_id and user_id from kwargs if provided
        if 'tenant_id' in kwargs:
            self.tenant_id = kwargs['tenant_id']
        if 'user_id' in kwargs:
            self.user_id = kwargs['user_id']
        self._event_publisher = EventPublisher(
            service_name="dataset_service",
            tenant_id=getattr(self, "tenant_id", None),
            user_id=getattr(self, "user_id", None),
        )

    def publish_dataset_created(
        self,
        dataset_id: str,
        asset_id: Optional[str] = None,
        file_id: Optional[str] = None,
        format: Optional[str] = None,
        schema_inferred: Optional[bool] = None,
        **kwargs,
    ) -> str:
        """Publish dataset.created event."""
        return self._event_publisher.publish(
            event_type="dataset.created",
            data={
                "dataset_id": dataset_id,
                "asset_id": asset_id,
                "file_id": file_id,
                "format": format,
                "schema_inferred": schema_inferred,
            },
            **kwargs,
        )

    def publish_dataset_updated(
        self, dataset_id: str, changes: Dict[str, Any], file_id: Optional[str] = None, **kwargs
    ) -> str:
        """Publish dataset.updated event."""
        return self._event_publisher.publish(
            event_type="dataset.updated",
            data={"dataset_id": dataset_id, "changes": changes, "file_id": file_id},
            **kwargs,
        )

    def publish_dataset_deleted(
        self, dataset_id: str, reason: Optional[str] = None, **kwargs
    ) -> str:
        """Publish dataset.deleted event."""
        from django.utils import timezone

        return self._event_publisher.publish(
            event_type="dataset.deleted",
            data={
                "dataset_id": dataset_id,
                "deleted_at": timezone.now().isoformat(),
                "reason": reason,
            },
            **kwargs,
        )

    def publish_dataset_uploaded(
        self,
        dataset_id: str,
        file_id: str,
        file_size: Optional[int] = None,
        file_format: Optional[str] = None,
        upload_duration_ms: Optional[int] = None,
        **kwargs,
    ) -> str:
        """Publish dataset.uploaded event."""
        return self._event_publisher.publish(
            event_type="dataset.uploaded",
            data={
                "dataset_id": dataset_id,
                "file_id": file_id,
                "file_size": file_size,
                "file_format": file_format,
                "upload_duration_ms": upload_duration_ms,
            },
            **kwargs,
        )


class IngestionEventPublisher:
    """Event publisher mixin for IngestionService."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._event_publisher = EventPublisher(
            service_name="ingestion_service",
            tenant_id=getattr(self, "tenant_id", None),
            user_id=getattr(self, "user_id", None),
        )

    def publish_ingestion_started(
        self,
        ingestion_id: str,
        source_type: str,
        source_config: Optional[Dict[str, Any]] = None,
        scheduled_ingestion_id: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish ingestion.started event."""
        return self._event_publisher.publish(
            event_type="ingestion.started",
            data={
                "ingestion_id": ingestion_id,
                "source_type": source_type,
                "source_config": source_config or {},
                "scheduled_ingestion_id": scheduled_ingestion_id,
            },
            **kwargs,
        )

    def publish_ingestion_completed(
        self,
        ingestion_id: str,
        files_processed: int,
        files_succeeded: int = 0,
        files_failed: int = 0,
        duration_ms: Optional[int] = None,
        datasets_created: Optional[int] = None,
        **kwargs,
    ) -> str:
        """Publish ingestion.completed event."""
        return self._event_publisher.publish(
            event_type="ingestion.completed",
            data={
                "ingestion_id": ingestion_id,
                "files_processed": files_processed,
                "files_succeeded": files_succeeded,
                "files_failed": files_failed,
                "duration_ms": duration_ms,
                "datasets_created": datasets_created or 0,
            },
            **kwargs,
        )

    def publish_ingestion_failed(
        self,
        ingestion_id: str,
        error_message: str,
        error_details: Optional[Dict[str, Any]] = None,
        retry_count: Optional[int] = None,
        **kwargs,
    ) -> str:
        """Publish ingestion.failed event."""
        return self._event_publisher.publish(
            event_type="ingestion.failed",
            data={
                "ingestion_id": ingestion_id,
                "error_message": error_message,
                "error_details": error_details or {},
                "retry_count": retry_count or 0,
            },
            **kwargs,
        )

    def publish_ingestion_file_processed(
        self,
        ingestion_id: str,
        file_id: str,
        status: str,
        dataset_id: Optional[str] = None,
        error_message: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish ingestion.file_processed event."""
        return self._event_publisher.publish(
            event_type="ingestion.file_processed",
            data={
                "ingestion_id": ingestion_id,
                "file_id": file_id,
                "status": status,
                "dataset_id": dataset_id,
                "error_message": error_message,
            },
            **kwargs,
        )


class QualityEventPublisher:
    """Event publisher mixin for QualityService."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._event_publisher = EventPublisher(
            service_name="quality_service",
            tenant_id=getattr(self, "tenant_id", None),
            user_id=getattr(self, "user_id", None),
        )

    def publish_quality_check_started(
        self,
        quality_check_id: str,
        target_type: str,
        target_id: str,
        rules_count: Optional[int] = None,
        **kwargs,
    ) -> str:
        """Publish quality.check.started event."""
        return self._event_publisher.publish(
            event_type="quality.check.started",
            data={
                "quality_check_id": quality_check_id,
                "target_type": target_type,
                "target_id": target_id,
                "rules_count": rules_count,
            },
            **kwargs,
        )

    def publish_quality_check_completed(
        self,
        quality_check_id: str,
        overall_score: float,
        rules_passed: Optional[int] = None,
        rules_failed: Optional[int] = None,
        duration_ms: Optional[int] = None,
        **kwargs,
    ) -> str:
        """Publish quality.check.completed event."""
        return self._event_publisher.publish(
            event_type="quality.check.completed",
            data={
                "quality_check_id": quality_check_id,
                "overall_score": overall_score,
                "rules_passed": rules_passed or 0,
                "rules_failed": rules_failed or 0,
                "duration_ms": duration_ms,
            },
            **kwargs,
        )

    def publish_quality_check_failed(
        self,
        quality_check_id: str,
        error_message: str,
        error_details: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> str:
        """Publish quality.check.failed event."""
        return self._event_publisher.publish(
            event_type="quality.check.failed",
            data={
                "quality_check_id": quality_check_id,
                "error_message": error_message,
                "error_details": error_details or {},
            },
            **kwargs,
        )

    def publish_quality_anomaly_detected(
        self,
        quality_check_id: str,
        anomaly_type: str,
        anomaly_details: Optional[Dict[str, Any]] = None,
        severity: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish quality.anomaly.detected event."""
        return self._event_publisher.publish(
            event_type="quality.anomaly.detected",
            data={
                "quality_check_id": quality_check_id,
                "anomaly_type": anomaly_type,
                "anomaly_details": anomaly_details or {},
                "severity": severity,
            },
            **kwargs,
        )


class ComplianceEventPublisher:
    """Event publisher mixin for ComplianceService."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._event_publisher = EventPublisher(
            service_name="compliance_service",
            tenant_id=getattr(self, "tenant_id", None),
            user_id=getattr(self, "user_id", None),
        )

    def publish_compliance_check_started(
        self,
        compliance_check_id: str,
        target_type: str,
        target_id: str,
        compliance_frameworks: Optional[list] = None,
        **kwargs,
    ) -> str:
        """Publish compliance.check.started event."""
        return self._event_publisher.publish(
            event_type="compliance.check.started",
            data={
                "compliance_check_id": compliance_check_id,
                "target_type": target_type,
                "target_id": target_id,
                "compliance_frameworks": compliance_frameworks or [],
            },
            **kwargs,
        )

    def publish_compliance_check_completed(
        self,
        compliance_check_id: str,
        compliance_status: str,
        frameworks_passed: Optional[list] = None,
        frameworks_failed: Optional[list] = None,
        duration_ms: Optional[int] = None,
        **kwargs,
    ) -> str:
        """Publish compliance.check.completed event."""
        return self._event_publisher.publish(
            event_type="compliance.check.completed",
            data={
                "compliance_check_id": compliance_check_id,
                "compliance_status": compliance_status,
                "frameworks_passed": frameworks_passed or [],
                "frameworks_failed": frameworks_failed or [],
                "duration_ms": duration_ms,
            },
            **kwargs,
        )

    def publish_compliance_check_failed(
        self,
        compliance_check_id: str,
        error_message: str,
        error_details: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> str:
        """Publish compliance.check.failed event."""
        return self._event_publisher.publish(
            event_type="compliance.check.failed",
            data={
                "compliance_check_id": compliance_check_id,
                "error_message": error_message,
                "error_details": error_details or {},
            },
            **kwargs,
        )

    def publish_compliance_report_generated(
        self,
        report_id: str,
        report_type: str,
        compliance_framework: Optional[str] = None,
        report_format: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish compliance.report.generated event."""
        from django.utils import timezone

        return self._event_publisher.publish(
            event_type="compliance.report.generated",
            data={
                "report_id": report_id,
                "report_type": report_type,
                "compliance_framework": compliance_framework,
                "report_format": report_format,
                "generated_at": timezone.now().isoformat(),
            },
            **kwargs,
        )


class VersionEventPublisher:
    """Event publisher mixin for VersioningService."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._event_publisher = EventPublisher(
            service_name="versioning_service",
            tenant_id=getattr(self, "tenant_id", None),
            user_id=getattr(self, "user_id", None),
        )

    def publish_version_created(
        self,
        version_id: str,
        resource_type: str,
        resource_id: str,
        version_number: Optional[str] = None,
        version_type: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish version.created event."""
        return self._event_publisher.publish(
            event_type="version.created",
            data={
                "version_id": version_id,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "version_number": version_number,
                "version_type": version_type,
            },
            **kwargs,
        )

    def publish_version_updated(
        self,
        version_id: str,
        changes: Dict[str, Any],
        previous_version: Optional[str] = None,
        new_version: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish version.updated event."""
        return self._event_publisher.publish(
            event_type="version.updated",
            data={
                "version_id": version_id,
                "changes": changes,
                "previous_version": previous_version,
                "new_version": new_version,
            },
            **kwargs,
        )

    def publish_version_rolled_back(
        self, version_id: str, target_version: str, rollback_reason: Optional[str] = None, **kwargs
    ) -> str:
        """Publish version.rolled_back event."""
        return self._event_publisher.publish(
            event_type="version.rolled_back",
            data={
                "version_id": version_id,
                "target_version": target_version,
                "rollback_reason": rollback_reason,
            },
            **kwargs,
        )


class VersioningEventPublisher:
    """Event publisher mixin for VersioningService."""

    def __init__(self, *args, **kwargs):
        # Only call super().__init__ if parent class supports it
        # BaseService doesn't have __init__, so we skip calling super
        # The actual service class (VersioningService) handles initialization
        try:
            # Check if parent has __init__ that accepts arguments
            parent_init = super().__init__
            if parent_init is not object.__init__:
                parent_init(*args, **kwargs)
        except (TypeError, AttributeError):
            # Parent doesn't support __init__ with arguments, skip
            pass
        self._event_publisher = EventPublisher(
            service_name="versioning_service",
            tenant_id=getattr(self, "tenant_id", None),
            user_id=getattr(self, "user_id", None),
        )

    def publish_version_created(
        self,
        version_id: str,
        resource_type: str,
        resource_id: str,
        version_number: Optional[str] = None,
        version_type: Optional[str] = None,
        semantic_version: Optional[str] = None,
        parent_version_id: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish version.created event."""
        # Build data dict, only including non-None optional fields
        data = {
            "version_id": version_id,
            "resource_type": resource_type,
            "resource_id": resource_id,
        }
        if version_number is not None:
            data["version_number"] = version_number
        if version_type is not None:
            data["version_type"] = version_type
        if semantic_version is not None:
            data["semantic_version"] = semantic_version
        if parent_version_id is not None:
            data["parent_version_id"] = parent_version_id

        # Merge default tags with custom tags if provided
        default_tags = ["versioning", "version"]
        custom_tags = kwargs.pop("tags", [])
        if custom_tags:
            tags = list(set(default_tags + (custom_tags if isinstance(custom_tags, list) else [custom_tags])))
        else:
            tags = default_tags

        return self._event_publisher.publish(
            event_type="version.created",
            data=data,
            tags=tags,
            **kwargs,
        )

    def publish_version_updated(
        self,
        version_id: str,
        changes: Dict[str, Any],
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        previous_version: Optional[str] = None,
        new_version: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish version.updated event."""
        data = {
            "version_id": version_id,
            "changes": changes,
        }
        if resource_type is not None:
            data["resource_type"] = resource_type
        if resource_id is not None:
            data["resource_id"] = resource_id
        if previous_version is not None:
            data["previous_version"] = previous_version
        if new_version is not None:
            data["new_version"] = new_version

        # Merge default tags with custom tags if provided
        default_tags = ["versioning", "version"]
        custom_tags = kwargs.pop("tags", [])
        if custom_tags:
            tags = list(set(default_tags + (custom_tags if isinstance(custom_tags, list) else [custom_tags])))
        else:
            tags = default_tags

        return self._event_publisher.publish(
            event_type="version.updated",
            data=data,
            tags=tags,
            **kwargs,
        )

    def publish_version_deleted(
        self,
        version_id: str,
        resource_type: str,
        resource_id: str,
        reason: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish version.deleted event."""
        from django.utils import timezone

        data = {
            "version_id": version_id,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "deleted_at": timezone.now().isoformat(),
        }
        if reason is not None:
            data["reason"] = reason

        # Merge default tags with custom tags if provided
        default_tags = ["versioning", "version"]
        custom_tags = kwargs.pop("tags", [])
        if custom_tags:
            tags = list(set(default_tags + (custom_tags if isinstance(custom_tags, list) else [custom_tags])))
        else:
            tags = default_tags

        return self._event_publisher.publish(
            event_type="version.deleted",
            data=data,
            tags=tags,
            **kwargs,
        )

    def publish_version_promoted(
        self,
        version_id: str,
        resource_type: str,
        resource_id: str,
        promoted_from: str,
        promoted_to: str,
        promotion_reason: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish version.promoted event."""
        data = {
            "version_id": version_id,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "promoted_from": promoted_from,
            "promoted_to": promoted_to,
        }
        if promotion_reason is not None:
            data["promotion_reason"] = promotion_reason

        # Merge default tags with custom tags if provided
        default_tags = ["versioning", "version"]
        custom_tags = kwargs.pop("tags", [])
        if custom_tags:
            tags = list(set(default_tags + (custom_tags if isinstance(custom_tags, list) else [custom_tags])))
        else:
            tags = default_tags

        return self._event_publisher.publish(
            event_type="version.promoted",
            data=data,
            tags=tags,
            **kwargs,
        )


class AccessEventPublisher:
    """Event publisher mixin for GovernanceService."""

    def __init__(self, *args, **kwargs):
        # Only call super().__init__ if parent class supports it
        # BaseService doesn't have __init__, so we skip calling super
        # The actual service class (GovernanceService) handles initialization
        try:
            # Check if parent has __init__ that accepts arguments
            parent_init = super().__init__
            if parent_init is not object.__init__:
                parent_init(*args, **kwargs)
        except (TypeError, AttributeError):
            # Parent doesn't support __init__ with arguments, skip
            pass
        self._event_publisher = EventPublisher(
            service_name="governance_service",
            tenant_id=getattr(self, "tenant_id", None),
            user_id=getattr(self, "user_id", None),
        )

    def publish_access_requested(
        self,
        access_request_id: str,
        resource_type: str,
        resource_id: str,
        requester_id: Optional[str] = None,
        request_reason: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish access.requested event."""
        return self._event_publisher.publish(
            event_type="access.requested",
            data={
                "access_request_id": access_request_id,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "requester_id": requester_id,
                "request_reason": request_reason,
            },
            **kwargs,
        )

    def publish_access_granted(
        self,
        access_request_id: str,
        resource_type: str,
        resource_id: str,
        granted_by: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish access.granted event."""
        from django.utils import timezone

        return self._event_publisher.publish(
            event_type="access.granted",
            data={
                "access_request_id": access_request_id,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "granted_by": granted_by,
                "granted_at": timezone.now().isoformat(),
            },
            **kwargs,
        )

    def publish_access_revoked(
        self,
        access_request_id: str,
        resource_type: str,
        resource_id: str,
        revoked_by: Optional[str] = None,
        revocation_reason: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish access.revoked event."""
        from django.utils import timezone

        return self._event_publisher.publish(
            event_type="access.revoked",
            data={
                "access_request_id": access_request_id,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "revoked_by": revoked_by,
                "revoked_at": timezone.now().isoformat(),
                "revocation_reason": revocation_reason,
            },
            **kwargs,
        )

    def publish_access_certified(
        self,
        access_request_id: str,
        certification_type: str,
        certified_by: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish access.certified event."""
        from django.utils import timezone

        return self._event_publisher.publish(
            event_type="access.certified",
            data={
                "access_request_id": access_request_id,
                "certification_type": certification_type,
                "certified_by": certified_by,
                "certified_at": timezone.now().isoformat(),
            },
            **kwargs,
        )


class MarketplaceEventPublisher:
    """Event publisher mixin for MarketplaceService."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._event_publisher = EventPublisher(
            service_name="marketplace_service",
            tenant_id=getattr(self, "tenant_id", None),
            user_id=getattr(self, "user_id", None),
        )

    def publish_listing_published(
        self, listing_id: str, asset_id: str, pricing_model: Optional[str] = None, **kwargs
    ) -> str:
        """Publish marketplace.listing.published event."""
        from django.utils import timezone

        return self._event_publisher.publish(
            event_type="marketplace.listing.published",
            data={
                "listing_id": listing_id,
                "asset_id": asset_id,
                "pricing_model": pricing_model,
                "published_at": timezone.now().isoformat(),
            },
            **kwargs,
        )

    def publish_listing_unpublished(
        self, listing_id: str, reason: Optional[str] = None, **kwargs
    ) -> str:
        """Publish marketplace.listing.unpublished event."""
        from django.utils import timezone

        return self._event_publisher.publish(
            event_type="marketplace.listing.unpublished",
            data={
                "listing_id": listing_id,
                "unpublished_at": timezone.now().isoformat(),
                "reason": reason,
            },
            **kwargs,
        )

    def publish_order_created(
        self,
        order_id: str,
        listing_id: str,
        buyer_id: str,
        order_amount: Optional[float] = None,
        currency: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish marketplace.order.created event."""
        return self._event_publisher.publish(
            event_type="marketplace.order.created",
            data={
                "order_id": order_id,
                "listing_id": listing_id,
                "buyer_id": buyer_id,
                "order_amount": order_amount,
                "currency": currency,
            },
            **kwargs,
        )

    def publish_order_approved(
        self, order_id: str, approved_by: Optional[str] = None, **kwargs
    ) -> str:
        """Publish marketplace.order.approved event."""
        from django.utils import timezone

        return self._event_publisher.publish(
            event_type="marketplace.order.approved",
            data={
                "order_id": order_id,
                "approved_by": approved_by,
                "approved_at": timezone.now().isoformat(),
            },
            **kwargs,
        )

    def publish_order_rejected(
        self,
        order_id: str,
        rejected_by: Optional[str] = None,
        rejection_reason: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish marketplace.order.rejected event."""
        from django.utils import timezone

        return self._event_publisher.publish(
            event_type="marketplace.order.rejected",
            data={
                "order_id": order_id,
                "rejected_by": rejected_by,
                "rejected_at": timezone.now().isoformat(),
                "rejection_reason": rejection_reason,
            },
            **kwargs,
        )

    def publish_order_fulfilled(
        self, order_id: str, entitlement_id: Optional[str] = None, **kwargs
    ) -> str:
        """Publish marketplace.order.fulfilled event."""
        from django.utils import timezone

        return self._event_publisher.publish(
            event_type="marketplace.order.fulfilled",
            data={
                "order_id": order_id,
                "fulfilled_at": timezone.now().isoformat(),
                "entitlement_id": entitlement_id,
            },
            **kwargs,
        )

    def publish_entitlement_granted(
        self,
        entitlement_id: str,
        order_id: str,
        user_id: str,
        expires_at: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish marketplace.entitlement.granted event."""
        from django.utils import timezone

        return self._event_publisher.publish(
            event_type="marketplace.entitlement.granted",
            data={
                "entitlement_id": entitlement_id,
                "order_id": order_id,
                "user_id": user_id,
                "granted_at": timezone.now().isoformat(),
                "expires_at": expires_at,
            },
            **kwargs,
        )

    def publish_entitlement_revoked(
        self,
        entitlement_id: str,
        revoked_by: Optional[str] = None,
        revocation_reason: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish marketplace.entitlement.revoked event."""
        from django.utils import timezone

        return self._event_publisher.publish(
            event_type="marketplace.entitlement.revoked",
            data={
                "entitlement_id": entitlement_id,
                "revoked_by": revoked_by,
                "revoked_at": timezone.now().isoformat(),
                "revocation_reason": revocation_reason,
            },
            **kwargs,
        )


class WorkflowEventPublisher:
    """Event publisher mixin for WorkflowEngine."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._event_publisher = EventPublisher(
            service_name="workflow_engine",
            tenant_id=getattr(self, "tenant_id", None),
            user_id=getattr(self, "user_id", None),
        )

    def publish_workflow_created(
        self,
        workflow_instance_id: str,
        workflow_name: str,
        workflow_version: Optional[str] = None,
        input_data: Optional[Dict[str, Any]] = None,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish workflow.created event."""
        return self._event_publisher.publish(
            event_type="workflow.created",
            data={
                "workflow_instance_id": workflow_instance_id,
                "workflow_name": workflow_name,
                "workflow_version": workflow_version,
                "input_data": input_data or {},
            },
            tenant_id=tenant_id,
            user_id=user_id,
            **kwargs,
        )

    def publish_workflow_started(
        self,
        workflow_instance_id: str,
        workflow_name: str,
        workflow_version: Optional[str] = None,
        input_data: Optional[Dict[str, Any]] = None,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish workflow.started event."""
        return self._event_publisher.publish(
            event_type="workflow.started",
            data={
                "workflow_instance_id": workflow_instance_id,
                "workflow_name": workflow_name,
                "workflow_version": workflow_version,
                "input_data": input_data or {},
            },
            tenant_id=tenant_id,
            user_id=user_id,
            **kwargs,
        )

    def publish_workflow_completed(
        self,
        workflow_instance_id: str,
        workflow_name: str,
        output_data: Optional[Dict[str, Any]] = None,
        duration_ms: Optional[int] = None,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish workflow.completed event."""
        return self._event_publisher.publish(
            event_type="workflow.completed",
            data={
                "workflow_instance_id": workflow_instance_id,
                "workflow_name": workflow_name,
                "output_data": output_data or {},
                "duration_ms": duration_ms,
            },
            tenant_id=tenant_id,
            user_id=user_id,
            **kwargs,
        )

    def publish_workflow_failed(
        self,
        workflow_instance_id: str,
        workflow_name: str,
        error_message: str,
        error_details: Optional[Dict[str, Any]] = None,
        failed_step_index: Optional[int] = None,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish workflow.failed event."""
        return self._event_publisher.publish(
            event_type="workflow.failed",
            data={
                "workflow_instance_id": workflow_instance_id,
                "workflow_name": workflow_name,
                "error_message": error_message,
                "error_details": error_details or {},
                "failed_step_index": failed_step_index,
            },
            tenant_id=tenant_id,
            user_id=user_id,
            **kwargs,
        )

    def publish_workflow_cancelled(
        self,
        workflow_instance_id: str,
        workflow_name: str,
        cancelled_by: Optional[str] = None,
        cancellation_reason: Optional[str] = None,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish workflow.cancelled event."""
        return self._event_publisher.publish(
            event_type="workflow.cancelled",
            data={
                "workflow_instance_id": workflow_instance_id,
                "workflow_name": workflow_name,
                "cancelled_by": cancelled_by,
                "cancellation_reason": cancellation_reason,
            },
            tenant_id=tenant_id,
            user_id=user_id,
            **kwargs,
        )

    def publish_workflow_step_started(
        self,
        workflow_instance_id: str,
        step_index: int,
        step_name: str,
        step_type: Optional[str] = None,
        progress_percentage: Optional[float] = None,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        validation_status: Optional[str] = None,
        validation_context: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> str:
        """Publish workflow.step.started event."""
        data = {
            "workflow_instance_id": workflow_instance_id,
            "step_index": step_index,
            "step_name": step_name,
            "step_type": step_type,
            "progress_percentage": progress_percentage,
        }
        
        # Add validation context if provided
        if validation_status is not None:
            data["validation_status"] = validation_status
        if validation_context is not None:
            data["validation_context"] = validation_context
        
        return self._event_publisher.publish(
            event_type="workflow.step.started",
            data=data,
            tenant_id=tenant_id,
            user_id=user_id,
            **kwargs,
        )

    def publish_workflow_step_completed(
        self,
        workflow_instance_id: str,
        step_index: int,
        step_name: str,
        output_data: Optional[Dict[str, Any]] = None,
        duration_ms: Optional[int] = None,
        progress_percentage: Optional[float] = None,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        validation_status: Optional[str] = None,
        validation_context: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> str:
        """Publish workflow.step.completed event."""
        data = {
            "workflow_instance_id": workflow_instance_id,
            "step_index": step_index,
            "step_name": step_name,
            "output_data": output_data or {},
            "duration_ms": duration_ms,
            "progress_percentage": progress_percentage,
        }
        
        # Add validation context if provided
        if validation_status is not None:
            data["validation_status"] = validation_status
        if validation_context is not None:
            data["validation_context"] = validation_context
        
        return self._event_publisher.publish(
            event_type="workflow.step.completed",
            data=data,
            tenant_id=tenant_id,
            user_id=user_id,
            **kwargs,
        )

    def publish_workflow_step_failed(
        self,
        workflow_instance_id: str,
        step_index: int,
        step_name: str,
        error_message: str,
        error_details: Optional[Dict[str, Any]] = None,
        retry_count: Optional[int] = None,
        duration_ms: Optional[int] = None,
        progress_percentage: Optional[float] = None,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        validation_status: Optional[str] = None,
        validation_context: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> str:
        """Publish workflow.step.failed event."""
        data = {
            "workflow_instance_id": workflow_instance_id,
            "step_index": step_index,
            "step_name": step_name,
            "error_message": error_message,
            "error_details": error_details or {},
            "retry_count": retry_count or 0,
            "duration_ms": duration_ms,
            "progress_percentage": progress_percentage,
        }
        
        # Add validation context if provided
        if validation_status is not None:
            data["validation_status"] = validation_status
        if validation_context is not None:
            data["validation_context"] = validation_context
        
        return self._event_publisher.publish(
            event_type="workflow.step.failed",
            data=data,
            tenant_id=tenant_id,
            user_id=user_id,
            **kwargs,
        )


class ODPSEventPublisher:
    """Event publisher mixin for ODPS operations in ContractService."""

    def __init__(self, *args, **kwargs):
        # Only call super().__init__ if parent class supports it
        # BaseService doesn't have __init__, so we skip calling super
        # The actual service class (ContractService) handles initialization
        try:
            # Check if parent has __init__ that accepts arguments
            parent_init = super().__init__
            if parent_init is not object.__init__:
                parent_init(*args, **kwargs)
        except (TypeError, AttributeError):
            # Parent doesn't support __init__ with arguments, skip
            pass
        self._event_publisher = EventPublisher(
            service_name="contract_service",
            tenant_id=getattr(self, "tenant_id", None),
            user_id=getattr(self, "user_id", None),
        )

    def _is_transient_failure(self, error: Exception) -> bool:
        """
        Check if an exception represents a transient failure that should be retried.

        Transient failures include:
        - ConnectionError: Service unavailable, network issues
        - TimeoutError: Request timeout, service slow to respond
        - Redis connection errors
        - Temporary service unavailability

        Non-transient failures (should not retry):
        - ValidationError: Invalid event data
        - PermissionDenied: Authorization errors
        - ValueError: Invalid input

        Args:
            error: Exception instance

        Returns:
            True if exception is transient and should be retried
        """
        # Check for specific transient error types
        if isinstance(error, (ConnectionError, TimeoutError)):
            return True

        # Check for Redis connection errors
        error_str = str(error).lower()
        error_type = type(error).__name__

        # Transient error indicators
        transient_keywords = [
            'timeout', 'timed out', 'connection', 'unavailable', 'network',
            'temporary', 'retry', 'service unavailable', '503', '502', '504',
            'redis', 'connection refused', 'connection reset', 'broken pipe',
            'connection pool', 'socket', 'errno'
        ]

        # Non-retryable error types
        non_retryable_errors = [
            'ValidationError',
            'PermissionDenied',
            'AuthenticationFailed',
            'NotFound',
            'ValueError',
            'TypeError',
            'AttributeError',
        ]

        # Don't retry on non-retryable error types
        if any(non_retryable in error_type for non_retryable in non_retryable_errors):
            return False

        # Check for transient keywords in error message
        return any(keyword in error_str for keyword in transient_keywords)

    def _publish_with_retry(
        self,
        event_type: str,
        publish_func: Callable[[], str],
        max_retries: int = 3,
        base_delay: float = 1.0,
        enable_graceful_degradation: bool = True
    ) -> Optional[str]:
        """
        Publish event with retry logic and graceful error handling.

        Args:
            event_type: Event type for logging
            publish_func: Function that publishes the event (returns event_id)
            max_retries: Maximum number of retry attempts (default: 3)
            base_delay: Base delay in seconds for exponential backoff (default: 1.0)
            enable_graceful_degradation: If True, log errors but don't raise (default: True)

        Returns:
            Event ID if successful, None if graceful degradation is enabled and all retries failed

        Raises:
            EventPublishError: If graceful degradation is disabled and all retries failed
        """
        retry_count = 0
        last_error = None

        while retry_count <= max_retries:
            try:
                # Attempt to publish event via EventBus
                event_id = publish_func()

                # Log success on retry
                if retry_count > 0:
                    logger.info(
                        "odps_event_publish_retry_success",
                        event_type=event_type,
                        retry_count=retry_count,
                        event_id=event_id,
                        message=f"Successfully published {event_type} after {retry_count} retries"
                    )

                return event_id

            except Exception as e:
                last_error = e

                # Check if error is transient and should be retried
                is_transient = self._is_transient_failure(e)

                if not is_transient:
                    # Non-transient error - don't retry
                    logger.error(
                        "odps_event_publish_non_transient_error",
                        event_type=event_type,
                        error=str(e),
                        error_type=type(e).__name__,
                        message=f"Non-transient error publishing {event_type}, not retrying"
                    )

                    if enable_graceful_degradation:
                        # Log error but don't block
                        logger.warning(
                            "odps_event_publish_graceful_degradation",
                            event_type=event_type,
                            error=str(e),
                            message=f"Event publishing failed for {event_type} but continuing (graceful degradation)"
                        )
                        return None
                    else:
                        raise

                # Transient error - check if we should retry
                if retry_count >= max_retries:
                    # Max retries exceeded
                    logger.error(
                        "odps_event_publish_retry_exhausted",
                        event_type=event_type,
                        retry_count=retry_count,
                        max_retries=max_retries,
                        error=str(e),
                        error_type=type(e).__name__,
                        message=f"Failed to publish {event_type} after {max_retries} retries"
                    )

                    if enable_graceful_degradation:
                        # Log error but don't block
                        logger.warning(
                            "odps_event_publish_graceful_degradation",
                            event_type=event_type,
                            retry_count=retry_count,
                            error=str(e),
                            message=f"Event publishing failed for {event_type} after {max_retries} retries but continuing (graceful degradation)"
                        )
                        return None
                    else:
                        raise EventPublishError(
                            f"Failed to publish {event_type} after {max_retries} retries: {e}"
                        ) from e

                # Calculate exponential backoff delay
                delay = base_delay * (2 ** retry_count)

                # Log retry attempt
                logger.warning(
                    "odps_event_publish_retry_attempt",
                    event_type=event_type,
                    retry_count=retry_count + 1,
                    max_retries=max_retries,
                    delay=delay,
                    error=str(e),
                    error_type=type(e).__name__,
                    message=f"Retrying {event_type} publish (attempt {retry_count + 1}/{max_retries + 1}) after {delay}s"
                )

                # Wait before retry
                time.sleep(delay)
                retry_count += 1

            except Exception as e:
                # Unexpected error - log and handle based on graceful degradation setting
                last_error = e
                logger.error(
                    "odps_event_publish_unexpected_error",
                    event_type=event_type,
                    retry_count=retry_count,
                    error=str(e),
                    error_type=type(e).__name__,
                    exc_info=True,
                    message=f"Unexpected error publishing {event_type}"
                )

                if enable_graceful_degradation:
                    # Log error but don't block
                    logger.warning(
                        "odps_event_publish_graceful_degradation",
                        event_type=event_type,
                        error=str(e),
                        message=f"Event publishing failed for {event_type} but continuing (graceful degradation)"
                    )
                    return None
                else:
                    raise EventPublishError(
                        f"Unexpected error publishing {event_type}: {e}"
                    ) from e

        # Should not reach here, but handle just in case
        if enable_graceful_degradation:
            logger.warning(
                "odps_event_publish_graceful_degradation",
                event_type=event_type,
                error=str(last_error) if last_error else "Unknown error",
                message=f"Event publishing failed for {event_type} but continuing (graceful degradation)"
            )
            return None
        else:
            raise EventPublishError(
                f"Failed to publish {event_type}: {last_error}"
            ) from last_error

    def publish_odps_created(
        self,
        contract_id: str,
        asset_id: Optional[str] = None,
        status: Optional[str] = None,
        odps_version: Optional[str] = None,
        original_format: Optional[str] = None,
        **kwargs,
    ) -> Optional[str]:
        """
        Publish odps.created event with retry logic and graceful error handling.

        All ODPS events are published via EventBus.publish() which:
        - Persists events to PostgreSQL
        - Delivers events via Redis Pub/Sub

        Returns:
            Event ID if successful, None if graceful degradation occurred
        """
        def _publish():
            return self._event_publisher.publish(
                event_type="odps.created",
                data={
                    "contract_id": contract_id,
                    "asset_id": asset_id,
                    "status": status,
                    "odps_version": odps_version,
                    "original_format": original_format,
                },
                **kwargs,
            )

        return self._publish_with_retry(
            event_type="odps.created",
            publish_func=_publish,
            max_retries=3,
            enable_graceful_degradation=True
        )

    def publish_odps_updated(
        self,
        contract_id: str,
        changes: Dict[str, Any],
        previous_status: Optional[str] = None,
        new_status: Optional[str] = None,
        **kwargs,
    ) -> Optional[str]:
        """
        Publish odps.updated event with retry logic and graceful error handling.

        Returns:
            Event ID if successful, None if graceful degradation occurred
        """
        def _publish():
            return self._event_publisher.publish(
                event_type="odps.updated",
                data={
                    "contract_id": contract_id,
                    "changes": changes,
                    "previous_status": previous_status,
                    "new_status": new_status,
                },
                **kwargs,
            )

        return self._publish_with_retry(
            event_type="odps.updated",
            publish_func=_publish,
            max_retries=3,
            enable_graceful_degradation=True
        )

    def publish_odps_deleted(
        self, contract_id: str, reason: Optional[str] = None, **kwargs
    ) -> Optional[str]:
        """
        Publish odps.deleted event with retry logic and graceful error handling.

        Returns:
            Event ID if successful, None if graceful degradation occurred
        """
        from django.utils import timezone

        def _publish():
            return self._event_publisher.publish(
                event_type="odps.deleted",
                data={
                    "contract_id": contract_id,
                    "deleted_at": timezone.now().isoformat(),
                    "reason": reason,
                },
                **kwargs,
            )

        return self._publish_with_retry(
            event_type="odps.deleted",
            publish_func=_publish,
            max_retries=3,
            enable_graceful_degradation=True
        )

    def publish_odps_normalized(
        self,
        contract_id: str,
        normalization_status: str,
        normalization_errors: Optional[list] = None,
        odps_version: Optional[str] = None,
        **kwargs,
    ) -> Optional[str]:
        """
        Publish odps.normalized event with retry logic and graceful error handling.

        Returns:
            Event ID if successful, None if graceful degradation occurred
        """
        def _publish():
            return self._event_publisher.publish(
                event_type="odps.normalized",
                data={
                    "contract_id": contract_id,
                    "normalization_status": normalization_status,
                    "normalization_errors": normalization_errors,
                    "odps_version": odps_version,
                },
                **kwargs,
            )

        return self._publish_with_retry(
            event_type="odps.normalized",
            publish_func=_publish,
            max_retries=3,
            enable_graceful_degradation=True
        )

    def publish_odps_linked(
        self,
        odps_contract_id: str,
        odcs_contract_id: str,
        link_type: Optional[str] = None,
        **kwargs,
    ) -> Optional[str]:
        """
        Publish odps.linked event with retry logic and graceful error handling.

        Returns:
            Event ID if successful, None if graceful degradation occurred
        """
        def _publish():
            return self._event_publisher.publish(
                event_type="odps.linked",
                data={
                    "odps_contract_id": odps_contract_id,
                    "odcs_contract_id": odcs_contract_id,
                    "link_type": link_type,
                },
                **kwargs,
            )

        return self._publish_with_retry(
            event_type="odps.linked",
            publish_func=_publish,
            max_retries=3,
            enable_graceful_degradation=True
        )

    def publish_odps_unlinked(
        self,
        odps_contract_id: str,
        odcs_contract_id: str,
        reason: Optional[str] = None,
        **kwargs,
    ) -> Optional[str]:
        """
        Publish odps.unlinked event with retry logic and graceful error handling.

        Returns:
            Event ID if successful, None if graceful degradation occurred
        """
        def _publish():
            return self._event_publisher.publish(
                event_type="odps.unlinked",
                data={
                    "odps_contract_id": odps_contract_id,
                    "odcs_contract_id": odcs_contract_id,
                    "reason": reason,
                },
                **kwargs,
            )

        return self._publish_with_retry(
            event_type="odps.unlinked",
            publish_func=_publish,
            max_retries=3,
            enable_graceful_degradation=True
        )

    def publish_odps_ref_resolved(
        self,
        contract_id: str,
        ref_path: str,
        ref_type: str,
        resolution_status: str,
        ref_count: Optional[int] = None,
        duration_ms: Optional[int] = None,
        **kwargs,
    ) -> Optional[str]:
        """
        Publish odps.ref.resolved event with retry logic and graceful error handling.

        Returns:
            Event ID if successful, None if graceful degradation occurred
        """
        def _publish():
            return self._event_publisher.publish(
                event_type="odps.ref.resolved",
                data={
                    "contract_id": contract_id,
                    "ref_path": ref_path,
                    "ref_type": ref_type,
                    "resolution_status": resolution_status,
                    "ref_count": ref_count,
                    "duration_ms": duration_ms,
                },
                **kwargs,
            )

        return self._publish_with_retry(
            event_type="odps.ref.resolved",
            publish_func=_publish,
            max_retries=3,
            enable_graceful_degradation=True
        )

    def publish_odps_ref_failed(
        self,
        contract_id: str,
        ref_path: str,
        ref_type: str,
        error_message: str,
        error_code: Optional[str] = None,
        error_details: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Optional[str]:
        """
        Publish odps.ref.failed event with retry logic and graceful error handling.

        Returns:
            Event ID if successful, None if graceful degradation occurred
        """
        def _publish():
            return self._event_publisher.publish(
                event_type="odps.ref.failed",
                data={
                    "contract_id": contract_id,
                    "ref_path": ref_path,
                    "ref_type": ref_type,
                    "error_message": error_message,
                    "error_code": error_code,
                    "error_details": error_details or {},
                },
                **kwargs,
            )

        return self._publish_with_retry(
            event_type="odps.ref.failed",
            publish_func=_publish,
            max_retries=3,
            enable_graceful_degradation=True
        )

    def publish_odps_export_started(
        self,
        contract_id: str,
        export_format: str,
        output_format: Optional[str] = None,
        odps_version: Optional[str] = None,
        **kwargs,
    ) -> Optional[str]:
        """
        Publish odps.export.started event with retry logic and graceful error handling.

        Returns:
            Event ID if successful, None if graceful degradation occurred
        """
        def _publish():
            return self._event_publisher.publish(
                event_type="odps.export.started",
                data={
                    "contract_id": contract_id,
                    "export_format": export_format,
                    "output_format": output_format,
                    "odps_version": odps_version,
                },
                **kwargs,
            )

        return self._publish_with_retry(
            event_type="odps.export.started",
            publish_func=_publish,
            max_retries=3,
            enable_graceful_degradation=True
        )

    def publish_odps_export_completed(
        self,
        contract_id: str,
        export_format: str,
        output_format: Optional[str] = None,
        file_size: Optional[int] = None,
        duration_ms: Optional[int] = None,
        **kwargs,
    ) -> Optional[str]:
        """
        Publish odps.export.completed event with retry logic and graceful error handling.

        Returns:
            Event ID if successful, None if graceful degradation occurred
        """
        def _publish():
            return self._event_publisher.publish(
                event_type="odps.export.completed",
                data={
                    "contract_id": contract_id,
                    "export_format": export_format,
                    "output_format": output_format,
                    "file_size": file_size,
                    "duration_ms": duration_ms,
                },
                **kwargs,
            )

        return self._publish_with_retry(
            event_type="odps.export.completed",
            publish_func=_publish,
            max_retries=3,
            enable_graceful_degradation=True
        )

    def publish_odps_export_failed(
        self,
        contract_id: str,
        export_format: str,
        error_message: str,
        error_details: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Optional[str]:
        """
        Publish odps.export.failed event with retry logic and graceful error handling.

        Returns:
            Event ID if successful, None if graceful degradation occurred
        """
        def _publish():
            return self._event_publisher.publish(
                event_type="odps.export.failed",
                data={
                    "contract_id": contract_id,
                    "export_format": export_format,
                    "error_message": error_message,
                    "error_details": error_details or {},
                },
                **kwargs,
            )

        return self._publish_with_retry(
            event_type="odps.export.failed",
            publish_func=_publish,
            max_retries=3,
            enable_graceful_degradation=True
        )

    # ODPS Workflow Event Publishing Methods (Task 7.1.4)
    def publish_odps_workflow_started(
        self,
        workflow_instance_id: str,
        workflow_name: str,
        workflow_version: Optional[str] = None,
        input_data: Optional[Dict[str, Any]] = None,
        odps_version: Optional[str] = None,
        progress_percentage: Optional[float] = None,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        **kwargs,
    ) -> Optional[str]:
        """
        Publish odps.workflow.started event with retry logic and graceful error handling.

        Returns:
            Event ID if successful, None if graceful degradation occurred
        """
        def _publish():
            return self._event_publisher.publish(
                event_type="odps.workflow.started",
                data={
                    "workflow_instance_id": workflow_instance_id,
                    "workflow_name": workflow_name,
                    "workflow_version": workflow_version,
                    "input_data": input_data,
                    "odps_version": odps_version,
                    "progress_percentage": progress_percentage,
                },
                tenant_id=tenant_id,
                user_id=user_id,
                **kwargs,
            )

        return self._publish_with_retry(
            event_type="odps.workflow.started",
            publish_func=_publish,
            max_retries=3,
            enable_graceful_degradation=True
        )

    def publish_odps_workflow_completed(
        self,
        workflow_instance_id: str,
        workflow_name: str,
        workflow_version: Optional[str] = None,
        output_data: Optional[Dict[str, Any]] = None,
        duration_ms: Optional[int] = None,
        odps_contract_id: Optional[str] = None,
        odcs_contract_id: Optional[str] = None,
        progress_percentage: Optional[float] = None,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        **kwargs,
    ) -> Optional[str]:
        """
        Publish odps.workflow.completed event with retry logic and graceful error handling.

        Returns:
            Event ID if successful, None if graceful degradation occurred
        """
        def _publish():
            return self._event_publisher.publish(
                event_type="odps.workflow.completed",
                data={
                    "workflow_instance_id": workflow_instance_id,
                    "workflow_name": workflow_name,
                    "workflow_version": workflow_version,
                    "output_data": output_data,
                    "duration_ms": duration_ms,
                    "odps_contract_id": odps_contract_id,
                    "odcs_contract_id": odcs_contract_id,
                    "progress_percentage": progress_percentage,
                },
                tenant_id=tenant_id,
                user_id=user_id,
                **kwargs,
            )

        return self._publish_with_retry(
            event_type="odps.workflow.completed",
            publish_func=_publish,
            max_retries=3,
            enable_graceful_degradation=True
        )

    def publish_odps_workflow_failed(
        self,
        workflow_instance_id: str,
        workflow_name: str,
        error_message: str,
        workflow_version: Optional[str] = None,
        error_details: Optional[Dict[str, Any]] = None,
        failed_step_index: Optional[int] = None,
        failed_step_name: Optional[str] = None,
        progress_percentage: Optional[float] = None,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish odps.workflow.failed event."""
        return self._event_publisher.publish(
            event_type="odps.workflow.failed",
            data={
                "workflow_instance_id": workflow_instance_id,
                "workflow_name": workflow_name,
                "workflow_version": workflow_version,
                "error_message": error_message,
                "error_details": error_details or {},
                "failed_step_index": failed_step_index,
                "failed_step_name": failed_step_name,
                "progress_percentage": progress_percentage,
            },
            tenant_id=tenant_id,
            user_id=user_id,
            **kwargs,
        )

    def publish_odps_workflow_step_completed(
        self,
        workflow_instance_id: str,
        step_index: int,
        step_name: str,
        step_type: Optional[str] = None,
        output_data: Optional[Dict[str, Any]] = None,
        duration_ms: Optional[int] = None,
        progress_percentage: Optional[float] = None,
        odps_version: Optional[str] = None,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish odps.workflow.step.completed event."""
        return self._event_publisher.publish(
            event_type="odps.workflow.step.completed",
            data={
                "workflow_instance_id": workflow_instance_id,
                "step_index": step_index,
                "step_name": step_name,
                "step_type": step_type,
                "output_data": output_data,
                "duration_ms": duration_ms,
                "progress_percentage": progress_percentage,
                "odps_version": odps_version,
            },
            tenant_id=tenant_id,
            user_id=user_id,
            **kwargs,
        )

    def publish_odps_workflow_step_failed(
        self,
        workflow_instance_id: str,
        step_index: int,
        step_name: str,
        error_message: str,
        error_details: Optional[Dict[str, Any]] = None,
        retry_count: Optional[int] = None,
        duration_ms: Optional[int] = None,
        progress_percentage: Optional[float] = None,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish odps.workflow.step.failed event."""
        return self._event_publisher.publish(
            event_type="odps.workflow.step.failed",
            data={
                "workflow_instance_id": workflow_instance_id,
                "step_index": step_index,
                "step_name": step_name,
                "error_message": error_message,
                "error_details": error_details or {},
                "retry_count": retry_count or 0,
                "duration_ms": duration_ms,
                "progress_percentage": progress_percentage,
            },
            tenant_id=tenant_id,
            user_id=user_id,
            **kwargs,
        )

    def publish_odps_workflow_progress(
        self,
        workflow_instance_id: str,
        workflow_name: str,
        progress_percentage: float,
        workflow_version: Optional[str] = None,
        current_step_index: Optional[int] = None,
        current_step_name: Optional[str] = None,
        total_steps: Optional[int] = None,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish odps.workflow.progress event."""
        return self._event_publisher.publish(
            event_type="odps.workflow.progress",
            data={
                "workflow_instance_id": workflow_instance_id,
                "workflow_name": workflow_name,
                "workflow_version": workflow_version,
                "progress_percentage": progress_percentage,
                "current_step_index": current_step_index,
                "current_step_name": current_step_name,
                "total_steps": total_steps,
            },
            tenant_id=tenant_id,
            user_id=user_id,
            **kwargs,
        )

    def publish_odps_creation_progress(
        self,
        contract_id: Optional[str] = None,
        workflow_instance_id: Optional[str] = None,
        progress_percentage: float = 0.0,
        current_step: Optional[str] = None,
        total_steps: Optional[int] = None,
        step_index: Optional[int] = None,
        status_message: Optional[str] = None,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish odps.creation.progress event."""
        return self._event_publisher.publish(
            event_type="odps.creation.progress",
            data={
                "contract_id": contract_id,
                "workflow_instance_id": workflow_instance_id,
                "progress_percentage": progress_percentage,
                "current_step": current_step,
                "total_steps": total_steps,
                "step_index": step_index,
                "status_message": status_message,
            },
            tenant_id=tenant_id,
            user_id=user_id,
            **kwargs,
        )

    def publish_odps_normalization_progress(
        self,
        contract_id: Optional[str] = None,
        progress_percentage: float = 0.0,
        current_phase: Optional[str] = None,
        total_phases: Optional[int] = None,
        phase_index: Optional[int] = None,
        items_processed: Optional[int] = None,
        items_total: Optional[int] = None,
        status_message: Optional[str] = None,
        odps_version: Optional[str] = None,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish odps.normalization.progress event."""
        return self._event_publisher.publish(
            event_type="odps.normalization.progress",
            data={
                "contract_id": contract_id,
                "progress_percentage": progress_percentage,
                "current_phase": current_phase,
                "total_phases": total_phases,
                "phase_index": phase_index,
                "items_processed": items_processed,
                "items_total": items_total,
                "status_message": status_message,
                "odps_version": odps_version,
            },
            tenant_id=tenant_id,
            user_id=user_id,
            **kwargs,
        )

    def publish_odps_ref_progress(
        self,
        contract_id: Optional[str] = None,
        progress_percentage: float = 0.0,
        refs_processed: Optional[int] = None,
        refs_total: Optional[int] = None,
        current_ref_path: Optional[str] = None,
        ref_type: Optional[str] = None,
        status_message: Optional[str] = None,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish odps.ref.progress event."""
        return self._event_publisher.publish(
            event_type="odps.ref.progress",
            data={
                "contract_id": contract_id,
                "progress_percentage": progress_percentage,
                "refs_processed": refs_processed,
                "refs_total": refs_total,
                "current_ref_path": current_ref_path,
                "ref_type": ref_type,
                "status_message": status_message,
            },
            tenant_id=tenant_id,
            user_id=user_id,
            **kwargs,
        )

    def publish_odps_linking_status(
        self,
        odps_contract_id: str,
        odcs_contract_id: str,
        status: str,
        progress_percentage: Optional[float] = None,
        current_phase: Optional[str] = None,
        validation_passed: Optional[bool] = None,
        validation_errors: Optional[list] = None,
        link_type: Optional[str] = None,
        status_message: Optional[str] = None,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish odps.linking.status event."""
        return self._event_publisher.publish(
            event_type="odps.linking.status",
            data={
                "odps_contract_id": odps_contract_id,
                "odcs_contract_id": odcs_contract_id,
                "status": status,
                "progress_percentage": progress_percentage,
                "current_phase": current_phase,
                "validation_passed": validation_passed,
                "validation_errors": validation_errors or [],
                "link_type": link_type,
                "status_message": status_message,
            },
            tenant_id=tenant_id,
            user_id=user_id,
            **kwargs,
        )

    def publish_odps_export_progress(
        self,
        contract_id: str,
        export_format: str,
        progress_percentage: float = 0.0,
        current_phase: Optional[str] = None,
        bytes_processed: Optional[int] = None,
        bytes_total: Optional[int] = None,
        status_message: Optional[str] = None,
        odps_version: Optional[str] = None,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish odps.export.progress event."""
        return self._event_publisher.publish(
            event_type="odps.export.progress",
            data={
                "contract_id": contract_id,
                "export_format": export_format,
                "progress_percentage": progress_percentage,
                "current_phase": current_phase,
                "bytes_processed": bytes_processed,
                "bytes_total": bytes_total,
                "status_message": status_message,
                "odps_version": odps_version,
            },
            tenant_id=tenant_id,
            user_id=user_id,
            **kwargs,
        )

    def publish_odps_semantic_mapping_progress(
        self,
        contract_id: Optional[str] = None,
        progress_percentage: float = 0.0,
        current_phase: Optional[str] = None,
        phase_index: Optional[int] = None,
        total_phases: Optional[int] = None,
        status_message: Optional[str] = None,
        odps_version: Optional[str] = None,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish odps.semantic.mapping.progress event."""
        return self._event_publisher.publish(
            event_type="odps.semantic.mapping.progress",
            data={
                "contract_id": contract_id,
                "progress_percentage": progress_percentage,
                "current_phase": current_phase,
                "phase_index": phase_index,
                "total_phases": total_phases,
                "status_message": status_message,
                "odps_version": odps_version,
            },
            tenant_id=tenant_id,
            user_id=user_id,
            **kwargs,
        )

    def publish_odps_semantic_mapped(
        self,
        contract_id: str,
        semantic_resource_id: Optional[str] = None,
        semantic_uri: Optional[str] = None,
        triples_count: Optional[int] = None,
        semantic_status: Optional[str] = None,
        duration_ms: Optional[int] = None,
        odps_version: Optional[str] = None,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish odps.semantic.mapped event."""
        return self._event_publisher.publish(
            event_type="odps.semantic.mapped",
            data={
                "contract_id": contract_id,
                "semantic_resource_id": semantic_resource_id,
                "semantic_uri": semantic_uri,
                "triples_count": triples_count,
                "semantic_status": semantic_status,
                "duration_ms": duration_ms,
                "odps_version": odps_version,
            },
            tenant_id=tenant_id,
            user_id=user_id,
            **kwargs,
        )
class DataMeshEventPublisher:
    """Event publisher mixin for DataMeshService."""

    def __init__(self, *args, **kwargs):
        # Only call super().__init__ if parent class supports it
        # BaseService doesn't have __init__, so we skip calling super
        # The actual service class (DataMeshService) handles initialization
        try:
            # Check if parent has __init__ that accepts arguments
            parent_init = super().__init__
            if parent_init is not object.__init__:
                parent_init(*args, **kwargs)
        except (TypeError, AttributeError):
            # Parent doesn't support __init__ with arguments, skip
            pass
        self._event_publisher = EventPublisher(
            service_name="data_mesh_service",
            tenant_id=getattr(self, "tenant_id", None),
            user_id=getattr(self, "user_id", None),
        )

    def _trigger_webhook_for_event(
        self,
        internal_event_type: str,
        resource_type: str,
        resource_id: str,
        event_data: Dict[str, Any],
        tenant_id: Optional[str] = None,
    ) -> None:
        """
        Trigger webhook for mesh event.

        Args:
            internal_event_type: Internal event type (e.g., "mesh.domain.created")
            resource_type: Resource type
            resource_id: Resource ID
            event_data: Event data
            tenant_id: Tenant ID
        """
        if not tenant_id:
            tenant_id = getattr(self, "tenant_id", None)
            if not tenant_id:
                return

        try:
            from hub.apps.webhooks.service import WebhookDeliveryService

            WebhookDeliveryService.trigger_webhook(
                tenant_id=str(tenant_id),
                event_type=internal_event_type,
                resource_type=resource_type,
                resource_id=resource_id,
                event_data=event_data
            )
        except Exception as e:
            # Log but don't fail event publishing if webhook fails
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                f"Failed to trigger webhook for mesh event {internal_event_type}: {e}",
                extra={
                    "event_type": internal_event_type,
                    "resource_type": resource_type,
                    "resource_id": resource_id,
                    "tenant_id": tenant_id,
                    "error": str(e)
                },
                exc_info=True
            )

    def publish_domain_created(
        self,
        domain_id: str,
        name: Optional[str] = None,
        status: Optional[str] = None,
        owner_id: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish domain.created event."""
        return self._event_publisher.publish(
            event_type="domain.created",
            data={
                "domain_id": domain_id,
                "name": name,
                "status": status,
                "owner_id": owner_id,
            },
            **kwargs,
        )

    def publish_domain_updated(
        self,
        domain_id: str,
        changes: Dict[str, Any],
        previous_status: Optional[str] = None,
        new_status: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish domain.updated event."""
        return self._event_publisher.publish(
            event_type="domain.updated",
            data={
                "domain_id": domain_id,
                "changes": changes,
                "previous_status": previous_status,
                "new_status": new_status,
            },
            **kwargs,
        )

    def publish_domain_deleted(
        self,
        domain_id: str,
        reason: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish domain.deleted event."""
        from django.utils import timezone

        return self._event_publisher.publish(
            event_type="domain.deleted",
            data={
                "domain_id": domain_id,
                "deleted_at": timezone.now().isoformat(),
                "reason": reason,
            },
            **kwargs,
        )

    def publish_policy_applied(
        self,
        policy_application_id: str,
        domain_id: str,
        policy_id: Optional[str] = None,
        status: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish policy.applied event."""
        return self._event_publisher.publish(
            event_type="policy.applied",
            data={
                "policy_application_id": policy_application_id,
                "domain_id": domain_id,
                "policy_id": policy_id,
                "status": status,
            },
            **kwargs,
        )

    def publish_policy_revoked(
        self,
        policy_application_id: str,
        domain_id: str,
        policy_id: Optional[str] = None,
        reason: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish policy.revoked event."""
        return self._event_publisher.publish(
            event_type="policy.revoked",
            data={
                "policy_application_id": policy_application_id,
                "domain_id": domain_id,
                "policy_id": policy_id,
                "reason": reason,
            },
            **kwargs,
        )

    def publish_compliance_report_generated(
        self,
        compliance_report_id: str,
        domain_id: str,
        compliance_status: Optional[str] = None,
        asset_id: Optional[str] = None,
        violation_count: Optional[int] = None,
        **kwargs,
    ) -> str:
        """Publish compliance.report.generated event."""
        return self._event_publisher.publish(
            event_type="compliance.report.generated",
            data={
                "compliance_report_id": compliance_report_id,
                "domain_id": domain_id,
                "compliance_status": compliance_status,
                "asset_id": asset_id,
                "violation_count": violation_count,
            },
            **kwargs,
        )

    def publish_compliance_checked(
        self,
        domain_id: str,
        compliance_status: Optional[str] = None,
        violation_count: Optional[int] = None,
        checked_at: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish mesh.compliance.checked event."""
        return self._event_publisher.publish(
            event_type="mesh.compliance.checked",
            data={
                "domain_id": domain_id,
                "compliance_status": compliance_status,
                "violation_count": violation_count,
                "checked_at": checked_at,
            },
            **kwargs,
        )

    def publish_topology_updated(
        self,
        tenant_id: Optional[str] = None,
        domain_count: Optional[int] = None,
        relationship_count: Optional[int] = None,
        updated_at: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish mesh.topology.updated event."""
        event_id = self._event_publisher.publish(
            event_type="mesh.topology.updated",
            data={
                "tenant_id": tenant_id,
                "domain_count": domain_count,
                "relationship_count": relationship_count,
                "updated_at": updated_at,
            },
            **kwargs,
        )

        # Trigger webhook
        self._trigger_webhook_for_event(
            internal_event_type="mesh.topology.updated",
            resource_type="DATA_MESH_TOPOLOGY",
            resource_id=tenant_id or "",
            event_data={
                "tenant_id": tenant_id,
                "domain_count": domain_count,
                "relationship_count": relationship_count,
                "updated_at": updated_at,
            },
            tenant_id=tenant_id,
        )

        return event_id

    def publish_mesh_domain_created(
        self,
        domain_id: str,
        name: Optional[str] = None,
        status: Optional[str] = None,
        owner_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish mesh.domain.created event."""
        event_id = self._event_publisher.publish(
            event_type="mesh.domain.created",
            data={
                "domain_id": domain_id,
                "name": name,
                "status": status,
                "owner_id": owner_id,
                "tenant_id": tenant_id,
            },
            **kwargs,
        )

        # Trigger webhook
        self._trigger_webhook_for_event(
            internal_event_type="mesh.domain.created",
            resource_type="DATA_MESH_DOMAIN",
            resource_id=domain_id,
            event_data={
                "domain_id": domain_id,
                "name": name,
                "status": status,
                "owner_id": owner_id,
                "tenant_id": tenant_id,
            },
            tenant_id=tenant_id,
        )

        return event_id

    def publish_mesh_domain_updated(
        self,
        domain_id: str,
        changes: Dict[str, Any],
        previous_status: Optional[str] = None,
        new_status: Optional[str] = None,
        tenant_id: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish mesh.domain.updated event."""
        event_id = self._event_publisher.publish(
            event_type="mesh.domain.updated",
            data={
                "domain_id": domain_id,
                "changes": changes,
                "previous_status": previous_status,
                "new_status": new_status,
                "tenant_id": tenant_id,
            },
            **kwargs,
        )

        # Trigger webhook
        self._trigger_webhook_for_event(
            internal_event_type="mesh.domain.updated",
            resource_type="DATA_MESH_DOMAIN",
            resource_id=domain_id,
            event_data={
                "domain_id": domain_id,
                "changes": changes,
                "previous_status": previous_status,
                "new_status": new_status,
                "tenant_id": tenant_id,
            },
            tenant_id=tenant_id,
        )

        return event_id

    def publish_mesh_policy_applied(
        self,
        policy_application_id: str,
        domain_id: str,
        policy_id: Optional[str] = None,
        status: Optional[str] = None,
        tenant_id: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish mesh.policy.applied event."""
        event_id = self._event_publisher.publish(
            event_type="mesh.policy.applied",
            data={
                "policy_application_id": policy_application_id,
                "domain_id": domain_id,
                "policy_id": policy_id,
                "status": status,
                "tenant_id": tenant_id,
            },
            **kwargs,
        )

        # Trigger webhook
        self._trigger_webhook_for_event(
            internal_event_type="mesh.policy.applied",
            resource_type="POLICY_APPLICATION",
            resource_id=policy_application_id,
            event_data={
                "policy_application_id": policy_application_id,
                "domain_id": domain_id,
                "policy_id": policy_id,
                "status": status,
                "tenant_id": tenant_id,
            },
            tenant_id=tenant_id,
        )

        return event_id

    def publish_mesh_compliance_checked(
        self,
        domain_id: str,
        compliance_status: Optional[str] = None,
        violation_count: Optional[int] = None,
        checked_at: Optional[str] = None,
        tenant_id: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish mesh.compliance.checked event."""
        event_id = self._event_publisher.publish(
            event_type="mesh.compliance.checked",
            data={
                "domain_id": domain_id,
                "compliance_status": compliance_status,
                "violation_count": violation_count,
                "checked_at": checked_at,
                "tenant_id": tenant_id,
            },
            **kwargs,
        )

        # Trigger webhook
        self._trigger_webhook_for_event(
            internal_event_type="mesh.compliance.checked",
            resource_type="DATA_MESH_DOMAIN",
            resource_id=domain_id,
            event_data={
                "domain_id": domain_id,
                "compliance_status": compliance_status,
                "violation_count": violation_count,
                "checked_at": checked_at,
                "tenant_id": tenant_id,
            },
            tenant_id=tenant_id,
        )

        return event_id

    def publish_mesh_health_status_changed(
        self,
        domain_id: str,
        previous_status: Optional[str] = None,
        new_status: str = None,
        health_metrics: Optional[Dict[str, Any]] = None,
        changed_at: Optional[str] = None,
        tenant_id: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish mesh.health.status_changed event."""
        from django.utils import timezone

        if changed_at is None:
            changed_at = timezone.now().isoformat()

        event_id = self._event_publisher.publish(
            event_type="mesh.health.status_changed",
            data={
                "domain_id": domain_id,
                "previous_status": previous_status,
                "new_status": new_status,
                "health_metrics": health_metrics,
                "changed_at": changed_at,
                "tenant_id": tenant_id,
            },
            **kwargs,
        )

        # Trigger webhook
        self._trigger_webhook_for_event(
            internal_event_type="mesh.health.status_changed",
            resource_type="DATA_MESH_DOMAIN",
            resource_id=domain_id,
            event_data={
                "domain_id": domain_id,
                "previous_status": previous_status,
                "new_status": new_status,
                "health_metrics": health_metrics,
                "changed_at": changed_at,
                "tenant_id": tenant_id,
            },
            tenant_id=tenant_id,
        )

        return event_id


class VirtualizationEventPublisher:
    """Event publisher mixin for VirtualizationService."""

    def __init__(self, *args, **kwargs):
        # Only call super().__init__ if parent class supports it
        # BaseService doesn't have __init__, so we skip calling super
        # The actual service class (VirtualizationService) handles initialization
        try:
            # Check if parent has __init__ that accepts arguments
            parent_init = super().__init__
            if parent_init is not object.__init__:
                parent_init(*args, **kwargs)
        except (TypeError, AttributeError):
            # Parent doesn't support __init__ with arguments, skip
            pass
        self._event_publisher = EventPublisher(
            service_name="virtualization_service",
            tenant_id=getattr(self, "tenant_id", None),
            user_id=getattr(self, "user_id", None),
        )

    def _trigger_webhook_for_event(
        self,
        internal_event_type: str,
        resource_type: str,
        resource_id: str,
        event_data: Dict[str, Any],
        tenant_id: Optional[str] = None,
    ) -> None:
        """
        Trigger webhook for virtualization event.

        Args:
            internal_event_type: Internal event type (e.g., "virtualization.dataset.created")
            resource_type: Resource type
            resource_id: Resource ID
            event_data: Event data
            tenant_id: Tenant ID
        """
        if not tenant_id:
            tenant_id = getattr(self, "tenant_id", None)
            if not tenant_id:
                return

        try:
            from hub.apps.webhooks.service import WebhookDeliveryService

            WebhookDeliveryService.trigger_webhook(
                tenant_id=str(tenant_id),
                event_type=internal_event_type,
                resource_type=resource_type,
                resource_id=resource_id,
                event_data=event_data
            )
        except Exception as e:
            # Log but don't fail event publishing if webhook fails
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                f"Failed to trigger webhook for virtualization event {internal_event_type}: {e}",
                extra={
                    "event_type": internal_event_type,
                    "resource_type": resource_type,
                    "resource_id": resource_id,
                    "tenant_id": tenant_id,
                    "error": str(e)
                },
                exc_info=True
            )

    def publish_virtual_dataset_created(
        self,
        virtual_dataset_id: str,
        name: Optional[str] = None,
        query_type: Optional[str] = None,
        status: Optional[str] = None,
        version: Optional[str] = None,
        tenant_id: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish virtualization.dataset.created event."""
        event_id = self._event_publisher.publish(
            event_type="virtualization.dataset.created",
            data={
                "virtual_dataset_id": virtual_dataset_id,
                "name": name,
                "query_type": query_type,
                "status": status,
                "version": version,
            },
            **kwargs,
        )

        # Trigger webhook
        self._trigger_webhook_for_event(
            internal_event_type="virtualization.dataset.created",
            resource_type="VIRTUAL_DATASET",
            resource_id=virtual_dataset_id,
            event_data={
                "virtual_dataset_id": virtual_dataset_id,
                "name": name,
                "query_type": query_type,
                "status": status,
                "version": version,
            },
            tenant_id=tenant_id or getattr(self, "tenant_id", None),
        )

        return event_id

    def publish_virtual_dataset_updated(
        self,
        virtual_dataset_id: str,
        changes: Dict[str, Any],
        previous_status: Optional[str] = None,
        new_status: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish virtualization.dataset.updated event."""
        return self._event_publisher.publish(
            event_type="virtualization.dataset.updated",
            data={
                "virtual_dataset_id": virtual_dataset_id,
                "changes": changes,
                "previous_status": previous_status,
                "new_status": new_status,
            },
            **kwargs,
        )

    def publish_virtual_dataset_deleted(
        self,
        virtual_dataset_id: str,
        reason: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish virtualization.dataset.deleted event."""
        from django.utils import timezone

        return self._event_publisher.publish(
            event_type="virtualization.dataset.deleted",
            data={
                "virtual_dataset_id": virtual_dataset_id,
                "deleted_at": timezone.now().isoformat(),
                "reason": reason,
            },
            **kwargs,
        )

    def publish_query_execution_started(
        self,
        query_execution_id: str,
        virtual_dataset_id: str,
        execution_mode: Optional[str] = None,
        tenant_id: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish virtualization.query.execution.started event."""
        from django.utils import timezone

        event_id = self._event_publisher.publish(
            event_type="virtualization.query.execution.started",
            data={
                "query_execution_id": query_execution_id,
                "virtual_dataset_id": virtual_dataset_id,
                "execution_mode": execution_mode,
                "started_at": timezone.now().isoformat(),
            },
            **kwargs,
        )

        # Trigger webhook
        self._trigger_webhook_for_event(
            internal_event_type="virtualization.query.execution.started",
            resource_type="QUERY_EXECUTION",
            resource_id=query_execution_id,
            event_data={
                "query_execution_id": query_execution_id,
                "virtual_dataset_id": virtual_dataset_id,
                "execution_mode": execution_mode,
                "started_at": timezone.now().isoformat(),
            },
            tenant_id=tenant_id or getattr(self, "tenant_id", None),
        )

        return event_id

    def publish_query_execution_progress(
        self,
        query_execution_id: str,
        virtual_dataset_id: str,
        progress_percent: float,
        current_step: Optional[str] = None,
        elapsed_time_ms: Optional[int] = None,
        completed_steps: Optional[int] = None,
        total_steps: Optional[int] = None,
        tenant_id: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish virtualization.query.execution.progress event."""
        from django.utils import timezone

        event_id = self._event_publisher.publish(
            event_type="virtualization.query.execution.progress",
            data={
                "query_execution_id": query_execution_id,
                "virtual_dataset_id": virtual_dataset_id,
                "progress_percent": progress_percent,
                "current_step": current_step,
                "elapsed_time_ms": elapsed_time_ms,
                "completed_steps": completed_steps,
                "total_steps": total_steps,
                "timestamp": timezone.now().isoformat(),
            },
            **kwargs,
        )

        # Trigger webhook
        self._trigger_webhook_for_event(
            internal_event_type="virtualization.query.execution.progress",
            resource_type="QUERY_EXECUTION",
            resource_id=query_execution_id,
            event_data={
                "query_execution_id": query_execution_id,
                "virtual_dataset_id": virtual_dataset_id,
                "progress_percent": progress_percent,
                "current_step": current_step,
                "elapsed_time_ms": elapsed_time_ms,
                "completed_steps": completed_steps,
                "total_steps": total_steps,
                "timestamp": timezone.now().isoformat(),
            },
            tenant_id=tenant_id or getattr(self, "tenant_id", None),
        )

        return event_id

    def publish_query_execution_completed(
        self,
        query_execution_id: str,
        virtual_dataset_id: str,
        status: str,
        duration_ms: Optional[int] = None,
        rows_processed: Optional[int] = None,
        tenant_id: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish virtualization.query.execution.completed event."""
        from django.utils import timezone

        event_id = self._event_publisher.publish(
            event_type="virtualization.query.execution.completed",
            data={
                "query_execution_id": query_execution_id,
                "virtual_dataset_id": virtual_dataset_id,
                "status": status,
                "completed_at": timezone.now().isoformat(),
                "duration_ms": duration_ms,
                "rows_processed": rows_processed,
            },
            **kwargs,
        )

        # Trigger webhook
        self._trigger_webhook_for_event(
            internal_event_type="virtualization.query.execution.completed",
            resource_type="QUERY_EXECUTION",
            resource_id=query_execution_id,
            event_data={
                "query_execution_id": query_execution_id,
                "virtual_dataset_id": virtual_dataset_id,
                "status": status,
                "completed_at": timezone.now().isoformat(),
                "duration_ms": duration_ms,
                "rows_processed": rows_processed,
            },
            tenant_id=tenant_id or getattr(self, "tenant_id", None),
        )

        return event_id

    def publish_query_execution_failed(
        self,
        query_execution_id: str,
        virtual_dataset_id: str,
        error_message: str,
        duration_ms: Optional[int] = None,
        tenant_id: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish virtualization.query.execution.failed event."""
        from django.utils import timezone

        event_id = self._event_publisher.publish(
            event_type="virtualization.query.execution.failed",
            data={
                "query_execution_id": query_execution_id,
                "virtual_dataset_id": virtual_dataset_id,
                "error_message": error_message,
                "failed_at": timezone.now().isoformat(),
                "duration_ms": duration_ms,
            },
            **kwargs,
        )

        # Trigger webhook
        self._trigger_webhook_for_event(
            internal_event_type="virtualization.query.execution.failed",
            resource_type="QUERY_EXECUTION",
            resource_id=query_execution_id,
            event_data={
                "query_execution_id": query_execution_id,
                "virtual_dataset_id": virtual_dataset_id,
                "error_message": error_message,
                "failed_at": timezone.now().isoformat(),
                "duration_ms": duration_ms,
            },
            tenant_id=tenant_id or getattr(self, "tenant_id", None),
        )

        return event_id

    def publish_query_execution_cancelled(
        self,
        query_execution_id: str,
        virtual_dataset_id: str,
        reason: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish virtualization.query.execution.cancelled event."""
        from django.utils import timezone

        return self._event_publisher.publish(
            event_type="virtualization.query.execution.cancelled",
            data={
                "query_execution_id": query_execution_id,
                "virtual_dataset_id": virtual_dataset_id,
                "reason": reason,
                "cancelled_at": timezone.now().isoformat(),
            },
            **kwargs,
        )


class FileEventPublisher:
    """Event publisher mixin for FileService."""

    def __init__(self, *args, **kwargs):
        # Only call super().__init__ if parent class supports it
        # BaseService doesn't have __init__, so we skip calling super
        # The actual service class (FileService) handles initialization
        try:
            # Check if parent has __init__ that accepts arguments
            parent_init = super().__init__
            if parent_init is not object.__init__:
                parent_init(*args, **kwargs)
        except (TypeError, AttributeError):
            # Parent doesn't support __init__ with arguments, skip
            pass
        # Set tenant_id and user_id from kwargs if provided
        if 'tenant_id' in kwargs:
            self.tenant_id = kwargs['tenant_id']
        if 'user_id' in kwargs:
            self.user_id = kwargs['user_id']
        self._event_publisher = EventPublisher(
            service_name="file_service",
            tenant_id=getattr(self, "tenant_id", None),
            user_id=getattr(self, "user_id", None),
        )

    def publish_file_created(
        self,
        file_id: str,
        name: Optional[str] = None,
        content_type: Optional[str] = None,
        size: Optional[int] = None,
        status: Optional[str] = None,
        content_sha256: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish file.created event."""
        return self._event_publisher.publish(
            event_type="file.created",
            data={
                "file_id": file_id,
                "name": name,
                "content_type": content_type,
                "size": size,
                "status": status,
                "content_sha256": content_sha256,
            },
            **kwargs,
        )

    def publish_file_updated(
        self,
        file_id: str,
        changes: Dict[str, Any],
        previous_status: Optional[str] = None,
        new_status: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish file.updated event."""
        return self._event_publisher.publish(
            event_type="file.updated",
            data={
                "file_id": file_id,
                "changes": changes,
                "previous_status": previous_status,
                "new_status": new_status,
            },
            **kwargs,
        )

    def publish_file_deleted(
        self,
        file_id: str,
        reason: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish file.deleted event."""
        from django.utils import timezone

        return self._event_publisher.publish(
            event_type="file.deleted",
            data={
                "file_id": file_id,
                "deleted_at": timezone.now().isoformat(),
                "reason": reason,
            },
            **kwargs,
        )

    def publish_file_uploaded(
        self,
        file_id: str,
        file_size: Optional[int] = None,
        content_type: Optional[str] = None,
        upload_duration_ms: Optional[int] = None,
        content_sha256: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish file.uploaded event."""
        return self._event_publisher.publish(
            event_type="file.uploaded",
            data={
                "file_id": file_id,
                "file_size": file_size,
                "content_type": content_type,
                "upload_duration_ms": upload_duration_ms,
                "content_sha256": content_sha256,
            },
            **kwargs,
        )

    def publish_file_downloaded(
        self,
        file_id: str,
        download_duration_ms: Optional[int] = None,
        download_size: Optional[int] = None,
        **kwargs,
    ) -> str:
        """Publish file.downloaded event."""
        return self._event_publisher.publish(
            event_type="file.downloaded",
            data={
                "file_id": file_id,
                "download_duration_ms": download_duration_ms,
                "download_size": download_size,
            },
            **kwargs,
        )


class LineageEventPublisher:
    """Event publisher mixin for LineageService."""

    def __init__(self, *args, **kwargs):
        # Only call super().__init__ if parent class supports it
        # BaseService doesn't have __init__, so we skip calling super
        # The actual service class (LineageService) handles initialization
        try:
            # Check if parent has __init__ that accepts arguments
            parent_init = super().__init__
            if parent_init is not object.__init__:
                parent_init(*args, **kwargs)
        except (TypeError, AttributeError):
            # Parent doesn't support __init__ with arguments, skip
            pass
        # Set tenant_id and user_id from kwargs if provided
        if 'tenant_id' in kwargs:
            self.tenant_id = kwargs['tenant_id']
        if 'user_id' in kwargs:
            self.user_id = kwargs['user_id']
        self._event_publisher = EventPublisher(
            service_name="lineage_service",
            tenant_id=getattr(self, "tenant_id", None),
            user_id=getattr(self, "user_id", None),
        )

    def publish_lineage_updated(
        self,
        contract_id: str,
        model_name: Optional[str] = None,
        field_name: Optional[str] = None,
        lineage_type: Optional[str] = None,
        changes: Optional[Dict[str, Any]] = None,
        relationship_count: Optional[int] = None,
        **kwargs,
    ) -> str:
        """Publish lineage.updated event."""
        return self._event_publisher.publish(
            event_type="lineage.updated",
            data={
                "contract_id": contract_id,
                "model_name": model_name,
                "field_name": field_name,
                "lineage_type": lineage_type,
                "changes": changes,
                "relationship_count": relationship_count,
            },
            **kwargs,
        )

    def publish_lineage_relationship_added(
        self,
        contract_id: str,
        source_reference: str,
        target_reference: str,
        relationship_type: Optional[str] = None,
        model_name: Optional[str] = None,
        field_name: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish lineage.relationship_added event."""
        return self._event_publisher.publish(
            event_type="lineage.relationship_added",
            data={
                "contract_id": contract_id,
                "source_reference": source_reference,
                "target_reference": target_reference,
                "relationship_type": relationship_type,
                "model_name": model_name,
                "field_name": field_name,
            },
            **kwargs,
        )

    def publish_lineage_relationship_removed(
        self,
        contract_id: str,
        source_reference: str,
        target_reference: str,
        relationship_type: Optional[str] = None,
        model_name: Optional[str] = None,
        field_name: Optional[str] = None,
        reason: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish lineage.relationship_removed event."""
        return self._event_publisher.publish(
            event_type="lineage.relationship_removed",
            data={
                "contract_id": contract_id,
                "source_reference": source_reference,
                "target_reference": target_reference,
                "relationship_type": relationship_type,
                "model_name": model_name,
                "field_name": field_name,
                "reason": reason,
            },
            **kwargs,
        )


class SearchEventPublisher:
    """Event publisher mixin for SearchService."""

    def __init__(self, *args, **kwargs):
        # Only call super().__init__ if parent class supports it
        # BaseService doesn't have __init__, so we skip calling super
        # The actual service class (SearchService) handles initialization
        try:
            # Check if parent has __init__ that accepts arguments
            parent_init = super().__init__
            if parent_init is not object.__init__:
                parent_init(*args, **kwargs)
        except (TypeError, AttributeError):
            # Parent doesn't support __init__ with arguments, skip
            pass
        # Set tenant_id and user_id from kwargs if provided
        if 'tenant_id' in kwargs:
            self.tenant_id = kwargs['tenant_id']
        if 'user_id' in kwargs:
            self.user_id = kwargs['user_id']
        self._event_publisher = EventPublisher(
            service_name="search_service",
            tenant_id=getattr(self, "tenant_id", None),
            user_id=getattr(self, "user_id", None),
        )

    def publish_search_query(
        self,
        query: str,
        query_type: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        result_count: Optional[int] = None,
        no_results: Optional[bool] = None,
        execution_time_ms: Optional[int] = None,
        **kwargs,
    ) -> str:
        """Publish search.query event."""
        return self._event_publisher.publish(
            event_type="search.query",
            data={
                "query": query,
                "query_type": query_type,
                "filters": filters or {},
                "result_count": result_count,
                "no_results": no_results,
                "execution_time_ms": execution_time_ms,
            },
            tags=["search", "query"],
            **kwargs,
        )

    def publish_index_updated(
        self,
        resource_type: str,
        resource_id: str,
        index_id: Optional[str] = None,
        title: Optional[str] = None,
        update_type: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish search.index.updated event."""
        return self._event_publisher.publish(
            event_type="search.index.updated",
            data={
                "index_id": index_id,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "title": title,
                "update_type": update_type,  # 'created', 'updated', 'deleted'
            },
            tags=["search", "index"],
            **kwargs,
        )

    def publish_index_rebuilt(
        self,
        tenant_id: Optional[str] = None,
        resource_count: Optional[int] = None,
        duration_ms: Optional[int] = None,
        resource_types: Optional[List[str]] = None,
        success: Optional[bool] = None,
        errors: Optional[List[str]] = None,
        **kwargs,
    ) -> str:
        """Publish search.index.rebuilt event."""
        return self._event_publisher.publish(
            event_type="search.index.rebuilt",
            data={
                "tenant_id": tenant_id,
                "resource_count": resource_count,
                "duration_ms": duration_ms,
                "resource_types": resource_types or [],
                "success": success,
                "errors": errors or [],
            },
            tenant_id=tenant_id,
            tags=["search", "index", "rebuild"],
            **kwargs,
        )


class PaymentGatewayEventPublisher:
    """Event publisher mixin for PaymentGatewayService."""

    def __init__(self, *args, **kwargs):
        # Only call super().__init__ if parent class supports it
        # BaseService doesn't have __init__, so we skip calling super
        # The actual service class (PaymentGatewayService) handles initialization
        try:
            # Check if parent has __init__ that accepts arguments
            parent_init = super().__init__
            if parent_init is not object.__init__:
                parent_init(*args, **kwargs)
        except (TypeError, AttributeError):
            # Parent doesn't support __init__ with arguments, skip
            pass
        # Set tenant_id and user_id from kwargs if provided
        if 'tenant_id' in kwargs:
            self.tenant_id = kwargs['tenant_id']
        if 'user_id' in kwargs:
            self.user_id = kwargs['user_id']
        self._event_publisher = EventPublisher(
            service_name="payment_gateway_service",
            tenant_id=getattr(self, "tenant_id", None),
            user_id=getattr(self, "user_id", None),
        )

    def publish_gateway_linked(
        self,
        contract_id: str,
        gateway_id: str,
        webhook_url: Optional[str] = None,
        gateway_type: Optional[str] = None,
        gateway_name: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish payment.gateway.linked event."""
        return self._event_publisher.publish(
            event_type="payment.gateway.linked",
            data={
                "contract_id": contract_id,
                "gateway_id": gateway_id,
                "webhook_url": webhook_url,
                "gateway_type": gateway_type,
                "gateway_name": gateway_name,
            },
            tags=["payment", "gateway", "linked"],
            **kwargs,
        )

    def publish_gateway_unlinked(
        self,
        contract_id: str,
        gateway_id: str,
        reason: Optional[str] = None,
        gateway_type: Optional[str] = None,
        gateway_name: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish payment.gateway.unlinked event."""
        return self._event_publisher.publish(
            event_type="payment.gateway.unlinked",
            data={
                "contract_id": contract_id,
                "gateway_id": gateway_id,
                "reason": reason,
                "gateway_type": gateway_type,
                "gateway_name": gateway_name,
            },
            tags=["payment", "gateway", "unlinked"],
            **kwargs,
        )

    def publish_gateway_webhook_received(
        self,
        contract_id: str,
        gateway_id: str,
        webhook_type: Optional[str] = None,
        webhook_data: Optional[Dict[str, Any]] = None,
        webhook_headers: Optional[Dict[str, str]] = None,
        webhook_signature: Optional[str] = None,
        processing_status: Optional[str] = None,
        processing_error: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish payment.gateway.webhook.received event."""
        return self._event_publisher.publish(
            event_type="payment.gateway.webhook.received",
            data={
                "contract_id": contract_id,
                "gateway_id": gateway_id,
                "webhook_type": webhook_type,
                "webhook_data": webhook_data if isinstance(webhook_data, dict) else {},
                "webhook_headers": webhook_headers if isinstance(webhook_headers, dict) else {},
                "webhook_signature": webhook_signature,
                "processing_status": processing_status,
                "processing_error": processing_error,
            },
            tags=["payment", "gateway", "webhook"],
            **kwargs,
        )


class TenantEventPublisher:
    """Event publisher mixin for TenantService."""

    def __init__(self, *args, **kwargs):
        # Only call super().__init__ if parent class supports it
        # BaseService doesn't have __init__, so we skip calling super
        # The actual service class (TenantService) handles initialization
        try:
            # Check if parent has __init__ that accepts arguments
            parent_init = super().__init__
            if parent_init is not object.__init__:
                parent_init(*args, **kwargs)
        except (TypeError, AttributeError):
            # Parent doesn't support __init__ with arguments, skip
            pass
        # Set tenant_id and user_id from kwargs if provided
        if 'tenant_id' in kwargs:
            self.tenant_id = kwargs['tenant_id']
        if 'user_id' in kwargs:
            self.user_id = kwargs['user_id']
        self._event_publisher = EventPublisher(
            service_name="hub",
            tenant_id=getattr(self, "tenant_id", None),
            user_id=getattr(self, "user_id", None),
        )

    def publish_tenant_created(
        self,
        tenant_id: str,
        name: Optional[str] = None,
        slug: Optional[str] = None,
        status: Optional[str] = None,
        kyc_status: Optional[str] = None,
        region: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish tenant.created event."""
        return self._event_publisher.publish(
            event_type="tenant.created",
            data={
                "tenant_id": tenant_id,
                "name": name,
                "slug": slug,
                "status": status,
                "kyc_status": kyc_status,
                "region": region,
            },
            tags=["tenant", "creation"],
            **kwargs,
        )

    def publish_tenant_updated(
        self,
        tenant_id: str,
        changes: Dict[str, Any],
        previous_status: Optional[str] = None,
        new_status: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish tenant.updated event."""
        return self._event_publisher.publish(
            event_type="tenant.updated",
            data={
                "tenant_id": tenant_id,
                "changes": changes,
                "previous_status": previous_status,
                "new_status": new_status,
            },
            tags=["tenant", "update"],
            **kwargs,
        )

    def publish_tenant_deleted(
        self,
        tenant_id: str,
        reason: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish tenant.deleted event."""
        from django.utils import timezone

        return self._event_publisher.publish(
            event_type="tenant.deleted",
            data={
                "tenant_id": tenant_id,
                "deleted_at": timezone.now().isoformat(),
                "reason": reason,
            },
            tags=["tenant", "deletion"],
            **kwargs,
        )

    def publish_tenant_quota_changed(
        self,
        tenant_id: str,
        quota_type: str,
        quota_field: str,
        previous_value: Optional[Any] = None,
        new_value: Optional[Any] = None,
        **kwargs,
    ) -> str:
        """Publish tenant.quota.changed event."""
        return self._event_publisher.publish(
            event_type="tenant.quota.changed",
            data={
                "tenant_id": tenant_id,
                "quota_type": quota_type,
                "quota_field": quota_field,
                "previous_value": previous_value,
                "new_value": new_value,
            },
            tags=["tenant", "quota"],
            **kwargs,
        )


class NormalizationEventPublisher:
    """Event publisher mixin for NormalizationService."""

    def __init__(self, *args, **kwargs):
        try:
            parent_init = super().__init__
            if parent_init is not object.__init__:
                parent_init(*args, **kwargs)
        except (TypeError, AttributeError):
            pass
        self._event_publisher = EventPublisher(
            service_name="normalization_service",
            tenant_id=getattr(self, "tenant_id", None),
            user_id=getattr(self, "user_id", None),
        )

    def publish_normalization_started(
        self,
        contract_id: str,
        normalization_type: str,
        spec_version: Optional[str] = None,
        source_format: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish normalization.started event."""
        return self._event_publisher.publish(
            event_type="normalization.started",
            data={
                "contract_id": contract_id,
                "normalization_type": normalization_type,
                "spec_version": spec_version,
                "source_format": source_format,
            },
            tags=["normalization", "started"],
            **kwargs,
        )

    def publish_normalization_completed(
        self,
        contract_id: str,
        normalization_status: str,
        normalization_errors: Optional[List[str]] = None,
        normalization_warnings: Optional[List[str]] = None,
        duration_ms: Optional[int] = None,
        spec_version: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish normalization.completed event."""
        return self._event_publisher.publish(
            event_type="normalization.completed",
            data={
                "contract_id": contract_id,
                "normalization_status": normalization_status,
                "normalization_errors": normalization_errors,
                "normalization_warnings": normalization_warnings,
                "duration_ms": duration_ms,
                "spec_version": spec_version,
            },
            tags=["normalization", "completed"],
            **kwargs,
        )

    def publish_normalization_failed(
        self,
        contract_id: str,
        error_message: str,
        error_details: Optional[Dict[str, Any]] = None,
        normalization_errors: Optional[List[str]] = None,
        retry_count: Optional[int] = None,
        spec_version: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish normalization.failed event."""
        return self._event_publisher.publish(
            event_type="normalization.failed",
            data={
                "contract_id": contract_id,
                "error_message": error_message,
                "error_details": error_details,
                "normalization_errors": normalization_errors,
                "retry_count": retry_count,
                "spec_version": spec_version,
            },
            tags=["normalization", "failed"],
            **kwargs,
        )


class PaymentEventPublisher:
    """Event publisher mixin for PaymentService."""

    def __init__(self, *args, **kwargs):
        try:
            parent_init = super().__init__
            if parent_init is not object.__init__:
                parent_init(*args, **kwargs)
        except (TypeError, AttributeError):
            pass
        self._event_publisher = EventPublisher(
            service_name="payment_service",
            tenant_id=getattr(self, "tenant_id", None),
            user_id=getattr(self, "user_id", None),
        )

    def publish_payment_initiated(
        self,
        payment_id: str,
        order_id: str,
        amount: Optional[float] = None,
        currency: Optional[str] = None,
        gateway: Optional[str] = None,
        payment_method: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish payment.initiated event."""
        return self._event_publisher.publish(
            event_type="payment.initiated",
            data={
                "payment_id": payment_id,
                "order_id": order_id,
                "amount": amount,
                "currency": currency,
                "gateway": gateway,
                "payment_method": payment_method,
            },
            tags=["payment", "initiated"],
            **kwargs,
        )

    def publish_payment_completed(
        self,
        payment_id: str,
        order_id: str,
        status: str,
        amount: Optional[float] = None,
        currency: Optional[str] = None,
        gateway: Optional[str] = None,
        gateway_transaction_id: Optional[str] = None,
        processed_at: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish payment.completed event."""
        from django.utils import timezone

        if processed_at is None:
            processed_at = timezone.now().isoformat()

        return self._event_publisher.publish(
            event_type="payment.completed",
            data={
                "payment_id": payment_id,
                "order_id": order_id,
                "status": status,
                "amount": amount,
                "currency": currency,
                "gateway": gateway,
                "gateway_transaction_id": gateway_transaction_id,
                "processed_at": processed_at,
            },
            tags=["payment", "completed"],
            **kwargs,
        )

    def publish_payment_failed(
        self,
        payment_id: str,
        order_id: str,
        error_message: str,
        error_details: Optional[Dict[str, Any]] = None,
        amount: Optional[float] = None,
        currency: Optional[str] = None,
        gateway: Optional[str] = None,
        failed_at: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish payment.failed event."""
        from django.utils import timezone

        if failed_at is None:
            failed_at = timezone.now().isoformat()

        return self._event_publisher.publish(
            event_type="payment.failed",
            data={
                "payment_id": payment_id,
                "order_id": order_id,
                "error_message": error_message,
                "error_details": error_details,
                "amount": amount,
                "currency": currency,
                "gateway": gateway,
                "failed_at": failed_at,
            },
            tags=["payment", "failed"],
            **kwargs,
        )

    def publish_payment_refunded(
        self,
        payment_id: str,
        order_id: str,
        refund_amount: Optional[float] = None,
        currency: Optional[str] = None,
        gateway: Optional[str] = None,
        gateway_refund_id: Optional[str] = None,
        refund_reason: Optional[str] = None,
        refunded_at: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish payment.refunded event."""
        from django.utils import timezone

        if refunded_at is None:
            refunded_at = timezone.now().isoformat()

        return self._event_publisher.publish(
            event_type="payment.refunded",
            data={
                "payment_id": payment_id,
                "order_id": order_id,
                "refund_amount": refund_amount,
                "currency": currency,
                "gateway": gateway,
                "gateway_refund_id": gateway_refund_id,
                "refund_reason": refund_reason,
                "refunded_at": refunded_at,
            },
            tags=["payment", "refunded"],
            **kwargs,
        )


class ObservabilityEventPublisher:
    """Event publisher mixin for ObservabilityService."""

    def __init__(self, *args, **kwargs):
        # Only call super().__init__ if parent class supports it
        # BaseService doesn't have __init__, so we skip calling super
        # The actual service class (ObservabilityService) handles initialization
        try:
            # Check if parent has __init__ that accepts arguments
            parent_init = super().__init__
            if parent_init is not object.__init__:
                parent_init(*args, **kwargs)
        except (TypeError, AttributeError):
            # Parent doesn't support __init__ with arguments, skip
            pass
        # Set tenant_id and user_id from kwargs if provided
        if 'tenant_id' in kwargs:
            self.tenant_id = kwargs['tenant_id']
        if 'user_id' in kwargs:
            self.user_id = kwargs['user_id']
        self._event_publisher = EventPublisher(
            service_name="observability_service",
            tenant_id=getattr(self, "tenant_id", None),
            user_id=getattr(self, "user_id", None),
        )

    def publish_metric_recorded(
        self,
        metric_name: str,
        metric_value: Optional[float] = None,
        metric_type: Optional[str] = None,
        labels: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> str:
        """Publish observability.metric.recorded event."""
        return self._event_publisher.publish(
            event_type="observability.metric.recorded",
            data={
                "metric_name": metric_name,
                "metric_value": metric_value,
                "metric_type": metric_type,
                "labels": labels,
            },
            tags=["observability", "metric"],
            **kwargs,
        )

    def publish_trace_created(
        self,
        trace_id: str,
        span_id: str,
        operation_name: Optional[str] = None,
        duration_ms: Optional[float] = None,
        status: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> str:
        """Publish observability.trace.created event."""
        return self._event_publisher.publish(
            event_type="observability.trace.created",
            data={
                "trace_id": trace_id,
                "span_id": span_id,
                "operation_name": operation_name,
                "duration_ms": duration_ms,
                "status": status,
                "attributes": attributes,
            },
            tags=["observability", "trace"],
            **kwargs,
        )

    def publish_log_created(
        self,
        message: str,
        log_level: Optional[str] = None,
        logger_name: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> str:
        """Publish observability.log.created event."""
        return self._event_publisher.publish(
            event_type="observability.log.created",
            data={
                "message": message,
                "log_level": log_level,
                "logger_name": logger_name,
                "context": context,
            },
            tags=["observability", "log"],
            **kwargs,
        )

    def publish_alert_triggered(
        self,
        alert_name: str,
        alert_severity: str,
        alert_message: Optional[str] = None,
        metric_name: Optional[str] = None,
        threshold_value: Optional[float] = None,
        current_value: Optional[float] = None,
        triggered_at: Optional[str] = None,
        dataset_id: Optional[str] = None,
        asset_id: Optional[str] = None,
        labels: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> str:
        """Publish observability.alert.triggered event."""
        from django.utils import timezone

        if triggered_at is None:
            triggered_at = timezone.now().isoformat()

        data = {
            "alert_name": alert_name,
            "alert_severity": alert_severity,
            "alert_message": alert_message,
            "metric_name": metric_name,
            "threshold_value": threshold_value,
            "current_value": current_value,
            "triggered_at": triggered_at,
        }
        if dataset_id is not None:
            data["dataset_id"] = dataset_id
        if asset_id is not None:
            data["asset_id"] = asset_id
        if labels is not None:
            data["labels"] = labels

        return self._event_publisher.publish(
            event_type="observability.alert.triggered",
            data=data,
            tags=["observability", "alert"],
            **kwargs,
        )


class IntegrationEventPublisher:
    """Event publisher mixin for MarketplaceIntegrationService."""

    def __init__(self, *args, **kwargs):
        # Only call super().__init__ if parent class supports it
        # BaseService doesn't have __init__, so we skip calling super
        # The actual service class (MarketplaceIntegrationService) handles initialization
        try:
            # Check if parent has __init__ that accepts arguments
            parent_init = super().__init__
            if parent_init is not object.__init__:
                parent_init(*args, **kwargs)
        except (TypeError, AttributeError):
            # Parent doesn't support __init__ with arguments, skip
            pass
        self._event_publisher = EventPublisher(
            service_name="marketplace_integration_service",
            tenant_id=getattr(self, "tenant_id", None),
            user_id=getattr(self, "user_id", None),
        )

    def publish_connection_created(
        self,
        connection_id: str,
        marketplace_type: str,
        name: str,
        **kwargs,
    ) -> str:
        """Publish integration.connection.created event.
        Raises ValueError if connection_id or marketplace_type is None/invalid.
        """
        from django.utils import timezone

        if (
            connection_id is None
            or not isinstance(connection_id, str)
            or not connection_id.strip()
        ):
            raise ValueError(
                "connection_id is required and must be a non-empty string "
                "for integration.connection.created"
            )
        if marketplace_type is None:
            raise ValueError(
                "marketplace_type is required for integration.connection.created"
            )
        safe_name = name if name is not None else ""
        return self._event_publisher.publish(
            event_type="integration.connection.created",
            data={
                "connection_id": connection_id.strip(),
                "marketplace_type": marketplace_type,
                "name": safe_name,
                "created_at": timezone.now().isoformat(),
            },
            tags=["integration", "connection", "created"],
            **kwargs,
        )

    def publish_connection_updated(
        self,
        connection_id: str,
        changes: Dict[str, Any],
        **kwargs,
    ) -> str:
        """Publish integration.connection.updated event."""
        from django.utils import timezone

        return self._event_publisher.publish(
            event_type="integration.connection.updated",
            data={
                "connection_id": connection_id,
                "changes": changes,
                "updated_at": timezone.now().isoformat(),
            },
            tags=["integration", "connection", "updated"],
            **kwargs,
        )

    def publish_connection_deleted(
        self,
        connection_id: str,
        marketplace_type: str,
        name: Optional[str] = None,
        reason: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish integration.connection.deleted event."""
        from django.utils import timezone

        return self._event_publisher.publish(
            event_type="integration.connection.deleted",
            data={
                "connection_id": connection_id,
                "marketplace_type": marketplace_type,
                "name": name or "",  # Required field
                "deleted_at": timezone.now().isoformat(),
                "reason": reason,
            },
            tags=["integration", "connection", "deleted"],
            **kwargs,
        )

    def publish_connection_tested(
        self,
        connection_id: str,
        success: bool,
        error_message: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish integration.connection.tested event."""
        from django.utils import timezone

        return self._event_publisher.publish(
            event_type="integration.connection.tested",
            data={
                "connection_id": connection_id,
                "success": success,
                "error_message": error_message,
                "tested_at": timezone.now().isoformat(),
            },
            tags=["integration", "connection", "tested"],
            **kwargs,
        )

    def publish_sync_job_created(
        self,
        sync_job_id: str,
        connection_id: str,
        direction: str,
        **kwargs,
    ) -> str:
        """Publish integration.sync_job.created event."""
        from django.utils import timezone

        return self._event_publisher.publish(
            event_type="integration.sync_job.created",
            data={
                "sync_job_id": sync_job_id,
                "connection_id": connection_id,
                "direction": direction,
                "created_at": timezone.now().isoformat(),
            },
            tags=["integration", "sync_job", "created"],
            **kwargs,
        )

    def publish_sync_job_started(
        self,
        sync_job_id: str,
        connection_id: str,
        direction: str,
        **kwargs,
    ) -> str:
        """Publish integration.sync_job.started event."""
        from django.utils import timezone

        return self._event_publisher.publish(
            event_type="integration.sync_job.started",
            data={
                "sync_job_id": sync_job_id,
                "connection_id": connection_id,
                "direction": direction,
                "started_at": timezone.now().isoformat(),
            },
            tags=["integration", "sync_job", "started"],
            **kwargs,
        )

    def publish_sync_job_completed(
        self,
        sync_job_id: str,
        connection_id: str,
        direction: str,
        status: str,
        items_synced: int,
        items_failed: int,
        **kwargs,
    ) -> str:
        """Publish integration.sync_job.completed event."""
        from django.utils import timezone

        return self._event_publisher.publish(
            event_type="integration.sync_job.completed",
            data={
                "sync_job_id": sync_job_id,
                "connection_id": connection_id,
                "direction": direction,
                "status": status,
                "items_synced": items_synced,
                "items_failed": items_failed,
                "completed_at": timezone.now().isoformat(),
            },
            tags=["integration", "sync_job", "completed"],
            **kwargs,
        )

    def publish_sync_job_cancelled(
        self,
        sync_job_id: str,
        connection_id: str,
        direction: str,
        reason: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish integration.sync_job.cancelled event."""
        from django.utils import timezone

        return self._event_publisher.publish(
            event_type="integration.sync_job.cancelled",
            data={
                "sync_job_id": sync_job_id,
                "connection_id": connection_id,
                "direction": direction,
                "reason": reason,
                "cancelled_at": timezone.now().isoformat(),
            },
            tags=["integration", "sync_job", "cancelled"],
            **kwargs,
        )

    def publish_scheduled_sync_created(
        self,
        scheduled_sync_id: str,
        connection_id: str,
        direction: str,
        schedule_type: str,
        **kwargs,
    ) -> str:
        """Publish integration.scheduled_sync.created event."""
        from django.utils import timezone

        return self._event_publisher.publish(
            event_type="integration.scheduled_sync.created",
            data={
                "scheduled_sync_id": scheduled_sync_id,
                "connection_id": connection_id,
                "direction": direction,
                "schedule_type": schedule_type,
                "created_at": timezone.now().isoformat(),
            },
            tags=["integration", "scheduled_sync", "created"],
            **kwargs,
        )

    def publish_scheduled_sync_deleted(
        self,
        scheduled_sync_id: str,
        connection_id: str,
        **kwargs,
    ) -> str:
        """Publish integration.scheduled_sync.deleted event."""
        from django.utils import timezone

        return self._event_publisher.publish(
            event_type="integration.scheduled_sync.deleted",
            data={
                "scheduled_sync_id": scheduled_sync_id,
                "connection_id": connection_id,
                "deleted_at": timezone.now().isoformat(),
            },
            tags=["integration", "scheduled_sync", "deleted"],
            **kwargs,
        )

    def publish_mapping_created(
        self,
        mapping_id: str,
        connection_id: str,
        hub_asset_id: str,
        external_listing_id: str,
        **kwargs,
    ) -> str:
        """Publish integration.mapping.created event."""
        from django.utils import timezone
        return self._event_publisher.publish(
            event_type="integration.mapping.created",
            data={
                "mapping_id": mapping_id,
                "connection_id": connection_id,
                "hub_asset_id": hub_asset_id,
                "external_listing_id": external_listing_id,
                "created_at": timezone.now().isoformat(),
            },
            tags=["integration", "mapping", "created"],
            **kwargs,
        )

    def publish_mapping_updated(
        self,
        mapping_id: str,
        connection_id: str,
        changes: Dict[str, Any],
        **kwargs,
    ) -> str:
        """Publish integration.mapping.updated event."""
        from django.utils import timezone
        return self._event_publisher.publish(
            event_type="integration.mapping.updated",
            data={
                "mapping_id": mapping_id,
                "connection_id": connection_id,
                "changes": changes,
                "updated_at": timezone.now().isoformat(),
            },
            tags=["integration", "mapping", "updated"],
            **kwargs,
        )

    def publish_mapping_deleted(
        self,
        mapping_id: str,
        connection_id: str,
        hub_asset_id: str,
        external_listing_id: str,
        reason: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish integration.mapping.deleted event."""
        from django.utils import timezone
        return self._event_publisher.publish(
            event_type="integration.mapping.deleted",
            data={
                "mapping_id": mapping_id,
                "connection_id": connection_id,
                "hub_asset_id": hub_asset_id,
                "external_listing_id": external_listing_id,
                "reason": reason,
                "deleted_at": timezone.now().isoformat(),
            },
            tags=["integration", "mapping", "deleted"],
            **kwargs,
        )


class BaaSEventPublisher:
    """Event publisher mixin for BaaS Platform services."""

    def __init__(self, *args, **kwargs):
        try:
            parent_init = super().__init__
            if parent_init is not object.__init__:
                parent_init(*args, **kwargs)
        except (TypeError, AttributeError):
            pass
        self._event_publisher = EventPublisher(
            service_name="baas_service",
            tenant_id=getattr(self, "tenant_id", None),
            user_id=getattr(self, "user_id", None),
        )

    def publish_api_key_created(
        self,
        api_key_id: str,
        tenant_id: str,
        user_id: str,
        tier: str,
        **kwargs,
    ) -> str:
        """Publish baas.api_key.created event."""
        return self._event_publisher.publish(
            event_type="baas.api_key.created",
            data={
                "api_key_id": api_key_id,
                "tenant_id": tenant_id,
                "user_id": user_id,
                "tier": tier,
            },
            **kwargs,
        )

    def publish_api_key_revoked(
        self,
        api_key_id: str,
        tenant_id: str,
        user_id: str,
        reason: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish baas.api_key.revoked event."""
        from django.utils import timezone

        return self._event_publisher.publish(
            event_type="baas.api_key.revoked",
            data={
                "api_key_id": api_key_id,
                "tenant_id": tenant_id,
                "user_id": user_id,
                "revoked_at": timezone.now().isoformat(),
                "reason": reason,
            },
            **kwargs,
        )

    def publish_usage_tracked(
        self,
        api_key_id: str,
        endpoint: str,
        method: str,
        status_code: int,
        response_time_ms: int,
        **kwargs,
    ) -> str:
        """Publish baas.usage.tracked event."""
        return self._event_publisher.publish(
            event_type="baas.usage.tracked",
            data={
                "api_key_id": api_key_id,
                "endpoint": endpoint,
                "method": method,
                "status_code": status_code,
                "response_time_ms": response_time_ms,
            },
            **kwargs,
        )

    def publish_billing_report_generated(
        self,
        report_id: str,
        customer_id: str,
        total_amount: str,
        currency: str,
        tenant_id: str = None,
        **kwargs,
    ) -> str:
        """Publish billing.report.generated event."""
        return self._event_publisher.publish(
            event_type="billing.report.generated",
            data={
                "report_id": report_id,
                "customer_id": customer_id,
                "total_amount": total_amount,
                "currency": currency,
            },
            tenant_id=tenant_id,
            **kwargs,
        )

    def publish_billing_report_sent(
        self,
        report_id: str,
        customer_id: str,
        customer_email: str,
        tenant_id: str = None,
        **kwargs,
    ) -> str:
        """Publish billing.report.sent event."""
        return self._event_publisher.publish(
            event_type="billing.report.sent",
            data={
                "report_id": report_id,
                "customer_id": customer_id,
                "customer_email": customer_email,
            },
            tenant_id=tenant_id,
            **kwargs,
        )


class MLEventPublisher:
    """Event publisher mixin for ML Model Registry Bridge Service."""

    def __init__(self, *args, **kwargs):
        try:
            parent_init = super().__init__
            if parent_init is not object.__init__:
                parent_init(*args, **kwargs)
        except (TypeError, AttributeError):
            pass
        self._event_publisher = EventPublisher(
            service_name="ml_model_registry_service",
            tenant_id=getattr(self, "tenant_id", None),
            user_id=getattr(self, "user_id", None),
        )

    def publish_model_linked(
        self,
        model_id: str,
        odh_model_id: str,
        asset_id: Optional[str] = None,
        contract_id: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish ml.model.linked event."""
        from django.utils import timezone
        return self._event_publisher.publish(
            event_type="ml.model.linked",
            data={
                "model_id": model_id,
                "odh_model_id": odh_model_id,
                "asset_id": asset_id,
                "contract_id": contract_id,
                "linked_at": timezone.now().isoformat(),
            },
            tags=["ml", "model", "linked"],
            **kwargs,
        )

    def publish_model_synced(
        self,
        model_id: str,
        odh_model_id: str,
        sync_status: str,
        **kwargs,
    ) -> str:
        """Publish ml.model.synced event."""
        from django.utils import timezone
        return self._event_publisher.publish(
            event_type="ml.model.synced",
            data={
                "model_id": model_id,
                "odh_model_id": odh_model_id,
                "sync_status": sync_status,
                "synced_at": timezone.now().isoformat(),
            },
            tags=["ml", "model", "synced"],
            **kwargs,
        )

    def publish_dataset_linked(
        self,
        model_id: str,
        dataset_id: str,
        role: str,
        **kwargs,
    ) -> str:
        """Publish ml.dataset.linked event."""
        from django.utils import timezone
        return self._event_publisher.publish(
            event_type="ml.dataset.linked",
            data={
                "model_id": model_id,
                "dataset_id": dataset_id,
                "role": role,
                "linked_at": timezone.now().isoformat(),
            },
            tags=["ml", "dataset", "linked"],
            **kwargs,
        )

    def publish_model_asset_created(
        self,
        model_id: str,
        asset_id: str,
        **kwargs,
    ) -> str:
        """Publish ml.model.asset.created event."""
        from django.utils import timezone
        return self._event_publisher.publish(
            event_type="ml.model.asset.created",
            data={
                "model_id": model_id,
                "asset_id": asset_id,
                "created_at": timezone.now().isoformat(),
            },
            tags=["ml", "model", "asset", "created"],
            **kwargs,
        )


class TransformationEventPublisher:
    """Event publisher mixin for Transformation Service."""

    def __init__(self, *args, **kwargs):
        try:
            parent_init = super().__init__
            if parent_init is not object.__init__:
                parent_init(*args, **kwargs)
        except (TypeError, AttributeError):
            pass
        self._event_publisher = EventPublisher(
            service_name="transformation_service",
            tenant_id=getattr(self, "tenant_id", None),
            user_id=getattr(self, "user_id", None),
        )

    def publish_pipeline_created(
        self, pipeline_id: str, name: str, **kwargs,
    ) -> str:
        from django.utils import timezone
        return self._event_publisher.publish(
            event_type="transformation.pipeline.created",
            data={
                "pipeline_id": pipeline_id,
                "name": name,
                "created_at": timezone.now().isoformat(),
            },
            tags=["transformation", "pipeline", "created"],
            **kwargs,
        )

    def publish_pipeline_executed(
        self,
        pipeline_id: str,
        execution_id: str,
        status: str,
        **kwargs,
    ) -> str:
        from django.utils import timezone
        return self._event_publisher.publish(
            event_type="transformation.pipeline.executed",
            data={
                "pipeline_id": pipeline_id,
                "execution_id": execution_id,
                "status": status,
                "executed_at": timezone.now().isoformat(),
            },
            tags=["transformation", "pipeline", "executed"],
            **kwargs,
        )

    def publish_pipeline_updated(
        self, pipeline_id: str, name: str, **kwargs,
    ) -> str:
        from django.utils import timezone
        return self._event_publisher.publish(
            event_type="transformation.pipeline.updated",
            data={
                "pipeline_id": pipeline_id,
                "name": name,
                "updated_at": timezone.now().isoformat(),
            },
            tags=["transformation", "pipeline", "updated"],
            **kwargs,
        )

    def publish_pipeline_deleted(
        self, pipeline_id: str, name: str, **kwargs,
    ) -> str:
        from django.utils import timezone
        return self._event_publisher.publish(
            event_type="transformation.pipeline.deleted",
            data={
                "pipeline_id": pipeline_id,
                "name": name,
                "deleted_at": timezone.now().isoformat(),
            },
            tags=["transformation", "pipeline", "deleted"],
            **kwargs,
        )

    def publish_pipeline_started(
        self, pipeline_id: str, execution_id: str, **kwargs,
    ) -> str:
        from django.utils import timezone
        return self._event_publisher.publish(
            event_type="transformation.pipeline.started",
            data={
                "pipeline_id": pipeline_id,
                "execution_id": execution_id,
                "started_at": timezone.now().isoformat(),
            },
            tags=["transformation", "pipeline", "started"],
            **kwargs,
        )

    def publish_pipeline_completed(
        self, pipeline_id: str, execution_id: str, **kwargs,
    ) -> str:
        from django.utils import timezone
        return self._event_publisher.publish(
            event_type="transformation.pipeline.completed",
            data={
                "pipeline_id": pipeline_id,
                "execution_id": execution_id,
                "completed_at": timezone.now().isoformat(),
            },
            tags=["transformation", "pipeline", "completed"],
            **kwargs,
        )

    def publish_pipeline_failed(
        self, pipeline_id: str, error: str, **kwargs,
    ) -> str:
        from django.utils import timezone
        return self._event_publisher.publish(
            event_type="transformation.pipeline.failed",
            data={
                "pipeline_id": pipeline_id,
                "error": error,
                "failed_at": timezone.now().isoformat(),
            },
            tags=["transformation", "pipeline", "failed"],
            **kwargs,
        )
