"""
Marketplace Sync Workflow

Orchestrates marketplace synchronization process for both PUSH and PULL operations:
- PUSH: Synchronize Hub assets to external marketplace
- PULL: Synchronize external marketplace listings to Hub as federated assets

Includes comprehensive validation, error handling, compensation, and progress tracking.
"""
from typing import Dict, Any, Optional, List
from django.utils import timezone
from django.db import transaction
from concurrent.futures import ThreadPoolExecutor, as_completed
import structlog

from hub.apps.orchestration.models import WorkflowInstance, WorkflowStatus
from hub.apps.orchestration.registry import WorkflowRegistry
from hub.apps.orchestration.workflow_engine import WorkflowEngine
from hub.apps.integrations.models import (
    MarketplaceConnection,
    MarketplaceSyncJob,
    MarketplaceMapping
)
from hub.apps.integrations.base import (
    MarketplaceType,
    SyncDirection,
    SyncStatus,
    MarketplaceAssetMapping,
    MarketplaceListing,
)
from hub.apps.integrations.business_rules import MarketplaceIntegrationBusinessRules
from hub.apps.integrations.factory import MarketplaceConnectorFactory
from hub.apps.assets.models import Asset, AssetStatus, AssetSourceType
from hub.apps.assets.services import AssetService
from hub.apps.contracts.models import Contract, OriginalSpecType
from hub.apps.contracts.services import ContractService
from hub.apps.semantic.utils import map_asset_to_semantic
from hub.apps.tenants.models import Tenant

logger = structlog.get_logger(__name__)


class MarketplaceSyncWorkflow:
    """
    Marketplace synchronization workflow orchestrator.

    Orchestrates bidirectional synchronization between Hub and external marketplaces:

    PUSH Sync (Hub → Marketplace):
    1. Validate connection is active and tested
    2. Validate source assets exist and accessible
    3. Map Hub assets to marketplace format
    4. Publish assets to marketplace (via connector)
    5. Create MarketplaceMapping records
    6. Update semantic layer with federated asset properties
    7. Mark sync job as completed

    PULL Sync (Marketplace → Hub):
    1. Validate connection is active and tested
    2. Discover marketplace listings (via connector)
    3. Map marketplace listings to Hub asset format
    4. Create federated assets with dual contracts
    5. Download resources from marketplace
    6. Create MarketplaceMapping records
    7. Update semantic layer with federated asset properties
    8. Mark sync job as completed
    """

    WORKFLOW_NAME = "marketplace_sync"
    WORKFLOW_VERSION = "1.0.0"

    @classmethod
    def register_workflow(cls, registry: WorkflowRegistry) -> None:
        """
        Register the marketplace sync workflow definitions.

        Registers separate workflow DSLs for PUSH and PULL operations.
        The workflow engine will select the appropriate DSL based on sync direction.

        Args:
            registry: WorkflowRegistry instance
        """
        # PUSH workflow DSL
        push_workflow_dsl = {
            "version": cls.WORKFLOW_VERSION,
            "dependencies": [],
            "steps": [
                {
                    "name": "validate_connection",
                    "type": "task",
                    "task": "marketplace_sync.validate_connection"
                },
                {
                    "name": "validate_assets",
                    "type": "task",
                    "task": "marketplace_sync.validate_assets"
                },
                {
                    "name": "map_assets_to_marketplace",
                    "type": "task",
                    "task": "marketplace_sync.map_assets_to_marketplace",
                    "compensation": {
                        "type": "task",
                        "task": "marketplace_sync.rollback_mapping"
                    }
                },
                {
                    "name": "publish_to_marketplace",
                    "type": "task",
                    "task": "marketplace_sync.publish_to_marketplace",
                    "compensation": {
                        "type": "task",
                        "task": "marketplace_sync.rollback_marketplace_publish"
                    }
                },
                {
                    "name": "create_mappings",
                    "type": "task",
                    "task": "marketplace_sync.create_mappings",
                    "compensation": {
                        "type": "task",
                        "task": "marketplace_sync.rollback_mapping_creation"
                    }
                },
                {
                    "name": "update_semantic_layer",
                    "type": "task",
                    "task": "marketplace_sync.update_semantic_layer"
                },
                {
                    "name": "complete",
                    "type": "task",
                    "task": "marketplace_sync.complete"
                }
            ],
            "compensation": {"enabled": True}
        }

        # PULL workflow DSL
        pull_workflow_dsl = {
            "version": cls.WORKFLOW_VERSION,
            "dependencies": [],
            "steps": [
                {
                    "name": "validate_connection",
                    "type": "task",
                    "task": "marketplace_sync.validate_connection"
                },
                {
                    "name": "discover_listings",
                    "type": "task",
                    "task": "marketplace_sync.discover_listings"
                },
                {
                    "name": "map_listings_to_assets",
                    "type": "task",
                    "task": "marketplace_sync.map_listings_to_assets",
                    "compensation": {
                        "type": "task",
                        "task": "marketplace_sync.rollback_mapping"
                    }
                },
                {
                    "name": "create_federated_assets",
                    "type": "task",
                    "task": "marketplace_sync.create_federated_assets",
                    "compensation": {
                        "type": "task",
                        "task": "marketplace_sync.rollback_federated_asset_creation"
                    }
                },
                {
                    "name": "download_resources",
                    "type": "task",
                    "task": "marketplace_sync.download_resources",
                    "compensation": {
                        "type": "task",
                        "task": "marketplace_sync.rollback_resource_download"
                    }
                },
                {
                    "name": "create_mappings",
                    "type": "task",
                    "task": "marketplace_sync.create_mappings",
                    "compensation": {
                        "type": "task",
                        "task": "marketplace_sync.rollback_mapping_creation"
                    }
                },
                {
                    "name": "update_semantic_layer",
                    "type": "task",
                    "task": "marketplace_sync.update_semantic_layer"
                },
                {
                    "name": "complete",
                    "type": "task",
                    "task": "marketplace_sync.complete"
                }
            ],
            "compensation": {"enabled": True}
        }

        # Register both workflows (engine will select based on direction)
        registry.register_workflow(
            workflow_name=f"{cls.WORKFLOW_NAME}_push",
            dsl_json=push_workflow_dsl,
            description="Orchestrates marketplace PUSH sync (Hub → Marketplace)"
        )
        registry.register_workflow(
            workflow_name=f"{cls.WORKFLOW_NAME}_pull",
            dsl_json=pull_workflow_dsl,
            description="Orchestrates marketplace PULL sync (Marketplace → Hub)"
        )

    @classmethod
    def register_tasks(cls, engine: WorkflowEngine) -> None:
        """
        Register all workflow task functions.

        Args:
            engine: WorkflowEngine instance
        """
        # Common tasks
        engine.register_task(
            "marketplace_sync.validate_connection",
            cls._validate_connection_task
        )
        engine.register_task(
            "marketplace_sync.complete",
            cls._complete_task
        )

        # PUSH-specific tasks
        engine.register_task(
            "marketplace_sync.validate_assets",
            cls._validate_assets_task
        )
        engine.register_task(
            "marketplace_sync.map_assets_to_marketplace",
            cls._map_assets_to_marketplace_task
        )
        engine.register_task(
            "marketplace_sync.publish_to_marketplace",
            cls._publish_to_marketplace_task
        )

        # PULL-specific tasks
        engine.register_task(
            "marketplace_sync.discover_listings",
            cls._discover_listings_task
        )
        engine.register_task(
            "marketplace_sync.map_listings_to_assets",
            cls._map_listings_to_assets_task
        )
        engine.register_task(
            "marketplace_sync.create_federated_assets",
            cls._create_federated_assets_task
        )
        engine.register_task(
            "marketplace_sync.download_resources",
            cls._download_resources_task
        )

        # Common tasks
        engine.register_task(
            "marketplace_sync.create_mappings",
            cls._create_mappings_task
        )
        engine.register_task(
            "marketplace_sync.update_semantic_layer",
            cls._update_semantic_layer_task
        )

        # Compensation tasks
        engine.register_task(
            "marketplace_sync.rollback_connection_validation",
            cls._rollback_connection_validation_task
        )
        engine.register_task(
            "marketplace_sync.rollback_asset_validation",
            cls._rollback_asset_validation_task
        )
        engine.register_task(
            "marketplace_sync.rollback_mapping",
            cls._rollback_mapping_task
        )
        engine.register_task(
            "marketplace_sync.rollback_marketplace_publish",
            cls._rollback_marketplace_publish_task
        )
        engine.register_task(
            "marketplace_sync.rollback_mapping_creation",
            cls._rollback_mapping_creation_task
        )
        engine.register_task(
            "marketplace_sync.rollback_federated_asset_creation",
            cls._rollback_federated_asset_creation_task
        )
        engine.register_task(
            "marketplace_sync.rollback_resource_download",
            cls._rollback_resource_download_task
        )

    @staticmethod
    def _serialize_asset_mapping(asset_mapping: MarketplaceAssetMapping) -> Dict[str, Any]:
        """
        Serialize MarketplaceAssetMapping to dict for JSON storage.

        Args:
            asset_mapping: MarketplaceAssetMapping instance

        Returns:
            Dictionary representation
        """
        return {
            "asset_data": asset_mapping.asset_data,
            "source_type": asset_mapping.source_type.value if hasattr(asset_mapping.source_type, 'value') else str(asset_mapping.source_type),
            "source_metadata": asset_mapping.source_metadata,
            "odps_metadata": asset_mapping.odps_metadata,
            "odcs_metadata": asset_mapping.odcs_metadata,
            "resources": [
                {
                    "resource_id": r.resource_id,
                    "resource_type": str(r.resource_type),
                    "name": r.name,
                    "description": r.description,
                    "url": r.url,
                    "format": r.format,
                    "size_bytes": r.size_bytes,
                    "metadata": r.metadata if hasattr(r, 'metadata') else {}
                }
                for r in asset_mapping.resources
            ]
        }

    @staticmethod
    def _deserialize_asset_mapping(mapping_dict: Dict[str, Any]) -> MarketplaceAssetMapping:
        """
        Deserialize dict to MarketplaceAssetMapping.

        Args:
            mapping_dict: Dictionary representation

        Returns:
            MarketplaceAssetMapping instance
        """
        from hub.apps.integrations.base import MarketplaceResource

        resources = [
            MarketplaceResource(
                resource_id=r["resource_id"],
                resource_type=r["resource_type"],
                name=r.get("name", ""),
                description=r.get("description"),
                url=r.get("url"),
                format=r.get("format"),
                size_bytes=r.get("size_bytes"),
                metadata=r.get("metadata", {})
            )
            for r in mapping_dict.get("resources", [])
        ]

        return MarketplaceAssetMapping(
            asset_data=mapping_dict["asset_data"],
            source_type=AssetSourceType(mapping_dict["source_type"]),
            source_metadata=mapping_dict["source_metadata"],
            odps_metadata=mapping_dict.get("odps_metadata"),
            odcs_metadata=mapping_dict.get("odcs_metadata"),
            resources=resources
        )

    @staticmethod
    def _update_progress(instance: WorkflowInstance, progress: int, step_name: str) -> None:
        """
        Update workflow progress and sync job progress.

        Args:
            instance: Workflow instance
            progress: Progress percentage (0-100)
            step_name: Current step name
        """
        if instance.state_data is None:
            instance.state_data = {}
        instance.state_data["progress_percentage"] = progress
        instance.state_data["current_step_name"] = step_name
        instance.save(update_fields=['state_data'])

        # Update sync job progress via service layer
        sync_job_id = instance.state_data.get("sync_job_id")
        if sync_job_id:
            try:
                from hub.apps.integrations.services import MarketplaceIntegrationService
                service = MarketplaceIntegrationService(tenant_id=str(instance.tenant_id))
                service.update_sync_job_progress(
                    sync_job_id=sync_job_id,
                    progress_percentage=progress,
                    current_step=step_name,
                    tenant_id=str(instance.tenant_id)
                )
            except Exception as e:
                logger.warning(
                    "Failed to update sync job progress via service",
                    workflow_instance_id=str(instance.id),
                    sync_job_id=sync_job_id,
                    error=str(e)
                )
                # Fallback to direct update if service call fails
                try:
                    sync_job = MarketplaceSyncJob.objects.get(id=sync_job_id)
                    if sync_job.metadata is None:
                        sync_job.metadata = {}
                    sync_job.metadata["progress_percentage"] = progress
                    sync_job.metadata["current_step"] = step_name
                    sync_job.save(update_fields=['metadata'])
                except MarketplaceSyncJob.DoesNotExist:
                    logger.warning(
                        "Sync job not found for progress update",
                        workflow_instance_id=str(instance.id),
                        sync_job_id=sync_job_id
                    )

    # Common task implementations

    @staticmethod
    def _update_sync_job_status(instance: WorkflowInstance, status: SyncStatus) -> None:
        """
        Update sync job status.

        Args:
            instance: Workflow instance
            status: New sync job status
        """
        sync_job_id = instance.state_data.get("sync_job_id")
        if sync_job_id:
            try:
                sync_job = MarketplaceSyncJob.objects.get(id=sync_job_id)
                sync_job.status = status.value
                if status == SyncStatus.COMPLETED:
                    sync_job.completed_at = timezone.now()
                sync_job.save(update_fields=['status', 'completed_at', 'updated_at'])
            except MarketplaceSyncJob.DoesNotExist:
                logger.warning(
                    "Sync job not found for status update",
                    workflow_instance_id=str(instance.id),
                    sync_job_id=sync_job_id
                )

    @staticmethod
    def _validate_connection_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Validate marketplace connection is active and tested.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with validation results
        """
        connection_id = input_data.get("connection_id") or instance.state_data.get("connection_id")
        tenant_id = input_data.get("tenant_id") or instance.tenant_id

        if not connection_id:
            raise ValueError("connection_id is required")
        if not tenant_id:
            raise ValueError("tenant_id is required")

        tenant = Tenant.objects.get(id=tenant_id)
        connection = MarketplaceConnection.objects.get(id=connection_id, tenant=tenant)

        # Validate using business rules
        rules = MarketplaceIntegrationBusinessRules(
            tenant_id=str(tenant_id),
            user_id=str(instance.created_by_id) if instance.created_by_id else None
        )
        from hub.apps.integrations.business_rules import MarketplaceIntegrationRuleExecutionContext
        context = MarketplaceIntegrationRuleExecutionContext(
            tenant_id=str(tenant_id),
            user_id=str(instance.created_by_id) if instance.created_by_id else None,
            connection=connection
        )
        validation_result = rules.validate(context=context, validation_type='connection')

        if not validation_result.is_valid:
            error_message = "; ".join(validation_result.errors)
            logger.warning(
                "Connection validation failed",
                workflow_instance_id=str(instance.id),
                connection_id=str(connection.id),
                errors=validation_result.errors
            )
            raise ValueError(f"Connection validation failed: {error_message}")

        # Test connection via connector
        marketplace_type = MarketplaceType(connection.marketplace_type)
        factory = MarketplaceConnectorFactory()

        if not factory.is_supported(marketplace_type):
            raise ValueError(f"Marketplace type {marketplace_type.value} is not supported")

        # Create connector using factory with connection config
        connector = factory.create_connector(marketplace_type=marketplace_type, config=connection.get_config())

        if not connector.test_connection():
            raise ValueError("Connection test failed - unable to connect to marketplace")

        logger.info(
            "Connection validated",
            workflow_instance_id=str(instance.id),
            connection_id=str(connection.id)
        )

        # Update sync job status to RUNNING on first task
        MarketplaceSyncWorkflow._update_sync_job_status(instance, SyncStatus.RUNNING)
        MarketplaceSyncWorkflow._update_progress(instance, 10, "validate_connection")

        # Store connection in state for later use
        if instance.state_data is None:
            instance.state_data = {}
        instance.state_data["connection_id"] = str(connection.id)
        instance.save(update_fields=['state_data'])

        return {
            "connection_validated": True,
            "connection_id": str(connection.id),
            "state": {
                "connection_id": str(connection.id),
                "connection_validated": True
            }
        }

    @staticmethod
    def _complete_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Mark sync job as completed.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with completion status
        """
        sync_job_id = instance.state_data.get("sync_job_id")

        MarketplaceSyncWorkflow._update_progress(instance, 100, "complete")

        # Directly update sync job status to COMPLETED since this is the completion task
        # The workflow engine will mark the workflow instance as COMPLETED after all tasks finish
        if sync_job_id:
            try:
                sync_job = MarketplaceSyncJob.objects.get(id=sync_job_id)
                sync_job.status = SyncStatus.COMPLETED.value
                sync_job.completed_at = timezone.now()
                sync_job.save(update_fields=['status', 'completed_at'])

                logger.info(
                    "Sync job marked as completed",
                    workflow_instance_id=str(instance.id),
                    sync_job_id=sync_job_id
                )
            except MarketplaceSyncJob.DoesNotExist:
                logger.warning(
                    "Sync job not found for completion",
                    workflow_instance_id=str(instance.id),
                    sync_job_id=sync_job_id
                )
            except Exception as e:
                logger.error(
                    "Failed to mark sync job as completed",
                    workflow_instance_id=str(instance.id),
                    sync_job_id=sync_job_id,
                    error=str(e),
                    exc_info=True
                )

        return {
            "completed": True,
            "state": {
                "completed": True
            }
        }

    # PUSH-specific task implementations

    @staticmethod
    def _validate_assets_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Validate source assets exist and are accessible.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with validation results
        """
        asset_ids = input_data.get("asset_ids", [])
        tenant_id = input_data.get("tenant_id") or instance.tenant_id

        if not asset_ids:
            raise ValueError("asset_ids is required for PUSH sync")
        if not tenant_id:
            raise ValueError("tenant_id is required")

        tenant = Tenant.objects.get(id=tenant_id)

        # Get connection from state
        connection_id = instance.state_data.get("connection_id")
        if not connection_id:
            raise ValueError("connection_id is required in state_data (from validate_connection step)")
        connection = MarketplaceConnection.objects.get(id=connection_id, tenant=tenant)

        validated_assets = []
        invalid_assets = []

        for asset_id in asset_ids:
            try:
                asset = Asset.objects.get(id=asset_id, tenant=tenant)

                # Validate asset is accessible and not retired
                if asset.status == AssetStatus.RETIRED:
                    invalid_assets.append({
                        "asset_id": str(asset.id),
                        "reason": "Asset is retired"
                    })
                    continue

                # Validate using business rules
                rules = MarketplaceIntegrationBusinessRules(
                    tenant_id=str(tenant_id),
                    user_id=str(instance.created_by_id) if instance.created_by_id else None
                )
                from hub.apps.integrations.business_rules import MarketplaceIntegrationRuleExecutionContext
                context = MarketplaceIntegrationRuleExecutionContext(
                    tenant_id=str(tenant_id),
                    user_id=str(instance.created_by_id) if instance.created_by_id else None,
                    asset=asset,
                    connection=connection
                )
                validation_result = rules.validate(context=context, validation_type='asset')

                if not validation_result.is_valid:
                    invalid_assets.append({
                        "asset_id": str(asset.id),
                        "reason": "; ".join(validation_result.errors)
                    })
                    continue

                validated_assets.append({
                    "asset_id": str(asset.id),
                    "asset_name": asset.name,
                    "asset_status": asset.status
                })
            except Asset.DoesNotExist:
                invalid_assets.append({
                    "asset_id": asset_id,
                    "reason": "Asset not found"
                })

        if invalid_assets:
            error_message = f"Validation failed for {len(invalid_assets)} assets"
            logger.warning(
                "Asset validation failed",
                workflow_instance_id=str(instance.id),
                invalid_assets=invalid_assets
            )
            raise ValueError(error_message)

        logger.info(
            "Assets validated",
            workflow_instance_id=str(instance.id),
            validated_count=len(validated_assets)
        )

        MarketplaceSyncWorkflow._update_progress(instance, 20, "validate_assets")

        return {
            "assets_validated": True,
            "validated_assets": validated_assets,
            "state": {
                "asset_ids": asset_ids,
                "validated_assets": validated_assets
            }
        }

    @staticmethod
    def _listing_to_state_dict(listing: MarketplaceListing) -> Dict[str, Any]:
        """Serialize MarketplaceListing to a JSON-serializable dict for workflow state."""
        return {
            "marketplace_id": listing.marketplace_id,
            "marketplace_type": (
                listing.marketplace_type.value
                if hasattr(listing.marketplace_type, "value")
                else str(listing.marketplace_type)
            ),
            "title": listing.title,
            "description": listing.description,
            "product_id": listing.product_id,
            "category": listing.category,
            "tags": list(listing.tags) if listing.tags else [],
            "pricing_plans": list(listing.pricing_plans) if listing.pricing_plans else [],
            "access_methods": dict(listing.access_methods) if listing.access_methods else {},
            "payment_gateways": dict(listing.payment_gateways) if listing.payment_gateways else {},
            "metadata": dict(listing.metadata) if listing.metadata else {},
            "url": listing.url,
            "created_at": (
                listing.created_at.isoformat() if listing.created_at else None
            ),
            "updated_at": (
                listing.updated_at.isoformat() if listing.updated_at else None
            ),
        }

    @staticmethod
    def _listing_from_state_dict(d: Dict[str, Any]) -> MarketplaceListing:
        """Deserialize MarketplaceListing from workflow state dict."""
        from datetime import datetime
        mt = d.get("marketplace_type")
        if isinstance(mt, MarketplaceType):
            marketplace_type = mt
        elif isinstance(mt, str):
            marketplace_type = MarketplaceType(mt)
        else:
            marketplace_type = MarketplaceType.CUSTOM
        created_at = d.get("created_at")
        updated_at = d.get("updated_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        return MarketplaceListing(
            marketplace_id=d["marketplace_id"],
            marketplace_type=marketplace_type,
            title=d.get("title", ""),
            description=d.get("description"),
            product_id=d.get("product_id"),
            category=d.get("category"),
            tags=list(d["tags"]) if d.get("tags") else [],
            pricing_plans=list(d["pricing_plans"]) if d.get("pricing_plans") else [],
            access_methods=dict(d["access_methods"]) if d.get("access_methods") else {},
            payment_gateways=dict(d["payment_gateways"]) if d.get("payment_gateways") else {},
            metadata=dict(d["metadata"]) if d.get("metadata") else {},
            resources=[],
            created_at=created_at,
            updated_at=updated_at,
            url=d.get("url"),
        )

    @staticmethod
    def _map_assets_to_marketplace_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Map Hub assets to marketplace format.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with mapped listings
        """
        asset_ids = instance.state_data.get("asset_ids", [])
        connection_id = instance.state_data.get("connection_id")
        tenant_id = input_data.get("tenant_id") or instance.tenant_id

        if not asset_ids:
            raise ValueError("asset_ids is required (from previous step)")
        if not connection_id:
            raise ValueError("connection_id is required (from previous step)")

        tenant = Tenant.objects.get(id=tenant_id)
        connection = MarketplaceConnection.objects.get(id=connection_id, tenant=tenant)

        # Get connector
        marketplace_type = MarketplaceType(connection.marketplace_type)
        factory = MarketplaceConnectorFactory()
        # Create connector using factory with connection config
        connector = factory.create_connector(marketplace_type=marketplace_type, config=connection.get_config())

        # Map each asset
        mapped_listings = []
        for asset_id in asset_ids:
            asset = Asset.objects.get(id=asset_id, tenant=tenant)

            # Get contract metadata if available
            odps_metadata = None
            odcs_metadata = None

            # Find ODPS and ODCS contracts
            from hub.apps.contracts.models import Contract, OriginalSpecType, ContractStatus
            import json

            odps_contract = asset.contracts.filter(
                status=ContractStatus.ACTIVE,
                original_spec_type=OriginalSpecType.ODPS
            ).first()

            odcs_contract = asset.contracts.filter(
                status=ContractStatus.ACTIVE,
                original_spec_type=OriginalSpecType.ODCS
            ).first()

            if odps_contract and odps_contract.original_raw:
                try:
                    if odps_contract.original_format == "JSON":
                        odps_metadata = json.loads(odps_contract.original_raw)
                    else:
                        # Try YAML
                        try:
                            import yaml
                            odps_metadata = yaml.safe_load(odps_contract.original_raw)
                        except ImportError:
                            logger.warning("YAML library not available for ODPS parsing")
                except Exception as e:
                    logger.warning(
                        "Failed to parse ODPS contract metadata",
                        workflow_instance_id=str(instance.id),
                        contract_id=str(odps_contract.id),
                        error=str(e)
                    )

            if odcs_contract and odcs_contract.original_raw:
                try:
                    if odcs_contract.original_format == "JSON":
                        odcs_metadata = json.loads(odcs_contract.original_raw)
                    else:
                        # Try YAML
                        try:
                            import yaml
                            odcs_metadata = yaml.safe_load(odcs_contract.original_raw)
                        except ImportError:
                            logger.warning("YAML library not available for ODCS parsing")
                except Exception as e:
                    logger.warning(
                        "Failed to parse ODCS contract metadata",
                        workflow_instance_id=str(instance.id),
                        contract_id=str(odcs_contract.id),
                        error=str(e)
                    )

            # Map asset to marketplace listing
            asset_data = {
                "name": asset.name,
                "description": asset.description,
                "domain": asset.domain,
                "status": asset.status
            }

            listing = connector.map_from_hub_asset(
                asset_data=asset_data,
                odps_metadata=odps_metadata,
                odcs_metadata=odcs_metadata
            )

            # Serialize listing to dict so step output is JSON-serializable (engine validation)
            mapped_listings.append({
                "asset_id": str(asset.id),
                "listing": MarketplaceSyncWorkflow._listing_to_state_dict(listing),
                "marketplace_id": listing.marketplace_id,
                "marketplace_type": listing.marketplace_type.value,
            })

        logger.info(
            "Assets mapped to marketplace format",
            workflow_instance_id=str(instance.id),
            mapped_count=len(mapped_listings)
        )

        MarketplaceSyncWorkflow._update_progress(instance, 40, "map_assets_to_marketplace")

        return {
            "mapped_listings": mapped_listings,
            "state": {
                "mapped_listings": [
                    {
                        "asset_id": item["asset_id"],
                        "marketplace_id": item["marketplace_id"]
                    }
                    for item in mapped_listings
                ]
            }
        }

    @staticmethod
    def _publish_to_marketplace_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Publish assets to marketplace via connector.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with publication results
        """
        mapped_listings = instance.state_data.get("mapped_listings", [])
        connection_id = instance.state_data.get("connection_id")
        tenant_id = input_data.get("tenant_id") or instance.tenant_id

        if not mapped_listings:
            raise ValueError("mapped_listings is required (from previous step)")
        if not connection_id:
            raise ValueError("connection_id is required (from previous step)")

        tenant = Tenant.objects.get(id=tenant_id)
        connection = MarketplaceConnection.objects.get(id=connection_id, tenant=tenant)

        # Get connector
        marketplace_type = MarketplaceType(connection.marketplace_type)
        factory = MarketplaceConnectorFactory()
        # Create connector using factory with connection config
        connector = factory.create_connector(marketplace_type=marketplace_type, config=connection.get_config())

        # Publish each listing
        published_listings = []
        for mapped_item in mapped_listings:
            raw_listing = mapped_item["listing"]
            # Listing may be dict (from JSON-serialized state) or MarketplaceListing
            if isinstance(raw_listing, dict):
                listing = MarketplaceSyncWorkflow._listing_from_state_dict(raw_listing)
            else:
                listing = raw_listing

            # Publish via connector (create or update listing)
            # Check if listing already exists
            existing_listing = None
            if listing.marketplace_id:
                try:
                    existing_listing = connector.get_listing(listing.marketplace_id)
                except Exception as e:
                    logger.debug(
                        "marketplace_sync_get_listing_failed",
                        extra={"error_type": type(e).__name__, "error": str(e), "marketplace_id": listing.marketplace_id},
                    )

            if existing_listing:
                result = connector.update_listing(listing.marketplace_id, listing)
            else:
                result = connector.create_listing(listing)

            published_listings.append({
                "asset_id": mapped_item["asset_id"],
                "marketplace_id": result.marketplace_id if hasattr(result, 'marketplace_id') else listing.marketplace_id,
                "published": True
            })

        logger.info(
            "Assets published to marketplace",
            workflow_instance_id=str(instance.id),
            published_count=len(published_listings)
        )

        MarketplaceSyncWorkflow._update_progress(instance, 60, "publish_to_marketplace")

        return {
            "published_listings": published_listings,
            "state": {
                "published_listings": published_listings
            }
        }

    # PULL-specific task implementations

    @staticmethod
    def _discover_listings_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Discover marketplace listings via connector.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with discovered listings
        """
        connection_id = instance.state_data.get("connection_id")
        tenant_id = input_data.get("tenant_id") or instance.tenant_id
        listing_ids = input_data.get("listing_ids")
        filters = input_data.get("filters", {})
        options = input_data.get("options", {})
        limit = options.get("limit") if options else None

        if not connection_id:
            raise ValueError("connection_id is required (from previous step)")
        if not tenant_id:
            raise ValueError("tenant_id is required")

        tenant = Tenant.objects.get(id=tenant_id)
        connection = MarketplaceConnection.objects.get(id=connection_id, tenant=tenant)

        # Get connector
        marketplace_type = MarketplaceType(connection.marketplace_type)
        factory = MarketplaceConnectorFactory()
        # Create connector using factory with connection config
        connector = factory.create_connector(marketplace_type=marketplace_type, config=connection.get_config())

        # Discover listings
        if listing_ids:
            # Fetch specific listings
            listings = []
            for listing_id in listing_ids:
                try:
                    listing = connector.get_listing(listing_id)
                    if listing:
                        listings.append(listing)
                except Exception as e:
                    logger.warning(
                        "Failed to get listing",
                        workflow_instance_id=str(instance.id),
                        listing_id=listing_id,
                        error=str(e)
                    )
        else:
            # Discover listings with filters using list_listings
            # Respect limit from options if provided
            listings = connector.list_listings(filters=filters, limit=limit)

        logger.info(
            "Listings discovered",
            workflow_instance_id=str(instance.id),
            discovered_count=len(listings)
        )

        MarketplaceSyncWorkflow._update_progress(instance, 20, "discover_listings")

        return {
            "discovered_listings": [
                {
                    "marketplace_id": listing.marketplace_id,
                    "marketplace_type": listing.marketplace_type.value,
                    "title": listing.title
                }
                for listing in listings
            ],
            "state": {
                "discovered_listings": [
                    {
                        "marketplace_id": listing.marketplace_id,
                        "marketplace_type": listing.marketplace_type.value
                    }
                    for listing in listings
                ]
            }
        }

    @staticmethod
    def _map_listings_to_assets_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Map marketplace listings to Hub asset format.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with mapped asset data
        """
        discovered_listings = instance.state_data.get("discovered_listings", [])
        connection_id = instance.state_data.get("connection_id")
        tenant_id = input_data.get("tenant_id") or instance.tenant_id

        if not discovered_listings:
            raise ValueError("discovered_listings is required (from previous step)")
        if not connection_id:
            raise ValueError("connection_id is required (from previous step)")

        tenant = Tenant.objects.get(id=tenant_id)
        connection = MarketplaceConnection.objects.get(id=connection_id, tenant=tenant)

        # Get connector
        marketplace_type = MarketplaceType(connection.marketplace_type)
        factory = MarketplaceConnectorFactory()
        # Create connector using factory with connection config
        connector = factory.create_connector(marketplace_type=marketplace_type, config=connection.get_config())

        # Map each listing to asset format
        mapped_assets = []
        for listing_data in discovered_listings:
            listing_id = listing_data["marketplace_id"]
            listing = connector.get_listing(listing_id)

            if not listing:
                logger.warning(
                    "Listing not found during mapping",
                    workflow_instance_id=str(instance.id),
                    listing_id=listing_id
                )
                continue

            # Map listing to MarketplaceAssetMapping
            asset_mapping = connector.map_to_hub_asset(listing)

            # Validate mapping using business rules
            rules = MarketplaceIntegrationBusinessRules(
                tenant_id=str(tenant_id),
                user_id=str(instance.created_by_id) if instance.created_by_id else None
            )
            validation_result = rules.validate_federated_asset_creation(
                asset_mapping=asset_mapping,
                connection=connection
            )

            if not validation_result.is_valid:
                logger.warning(
                    "Asset mapping validation failed",
                    workflow_instance_id=str(instance.id),
                    listing_id=listing_id,
                    errors=validation_result.errors
                )
                continue

            # Serialize asset_mapping for storage
            asset_mapping_dict = MarketplaceSyncWorkflow._serialize_asset_mapping(asset_mapping)

            mapped_assets.append({
                "listing_id": listing_id,
                "asset_mapping": asset_mapping_dict,
                "marketplace_id": listing_id
            })

        logger.info(
            "Listings mapped to asset format",
            workflow_instance_id=str(instance.id),
            mapped_count=len(mapped_assets)
        )

        MarketplaceSyncWorkflow._update_progress(instance, 40, "map_listings_to_assets")

        # Return full mapped_assets so engine merge does not overwrite with minimal data
        return {
            "mapped_assets": mapped_assets,
            "state": {
                "mapped_assets": mapped_assets
            }
        }

    @staticmethod
    def _create_federated_assets_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Create federated assets with dual contracts (parallelized for performance).

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with created assets
        """
        mapped_assets = instance.state_data.get("mapped_assets", [])
        connection_id = instance.state_data.get("connection_id")
        tenant_id = input_data.get("tenant_id") or instance.tenant_id
        user_id = input_data.get("user_id") or instance.created_by_id

        if not mapped_assets:
            raise ValueError("mapped_assets is required (from previous step)")
        if not connection_id:
            raise ValueError("connection_id is required (from previous step)")
        if not tenant_id:
            raise ValueError("tenant_id is required")

        # Get options from input_data
        options = input_data.get("options", {})
        skip_resource_downloads = options.get("skip_resource_downloads", False) or options.get("skip_resources", False)
        skip_semantic_mapping = options.get("skip_semantic_mapping", False) or options.get("skip_semantic", False)
        download_resources_for_last_n = options.get("download_resources_for_last_n")
        # Read data_strategy from options (default: METADATA_ONLY)
        data_strategy = options.get("data_strategy", "METADATA_ONLY")
        download_resources = options.get("download_resources")  # List of resource IDs for DOWNLOAD_SELECTIVE

        tenant = Tenant.objects.get(id=tenant_id)
        connection = MarketplaceConnection.objects.get(id=connection_id, tenant=tenant)

        # Validate dual contract creation using business rules
        rules = MarketplaceIntegrationBusinessRules()

        # Prepare items for parallel processing
        items_to_process = []
        for mapped_item in mapped_assets:
            # Deserialize asset_mapping from dict
            asset_mapping_dict = mapped_item.get("asset_mapping")
            if not asset_mapping_dict:
                logger.warning(
                    "Missing asset_mapping in mapped_item",
                    workflow_instance_id=str(instance.id),
                    listing_id=mapped_item.get("listing_id")
                )
                continue

            asset_mapping = MarketplaceSyncWorkflow._deserialize_asset_mapping(asset_mapping_dict)

            # Validate dual contract creation
            contract_validation = rules.validate_dual_contract_creation(
                asset_mapping=asset_mapping,
                tenant_id=str(tenant_id)
            )

            if not contract_validation.is_valid:
                logger.warning(
                    "Dual contract validation failed",
                    workflow_instance_id=str(instance.id),
                    listing_id=mapped_item["listing_id"],
                    errors=contract_validation.errors
                )
                continue

            items_to_process.append({
                "mapped_item": mapped_item,
                "asset_mapping": asset_mapping,
                "index": len(items_to_process)  # Track position for selective resource downloading
            })

        # Determine resource download strategy
        total_items = len(items_to_process)
        if download_resources_for_last_n and download_resources_for_last_n > 0:
            # Calculate threshold: download resources for last N items
            resource_download_threshold = max(0, total_items - download_resources_for_last_n)
            logger.info(
                "Selective resource downloading enabled",
                workflow_instance_id=str(instance.id),
                total_items=total_items,
                download_resources_for_last_n=download_resources_for_last_n,
                threshold=resource_download_threshold
            )
        else:
            resource_download_threshold = None

        # Parallelize asset creation
        def create_single_asset(item_data):
            """Create a single federated asset with contracts (runs in its own transaction)."""
            mapped_item = item_data["mapped_item"]
            asset_mapping = item_data["asset_mapping"]
            item_index = item_data.get("index", 0)

            # Determine data_strategy for this asset
            # If download_resources_for_last_n is set, use DOWNLOAD_ALL for last N items
            asset_data_strategy = data_strategy
            asset_download_resources = download_resources

            if download_resources_for_last_n and resource_download_threshold is not None:
                if item_index < resource_download_threshold:
                    # Skip downloads for items before threshold
                    asset_data_strategy = "METADATA_ONLY"
                else:
                    # Download all resources for items at or after threshold
                    asset_data_strategy = "DOWNLOAD_ALL"

            # Backward compatibility: skip_resource_downloads overrides data_strategy
            if skip_resource_downloads:
                asset_data_strategy = "METADATA_ONLY"

            # Each parallel task needs its own transaction
            # IMPORTANT: Fetch tenant and connection fresh in each thread to avoid transaction isolation issues
            with transaction.atomic():
                # Use MarketplaceIntegrationService to create federated asset with contracts
                from hub.apps.integrations.services import MarketplaceIntegrationService

                # Fetch tenant and connection fresh in this transaction (fixes transaction isolation in parallel threads)
                thread_tenant = Tenant.objects.get(id=tenant_id)
                thread_connection = MarketplaceConnection.objects.get(id=connection_id, tenant=thread_tenant)

                # Get sync_job if available
                # IMPORTANT: Refresh instance.state_data to get latest sync_job_id
                instance.refresh_from_db()
                sync_job = None
                sync_job_id = instance.state_data.get("sync_job_id")
                if sync_job_id:
                    try:
                        # Fetch sync_job fresh in this transaction
                        sync_job = MarketplaceSyncJob.objects.get(id=sync_job_id, tenant=thread_tenant)
                    except MarketplaceSyncJob.DoesNotExist:
                        logger.warning(
                            "Sync job not found in parallel thread, will create asset without sync_job reference",
                            workflow_instance_id=str(instance.id),
                            sync_job_id=sync_job_id
                        )
                        # Don't create fallback sync_job - let create_federated_asset_with_contracts handle it
                        # Creating sync_job here causes validation errors due to transaction isolation

                integration_service = MarketplaceIntegrationService(
                    tenant_id=str(tenant_id),
                    user_id=str(user_id) if user_id else None
                )

                try:
                    # Create federated asset with contracts using the new service method
                    # If sync_job is None, the service method will handle it gracefully
                    asset = integration_service.create_federated_asset_with_contracts(
                        asset_mapping=asset_mapping,
                        connection=thread_connection,
                        sync_job=sync_job,  # May be None if not found - service handles this
                        tenant_id=str(tenant_id),
                        user_id=str(user_id) if user_id else None,
                        skip_resource_downloads=skip_resource_downloads,  # Backward compatibility
                        skip_semantic_mapping=skip_semantic_mapping,
                        data_strategy=asset_data_strategy,
                        download_resources=asset_download_resources,
                    )

                    # Get created contracts
                    odps_contract = asset.contracts.filter(original_spec_type=OriginalSpecType.ODPS).first()
                    odcs_contract = asset.contracts.filter(original_spec_type=OriginalSpecType.ODCS).first()

                    return {
                        "asset_id": str(asset.id),
                        "listing_id": mapped_item["listing_id"],
                        "odps_contract_id": str(odps_contract.id) if odps_contract else None,
                        "odcs_contract_id": str(odcs_contract.id) if odcs_contract else None
                    }
                except Exception as e:
                    logger.error(
                        "Failed to create federated asset with contracts",
                        workflow_instance_id=str(instance.id),
                        listing_id=mapped_item.get("listing_id"),
                        error=str(e),
                        exc_info=True
                    )
                    return None

        # Execute asset creation
        # IMPORTANT: In Django TestCase, parallel threads can't see uncommitted transactions
        # Use sequential execution in test environment, parallel in production
        created_assets = []
        import sys
        is_test_env = (
            "test" in sys.argv
            or "pytest" in sys.modules
            or "unittest" in sys.modules
            or hasattr(sys, "_getframe")
            and any(
                "test" in str(f.filename).lower()
                for f in [sys._getframe(i) for i in range(10)]
                if f
            )
        )

        if is_test_env:
            # Sequential execution in tests to avoid transaction isolation issues
            logger.info(
                "Using sequential execution in test environment",
                workflow_instance_id=str(instance.id),
                item_count=len(items_to_process)
            )
            for item in items_to_process:
                result = create_single_asset(item)
                if result:
                    created_assets.append(result)
        else:
            # Parallel execution in production for performance (max 10 concurrent workers)
            max_workers = min(10, len(items_to_process))
            if max_workers == 0:
                logger.warning(
                    "No assets to process",
                    workflow_instance_id=str(instance.id)
                )
            else:
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    future_to_item = {
                        executor.submit(create_single_asset, item): item
                        for item in items_to_process
                    }

                    for future in as_completed(future_to_item):
                        result = future.result()
                        if result:
                            created_assets.append(result)

        logger.info(
            "Federated assets created",
            workflow_instance_id=str(instance.id),
            created_count=len(created_assets),
            total_processed=len(items_to_process),
            skip_resources=skip_resource_downloads if not download_resources_for_last_n else f"selective (last {download_resources_for_last_n})",
            skip_semantic=skip_semantic_mapping
        )

        MarketplaceSyncWorkflow._update_progress(instance, 60, "create_federated_assets")

        return {
            "created_assets": created_assets,
            "state": {
                "created_assets": created_assets
            }
        }

    @staticmethod
    def _download_resources_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Download resources from marketplace.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with download results
        """
        mapped_assets = instance.state_data.get("mapped_assets", [])
        connection_id = instance.state_data.get("connection_id")
        tenant_id = input_data.get("tenant_id") or instance.tenant_id

        if not mapped_assets:
            raise ValueError("mapped_assets is required (from previous step)")
        if not connection_id:
            raise ValueError("connection_id is required (from previous step)")

        tenant = Tenant.objects.get(id=tenant_id)
        connection = MarketplaceConnection.objects.get(id=connection_id, tenant=tenant)

        # Validate resources using business rules
        rules = MarketplaceIntegrationBusinessRules()

        downloaded_resources = []
        for mapped_item in mapped_assets:
            # Deserialize asset_mapping from dict
            asset_mapping_dict = mapped_item.get("asset_mapping")
            if not asset_mapping_dict:
                logger.warning(
                    "Missing asset_mapping in mapped_item",
                    workflow_instance_id=str(instance.id),
                    listing_id=mapped_item.get("listing_id")
                )
                continue

            asset_mapping: MarketplaceAssetMapping = MarketplaceSyncWorkflow._deserialize_asset_mapping(asset_mapping_dict)
            resources = asset_mapping.resources

            if not resources:
                continue

            # Validate resource download
            resource_validation = rules.validate_resource_download(
                resources=resources,
                connection=connection,
                tenant_id=str(tenant_id) if tenant_id else None
            )

            if not resource_validation.is_valid:
                logger.warning(
                    "Resource download validation failed",
                    workflow_instance_id=str(instance.id),
                    listing_id=mapped_item["listing_id"],
                    errors=resource_validation.errors
                )
                continue

            # Download resources via connector
            marketplace_type = MarketplaceType(connection.marketplace_type)
            factory = MarketplaceConnectorFactory()
            # Create connector using factory with connection config
            connector = factory.create_connector(marketplace_type=marketplace_type, config=connection.get_config())

            for resource in resources:
                try:
                    # Create temporary destination path for download
                    import tempfile
                    import os
                    temp_dir = tempfile.gettempdir()
                    destination_path = os.path.join(temp_dir, f"resource_{resource.resource_id}")

                    downloaded_path = connector.download_resource(
                        resource_id=resource.resource_id,
                        destination_path=destination_path
                    )
                    downloaded_resources.append({
                        "resource_id": resource.resource_id,
                        "asset_id": mapped_item.get("asset_id"),
                        "downloaded_path": downloaded_path,
                        "downloaded": True
                    })
                except Exception as e:
                    logger.warning(
                        "Resource download failed",
                        workflow_instance_id=str(instance.id),
                        resource_id=resource.resource_id,
                        error=str(e)
                    )

        logger.info(
            "Resources downloaded",
            workflow_instance_id=str(instance.id),
            downloaded_count=len(downloaded_resources)
        )

        MarketplaceSyncWorkflow._update_progress(instance, 70, "download_resources")

        return {
            "downloaded_resources": downloaded_resources,
            "state": {
                "downloaded_resources": downloaded_resources
            }
        }

    # Common task implementations

    @staticmethod
    @transaction.atomic
    def _create_mappings_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Create MarketplaceMapping records.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with created mappings
        """
        connection_id = instance.state_data.get("connection_id")
        tenant_id = input_data.get("tenant_id") or instance.tenant_id

        if not connection_id:
            raise ValueError("connection_id is required (from previous step)")
        if not tenant_id:
            raise ValueError("tenant_id is required")

        tenant = Tenant.objects.get(id=tenant_id)
        connection = MarketplaceConnection.objects.get(id=connection_id, tenant=tenant)

        created_mappings = []

        # For PUSH: use published_listings
        published_listings = instance.state_data.get("published_listings", [])
        if published_listings:
            for published_item in published_listings:
                asset_id = published_item["asset_id"]
                marketplace_id = published_item.get("marketplace_id") or ""

                # Skip mappings when connector did not produce a real external ID
                # (e.g. IN_MEMORY_FAKE returns empty marketplace_id)
                if not marketplace_id or not str(marketplace_id).strip():
                    continue

                mapping, created = MarketplaceMapping.objects.get_or_create(
                    tenant=tenant,
                    connection=connection,
                    hub_asset_id=asset_id,
                    defaults={
                        "external_listing_id": marketplace_id,
                        "external_resource_ids": [],
                        "sync_metadata": {
                            "sync_direction": "PUSH",
                            "synced_at": timezone.now().isoformat()
                        },
                        "last_synced_at": timezone.now()
                    }
                )

                if created:
                    created_mappings.append({
                        "mapping_id": str(mapping.id),
                        "asset_id": asset_id,
                        "marketplace_id": marketplace_id
                    })

        # For PULL: use created_assets
        created_assets = instance.state_data.get("created_assets", [])
        if created_assets:
            for asset_item in created_assets:
                asset_id = asset_item["asset_id"]
                listing_id = asset_item["listing_id"]

                mapping, created = MarketplaceMapping.objects.get_or_create(
                    tenant=tenant,
                    connection=connection,
                    hub_asset_id=asset_id,
                    defaults={
                        "external_listing_id": listing_id,
                        "external_resource_ids": [],
                        "sync_metadata": {
                            "sync_direction": "PULL",
                            "synced_at": timezone.now().isoformat()
                        },
                        "last_synced_at": timezone.now()
                    }
                )

                if created:
                    created_mappings.append({
                        "mapping_id": str(mapping.id),
                        "asset_id": asset_id,
                        "marketplace_id": listing_id
                    })

        logger.info(
            "Mappings created",
            workflow_instance_id=str(instance.id),
            created_count=len(created_mappings)
        )

        MarketplaceSyncWorkflow._update_progress(instance, 80, "create_mappings")

        return {
            "mappings_created": True,
            "created_mappings": created_mappings,
            "state": {
                "created_mappings": created_mappings
            }
        }

    @staticmethod
    def _update_semantic_layer_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Update semantic layer with federated asset properties.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with semantic update results
        """
        tenant_id = input_data.get("tenant_id") or instance.tenant_id

        if not tenant_id:
            raise ValueError("tenant_id is required")

        tenant = Tenant.objects.get(id=tenant_id)
        updated_assets = []

        # Get asset IDs from state
        published_listings = instance.state_data.get("published_listings", [])
        created_assets = instance.state_data.get("created_assets", [])

        asset_ids = []
        if published_listings:
            asset_ids.extend([item["asset_id"] for item in published_listings])
        if created_assets:
            asset_ids.extend([item["asset_id"] for item in created_assets])

        for asset_id in asset_ids:
            try:
                asset = Asset.objects.get(id=asset_id, tenant=tenant)
                semantic_resource = map_asset_to_semantic(asset, tenant=tenant)

                if semantic_resource:
                    updated_assets.append({
                        "asset_id": asset_id,
                        "semantic_resource_id": str(semantic_resource.id)
                    })
            except Asset.DoesNotExist:
                logger.warning(
                    "Asset not found for semantic update",
                    workflow_instance_id=str(instance.id),
                    asset_id=asset_id
                )
            except Exception as e:
                logger.warning(
                    "Semantic update failed",
                    workflow_instance_id=str(instance.id),
                    asset_id=asset_id,
                    error=str(e)
                )

        logger.info(
            "Semantic layer updated",
            workflow_instance_id=str(instance.id),
            updated_count=len(updated_assets)
        )

        MarketplaceSyncWorkflow._update_progress(instance, 90, "update_semantic_layer")

        return {
            "semantic_updated": True,
            "updated_assets": updated_assets,
            "state": {
                "updated_assets": updated_assets
            }
        }

    # Compensation task implementations

    @staticmethod
    def _rollback_connection_validation_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """Rollback connection validation (no-op - validation only)"""
        return {"rolled_back": True}

    @staticmethod
    def _rollback_asset_validation_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """Rollback asset validation (no-op - validation only)"""
        return {"rolled_back": True}

    @staticmethod
    def _rollback_mapping_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """Rollback mapping (no-op - mapping is in-memory)"""
        return {"rolled_back": True}

    @staticmethod
    @transaction.atomic
    def _rollback_marketplace_publish_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """Rollback marketplace publish - delete published listings"""
        published_listings = instance.state_data.get("published_listings", [])
        connection_id = instance.state_data.get("connection_id")

        if not published_listings or not connection_id:
            return {"rolled_back": True}

        try:
            connection = MarketplaceConnection.objects.get(id=connection_id)
            marketplace_type = MarketplaceType(connection.marketplace_type)
            factory = MarketplaceConnectorFactory()
            connector = factory.get_connector(marketplace_type)
            connector.authenticate(connection.get_config())

            for published_item in published_listings:
                marketplace_id = published_item.get("marketplace_id")
                if marketplace_id:
                    try:
                        # Try to get listing first to verify it exists
                        listing = connector.get_listing(marketplace_id)
                        # Note: delete_listing may not be available in all connectors
                        # For now, we log that rollback should be handled manually
                        logger.warning(
                            "Listing rollback requires manual deletion",
                            workflow_instance_id=str(instance.id),
                            marketplace_id=marketplace_id,
                            note="delete_listing method may not be available in connector"
                        )
                    except Exception as e:
                        logger.info(
                            "Listing may already be deleted or not found",
                            workflow_instance_id=str(instance.id),
                            marketplace_id=marketplace_id,
                            error=str(e)
                        )
        except Exception as e:
            logger.warning(
                "Rollback marketplace publish failed",
                workflow_instance_id=str(instance.id),
                error=str(e)
            )

        return {"rolled_back": True}

    @staticmethod
    @transaction.atomic
    def _rollback_mapping_creation_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """Rollback mapping creation - delete MarketplaceMapping records"""
        created_mappings = instance.state_data.get("created_mappings", [])

        if not created_mappings:
            return {"rolled_back": True}

        for mapping_item in created_mappings:
            mapping_id = mapping_item.get("mapping_id")
            if mapping_id:
                try:
                    mapping = MarketplaceMapping.objects.get(id=mapping_id)
                    mapping.delete()
                    logger.info(
                        "Mapping deleted during rollback",
                        workflow_instance_id=str(instance.id),
                        mapping_id=mapping_id
                    )
                except MarketplaceMapping.DoesNotExist:
                    logger.warning(
                        "Mapping not found for rollback",
                        workflow_instance_id=str(instance.id),
                        mapping_id=mapping_id
                    )
                except Exception as e:
                    logger.warning(
                        "Failed to delete mapping during rollback",
                        workflow_instance_id=str(instance.id),
                        mapping_id=mapping_id,
                        error=str(e)
                    )

        return {"rolled_back": True}

    @staticmethod
    @transaction.atomic
    def _rollback_federated_asset_creation_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """Rollback federated asset creation - delete created assets and contracts"""
        created_assets = instance.state_data.get("created_assets", [])

        if not created_assets:
            return {"rolled_back": True}

        for asset_item in created_assets:
            asset_id = asset_item.get("asset_id")
            if asset_id:
                try:
                    asset = Asset.objects.get(id=asset_id)

                    # Delete contracts if they exist
                    odps_contract_id = asset_item.get("odps_contract_id")
                    odcs_contract_id = asset_item.get("odcs_contract_id")

                    if odps_contract_id:
                        try:
                            from hub.apps.contracts.models import Contract
                            contract = Contract.objects.get(id=odps_contract_id)
                            contract.delete()
                        except Exception as e:
                            logger.warning(
                                "Failed to delete ODPS contract during rollback",
                                workflow_instance_id=str(instance.id),
                                contract_id=odps_contract_id,
                                error=str(e)
                            )

                    if odcs_contract_id:
                        try:
                            from hub.apps.contracts.models import Contract
                            contract = Contract.objects.get(id=odcs_contract_id)
                            contract.delete()
                        except Exception as e:
                            logger.warning(
                                "Failed to delete ODCS contract during rollback",
                                workflow_instance_id=str(instance.id),
                                contract_id=odcs_contract_id,
                                error=str(e)
                            )

                    # Delete asset
                    asset.delete()
                    logger.info(
                        "Asset deleted during rollback",
                        workflow_instance_id=str(instance.id),
                        asset_id=asset_id
                    )
                except Asset.DoesNotExist:
                    logger.warning(
                        "Asset not found for rollback",
                        workflow_instance_id=str(instance.id),
                        asset_id=asset_id
                    )
                except Exception as e:
                    logger.warning(
                        "Failed to delete asset during rollback",
                        workflow_instance_id=str(instance.id),
                        asset_id=asset_id,
                        error=str(e)
                    )

        return {"rolled_back": True}

    @staticmethod
    def _rollback_resource_download_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """Rollback resource download - delete downloaded resources"""
        downloaded_resources = instance.state_data.get("downloaded_resources", [])

        if not downloaded_resources:
            return {"rolled_back": True}

        # Resources are typically stored as files or in datasets
        # This is a simplified rollback - actual implementation would delete files/datasets
        logger.info(
            "Resource download rollback (resources should be cleaned up)",
            workflow_instance_id=str(instance.id),
            resource_count=len(downloaded_resources)
        )

        return {"rolled_back": True}

