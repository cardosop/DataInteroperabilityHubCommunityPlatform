"""
Version Creation Workflow

Orchestrates dataset version creation process, including:
- Detect schema changes
- Calculate semantic version (major/minor/patch)
- Create version record
- Store version snapshot (optional)
- Update version history
- Calculate version diff
- Update lineage references
- Index for search
- Send notifications
- Audit logging
"""

from typing import Any, Dict, List, Optional

import structlog
from django.db import transaction
from django.utils import timezone

from hub.apps.audit.utils import create_audit_event
from hub.apps.datasets.business_rules import DatasetsBusinessRules
from hub.apps.datasets.models import Dataset, DatasetSnapshot
from hub.apps.datasets.schema_evolution import SchemaEvolutionTracker
from hub.apps.datasets.version_comparison import VersionComparisonService
from hub.apps.datasets.versioning import VersionHistoryManager
from hub.apps.orchestration.models import WorkflowInstance, WorkflowStatus
from hub.apps.orchestration.registry import WorkflowRegistry
from hub.apps.orchestration.workflow_engine import WorkflowEngine
from hub.apps.search.indexing import SearchIndexer

logger = structlog.get_logger(__name__)


class VersionCreationWorkflow:
    """
    Version creation workflow orchestrator.

    Orchestrates the complete dataset version creation process:
    1. Detect schema changes
    2. Calculate semantic version (major/minor/patch)
    3. Create version record
    4. Store version snapshot (optional)
    5. Update version history
    6. Calculate version diff
    7. Update lineage references
    8. Index for search
    9. Send notifications
    10. Audit logging
    """

    WORKFLOW_NAME = "version_creation"

    @classmethod
    def register_workflow(cls, registry: WorkflowRegistry) -> None:
        """
        Register the version creation workflow definition.

        Args:
            registry: WorkflowRegistry instance
        """
        workflow_dsl = {
            "version": "1.0.0",
            "dependencies": [],
            "steps": [
                {
                    "name": "detect_schema_changes",
                    "type": "task",
                    "task": "version_creation.detect_schema_changes",
                },
                {
                    "name": "calculate_semantic_version",
                    "type": "task",
                    "task": "version_creation.calculate_semantic_version",
                },
                {
                    "name": "create_version_record",
                    "type": "task",
                    "task": "version_creation.create_version_record",
                    "compensation": {
                        "type": "task",
                        "task": "version_creation.rollback_version_record",
                    },
                },
                {
                    "name": "store_version_snapshot",
                    "type": "task",
                    "task": "version_creation.store_version_snapshot",
                    "compensation": {
                        "type": "task",
                        "task": "version_creation.rollback_version_snapshot",
                    },
                },
                {
                    "name": "update_version_history",
                    "type": "task",
                    "task": "version_creation.update_version_history",
                },
                {
                    "name": "calculate_version_diff",
                    "type": "task",
                    "task": "version_creation.calculate_version_diff",
                },
                {
                    "name": "update_lineage_references",
                    "type": "task",
                    "task": "version_creation.update_lineage_references",
                },
                {
                    "name": "index_for_search",
                    "type": "task",
                    "task": "version_creation.index_for_search",
                    "compensation": {"type": "task", "task": "version_creation.rollback_indexing"},
                },
                {
                    "name": "send_notifications",
                    "type": "task",
                    "task": "version_creation.send_notifications",
                },
                {"name": "audit_logging", "type": "task", "task": "version_creation.audit_logging"},
            ],
            "compensation": {"enabled": True},
        }
        registry.register_workflow(cls.WORKFLOW_NAME, workflow_dsl)

    @classmethod
    def register_tasks(cls, engine: WorkflowEngine) -> None:
        """
        Register all workflow task functions.

        Args:
            engine: WorkflowEngine instance
        """
        engine.register_task(
            "version_creation.detect_schema_changes", cls._detect_schema_changes_task
        )
        engine.register_task(
            "version_creation.calculate_semantic_version", cls._calculate_semantic_version_task
        )
        engine.register_task(
            "version_creation.create_version_record", cls._create_version_record_task
        )
        engine.register_task(
            "version_creation.store_version_snapshot", cls._store_version_snapshot_task
        )
        engine.register_task(
            "version_creation.update_version_history", cls._update_version_history_task
        )
        engine.register_task(
            "version_creation.calculate_version_diff", cls._calculate_version_diff_task
        )
        engine.register_task(
            "version_creation.update_lineage_references", cls._update_lineage_references_task
        )
        engine.register_task("version_creation.index_for_search", cls._index_for_search_task)
        engine.register_task("version_creation.send_notifications", cls._send_notifications_task)
        engine.register_task("version_creation.audit_logging", cls._audit_logging_task)

        # Compensation tasks
        engine.register_task(
            "version_creation.rollback_version_record", cls._rollback_version_record_task
        )
        engine.register_task(
            "version_creation.rollback_version_snapshot", cls._rollback_version_snapshot_task
        )
        engine.register_task("version_creation.rollback_indexing", cls._rollback_indexing_task)

    @staticmethod
    def _detect_schema_changes_task(
        input_data: Dict[str, Any], instance: WorkflowInstance, step
    ) -> Dict[str, Any]:
        """
        Detect schema changes between parent version and new dataset.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with schema change detection results
        """
        dataset_id = input_data.get("dataset_id")
        parent_version_id = input_data.get("parent_version_id")

        if not dataset_id:
            raise ValueError("dataset_id is required")

        from hub.apps.tenants.models import Tenant

        tenant_id = input_data.get("tenant_id") or instance.tenant_id
        tenant = Tenant.objects.get(id=tenant_id)
        dataset = Dataset.objects.get(id=dataset_id, tenant=tenant)

        schema_changes = None
        schema_diff = None
        parent_version = None

        if parent_version_id:
            try:
                parent_version = Dataset.objects.get(id=parent_version_id, tenant=tenant)

                # Calculate schema diff
                schema_diff = SchemaEvolutionTracker.calculate_schema_diff(
                    parent_version.schema_json or {}, dataset.schema_json or {}
                )

                schema_changes = {
                    "has_changes": len(schema_diff.changes) > 0,
                    "compatibility_level": schema_diff.compatibility_level.value,
                    "change_summary": schema_diff.summary,
                    "breaking_changes": [
                        {
                            "change_type": c.change_type.value,
                            "field_name": c.field_name,
                            "description": c.description,
                            "breaking": c.breaking,
                        }
                        for c in schema_diff.changes
                        if c.breaking
                    ],
                    "non_breaking_changes": [
                        {
                            "change_type": c.change_type.value,
                            "field_name": c.field_name,
                            "description": c.description,
                            "breaking": c.breaking,
                        }
                        for c in schema_diff.changes
                        if not c.breaking
                    ],
                }

                logger.info(
                    "Schema changes detected",
                    workflow_instance_id=str(instance.id),
                    dataset_id=str(dataset.id),
                    parent_version_id=str(parent_version.id),
                    has_changes=schema_changes["has_changes"],
                    compatibility_level=schema_changes["compatibility_level"],
                    breaking_count=len(schema_changes["breaking_changes"]),
                    non_breaking_count=len(schema_changes["non_breaking_changes"]),
                )
            except Dataset.DoesNotExist:
                logger.warning(
                    "Parent version not found, treating as first version",
                    workflow_instance_id=str(instance.id),
                    dataset_id=str(dataset.id),
                    parent_version_id=parent_version_id,
                )
                schema_changes = {
                    "has_changes": False,
                    "compatibility_level": "FULLY_COMPATIBLE",
                    "change_summary": {},
                    "breaking_changes": [],
                    "non_breaking_changes": [],
                }
        else:
            # No parent version - this is the first version
            schema_changes = {
                "has_changes": False,
                "compatibility_level": "FULLY_COMPATIBLE",
                "change_summary": {},
                "breaking_changes": [],
                "non_breaking_changes": [],
            }

        # Convert schema_diff to serializable format if present
        schema_diff_serializable = None
        if schema_diff:
            schema_diff_serializable = {
                "compatibility_level": schema_diff.compatibility_level.value,
                "summary": schema_diff.summary,
                "changes": [
                    {
                        "change_type": change.change_type.value,
                        "field_name": change.field_name,
                        "old_value": change.old_value,
                        "new_value": change.new_value,
                        "description": change.description,
                        "breaking": change.breaking,
                    }
                    for change in schema_diff.changes
                ],
            }

        return {
            "schema_changes": schema_changes,
            "schema_diff": schema_diff_serializable,
            "parent_version_id": str(parent_version.id) if parent_version else None,
            "state": {
                "schema_changes": schema_changes,
                "parent_version_id": str(parent_version.id) if parent_version else None,
            },
        }

    @staticmethod
    def _calculate_semantic_version_task(
        input_data: Dict[str, Any], instance: WorkflowInstance, step
    ) -> Dict[str, Any]:
        """
        Calculate semantic version based on schema changes.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with calculated semantic version
        """
        dataset_id = input_data.get("dataset_id")
        parent_version_id = instance.state_data.get("parent_version_id")
        semantic_version_override = input_data.get("semantic_version")

        if not dataset_id:
            raise ValueError("dataset_id is required")

        from hub.apps.tenants.models import Tenant

        tenant_id = input_data.get("tenant_id") or instance.tenant_id
        tenant = Tenant.objects.get(id=tenant_id)
        dataset = Dataset.objects.get(id=dataset_id, tenant=tenant)

        # Use override if provided, otherwise infer from parent
        if semantic_version_override:
            semantic_version = semantic_version_override
            logger.info(
                "Using provided semantic version",
                workflow_instance_id=str(instance.id),
                dataset_id=str(dataset.id),
                semantic_version=semantic_version,
            )
        else:
            parent_version = None
            if parent_version_id:
                try:
                    parent_version = Dataset.objects.get(id=parent_version_id, tenant=tenant)
                except Dataset.DoesNotExist:
                    logger.warning(
                        "Parent version not found for semantic version calculation",
                        workflow_instance_id=str(instance.id),
                        parent_version_id=parent_version_id,
                    )

            # Infer semantic version using VersionHistoryManager
            semantic_version = VersionHistoryManager._infer_semantic_version(
                dataset, parent_version
            )

            logger.info(
                "Semantic version calculated",
                workflow_instance_id=str(instance.id),
                dataset_id=str(dataset.id),
                semantic_version=semantic_version,
                parent_semantic_version=parent_version.semantic_version if parent_version else None,
            )

        return {
            "semantic_version": semantic_version,
            "state": {"semantic_version": semantic_version},
        }

    @staticmethod
    @transaction.atomic
    def _create_version_record_task(
        input_data: Dict[str, Any], instance: WorkflowInstance, step
    ) -> Dict[str, Any]:
        """
        Create version record with version history tracking.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with version record details
        """
        dataset_id = input_data.get("dataset_id")
        parent_version_id = instance.state_data.get("parent_version_id")
        semantic_version = instance.state_data.get("semantic_version")
        version_tags = input_data.get("version_tags", [])
        snapshot_metadata = input_data.get("snapshot_metadata", {})
        is_current = input_data.get("is_current", True)

        if not dataset_id:
            raise ValueError("dataset_id is required")
        if not semantic_version:
            raise ValueError("semantic_version is required (from previous step)")

        from hub.apps.tenants.models import Tenant

        tenant_id = input_data.get("tenant_id") or instance.tenant_id
        tenant = Tenant.objects.get(id=tenant_id)
        dataset = Dataset.objects.get(id=dataset_id, tenant=tenant)

        parent_version = None
        if parent_version_id:
            try:
                parent_version = Dataset.objects.get(id=parent_version_id, tenant=tenant)
            except Dataset.DoesNotExist:
                logger.warning(
                    "Parent version not found, creating version without parent",
                    workflow_instance_id=str(instance.id),
                    dataset_id=str(dataset.id),
                    parent_version_id=parent_version_id,
                )

        # Validate dataset version creation using DatasetsBusinessRules
        datasets_rules = DatasetsBusinessRules(
            tenant_id=str(tenant_id) if tenant_id else None,
            user_id=str(instance.created_by_id) if instance.created_by_id else None,
        )

        # Validate dataset before version creation
        dataset_validation_result = datasets_rules.validate(
            dataset=dataset, tenant=tenant, user=instance.created_by, validation_type="version"
        )

        if not dataset_validation_result.is_valid:
            error_messages = dataset_validation_result.errors
            raise ValueError(
                f"Dataset version creation validation failed: {'; '.join(error_messages)}"
            )

        # Log validation warnings if any
        if dataset_validation_result.warnings:
            logger.warning(
                "Dataset version creation validation warnings",
                workflow_instance_id=str(instance.id),
                dataset_id=str(dataset.id),
                warnings=dataset_validation_result.warnings,
            )

        # Create version using VersionHistoryManager
        VersionHistoryManager.create_version(
            dataset=dataset,
            parent_version=parent_version,
            semantic_version=semantic_version,
            version_tags=version_tags,
            snapshot_metadata=snapshot_metadata,
            is_current=is_current,
        )

        # Reload dataset to get updated fields (avoid refresh_from_db in transaction)
        dataset = Dataset.objects.get(id=dataset.id, tenant=tenant)

        # Validate created version using DatasetsBusinessRules
        created_version_validation_result = datasets_rules.validate(
            dataset=dataset, tenant=tenant, user=instance.created_by, validation_type="version"
        )

        if not created_version_validation_result.is_valid:
            error_messages = created_version_validation_result.errors
            # Log errors but don't fail - version is already created
            logger.warning(
                "Dataset version validation errors after creation",
                workflow_instance_id=str(instance.id),
                dataset_id=str(dataset.id),
                errors=error_messages,
            )
        elif created_version_validation_result.warnings:
            logger.warning(
                "Dataset version validation warnings after creation",
                workflow_instance_id=str(instance.id),
                dataset_id=str(dataset.id),
                warnings=created_version_validation_result.warnings,
            )

        logger.info(
            "Version record created",
            workflow_instance_id=str(instance.id),
            dataset_id=str(dataset.id),
            semantic_version=semantic_version,
            version=dataset.version,
            version_hash=dataset.version_hash,
            is_current=is_current,
            parent_version_id=str(parent_version.id) if parent_version else None,
        )

        return {
            "version_record_created": True,
            "semantic_version": semantic_version,
            "version": dataset.version,
            "version_hash": dataset.version_hash,
            "state": {
                "version_record_created": True,
                "semantic_version": semantic_version,
                "version": dataset.version,
                "version_hash": dataset.version_hash,
            },
        }

    @staticmethod
    @transaction.atomic
    def _store_version_snapshot_task(
        input_data: Dict[str, Any], instance: WorkflowInstance, step
    ) -> Dict[str, Any]:
        """
        Store version snapshot (optional).

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with snapshot details
        """
        dataset_id = input_data.get("dataset_id")
        store_snapshot = input_data.get("store_snapshot", False)
        snapshot_type = input_data.get("snapshot_type", "FULL")

        if not dataset_id:
            raise ValueError("dataset_id is required")

        if not store_snapshot:
            logger.info(
                "Snapshot storage skipped (store_snapshot=False)",
                workflow_instance_id=str(instance.id),
                dataset_id=dataset_id,
            )
            return {
                "snapshot_stored": False,
                "reason": "store_snapshot is False",
                "state": {"snapshot_stored": False},
            }

        from hub.apps.tenants.models import Tenant
        from hub.apps.datasets.time_travel import TimeTravelQuery

        tenant_id = input_data.get("tenant_id") or instance.tenant_id
        tenant = Tenant.objects.get(id=tenant_id)
        dataset = Dataset.objects.get(id=dataset_id, tenant=tenant)

        # Route through TimeTravelQuery.create_snapshot so the
        # workflow inherits the same validation surface (Phase 260.6.B.R1
        # GAP-A): INCREMENTAL → NotImplementedError, unknown → ValueError.
        snapshot = TimeTravelQuery.create_snapshot(
            dataset, snapshot_type=snapshot_type
        )

        logger.info(
            "Version snapshot stored",
            workflow_instance_id=str(instance.id),
            dataset_id=str(dataset.id),
            snapshot_id=str(snapshot.id),
            snapshot_type=snapshot_type,
        )

        return {
            "snapshot_stored": True,
            "snapshot_id": str(snapshot.id),
            "snapshot_type": snapshot_type,
            "state": {"snapshot_stored": True, "snapshot_id": str(snapshot.id)},
        }

    @staticmethod
    def _update_version_history_task(
        input_data: Dict[str, Any], instance: WorkflowInstance, step
    ) -> Dict[str, Any]:
        """
        Update version history (track schema evolution).

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with version history update status
        """
        dataset_id = input_data.get("dataset_id")
        parent_version_id = instance.state_data.get("parent_version_id")

        if not dataset_id:
            raise ValueError("dataset_id is required")

        from hub.apps.tenants.models import Tenant

        tenant_id = input_data.get("tenant_id") or instance.tenant_id
        tenant = Tenant.objects.get(id=tenant_id)
        dataset = Dataset.objects.get(id=dataset_id, tenant=tenant)

        parent_version = None
        if parent_version_id:
            try:
                parent_version = Dataset.objects.get(id=parent_version_id, tenant=tenant)
            except Dataset.DoesNotExist:
                logger.warning(
                    "Parent version not found for schema evolution tracking",
                    workflow_instance_id=str(instance.id),
                    parent_version_id=parent_version_id,
                )

        # Track schema evolution (this creates SchemaVersion record)
        # Note: VersionHistoryManager.create_version() may have already created a SchemaVersion,
        # so we check if one exists first
        try:
            from hub.apps.datasets.models import SchemaVersion

            # Check if SchemaVersion already exists (created by VersionHistoryManager.create_version)
            schema_version = SchemaVersion.objects.filter(dataset=dataset).first()

            if schema_version:
                # SchemaVersion already exists, just log it
                logger.info(
                    "Version history already exists",
                    workflow_instance_id=str(instance.id),
                    dataset_id=str(dataset.id),
                    schema_version_id=str(schema_version.id),
                    compatibility_level=schema_version.compatibility_level,
                )
            else:
                # Create SchemaVersion if it doesn't exist
                schema_version = SchemaEvolutionTracker.track_schema_version(
                    dataset=dataset, parent_dataset=parent_version
                )

                logger.info(
                    "Version history created",
                    workflow_instance_id=str(instance.id),
                    dataset_id=str(dataset.id),
                    schema_version_id=str(schema_version.id),
                    compatibility_level=schema_version.compatibility_level,
                )

            return {
                "version_history_updated": True,
                "schema_version_id": str(schema_version.id),
                "compatibility_level": schema_version.compatibility_level,
                "state": {
                    "version_history_updated": True,
                    "schema_version_id": str(schema_version.id),
                },
            }
        except Exception as e:
            # Schema tracking is optional, don't fail workflow
            logger.warning(
                "Failed to update version history (non-critical)",
                workflow_instance_id=str(instance.id),
                dataset_id=str(dataset.id),
                error=str(e),
            )
            return {
                "version_history_updated": False,
                "error": str(e),
                "state": {"version_history_updated": False},
            }

    @staticmethod
    def _calculate_version_diff_task(
        input_data: Dict[str, Any], instance: WorkflowInstance, step
    ) -> Dict[str, Any]:
        """
        Calculate version diff between parent and new version.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with version diff details
        """
        dataset_id = input_data.get("dataset_id")
        parent_version_id = instance.state_data.get("parent_version_id")
        include_data_diff = input_data.get("include_data_diff", True)

        if not dataset_id:
            raise ValueError("dataset_id is required")

        from hub.apps.tenants.models import Tenant

        tenant_id = input_data.get("tenant_id") or instance.tenant_id
        tenant = Tenant.objects.get(id=tenant_id)
        dataset = Dataset.objects.get(id=dataset_id, tenant=tenant)

        if not parent_version_id:
            logger.info(
                "Version diff skipped (no parent version)",
                workflow_instance_id=str(instance.id),
                dataset_id=str(dataset.id),
            )
            return {
                "version_diff_calculated": False,
                "reason": "No parent version",
                "state": {"version_diff_calculated": False},
            }

        try:
            parent_version = Dataset.objects.get(id=parent_version_id, tenant=tenant)

            # Calculate version comparison
            comparison = VersionComparisonService.compare_versions(
                old_version=parent_version, new_version=dataset, include_data_diff=include_data_diff
            )

            # Store diff summary in state
            diff_summary = {
                "compatibility_level": comparison.schema_diff.compatibility_level.value,
                "change_summary": comparison.schema_diff.summary,
                "breaking_changes_count": sum(
                    1 for c in comparison.schema_diff.changes if c.breaking
                ),
                "non_breaking_changes_count": sum(
                    1 for c in comparison.schema_diff.changes if not c.breaking
                ),
            }

            if comparison.data_diff:
                diff_summary["row_count_diff"] = comparison.data_diff.row_count_diff
                diff_summary["row_count_percent_change"] = (
                    comparison.data_diff.row_count_percent_change
                )

            logger.info(
                "Version diff calculated",
                workflow_instance_id=str(instance.id),
                dataset_id=str(dataset.id),
                parent_version_id=str(parent_version.id),
                compatibility_level=diff_summary["compatibility_level"],
                breaking_changes=diff_summary["breaking_changes_count"],
            )

            return {
                "version_diff_calculated": True,
                "diff_summary": diff_summary,
                "state": {"version_diff_calculated": True, "diff_summary": diff_summary},
            }
        except Dataset.DoesNotExist:
            logger.warning(
                "Parent version not found for diff calculation",
                workflow_instance_id=str(instance.id),
                parent_version_id=parent_version_id,
            )
            return {
                "version_diff_calculated": False,
                "reason": "Parent version not found",
                "state": {"version_diff_calculated": False},
            }

    @staticmethod
    def _update_lineage_references_task(
        input_data: Dict[str, Any], instance: WorkflowInstance, step
    ) -> Dict[str, Any]:
        """
        Update lineage references for the new version.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with lineage update status
        """
        dataset_id = input_data.get("dataset_id")
        parent_version_id = instance.state_data.get("parent_version_id")

        if not dataset_id:
            raise ValueError("dataset_id is required")

        from hub.apps.tenants.models import Tenant

        tenant_id = input_data.get("tenant_id") or instance.tenant_id
        tenant = Tenant.objects.get(id=tenant_id)
        dataset = Dataset.objects.get(id=dataset_id, tenant=tenant)

        # Lineage references are typically stored in the asset or contract level
        # For now, we'll log that lineage should be updated at the asset level
        # This is a placeholder for future lineage tracking implementation

        logger.info(
            "Lineage references update logged",
            workflow_instance_id=str(instance.id),
            dataset_id=str(dataset.id),
            asset_id=str(dataset.asset.id) if dataset.asset else None,
            parent_version_id=parent_version_id,
        )

        # TODO: Implement actual lineage reference updates when lineage system is ready
        # This would involve:
        # 1. Updating asset-level lineage to reference new version
        # 2. Updating contract-level lineage if applicable
        # 3. Updating field-level lineage references

        return {"lineage_references_updated": True, "state": {"lineage_references_updated": True}}

    @staticmethod
    def _index_for_search_task(
        input_data: Dict[str, Any], instance: WorkflowInstance, step
    ) -> Dict[str, Any]:
        """
        Index dataset version for search.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with indexing results
        """
        dataset_id = input_data.get("dataset_id")

        if not dataset_id:
            raise ValueError("dataset_id is required")

        dataset = Dataset.objects.get(id=dataset_id)

        # Index dataset (this updates existing index or creates new one)
        try:
            search_index = SearchIndexer.index_dataset(dataset)

            logger.info(
                "Dataset version indexed for search",
                workflow_instance_id=str(instance.id),
                dataset_id=str(dataset.id),
                search_index_id=str(search_index.id),
            )

            return {
                "indexed": True,
                "search_index_id": str(search_index.id),
                "state": {"indexed": True, "search_index_id": str(search_index.id)},
            }
        except Exception as e:
            logger.error(
                "Failed to index dataset version (non-critical)",
                workflow_instance_id=str(instance.id),
                dataset_id=str(dataset.id),
                error=str(e),
                exc_info=True,
            )
            # Don't fail workflow on indexing errors - log and continue
            return {"indexed": False, "error": str(e), "state": {"indexed": False, "error": str(e)}}

    @staticmethod
    def _send_notifications_task(
        input_data: Dict[str, Any], instance: WorkflowInstance, step
    ) -> Dict[str, Any]:
        """
        Send notifications about version creation.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with notification results
        """
        dataset_id = input_data.get("dataset_id")
        send_notifications = input_data.get("send_notifications", True)

        if not dataset_id:
            logger.warning(
                "Notifications skipped (missing dataset_id)", workflow_instance_id=str(instance.id)
            )
            return {"notifications_sent": False, "reason": "Missing dataset_id"}

        if not send_notifications:
            logger.info(
                "Notifications disabled, skipping",
                workflow_instance_id=str(instance.id),
                dataset_id=dataset_id,
            )
            return {"notifications_sent": False, "reason": "send_notifications is False"}

        dataset = Dataset.objects.get(id=dataset_id)

        # Log notification (email template can be added later)
        try:
            logger.info(
                "Version creation notification logged",
                workflow_instance_id=str(instance.id),
                dataset_id=str(dataset.id),
                semantic_version=dataset.semantic_version,
                version=dataset.version,
                asset_id=str(dataset.asset.id) if dataset.asset else None,
            )

            # TODO: Implement actual notification sending when notification system is ready
            # This would involve:
            # 1. Getting notification recipients (asset owners, subscribers)
            # 2. Sending email notifications about new version
            # 3. Sending in-app notifications

            return {"notifications_sent": True, "notification_type": "logged"}
        except Exception as e:
            logger.error(
                "Failed to log version creation notification",
                workflow_instance_id=str(instance.id),
                dataset_id=str(dataset.id),
                error=str(e),
                exc_info=True,
            )
            # Don't fail workflow on notification errors
            return {"notifications_sent": False, "error": str(e)}

    @staticmethod
    def _audit_logging_task(
        input_data: Dict[str, Any], instance: WorkflowInstance, step
    ) -> Dict[str, Any]:
        """
        Create audit log entry for version creation.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with audit event ID
        """
        tenant_id = input_data.get("tenant_id") or instance.tenant_id
        dataset_id = input_data.get("dataset_id")
        triggered_by_id = input_data.get("triggered_by_id") or instance.created_by_id

        if not tenant_id:
            raise ValueError("tenant_id is required")
        if not dataset_id:
            raise ValueError("dataset_id is required")

        from django.contrib.auth import get_user_model

        from hub.apps.tenants.models import Tenant

        User = get_user_model()
        tenant = Tenant.objects.get(id=tenant_id)
        user = User.objects.get(id=triggered_by_id) if triggered_by_id else None

        dataset = Dataset.objects.get(id=dataset_id)

        # Get diff summary from state if available
        diff_summary = instance.state_data.get("diff_summary", {})

        # Create audit event
        audit_event = create_audit_event(
            resource_type="DATASET",
            action="VERSION_CREATED",
            actor_user=user,
            tenant=tenant,
            resource_id=str(dataset.id),
            details={
                "dataset_id": str(dataset.id),
                "version": dataset.version,
                "semantic_version": dataset.semantic_version,
                "version_hash": dataset.version_hash,
                "parent_version_id": (
                    str(dataset.parent_version.id) if dataset.parent_version else None
                ),
                "asset_id": str(dataset.asset.id) if dataset.asset else None,
                "compatibility_level": diff_summary.get("compatibility_level"),
                "breaking_changes_count": diff_summary.get("breaking_changes_count", 0),
                "workflow_instance_id": str(instance.id),
            },
        )

        logger.info(
            "Audit log created",
            workflow_instance_id=str(instance.id),
            dataset_id=str(dataset.id),
            audit_event_id=str(audit_event.id) if audit_event else None,
        )

        return {
            "audit_event_id": str(audit_event.id) if audit_event else None,
            "state": {"audit_event_id": str(audit_event.id) if audit_event else None},
        }

    # Compensation tasks

    @staticmethod
    @transaction.atomic
    def _rollback_version_record_task(
        input_data: Dict[str, Any], instance: WorkflowInstance, step
    ) -> Dict[str, Any]:
        """Rollback version record creation (revert version history fields)"""
        dataset_id = instance.state_data.get("dataset_id")

        if not dataset_id:
            return {"rolled_back": True}

        try:
            dataset = Dataset.objects.get(id=dataset_id)

            # Revert version history fields
            dataset.parent_version = None
            dataset.version_hash = None
            dataset.snapshot_metadata = {}
            dataset.is_current = False
            dataset.semantic_version = None
            dataset.version_tags = []
            dataset.save()

            logger.info(
                "Version record rolled back",
                workflow_instance_id=str(instance.id),
                dataset_id=dataset_id,
            )
            return {"rolled_back": True}
        except Dataset.DoesNotExist:
            logger.warning(
                "Dataset not found for rollback",
                workflow_instance_id=str(instance.id),
                dataset_id=dataset_id,
            )
            return {"rolled_back": True}
        except Exception as e:
            logger.error(
                "Failed to rollback version record",
                workflow_instance_id=str(instance.id),
                dataset_id=dataset_id,
                error=str(e),
                exc_info=True,
            )
            return {"rolled_back": False, "error": str(e)}

    @staticmethod
    @transaction.atomic
    def _rollback_version_snapshot_task(
        input_data: Dict[str, Any], instance: WorkflowInstance, step
    ) -> Dict[str, Any]:
        """Rollback version snapshot (delete snapshot)"""
        snapshot_id = instance.state_data.get("snapshot_id")

        if snapshot_id:
            try:
                snapshot = DatasetSnapshot.objects.get(id=snapshot_id)
                snapshot.delete()
                logger.info(
                    "Version snapshot rolled back (deleted)",
                    workflow_instance_id=str(instance.id),
                    snapshot_id=snapshot_id,
                )
            except DatasetSnapshot.DoesNotExist:
                logger.warning(
                    "Snapshot not found for rollback",
                    workflow_instance_id=str(instance.id),
                    snapshot_id=snapshot_id,
                )
            except Exception as e:
                logger.warning(
                    "Snapshot rollback failed",
                    workflow_instance_id=str(instance.id),
                    snapshot_id=snapshot_id,
                    error=str(e),
                )

        return {"rolled_back": True}

    @staticmethod
    @transaction.atomic
    def _rollback_indexing_task(
        input_data: Dict[str, Any], instance: WorkflowInstance, step
    ) -> Dict[str, Any]:
        """Rollback search indexing (delete search index)"""
        search_index_id = instance.state_data.get("search_index_id")

        if search_index_id:
            try:
                from hub.apps.search.models import SearchIndex

                search_index = SearchIndex.objects.get(id=search_index_id)
                search_index.delete()
                logger.info(
                    "Search index rolled back (deleted)",
                    workflow_instance_id=str(instance.id),
                    search_index_id=search_index_id,
                )
            except Exception as e:
                logger.warning(
                    "Search index rollback failed",
                    workflow_instance_id=str(instance.id),
                    search_index_id=search_index_id,
                    error=str(e),
                )

        return {"rolled_back": True}

    @classmethod
    @transaction.atomic
    def execute(
        cls,
        tenant_id: str,
        dataset_id: str,
        parent_version_id: Optional[str] = None,
        semantic_version: Optional[str] = None,
        version_tags: Optional[List[str]] = None,
        snapshot_metadata: Optional[Dict[str, Any]] = None,
        store_snapshot: bool = False,
        snapshot_type: str = "FULL",
        is_current: bool = True,
        send_notifications: bool = True,
        include_data_diff: bool = True,
        triggered_by_id: Optional[str] = None,
        engine: Optional[WorkflowEngine] = None,
        registry: Optional[WorkflowRegistry] = None,
    ) -> Dict[str, Any]:
        """
        Execute version creation workflow.

        Args:
            tenant_id: Tenant ID
            dataset_id: Dataset ID to create version for
            parent_version_id: Optional parent version ID
            semantic_version: Optional semantic version override
            version_tags: Optional list of version tags
            snapshot_metadata: Optional snapshot metadata
            store_snapshot: Whether to store version snapshot
            snapshot_type: Snapshot type (FULL, SCHEMA_ONLY, METADATA_ONLY)
            is_current: Whether this is the current version
            send_notifications: Whether to send notifications
            include_data_diff: Whether to include data diff in comparison
            triggered_by_id: User ID who triggered the creation (optional)
            engine: Optional WorkflowEngine instance
            registry: Optional WorkflowRegistry instance

        Returns:
            Workflow execution result dictionary

        Raises:
            ValueError: If workflow execution fails
        """
        # Create engine and registry if not provided
        if engine is None:
            engine = WorkflowEngine()
            cls.register_tasks(engine)

        if registry is None:
            registry = WorkflowRegistry()
            cls.register_workflow(registry)

        # Prepare workflow input
        workflow_input = {
            "tenant_id": tenant_id,
            "dataset_id": dataset_id,
            "parent_version_id": parent_version_id,
            "semantic_version": semantic_version,
            "version_tags": version_tags or [],
            "snapshot_metadata": snapshot_metadata or {},
            "store_snapshot": store_snapshot,
            "snapshot_type": snapshot_type,
            "is_current": is_current,
            "send_notifications": send_notifications,
            "include_data_diff": include_data_diff,
            "triggered_by_id": triggered_by_id,
        }

        # Create workflow instance
        workflow_instance = engine.create_instance(
            workflow_name=cls.WORKFLOW_NAME,
            input_data=workflow_input,
            tenant_id=tenant_id,
            created_by_id=triggered_by_id,
        )

        # Initialize state_data from input_data
        if not workflow_instance.state_data:
            workflow_instance.state_data = workflow_input.copy()
            workflow_instance.save(update_fields=["state_data"])

        # Start and execute workflow
        workflow_instance = engine.start_instance(str(workflow_instance.id))
        workflow_instance = engine.execute_instance(str(workflow_instance.id))

        # Check workflow status
        if workflow_instance.status == WorkflowStatus.COMPLETED:
            logger.info(
                "Version creation workflow completed",
                workflow_instance_id=str(workflow_instance.id),
                tenant_id=tenant_id,
                dataset_id=dataset_id,
            )
            return {
                "success": True,
                "workflow_instance_id": str(workflow_instance.id),
                "dataset_id": dataset_id,
                "semantic_version": workflow_instance.state_data.get("semantic_version"),
                "version": workflow_instance.state_data.get("version"),
                "output_data": workflow_instance.output_data,
            }
        else:
            error_message = workflow_instance.error_message or "Workflow execution failed"
            logger.error(
                "Version creation workflow failed",
                workflow_instance_id=str(workflow_instance.id),
                tenant_id=tenant_id,
                dataset_id=dataset_id,
                error=error_message,
            )
            raise ValueError(f"Version creation workflow failed: {error_message}")
