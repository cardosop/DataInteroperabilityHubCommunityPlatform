"""
Marketplace Publication Workflow

Orchestrates marketplace publication process, including:
- Validate asset eligibility (KYC, contract validation, DQ/compliance)
- Create marketplace listing
- Configure pricing model
- Configure license information
- Publish listing (make public)
- Index for marketplace search
- Send notifications
- Audit logging
"""
from typing import Dict, Any, Optional, List
from django.utils import timezone
from django.db import transaction
import structlog

from hub.apps.orchestration.models import WorkflowInstance, WorkflowStatus
from hub.apps.orchestration.registry import WorkflowRegistry
from hub.apps.orchestration.workflow_engine import WorkflowEngine
from hub.apps.marketplace.business_rules import MarketplaceBusinessRules
from hub.apps.marketplace.models import Listing, ListingStatus, PricingModel
from hub.apps.assets.models import Asset, AssetStatus, DQStatus, ComplianceStatus
from hub.apps.tenants.models import Tenant, KYCStatus
from hub.apps.contracts.models import Contract, ContractStatus
from hub.apps.search.indexing import SearchIndexer
from hub.apps.audit.utils import create_audit_event
from hub.apps.marketplace.contract_integration import ContractMarketplacePolicyExtractor

logger = structlog.get_logger(__name__)


class MarketplacePublicationWorkflow:
    """
    Marketplace publication workflow orchestrator.
    
    Orchestrates the complete marketplace publication process:
    1. Validate asset eligibility (KYC, contract validation, DQ/compliance)
    2. Create marketplace listing
    3. Configure pricing model
    4. Configure license information
    5. Publish listing (make public)
    6. Index for marketplace search
    7. Send notifications
    8. Audit logging
    """
    
    WORKFLOW_NAME = "marketplace_publication"
    
    @classmethod
    def register_workflow(cls, registry: WorkflowRegistry) -> None:
        """
        Register the marketplace publication workflow definition.
        
        Args:
            registry: WorkflowRegistry instance
        """
        workflow_dsl = {
            "version": "1.0.0",
            "dependencies": [],
            "steps": [
                {
                    "name": "validate_asset_eligibility",
                    "type": "task",
                    "task": "marketplace_publication.validate_asset_eligibility"
                },
                {
                    "name": "create_marketplace_listing",
                    "type": "task",
                    "task": "marketplace_publication.create_marketplace_listing",
                    "compensation": {
                        "type": "task",
                        "task": "marketplace_publication.rollback_listing_creation"
                    }
                },
                {
                    "name": "configure_pricing_model",
                    "type": "task",
                    "task": "marketplace_publication.configure_pricing_model"
                },
                {
                    "name": "configure_license_information",
                    "type": "task",
                    "task": "marketplace_publication.configure_license_information"
                },
                {
                    "name": "publish_listing",
                    "type": "task",
                    "task": "marketplace_publication.publish_listing",
                    "compensation": {
                        "type": "task",
                        "task": "marketplace_publication.rollback_publication"
                    }
                },
                {
                    "name": "index_for_marketplace_search",
                    "type": "task",
                    "task": "marketplace_publication.index_for_marketplace_search",
                    "compensation": {
                        "type": "task",
                        "task": "marketplace_publication.rollback_indexing"
                    }
                },
                {
                    "name": "send_notifications",
                    "type": "task",
                    "task": "marketplace_publication.send_notifications"
                },
                {
                    "name": "audit_logging",
                    "type": "task",
                    "task": "marketplace_publication.audit_logging"
                }
            ],
            "compensation": {"enabled": True}
        }
        registry.register_workflow(
            cls.WORKFLOW_NAME,
            workflow_dsl
        )
    
    @classmethod
    def register_tasks(cls, engine: WorkflowEngine) -> None:
        """
        Register all workflow task functions.
        
        Args:
            engine: WorkflowEngine instance
        """
        engine.register_task(
            "marketplace_publication.validate_asset_eligibility",
            cls._validate_asset_eligibility_task
        )
        engine.register_task(
            "marketplace_publication.create_marketplace_listing",
            cls._create_marketplace_listing_task
        )
        engine.register_task(
            "marketplace_publication.configure_pricing_model",
            cls._configure_pricing_model_task
        )
        engine.register_task(
            "marketplace_publication.configure_license_information",
            cls._configure_license_information_task
        )
        engine.register_task(
            "marketplace_publication.publish_listing",
            cls._publish_listing_task
        )
        engine.register_task(
            "marketplace_publication.index_for_marketplace_search",
            cls._index_for_marketplace_search_task
        )
        engine.register_task(
            "marketplace_publication.send_notifications",
            cls._send_notifications_task
        )
        engine.register_task(
            "marketplace_publication.audit_logging",
            cls._audit_logging_task
        )
        
        # Compensation tasks
        engine.register_task(
            "marketplace_publication.rollback_listing_creation",
            cls._rollback_listing_creation_task
        )
        engine.register_task(
            "marketplace_publication.rollback_publication",
            cls._rollback_publication_task
        )
        engine.register_task(
            "marketplace_publication.rollback_indexing",
            cls._rollback_indexing_task
        )
    
    @staticmethod
    def _validate_asset_eligibility_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Validate asset eligibility for marketplace publication.
        
        Checks:
        - Tenant KYC status (must be VERIFIED)
        - Asset status (must be ACTIVE)
        - Contract validation (must have ACTIVE contract with VALID or WARNING_ONLY validation_status)
        - DQ status (must be PASS or WARN if dataset exists)
        - Compliance status (must be PASS or WARN if dataset exists)
        
        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step
            
        Returns:
            Task output with validation results
        """
        asset_id = input_data.get("asset_id")
        tenant_id = input_data.get("tenant_id") or instance.tenant_id
        
        if not asset_id:
            raise ValueError("asset_id is required")
        if not tenant_id:
            raise ValueError("tenant_id is required")
        
        tenant = Tenant.objects.get(id=tenant_id)
        asset = Asset.objects.get(id=asset_id, tenant=tenant)

        validation_results = {
            "kyc_verified": False,
            "asset_active": False,
            "contract_valid": False,
            "dq_status_ok": True,  # Default to True if no dataset
            "compliance_status_ok": True,  # Default to True if no dataset
            "eligibility_passed": False,
            "blockers": []
        }

        # Note: MarketplaceBusinessRules.validate() requires a listing or order,
        # but we're validating asset eligibility before creating the listing.
        # We'll validate using business rules after the listing is created.
        # For now, we do manual validation checks below.
        
        # Check KYC status
        if tenant.kyc_status != KYCStatus.VERIFIED:
            validation_results["blockers"].append(
                f"Tenant KYC status must be VERIFIED (current: {tenant.kyc_status})"
            )
        else:
            validation_results["kyc_verified"] = True
        
        # Check asset status
        if asset.status != AssetStatus.ACTIVE:
            validation_results["blockers"].append(
                f"Asset status must be ACTIVE (current: {asset.status})"
            )
        else:
            validation_results["asset_active"] = True
        
        # Check contract requirements
        active_contract = asset.contracts.filter(status=ContractStatus.ACTIVE).first()
        if not active_contract:
            validation_results["blockers"].append("Asset must have an ACTIVE contract")
        else:
            # Check contract validation status
            if active_contract.validation_status not in ["VALID", "WARNING_ONLY"]:
                validation_results["blockers"].append(
                    f"Contract validation_status must be VALID or WARNING_ONLY "
                    f"(current: {active_contract.validation_status})"
                )
            else:
                validation_results["contract_valid"] = True
        
        # Check DQ status (only if dataset exists)
        dataset = asset.datasets.first()
        if dataset:
            if asset.dq_status not in [DQStatus.PASS, DQStatus.WARN]:
                validation_results["blockers"].append(
                    f"DQ status must be PASS or WARN (current: {asset.dq_status})"
                )
                validation_results["dq_status_ok"] = False
            else:
                validation_results["dq_status_ok"] = True
        
        # Check compliance status (only if dataset exists)
        if dataset:
            if asset.compliance_status not in [ComplianceStatus.PASS, ComplianceStatus.WARN]:
                validation_results["blockers"].append(
                    f"Compliance status must be PASS or WARN (current: {asset.compliance_status})"
                )
                validation_results["compliance_status_ok"] = False
            else:
                validation_results["compliance_status_ok"] = True
        
        # Determine overall eligibility
        validation_results["eligibility_passed"] = len(validation_results["blockers"]) == 0
        
        if not validation_results["eligibility_passed"]:
            error_message = "; ".join(validation_results["blockers"])
            logger.warning(
                "Asset eligibility validation failed",
                workflow_instance_id=str(instance.id),
                asset_id=str(asset.id),
                tenant_id=str(tenant.id),
                blockers=validation_results["blockers"]
            )
            raise ValueError(f"Asset eligibility validation failed: {error_message}")
        
        logger.info(
            "Asset eligibility validated",
            workflow_instance_id=str(instance.id),
            asset_id=str(asset.id),
            tenant_id=str(tenant.id),
            kyc_verified=validation_results["kyc_verified"],
            asset_active=validation_results["asset_active"],
            contract_valid=validation_results["contract_valid"]
        )
        
        return {
            "validation_passed": True,
            "validation_results": validation_results,
            "state": {
                "validation_passed": True,
                "validation_results": validation_results,
                "asset_id": str(asset.id),
                "tenant_id": str(tenant.id)
            }
        }
    
    @staticmethod
    @transaction.atomic
    def _create_marketplace_listing_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Create marketplace listing for the asset.
        
        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step
            
        Returns:
            Task output with listing details
        """
        asset_id = instance.state_data.get("asset_id") or input_data.get("asset_id")
        tenant_id = instance.state_data.get("tenant_id") or input_data.get("tenant_id") or instance.tenant_id
        metadata_json = input_data.get("metadata_json", {})
        
        if not asset_id:
            raise ValueError("asset_id is required (from previous step or input_data)")
        
        tenant = Tenant.objects.get(id=tenant_id)
        asset = Asset.objects.get(id=asset_id, tenant=tenant)
        
        # Check if listing already exists
        existing_listing = Listing.objects.filter(tenant=tenant, asset=asset).first()
        if existing_listing:
            logger.info(
                "Listing already exists, using existing listing",
                workflow_instance_id=str(instance.id),
                asset_id=str(asset.id),
                listing_id=str(existing_listing.id)
            )
            return {
                "listing_created": False,
                "listing_id": str(existing_listing.id),
                "existing_listing": True,
                "state": {
                    "listing_id": str(existing_listing.id),
                    "existing_listing": True
                }
            }
        
        # Pre-populate metadata from contract if available
        active_contract = asset.contracts.filter(status=ContractStatus.ACTIVE).first()
        if active_contract:
            metadata_json = ContractMarketplacePolicyExtractor.pre_populate_listing_metadata(
                active_contract, existing_metadata=metadata_json
            )
        
        # Ensure required fields are present
        if not metadata_json.get("title"):
            # Use asset name as fallback
            metadata_json["title"] = asset.name
        
        # Validate listing before creation using MarketplaceBusinessRules
        marketplace_rules = MarketplaceBusinessRules(
            tenant_id=str(tenant_id) if tenant_id else None,
            user_id=str(instance.created_by_id) if instance.created_by_id else None
        )

        # Create listing in DRAFT status
        listing = Listing.objects.create(
            tenant=tenant,
            asset=asset,
            status=ListingStatus.DRAFT,
            pricing_model=input_data.get("pricing_model", PricingModel.FREE),
            metadata_json=metadata_json
        )

        # Validate created listing using MarketplaceBusinessRules
        listing_validation_result = marketplace_rules.validate(
            listing=listing,
            asset=asset,
            tenant=tenant,
            user=instance.created_by,
            validation_type="listing"
        )

        if not listing_validation_result.is_valid:
            error_messages = listing_validation_result.errors
            # Log errors but don't fail - listing is already created
            logger.warning(
                "Listing validation errors after creation",
                workflow_instance_id=str(instance.id),
                listing_id=str(listing.id),
                errors=error_messages,
            )
        elif listing_validation_result.warnings:
            logger.warning(
                "Listing validation warnings",
                workflow_instance_id=str(instance.id),
                listing_id=str(listing.id),
                warnings=listing_validation_result.warnings,
            )
        
        logger.info(
            "Marketplace listing created",
            workflow_instance_id=str(instance.id),
            asset_id=str(asset.id),
            listing_id=str(listing.id),
            tenant_id=str(tenant.id)
        )
        
        return {
            "listing_created": True,
            "listing_id": str(listing.id),
            "state": {
                "listing_id": str(listing.id),
                "listing_created": True
            }
        }
    
    @staticmethod
    @transaction.atomic
    def _configure_pricing_model_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Configure pricing model for the listing.
        
        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step
            
        Returns:
            Task output with pricing configuration
        """
        listing_id = instance.state_data.get("listing_id")
        pricing_model = input_data.get("pricing_model", PricingModel.FREE)
        price_amount = input_data.get("price_amount")
        currency = input_data.get("currency", "USD")
        
        if not listing_id:
            raise ValueError("listing_id is required (from previous step)")
        
        listing = Listing.objects.get(id=listing_id)
        
        # Update pricing model
        listing.pricing_model = pricing_model
        
        # Update metadata with pricing information
        if listing.metadata_json is None:
            listing.metadata_json = {}
        
        if price_amount is not None:
            listing.metadata_json["price_amount"] = float(price_amount)
            listing.metadata_json["currency"] = currency
        
        # Validate pricing model requirements
        if pricing_model == PricingModel.REQUEST_APPROVAL:
            if not price_amount or price_amount <= 0:
                raise ValueError(
                    "REQUEST_APPROVAL pricing model requires a valid price_amount > 0"
                )
        
        listing.save(update_fields=["pricing_model", "metadata_json"])
        
        logger.info(
            "Pricing model configured",
            workflow_instance_id=str(instance.id),
            listing_id=str(listing.id),
            pricing_model=pricing_model,
            price_amount=price_amount
        )
        
        return {
            "pricing_configured": True,
            "pricing_model": pricing_model,
            "price_amount": price_amount,
            "currency": currency,
            "state": {
                "pricing_configured": True,
                "pricing_model": pricing_model
            }
        }
    
    @staticmethod
    @transaction.atomic
    def _configure_license_information_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Configure license information from contract marketplace policy.
        
        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step
            
        Returns:
            Task output with license configuration
        """
        listing_id = instance.state_data.get("listing_id")
        asset_id = instance.state_data.get("asset_id")
        
        if not listing_id:
            raise ValueError("listing_id is required (from previous step)")
        if not asset_id:
            raise ValueError("asset_id is required (from previous step)")
        
        listing = Listing.objects.get(id=listing_id)
        asset = Asset.objects.get(id=asset_id, tenant=listing.tenant)
        
        # Get license information from contract
        active_contract = asset.contracts.filter(status=ContractStatus.ACTIVE).first()
        
        license_info = {}
        if active_contract:
            policy = ContractMarketplacePolicyExtractor.extract_marketplace_policy(active_contract)
            
            if policy.get("license_summary"):
                license_info["license_summary"] = policy["license_summary"]
            
            if policy.get("intended_use"):
                license_info["intended_use"] = policy["intended_use"]
            
            if policy.get("restricted_use"):
                license_info["restricted_use"] = policy["restricted_use"]
            
            # Generate ODRL policy if applicable
            odrl_policy = ContractMarketplacePolicyExtractor.generate_odrl_policy(active_contract)
            if odrl_policy:
                license_info["odrl_policy"] = odrl_policy
        
        # Update listing metadata with license information
        if listing.metadata_json is None:
            listing.metadata_json = {}
        
        listing.metadata_json.update(license_info)
        listing.save(update_fields=["metadata_json"])
        
        logger.info(
            "License information configured",
            workflow_instance_id=str(instance.id),
            listing_id=str(listing.id),
            has_license_summary=bool(license_info.get("license_summary")),
            has_intended_use=bool(license_info.get("intended_use")),
            has_restricted_use=bool(license_info.get("restricted_use"))
        )
        
        return {
            "license_configured": True,
            "license_info": license_info,
            "state": {
                "license_configured": True,
                "license_info": license_info
            }
        }
    
    @staticmethod
    @transaction.atomic
    def _publish_listing_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Publish the listing (make it public).
        
        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step
            
        Returns:
            Task output with publication status
        """
        listing_id = instance.state_data.get("listing_id")
        
        if not listing_id:
            raise ValueError("listing_id is required (from previous step)")
        
        listing = Listing.objects.get(id=listing_id)
        
        # Validate listing can be published
        can_publish, reason = listing.can_publish()
        if not can_publish:
            raise ValueError(f"Cannot publish listing: {reason}")
        
        # Publish the listing
        listing.publish()
        
        logger.info(
            "Listing published",
            workflow_instance_id=str(instance.id),
            listing_id=str(listing.id),
            published_at=str(listing.published_at)
        )
        
        return {
            "published": True,
            "published_at": listing.published_at.isoformat() if listing.published_at else None,
            "state": {
                "published": True,
                "published_at": listing.published_at.isoformat() if listing.published_at else None
            }
        }
    
    @staticmethod
    def _index_for_marketplace_search_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Index listing for marketplace search.
        
        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step
            
        Returns:
            Task output with indexing results
        """
        listing_id = instance.state_data.get("listing_id")
        asset_id = instance.state_data.get("asset_id")
        
        if not listing_id:
            raise ValueError("listing_id is required (from previous step)")
        if not asset_id:
            raise ValueError("asset_id is required (from previous step)")
        
        listing = Listing.objects.get(id=listing_id)
        asset = Asset.objects.get(id=asset_id, tenant=listing.tenant)
        
        # Index the asset (listings are indexed via their associated asset)
        try:
            search_index = SearchIndexer.index_asset(asset)
            
            logger.info(
                "Listing indexed for marketplace search",
                workflow_instance_id=str(instance.id),
                listing_id=str(listing.id),
                asset_id=str(asset.id),
                search_index_id=str(search_index.id)
            )
            
            return {
                "indexed": True,
                "search_index_id": str(search_index.id),
                "state": {
                    "indexed": True,
                    "search_index_id": str(search_index.id)
                }
            }
        except Exception as e:
            logger.error(
                "Failed to index listing for marketplace search (non-critical)",
                workflow_instance_id=str(instance.id),
                listing_id=str(listing.id),
                asset_id=str(asset.id),
                error=str(e),
                exc_info=True
            )
            # Don't fail workflow on indexing errors - log and continue
            return {
                "indexed": False,
                "error": str(e),
                "state": {
                    "indexed": False,
                    "error": str(e)
                }
            }
    
    @staticmethod
    def _send_notifications_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Send notifications about marketplace publication.
        
        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step
            
        Returns:
            Task output with notification results
        """
        listing_id = instance.state_data.get("listing_id")
        send_notifications = input_data.get("send_notifications", True)
        
        if not listing_id:
            logger.warning(
                "Notifications skipped (missing listing_id)",
                workflow_instance_id=str(instance.id)
            )
            return {
                "notifications_sent": False,
                "reason": "Missing listing_id"
            }
        
        if not send_notifications:
            logger.info(
                "Notifications disabled, skipping",
                workflow_instance_id=str(instance.id),
                listing_id=listing_id
            )
            return {
                "notifications_sent": False,
                "reason": "send_notifications is False"
            }
        
        listing = Listing.objects.get(id=listing_id)
        
        # Log notification (email template can be added later)
        try:
            logger.info(
                "Marketplace publication notification logged",
                workflow_instance_id=str(instance.id),
                listing_id=str(listing.id),
                asset_id=str(listing.asset.id),
                tenant_id=str(listing.tenant.id),
                title=listing.metadata_json.get("title") if listing.metadata_json else None
            )
            
            # TODO: Implement actual notification sending when notification system is ready
            # This would involve:
            # 1. Getting notification recipients (tenant admins, asset owners, subscribers)
            # 2. Sending email notifications about new marketplace listing
            # 3. Sending in-app notifications
            
            return {
                "notifications_sent": True,
                "notification_type": "logged"
            }
        except Exception as e:
            logger.error(
                "Failed to log marketplace publication notification",
                workflow_instance_id=str(instance.id),
                listing_id=str(listing.id),
                error=str(e),
                exc_info=True
            )
            # Don't fail workflow on notification errors
            return {
                "notifications_sent": False,
                "error": str(e)
            }
    
    @staticmethod
    def _audit_logging_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Create audit log entry for marketplace publication.
        
        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step
            
        Returns:
            Task output with audit event ID
        """
        tenant_id = input_data.get("tenant_id") or instance.tenant_id
        listing_id = instance.state_data.get("listing_id")
        asset_id = instance.state_data.get("asset_id")
        triggered_by_id = input_data.get("triggered_by_id") or instance.created_by_id
        
        if not tenant_id:
            raise ValueError("tenant_id is required")
        if not listing_id:
            raise ValueError("listing_id is required (from previous step)")
        
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        tenant = Tenant.objects.get(id=tenant_id)
        user = User.objects.get(id=triggered_by_id) if triggered_by_id else None
        
        listing = Listing.objects.get(id=listing_id)
        
        # Get validation results and other state data
        validation_results = instance.state_data.get("validation_results", {})
        pricing_model = instance.state_data.get("pricing_model", listing.pricing_model)
        license_info = instance.state_data.get("license_info", {})
        
        # Create audit event
        audit_event = create_audit_event(
            resource_type="LISTING",
            action="MARKETPLACE_PUBLISHED",
            actor_user=user,
            tenant=tenant,
            resource_id=str(listing.id),
            details={
                "listing_id": str(listing.id),
                "asset_id": str(listing.asset.id),
                "pricing_model": pricing_model,
                "title": listing.metadata_json.get("title") if listing.metadata_json else None,
                "license_summary": license_info.get("license_summary"),
                "validation_results": validation_results,
                "published_at": listing.published_at.isoformat() if listing.published_at else None,
                "workflow_instance_id": str(instance.id)
            }
        )
        
        logger.info(
            "Audit log created",
            workflow_instance_id=str(instance.id),
            listing_id=str(listing.id),
            audit_event_id=str(audit_event.id) if audit_event else None
        )
        
        return {
            "audit_event_id": str(audit_event.id) if audit_event else None,
            "state": {
                "audit_event_id": str(audit_event.id) if audit_event else None
            }
        }
    
    # Compensation tasks
    
    @staticmethod
    @transaction.atomic
    def _rollback_listing_creation_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """Rollback listing creation (delete listing)"""
        listing_id = instance.state_data.get("listing_id")
        existing_listing = instance.state_data.get("existing_listing", False)
        
        if not listing_id:
            return {"rolled_back": True}
        
        # Only delete if we created it (not if it already existed)
        if not existing_listing:
            try:
                listing = Listing.objects.get(id=listing_id)
                listing.delete()
                logger.info(
                    "Listing creation rolled back (deleted)",
                    workflow_instance_id=str(instance.id),
                    listing_id=listing_id
                )
            except Listing.DoesNotExist:
                logger.warning(
                    "Listing not found for rollback",
                    workflow_instance_id=str(instance.id),
                    listing_id=listing_id
                )
            except Exception as e:
                logger.warning(
                    "Listing rollback failed",
                    workflow_instance_id=str(instance.id),
                    listing_id=listing_id,
                    error=str(e)
                )
        else:
            logger.info(
                "Listing rollback skipped (existing listing)",
                workflow_instance_id=str(instance.id),
                listing_id=listing_id
            )
        
        return {"rolled_back": True}
    
    @staticmethod
    @transaction.atomic
    def _rollback_publication_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """Rollback publication (set listing to UNLISTED)"""
        listing_id = instance.state_data.get("listing_id")
        
        if listing_id:
            try:
                listing = Listing.objects.get(id=listing_id)
                if listing.status == ListingStatus.PUBLISHED:
                    listing.status = ListingStatus.UNLISTED
                    listing.published_at = None
                    listing.save(update_fields=["status", "published_at"])
                    logger.info(
                        "Publication rolled back (set to UNLISTED)",
                        workflow_instance_id=str(instance.id),
                        listing_id=listing_id
                    )
            except Listing.DoesNotExist:
                logger.warning(
                    "Listing not found for publication rollback",
                    workflow_instance_id=str(instance.id),
                    listing_id=listing_id
                )
            except Exception as e:
                logger.warning(
                    "Publication rollback failed",
                    workflow_instance_id=str(instance.id),
                    listing_id=listing_id,
                    error=str(e)
                )
        
        return {"rolled_back": True}
    
    @staticmethod
    @transaction.atomic
    def _rollback_indexing_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """Rollback search indexing (delete search index)"""
        search_index_id = instance.state_data.get("search_index_id")
        asset_id = instance.state_data.get("asset_id")
        
        if search_index_id:
            try:
                from hub.apps.search.models import SearchIndex
                search_index = SearchIndex.objects.get(id=search_index_id)
                search_index.delete()
                logger.info(
                    "Search index rolled back (deleted)",
                    workflow_instance_id=str(instance.id),
                    search_index_id=search_index_id
                )
            except Exception as e:
                logger.warning(
                    "Search index rollback failed",
                    workflow_instance_id=str(instance.id),
                    search_index_id=search_index_id,
                    error=str(e)
                )
        elif asset_id:
            # Fallback: delete by asset_id
            try:
                SearchIndexer.delete_index(
                    tenant_id=str(instance.tenant_id),
                    resource_type="ASSET",
                    resource_id=str(asset_id)
                )
                logger.info(
                    "Search index rolled back (deleted by asset_id)",
                    workflow_instance_id=str(instance.id),
                    asset_id=str(asset_id)
                )
            except Exception as e:
                logger.warning(
                    "Search index rollback failed (by asset_id)",
                    workflow_instance_id=str(instance.id),
                    asset_id=str(asset_id),
                    error=str(e)
                )
        
        return {"rolled_back": True}
    
    @classmethod
    @transaction.atomic
    def execute(
        cls,
        tenant_id: str,
        asset_id: str,
        metadata_json: Optional[Dict[str, Any]] = None,
        pricing_model: Optional[str] = None,
        price_amount: Optional[float] = None,
        currency: str = "USD",
        send_notifications: bool = True,
        triggered_by_id: Optional[str] = None,
        engine: Optional[WorkflowEngine] = None,
        registry: Optional[WorkflowRegistry] = None
    ) -> Dict[str, Any]:
        """
        Execute marketplace publication workflow.
        
        Args:
            tenant_id: Tenant ID
            asset_id: Asset ID to publish
            metadata_json: Optional listing metadata (title, description, tags, etc.)
            pricing_model: Pricing model (FREE, FREE_AUTO_APPROVE, REQUEST_APPROVAL)
            price_amount: Price amount (required for REQUEST_APPROVAL)
            currency: Currency code (default: USD)
            send_notifications: Whether to send notifications (default: True)
            triggered_by_id: User ID who triggered the publication (optional)
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
            "asset_id": asset_id,
            "metadata_json": metadata_json or {},
            "pricing_model": pricing_model or PricingModel.FREE,
            "price_amount": price_amount,
            "currency": currency,
            "send_notifications": send_notifications,
            "triggered_by_id": triggered_by_id
        }
        
        # Create workflow instance
        workflow_instance = engine.create_instance(
            workflow_name=cls.WORKFLOW_NAME,
            input_data=workflow_input,
            tenant_id=tenant_id,
            created_by_id=triggered_by_id
        )
        
        # Initialize state_data from input_data
        if not workflow_instance.state_data:
            workflow_instance.state_data = workflow_input.copy()
            workflow_instance.save(update_fields=['state_data'])
        
        # Start and execute workflow
        workflow_instance = engine.start_instance(str(workflow_instance.id))
        workflow_instance = engine.execute_instance(str(workflow_instance.id))
        
        # Check workflow status
        if workflow_instance.status == WorkflowStatus.COMPLETED:
            logger.info(
                "Marketplace publication workflow completed",
                workflow_instance_id=str(workflow_instance.id),
                tenant_id=tenant_id,
                asset_id=asset_id,
                listing_id=workflow_instance.state_data.get("listing_id")
            )
            return {
                "success": True,
                "workflow_instance_id": str(workflow_instance.id),
                "asset_id": asset_id,
                "listing_id": workflow_instance.state_data.get("listing_id"),
                "published": workflow_instance.state_data.get("published", False),
                "output_data": workflow_instance.output_data
            }
        else:
            error_message = workflow_instance.error_message or "Workflow execution failed"
            logger.error(
                "Marketplace publication workflow failed",
                workflow_instance_id=str(workflow_instance.id),
                tenant_id=tenant_id,
                asset_id=asset_id,
                error=error_message
            )
            raise ValueError(f"Marketplace publication workflow failed: {error_message}")

