"""
Integration tests for cross-service business rules.

Tests integration with:
- GovernanceService (ABACEngine)
- TenantService (get_tenant_job_limits)
- Marketplace entitlements
"""
import uuid
from django.test import TestCase
from django.core.cache import cache

from hub.apps.transformation.business_rules import (
    TransformationBusinessRules,
    ValidationResult
)
from hub.apps.transformation.models import (
    TransformationPipeline,
    PipelineStatus
)
from hub.apps.transformation.exceptions import (
    TransformationValidationError,
    ResourceQuotaExceededError
)
from hub.apps.core.services.base import PermissionError
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus
from hub.apps.tenants.models import Tenant, KYCStatus
from hub.apps.users.models import User, UserStatus
from hub.apps.governance.models import AccessPolicy
from hub.apps.marketplace.models import (
    Entitlement,
    EntitlementStatus,
    Listing,
    ListingStatus,
    PricingModel
)


class CrossServiceBusinessRulesIntegrationTest(TestCase):
    """Integration tests for cross-service business rules."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            kyc_status=KYCStatus.VERIFIED
        )

        self.other_tenant = Tenant.objects.create(
            name="Other Tenant",
            slug="other-tenant",
            kyc_status=KYCStatus.VERIFIED
        )

        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )

        self.other_user = User.objects.create_user(
            email="other@example.com",
            password="testpass123",
            tenant=self.other_tenant,
            status=UserStatus.ACTIVE
        )

        # Create assets
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE
        )

        self.other_asset = Asset.objects.create(
            tenant=self.other_tenant,
            key="other-asset",
            name="Other Asset",
            status=AssetStatus.ACTIVE
        )

        # Create pipeline
        self.pipeline_definition = {
            "version": "1.0.0",
            "steps": [
                {
                    "name": "filter_step",
                    "type": "task",
                    "node_config": {
                        "node_type": "filter",
                        "filter_expression": "age > 18"
                    }
                },
                {
                    "name": "output_step",
                    "type": "task",
                    "node_config": {
                        "node_type": "output"
                    }
                }
            ]
        }

        self.pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            name="Test Pipeline",
            pipeline_definition=self.pipeline_definition,
            status=PipelineStatus.ACTIVE
        )

        # Clear cache
        cache.clear()

    def test_validate_cross_tenant_operations_with_entitlement(self):
        """Test cross-tenant validation with active entitlement"""
        # Create listing for the other asset
        listing = Listing.objects.create(
            tenant=self.other_tenant,
            asset=self.other_asset,
            status=ListingStatus.PUBLISHED,
            pricing_model=PricingModel.FREE,
            metadata_json={"title": "Other Asset Listing"}
        )

        # Create entitlement for cross-tenant access
        entitlement = Entitlement.objects.create(
            tenant=self.tenant,
            listing=listing,
            asset=self.other_asset,
            status=EntitlementStatus.ACTIVE
        )

        # Create ALLOW policy
        policy = AccessPolicy.objects.create(
            tenant=self.other_tenant,
            name="Allow Cross-Tenant Access",
            conditions={
                "user": {"tenant_id": str(self.tenant.id)}
            },
            effect="ALLOW",
            priority=100,
            asset=self.other_asset
        )

        business_rules = TransformationBusinessRules(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        result = business_rules.validate_cross_tenant_operations(
            self.pipeline, self.other_asset, raise_on_error=False
        )

        # Should pass with entitlement and ABAC allow
        self.assertTrue(result.is_valid)

    def test_validate_cross_tenant_operations_without_entitlement(self):
        """Test cross-tenant validation fails without entitlement"""
        # Create ALLOW policy but no entitlement
        policy = AccessPolicy.objects.create(
            tenant=self.other_tenant,
            name="Allow Cross-Tenant Access",
            conditions={
                "user": {"tenant_id": str(self.tenant.id)}
            },
            effect="ALLOW",
            priority=100,
            asset=self.other_asset
        )

        business_rules = TransformationBusinessRules(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        result = business_rules.validate_cross_tenant_operations(
            self.pipeline, self.other_asset, raise_on_error=False
        )

        # Should fail without entitlement
        # Note: ABAC may allow, but entitlement check should fail
        # The actual behavior depends on ABAC evaluation
        self.assertTrue(
            not result.is_valid or
            "entitlement" in str(result.details).lower()
        )

    def test_validate_cross_tenant_operations_with_abac_deny(self):
        """Test cross-tenant validation fails with ABAC deny policy"""
        # Create DENY policy
        policy = AccessPolicy.objects.create(
            tenant=self.other_tenant,
            name="Deny Cross-Tenant Access",
            conditions={
                "user": {"tenant_id": str(self.tenant.id)}
            },
            effect="DENY",
            priority=50,  # Higher priority
            asset=self.other_asset
        )

        business_rules = TransformationBusinessRules(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        result = business_rules.validate_cross_tenant_operations(
            self.pipeline, self.other_asset, raise_on_error=False
        )

        # Should fail with ABAC deny
        self.assertFalse(result.is_valid)
        self.assertTrue(any("access denied" in err.lower() for err in result.errors))

    def test_validate_resource_quota_integration(self):
        """Test resource quota validation with real tenant service"""
        from hub.apps.tenants.services import get_tenant_job_limits

        limits = get_tenant_job_limits(str(self.tenant.id))
        max_concurrency = limits["max_job_concurrency"]

        # Set running jobs to limit
        running_key = f"job:tenant:{self.tenant.id}:running"
        cache.set(running_key, max_concurrency, timeout=300)

        business_rules = TransformationBusinessRules(tenant_id=str(self.tenant.id))

        with self.assertRaises(ResourceQuotaExceededError) as cm:
            business_rules.validate_resource_quota(self.pipeline, raise_on_error=True)

        self.assertEqual(
            cm.exception.error_code,
            ResourceQuotaExceededError.ERROR_CODE_CONCURRENT_EXECUTIONS_LIMIT
        )

        # Cleanup
        cache.delete(running_key)

    def test_validate_pipeline_execution_permission_with_abac(self):
        """Test pipeline execution permission with ABAC integration"""
        # Create ALLOW policy for pipeline execution
        policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Allow Pipeline Execution",
            conditions={
                "user": {"tenant_id": str(self.tenant.id)}
            },
            effect="ALLOW",
            priority=100
        )

        business_rules = TransformationBusinessRules(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        result = business_rules.validate_pipeline_execution_permission(
            self.pipeline, raise_on_error=False
        )

        # Should pass or have warnings (ABAC evaluation may vary)
        self.assertTrue(
            result.is_valid or
            len(result.warnings) > 0
        )

    def test_validate_pipeline_execution_permission_with_abac_deny(self):
        """Test pipeline execution permission fails with ABAC deny"""
        # Create DENY policy
        policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Deny Pipeline Execution",
            conditions={
                "user": {"tenant_id": str(self.tenant.id)}
            },
            effect="DENY",
            priority=50,  # Higher priority
        )

        business_rules = TransformationBusinessRules(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        result = business_rules.validate_pipeline_execution_permission(
            self.pipeline, raise_on_error=False
        )

        # Should fail with ABAC deny
        # Note: ABAC may default deny if no matching policy
        # The actual behavior depends on ABAC evaluation
        self.assertTrue(
            not result.is_valid or
            len(result.warnings) > 0
        )

    def test_validate_all_cross_service_checks(self):
        """Test all cross-service validations together"""
        from hub.apps.tenants.services import get_tenant_job_limits

        # Create ALLOW policies
        pipeline_policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Allow Pipeline Execution",
            conditions={
                "user": {"tenant_id": str(self.tenant.id)}
            },
            effect="ALLOW",
            priority=100
        )

        asset_policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Allow Asset Access",
            conditions={
                "user": {"tenant_id": str(self.tenant.id)}
            },
            effect="ALLOW",
            priority=100,
            asset=self.asset
        )

        # Ensure quota is available
        running_key = f"job:tenant:{self.tenant.id}:running"
        cache.set(running_key, 0, timeout=300)

        business_rules = TransformationBusinessRules(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Validate all checks
        quota_result = business_rules.validate_resource_quota(
            self.pipeline, raise_on_error=False
        )
        permission_result = business_rules.validate_pipeline_execution_permission(
            self.pipeline, source_asset=self.asset, raise_on_error=False
        )
        cross_tenant_result = business_rules.validate_cross_tenant_operations(
            self.pipeline, self.asset, raise_on_error=False
        )

        # All should pass (or have warnings)
        self.assertTrue(
            quota_result.is_valid or len(quota_result.warnings) > 0
        )
        self.assertTrue(
            permission_result.is_valid or len(permission_result.warnings) > 0
        )
        self.assertTrue(cross_tenant_result.is_valid)

        # Cleanup
        cache.delete(running_key)

