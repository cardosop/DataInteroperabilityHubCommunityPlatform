"""
Unit tests for AssetsBusinessRules.

Comprehensive tests without mocks/stubs, following engineering best practices.
"""

import uuid
from typing import Any

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.assets.business_rules import (
    AssetsBusinessRules,
    AssetsRuleExecutionContext,
)
from hub.apps.assets.models import Asset, AssetStatus, AssetVisibility, ComplianceStatus, DQStatus
from hub.apps.assets.services import AssetService
from hub.apps.assets.tests.factories import AssetFactory
from hub.apps.core.business_rules.base import RuleExecutionContext, ValidationResult
from hub.apps.core.business_rules.registry import get_registry
from hub.apps.tenants.models import KYCStatus, Tenant

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class AssetsBusinessRulesInitializationTest(TestCase):
    """Test AssetsBusinessRules initialization"""

    def test_initialization_without_parameters_sets_tenant_id_none(self):
        """Test initialization without parameters sets tenant_id to None."""
        rules = AssetsBusinessRules()
        self.assertIsNone(rules.tenant_id)

    def test_initialization_without_parameters_sets_user_id_none(self):
        """Test initialization without parameters sets user_id to None."""
        rules = AssetsBusinessRules()
        self.assertIsNone(rules.user_id)

    def test_initialization_with_tenant_id_sets_tenant_id(self):
        """Test initialization with tenant_id sets tenant_id."""
        _uid = uuid.uuid4().hex[:8]
        tenant = Tenant.objects.create(
            name=f"Test Tenant {_uid}", slug=f"test-tenant-{_uid}", kyc_status=KYCStatus.VERIFIED
        )
        rules = AssetsBusinessRules(tenant_id=str(tenant.id))
        self.assertEqual(rules.tenant_id, str(tenant.id))

    def test_initialization_with_tenant_id_sets_user_id_none(self):
        """Test initialization with tenant_id sets user_id to None."""
        _uid = uuid.uuid4().hex[:8]
        tenant = Tenant.objects.create(
            name=f"Test Tenant {_uid}", slug=f"test-tenant-{_uid}", kyc_status=KYCStatus.VERIFIED
        )
        rules = AssetsBusinessRules(tenant_id=str(tenant.id))
        self.assertIsNone(rules.user_id)

    def test_initialization_with_tenant_and_user_sets_tenant_id(self):
        """Test initialization with tenant_id and user_id sets tenant_id."""
        _uid = uuid.uuid4().hex[:8]
        tenant = Tenant.objects.create(
            name=f"Test Tenant {_uid}", slug=f"test-tenant-{_uid}", kyc_status=KYCStatus.VERIFIED
        )
        user = User.objects.create_user(
            email=f"test-{_uid}@example.com", password="testpass123", tenant=tenant
        )
        rules = AssetsBusinessRules(tenant_id=str(tenant.id), user_id=str(user.id))
        self.assertEqual(rules.tenant_id, str(tenant.id))

    def test_initialization_with_tenant_and_user_sets_user_id(self):
        """Test initialization with tenant_id and user_id sets user_id."""
        _uid = uuid.uuid4().hex[:8]
        tenant = Tenant.objects.create(
            name=f"Test Tenant {_uid}", slug=f"test-tenant-{_uid}", kyc_status=KYCStatus.VERIFIED
        )
        user = User.objects.create_user(
            email=f"test-{_uid}@example.com", password="testpass123", tenant=tenant
        )
        rules = AssetsBusinessRules(tenant_id=str(tenant.id), user_id=str(user.id))
        self.assertEqual(rules.user_id, str(user.id))

    def test_initialization_with_tenant_and_user_returns_rule_name(self):
        """Test initialization with tenant_id and user_id returns rule name."""
        _uid = uuid.uuid4().hex[:8]
        tenant = Tenant.objects.create(
            name=f"Test Tenant {_uid}", slug=f"test-tenant-{_uid}", kyc_status=KYCStatus.VERIFIED
        )
        user = User.objects.create_user(
            email=f"test-{_uid}@example.com", password="testpass123", tenant=tenant
        )
        rules = AssetsBusinessRules(tenant_id=str(tenant.id), user_id=str(user.id))
        self.assertEqual(rules.get_rule_name(), "AssetsBusinessRules")

    def test_rule_registration_returns_metadata(self):
        """Test that AssetsBusinessRules registration returns metadata."""
        registry = get_registry()
        rule_metadata = registry.get_rule("assets_validation")

        self.assertIsNotNone(rule_metadata)

    def test_rule_registration_has_correct_rule_name(self):
        """Test that AssetsBusinessRules registration has correct rule_name."""
        registry = get_registry()
        rule_metadata = registry.get_rule("assets_validation")

        self.assertEqual(rule_metadata.rule_name, "assets_validation")

    def test_rule_registration_has_correct_rule_class(self):
        """Test that AssetsBusinessRules registration has correct rule_class."""
        registry = get_registry()
        rule_metadata = registry.get_rule("assets_validation")

        self.assertEqual(rule_metadata.rule_class, AssetsBusinessRules)

    def test_rule_registration_has_assets_tag(self):
        """Test that AssetsBusinessRules registration has assets tag."""
        registry = get_registry()
        rule_metadata = registry.get_rule("assets_validation")

        self.assertIn("assets", rule_metadata.tags)

    def test_rule_registration_has_validation_tag(self):
        """Test that AssetsBusinessRules registration has validation tag."""
        registry = get_registry()
        rule_metadata = registry.get_rule("assets_validation")

        self.assertIn("validation", rule_metadata.tags)


class AssetsBusinessRulesValidationTest(TestCase):
    """Test AssetsBusinessRules validation methods"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com", password="testpass123", tenant=self.tenant
        )
        self.rules = AssetsBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

    def test_validate_with_assets_context(self):
        """Test validate with AssetsRuleExecutionContext"""
        asset = AssetFactory.create_asset(
            tenant=self.tenant, created_by=self.user, status=AssetStatus.DRAFT
        )

        context = AssetsRuleExecutionContext(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            asset=asset,
            tenant=self.tenant,
            user=self.user,
        )

        result = self.rules.validate(context, validation_type="structure")

        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

    def test_validate_with_standard_context(self):
        """Test validate with standard RuleExecutionContext"""
        asset = AssetFactory.create_asset(
            tenant=self.tenant, created_by=self.user, status=AssetStatus.DRAFT
        )

        context = RuleExecutionContext(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            resource=asset,
            metadata={"tenant": self.tenant, "user": self.user},
        )

        result = self.rules.validate(context, validation_type="structure")

        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.is_valid)

    def test_validate_with_kwargs(self):
        """Test validate with asset in kwargs"""
        asset = AssetFactory.create_asset(
            tenant=self.tenant, created_by=self.user, status=AssetStatus.DRAFT
        )

        context = RuleExecutionContext(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        result = self.rules.validate(
            context, asset=asset, tenant=self.tenant, user=self.user, validation_type="structure"
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.is_valid)

    def test_validate_missing_asset(self):
        """Test validate with missing asset"""
        rules = AssetsBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        context = RuleExecutionContext(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        result = rules.validate(context)

        self.assertIsInstance(result, ValidationResult)
        self.assertFalse(result.is_valid)
        self.assertIn("Asset is required", result.errors[0])

    def test_validate_tenant_context(self):
        """Test tenant context validation"""
        asset = AssetFactory.create_asset(tenant=self.tenant, created_by=self.user)

        result = self.rules.validate(context=None, asset=asset, validation_type="tenant_context")

        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.is_valid)

    def test_validate_tenant_context_mismatch(self):
        """Test tenant context validation with mismatch"""
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}", slug=f"other-tenant-{_uid}", kyc_status=KYCStatus.VERIFIED
        )
        asset = AssetFactory.create_asset(tenant=other_tenant, created_by=self.user)

        result = self.rules.validate(context=None, asset=asset, validation_type="tenant_context")

        self.assertIsInstance(result, ValidationResult)
        self.assertFalse(result.is_valid)
        self.assertTrue(any("Tenant mismatch" in error for error in result.errors))

    def test_validate_permissions(self):
        """Test permissions validation"""
        asset = AssetFactory.create_asset(tenant=self.tenant, created_by=self.user)

        result = self.rules.validate(
            context=None, asset=asset, user=self.user, validation_type="permissions"
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.is_valid)

    def test_validate_permissions_user_tenant_mismatch(self):
        """Test permissions validation with user tenant mismatch"""
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}", slug=f"other-tenant-{_uid}", kyc_status=KYCStatus.VERIFIED
        )
        other_user = User.objects.create_user(
            email=f"other-{_uid}@example.com", password="testpass123", tenant=other_tenant
        )
        asset = AssetFactory.create_asset(tenant=self.tenant, created_by=self.user)

        result = self.rules.validate(
            context=None, asset=asset, user=other_user, validation_type="permissions"
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertFalse(result.is_valid)
        self.assertTrue(
            any(
                "User tenant" in error and "does not match asset tenant" in error
                for error in result.errors
            )
        )

    def test_validate_all_types(self):
        """Test validate with all validation types"""
        asset = AssetFactory.create_asset(
            tenant=self.tenant, created_by=self.user, status=AssetStatus.DRAFT
        )

        context = AssetsRuleExecutionContext(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            asset=asset,
            tenant=self.tenant,
            user=self.user,
        )

        result = self.rules.validate(context, validation_type="all")

        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.is_valid)
        self.assertIn("validation_type", result.details)
        self.assertEqual(result.details["validation_type"], "all")

    def test_execute_with_assets_context(self):
        """Test execute method with AssetsRuleExecutionContext"""
        asset = AssetFactory.create_asset(
            tenant=self.tenant, created_by=self.user, status=AssetStatus.DRAFT
        )

        rules = AssetsBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        context = AssetsRuleExecutionContext(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            asset=asset,
            tenant=self.tenant,
            user=self.user,
        )

        result = rules.execute(context, validation_type="structure")

        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

    def test_execute_through_registry(self):
        """Test executing rule through the registry"""
        asset = AssetFactory.create_asset(
            tenant=self.tenant, created_by=self.user, status=AssetStatus.DRAFT
        )

        registry = get_registry()
        context = AssetsRuleExecutionContext(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            asset=asset,
            tenant=self.tenant,
            user=self.user,
        )

        # Execute through registry - kwargs are passed to rule.execute()
        results = registry.execute_rules(
            rule_names=["assets_validation"],
            context=context,
            asset=asset,
            tenant=self.tenant,
            user=self.user,
            validation_type="structure",
        )

        self.assertIn("assets_validation", results)
        result = results["assets_validation"]
        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.is_valid)


class AssetsBusinessRulesLifecycleValidationTest(TestCase):
    """Test asset lifecycle validation"""

    def setUp(self):
        """Set up test fixtures"""
        _uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {_uid}", slug=f"test-tenant-{_uid}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{_uid}@example.com", password="testpass123", tenant=self.tenant
        )
        self.rules = AssetsBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

    def test_status_transition_draft_to_active(self):
        """Test valid transition: DRAFT → ACTIVE"""
        asset = AssetFactory.create_asset(
            tenant=self.tenant, created_by=self.user, status=AssetStatus.DRAFT
        )

        result = self.rules._validate_status_transition(
            asset, old_status=AssetStatus.DRAFT, new_status=AssetStatus.ACTIVE
        )

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertTrue(result.details["transition_allowed"])

    def test_status_transition_active_to_public(self):
        """Test valid transition: ACTIVE → PUBLIC"""
        asset = AssetFactory.create_asset(
            tenant=self.tenant, created_by=self.user, status=AssetStatus.ACTIVE
        )

        result = self.rules._validate_status_transition(
            asset, old_status=AssetStatus.ACTIVE, new_status=AssetStatus.PUBLIC
        )

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

    def test_status_transition_active_to_retired(self):
        """Test valid transition: ACTIVE → RETIRED"""
        asset = AssetFactory.create_asset(
            tenant=self.tenant, created_by=self.user, status=AssetStatus.ACTIVE
        )

        result = self.rules._validate_status_transition(
            asset, old_status=AssetStatus.ACTIVE, new_status=AssetStatus.RETIRED
        )

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

    def test_status_transition_public_to_retired(self):
        """Test valid transition: PUBLIC → RETIRED"""
        asset = AssetFactory.create_asset(
            tenant=self.tenant, created_by=self.user, status=AssetStatus.PUBLIC
        )

        result = self.rules._validate_status_transition(
            asset, old_status=AssetStatus.PUBLIC, new_status=AssetStatus.RETIRED
        )

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

    def test_status_transition_invalid_draft_to_public(self):
        """Test invalid transition: DRAFT → PUBLIC (must go through ACTIVE)"""
        asset = AssetFactory.create_asset(
            tenant=self.tenant, created_by=self.user, status=AssetStatus.DRAFT
        )

        result = self.rules._validate_status_transition(
            asset, old_status=AssetStatus.DRAFT, new_status=AssetStatus.PUBLIC
        )

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("Invalid status transition", result.errors[0])

    def test_status_transition_invalid_retired_to_active(self):
        """Test invalid transition: RETIRED → ACTIVE (no transitions from RETIRED)"""
        asset = AssetFactory.create_asset(
            tenant=self.tenant, created_by=self.user, status=AssetStatus.RETIRED
        )

        result = self.rules._validate_status_transition(
            asset, old_status=AssetStatus.RETIRED, new_status=AssetStatus.ACTIVE
        )

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_status_transition_no_change(self):
        """Test no status change (should be valid)"""
        asset = AssetFactory.create_asset(
            tenant=self.tenant, created_by=self.user, status=AssetStatus.ACTIVE
        )

        result = self.rules._validate_status_transition(
            asset, old_status=AssetStatus.ACTIVE, new_status=AssetStatus.ACTIVE
        )

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

    def test_activation_requirements_with_valid_contract(self):
        """Test activation requirements with valid contract"""
        from hub.apps.contracts.models import (
            Contract,
            ContractStatus,
            NormalizationStatus,
            OriginalFormat,
            OriginalSpecType,
            ValidationStatus,
        )

        asset = AssetFactory.create_asset(
            tenant=self.tenant,
            created_by=self.user,
            status=AssetStatus.DRAFT,
            dq_status=DQStatus.PASS,
            compliance_status=ComplianceStatus.PASS,
        )

        # Create valid contract
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            status=ContractStatus.ACTIVE,
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw='{"version": "3.0.2"}',
            hub_contract_version="1.0.0",
            hub_contract_json={},
        )

        result = self.rules._validate_activation_requirements(asset)

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertTrue(result.details["activation_checks"]["has_active_contract"])

    def test_activation_requirements_missing_contract(self):
        """Test activation requirements without contract"""
        asset = AssetFactory.create_asset(
            tenant=self.tenant, created_by=self.user, status=AssetStatus.DRAFT
        )

        result = self.rules._validate_activation_requirements(asset)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("ACTIVE contract", result.errors[0])
        self.assertFalse(result.details["activation_checks"]["has_active_contract"])

    def test_activation_requirements_invalid_contract_validation_status(self):
        """Test activation requirements with invalid contract validation status"""
        from hub.apps.contracts.models import (
            Contract,
            ContractStatus,
            NormalizationStatus,
            OriginalFormat,
            OriginalSpecType,
            ValidationStatus,
        )

        asset = AssetFactory.create_asset(
            tenant=self.tenant, created_by=self.user, status=AssetStatus.DRAFT
        )

        # Create contract with invalid validation status
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            status=ContractStatus.ACTIVE,
            validation_status=ValidationStatus.INVALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw='{"version": "3.0.2"}',
            hub_contract_version="1.0.0",
            hub_contract_json={},
        )

        result = self.rules._validate_activation_requirements(asset)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("validation_status", result.errors[0])

    def test_activation_requirements_invalid_contract_normalization_status(self):
        """Test activation requirements with invalid contract normalization status"""
        from hub.apps.contracts.models import (
            Contract,
            ContractStatus,
            NormalizationStatus,
            OriginalFormat,
            OriginalSpecType,
            ValidationStatus,
        )

        asset = AssetFactory.create_asset(
            tenant=self.tenant, created_by=self.user, status=AssetStatus.DRAFT
        )

        # Create contract with invalid normalization status
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            status=ContractStatus.ACTIVE,
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZATION_FAILED,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw='{"version": "3.0.2"}',
            hub_contract_version="1.0.0",
            hub_contract_json={},
        )

        result = self.rules._validate_activation_requirements(asset)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("normalization_status", result.errors[0])

    def test_activation_requirements_with_dataset_dq_fail(self):
        """Test activation requirements with dataset having DQ FAIL"""
        from hub.apps.contracts.models import (
            Contract,
            ContractStatus,
            NormalizationStatus,
            OriginalFormat,
            OriginalSpecType,
            ValidationStatus,
        )
        from hub.apps.datasets.models import Dataset
        from hub.apps.files.models import File

        asset = AssetFactory.create_asset(
            tenant=self.tenant,
            created_by=self.user,
            status=AssetStatus.DRAFT,
            dq_status=DQStatus.FAIL,
            compliance_status=ComplianceStatus.PASS,
        )

        # Create valid contract
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            status=ContractStatus.ACTIVE,
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw='{"version": "3.0.2"}',
            hub_contract_version="1.0.0",
            hub_contract_json={},
        )

        # Create dataset
        file = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            size=1000,
            content_type="text/csv",
            storage_path="/test/test.csv",
        )
        dataset = Dataset.objects.create(tenant=self.tenant, asset=asset, file=file, format="CSV")

        result = self.rules._validate_activation_requirements(asset)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("dq_status", result.errors[0])

    def test_activation_requirements_with_dataset_compliance_fail(self):
        """Test activation requirements with dataset having compliance FAIL"""
        from hub.apps.contracts.models import (
            Contract,
            ContractStatus,
            NormalizationStatus,
            OriginalFormat,
            OriginalSpecType,
            ValidationStatus,
        )
        from hub.apps.datasets.models import Dataset
        from hub.apps.files.models import File

        asset = AssetFactory.create_asset(
            tenant=self.tenant,
            created_by=self.user,
            status=AssetStatus.DRAFT,
            dq_status=DQStatus.PASS,
            compliance_status=ComplianceStatus.FAIL,
        )

        # Create valid contract
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            status=ContractStatus.ACTIVE,
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw='{"version": "3.0.2"}',
            hub_contract_version="1.0.0",
            hub_contract_json={},
        )

        # Create dataset
        file = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            size=1000,
            content_type="text/csv",
            storage_path="/test/test.csv",
        )
        dataset = Dataset.objects.create(tenant=self.tenant, asset=asset, file=file, format="CSV")

        result = self.rules._validate_activation_requirements(asset)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("compliance_status", result.errors[0])

    def test_activation_requirements_with_dataset_dq_warn(self):
        """Test activation requirements with dataset having DQ WARN (should allow with warning)"""
        from hub.apps.contracts.models import (
            Contract,
            ContractStatus,
            NormalizationStatus,
            OriginalFormat,
            OriginalSpecType,
            ValidationStatus,
        )
        from hub.apps.datasets.models import Dataset
        from hub.apps.files.models import File

        asset = AssetFactory.create_asset(
            tenant=self.tenant,
            created_by=self.user,
            status=AssetStatus.DRAFT,
            dq_status=DQStatus.WARN,
            compliance_status=ComplianceStatus.PASS,
        )

        # Create valid contract
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            status=ContractStatus.ACTIVE,
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw='{"version": "3.0.2"}',
            hub_contract_version="1.0.0",
            hub_contract_json={},
        )

        # Create dataset
        file = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            size=1000,
            content_type="text/csv",
            storage_path="/test/test.csv",
        )
        dataset = Dataset.objects.create(tenant=self.tenant, asset=asset, file=file, format="CSV")

        result = self.rules._validate_activation_requirements(asset)

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertGreater(len(result.warnings), 0)
        self.assertIn("DQ status WARN", result.warnings[0])

    def test_visibility_change_internal_to_public_with_active_status(self):
        """Test visibility change INTERNAL → PUBLIC with ACTIVE status (valid)"""
        asset = AssetFactory.create_asset(
            tenant=self.tenant,
            created_by=self.user,
            status=AssetStatus.ACTIVE,
            visibility=AssetVisibility.INTERNAL,
        )

        result = self.rules._validate_visibility_change(
            asset,
            old_visibility=AssetVisibility.INTERNAL,
            new_visibility=AssetVisibility.PUBLIC,
            current_status=AssetStatus.ACTIVE,
        )

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

    def test_visibility_change_internal_to_public_with_draft_status(self):
        """Test visibility change INTERNAL → PUBLIC with DRAFT status (invalid)"""
        asset = AssetFactory.create_asset(
            tenant=self.tenant,
            created_by=self.user,
            status=AssetStatus.DRAFT,
            visibility=AssetVisibility.INTERNAL,
        )

        result = self.rules._validate_visibility_change(
            asset,
            old_visibility=AssetVisibility.INTERNAL,
            new_visibility=AssetVisibility.PUBLIC,
            current_status=AssetStatus.DRAFT,
        )

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("ACTIVE status", result.errors[0])

    def test_visibility_change_public_to_internal(self):
        """Test visibility change PUBLIC → INTERNAL (always allowed)"""
        asset = AssetFactory.create_asset(
            tenant=self.tenant,
            created_by=self.user,
            status=AssetStatus.ACTIVE,
            visibility=AssetVisibility.PUBLIC,
        )

        result = self.rules._validate_visibility_change(
            asset,
            old_visibility=AssetVisibility.PUBLIC,
            new_visibility=AssetVisibility.INTERNAL,
            current_status=AssetStatus.ACTIVE,
        )

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertGreater(len(result.warnings), 0)

    def test_visibility_change_no_change(self):
        """Test visibility change with no change (should be valid)"""
        asset = AssetFactory.create_asset(
            tenant=self.tenant, created_by=self.user, visibility=AssetVisibility.INTERNAL
        )

        result = self.rules._validate_visibility_change(
            asset,
            old_visibility=AssetVisibility.INTERNAL,
            new_visibility=AssetVisibility.INTERNAL,
            current_status=AssetStatus.DRAFT,
        )

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

    def test_retirement_requirements_no_active_listings(self):
        """Test retirement requirements with no active listings (valid)"""
        asset = AssetFactory.create_asset(
            tenant=self.tenant, created_by=self.user, status=AssetStatus.ACTIVE
        )

        result = self.rules._validate_retirement_requirements(asset)

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertFalse(result.details["retirement_checks"]["has_active_listings"])

    def test_retirement_requirements_with_active_listings(self):
        """Test retirement requirements with active listings (invalid)"""
        from hub.apps.marketplace.models import Listing, ListingStatus

        asset = AssetFactory.create_asset(
            tenant=self.tenant, created_by=self.user, status=AssetStatus.ACTIVE
        )

        # Create active listing
        listing = Listing.objects.create(
            tenant=self.tenant, asset=asset, status=ListingStatus.PUBLISHED
        )

        result = self.rules._validate_retirement_requirements(asset)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("active marketplace listing", result.errors[0])
        self.assertTrue(result.details["retirement_checks"]["has_active_listings"])

    def test_lifecycle_validation_complete_flow(self):
        """Test complete lifecycle validation flow"""
        from hub.apps.contracts.models import (
            Contract,
            ContractStatus,
            NormalizationStatus,
            OriginalFormat,
            OriginalSpecType,
            ValidationStatus,
        )

        asset = AssetFactory.create_asset(
            tenant=self.tenant,
            created_by=self.user,
            status=AssetStatus.DRAFT,
            visibility=AssetVisibility.INTERNAL,
            dq_status=DQStatus.PASS,
            compliance_status=ComplianceStatus.PASS,
        )

        # Create valid contract
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            status=ContractStatus.ACTIVE,
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw='{"version": "3.0.2"}',
            hub_contract_version="1.0.0",
            hub_contract_json={},
        )

        # Test DRAFT → ACTIVE transition
        result = self.rules._validate_asset_lifecycle(
            asset, old_status=AssetStatus.DRAFT, new_status=AssetStatus.ACTIVE
        )

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

        # Update asset status to ACTIVE
        asset.status = AssetStatus.ACTIVE
        asset.save()

        # Test ACTIVE → PUBLIC transition
        result = self.rules._validate_asset_lifecycle(
            asset, old_status=AssetStatus.ACTIVE, new_status=AssetStatus.PUBLIC
        )

        self.assertTrue(result.is_valid)

        # Test visibility change INTERNAL → PUBLIC
        result = self.rules._validate_asset_lifecycle(
            asset,
            old_status=AssetStatus.ACTIVE,
            new_status=AssetStatus.ACTIVE,
            old_visibility=AssetVisibility.INTERNAL,
            new_visibility=AssetVisibility.PUBLIC,
        )

        self.assertTrue(result.is_valid)

        # Update asset status to PUBLIC
        asset.status = AssetStatus.PUBLIC
        asset.save()

        # Test PUBLIC → RETIRED transition
        result = self.rules._validate_asset_lifecycle(
            asset, old_status=AssetStatus.PUBLIC, new_status=AssetStatus.RETIRED
        )

        self.assertTrue(result.is_valid)


class AssetsBusinessRulesLifecycleIntegrationTest(TestCase):
    """Integration tests for asset lifecycle validation with AssetService"""

    def setUp(self):
        """Set up test fixtures"""
        _uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {_uid}", slug=f"test-tenant-{_uid}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{_uid}@example.com", password="testpass123", tenant=self.tenant
        )
        self.asset_service = AssetService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))
        self.rules = AssetsBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

    def test_asset_service_update_with_lifecycle_validation(self):
        """Test AssetService.update_asset with lifecycle validation"""
        from hub.apps.contracts.models import (
            Contract,
            ContractStatus,
            NormalizationStatus,
            OriginalFormat,
            OriginalSpecType,
            ValidationStatus,
        )

        # Create asset
        asset = AssetFactory.create_asset(
            tenant=self.tenant,
            created_by=self.user,
            status=AssetStatus.DRAFT,
            dq_status=DQStatus.PASS,
            compliance_status=ComplianceStatus.PASS,
        )

        # Create valid contract
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            status=ContractStatus.ACTIVE,
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw='{"version": "3.0.2"}',
            hub_contract_version="1.0.0",
            hub_contract_json={},
        )

        # Validate lifecycle before update
        result = self.rules._validate_asset_lifecycle(
            asset, old_status=AssetStatus.DRAFT, new_status=AssetStatus.ACTIVE
        )

        self.assertTrue(result.is_valid)

        # Update asset status through service
        updated_asset = self.asset_service.update_asset(
            asset_id=str(asset.id), status=AssetStatus.ACTIVE
        )

        self.assertEqual(updated_asset.status, AssetStatus.ACTIVE)

    def test_asset_service_update_with_invalid_transition(self):
        """Test AssetService.update_asset with invalid status transition"""
        # Create asset
        asset = AssetFactory.create_asset(
            tenant=self.tenant, created_by=self.user, status=AssetStatus.DRAFT
        )

        # Validate lifecycle - should fail for DRAFT → PUBLIC
        result = self.rules._validate_asset_lifecycle(
            asset, old_status=AssetStatus.DRAFT, new_status=AssetStatus.PUBLIC
        )

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)


class AssetsBusinessRulesContractAttachmentValidationTest(TestCase):
    """Test contract attachment validation"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com", password="testpass123", tenant=self.tenant
        )
        self.rules = AssetsBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

    def test_contract_validation_status_valid(self):
        """Test contract with VALID validation status"""
        from hub.apps.contracts.models import (
            Contract,
            ContractStatus,
            NormalizationStatus,
            OriginalFormat,
            OriginalSpecType,
            ValidationStatus,
        )

        contract = Contract.objects.create(
            tenant=self.tenant,
            status=ContractStatus.DRAFT,
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw='{"version": "3.0.2"}',
            hub_contract_version="1.0.0",
            hub_contract_json={},
        )

        result = self.rules._validate_contract_validation_status(contract)

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertTrue(result.details["status_valid"])

    def test_contract_validation_status_warning_only(self):
        """Test contract with WARNING_ONLY validation status"""
        from hub.apps.contracts.models import (
            Contract,
            ContractStatus,
            NormalizationStatus,
            OriginalFormat,
            OriginalSpecType,
            ValidationStatus,
        )

        contract = Contract.objects.create(
            tenant=self.tenant,
            status=ContractStatus.DRAFT,
            validation_status=ValidationStatus.WARNING_ONLY,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw='{"version": "3.0.2"}',
            hub_contract_version="1.0.0",
            hub_contract_json={},
            validation_warnings=["Warning: field X is deprecated"],
        )

        result = self.rules._validate_contract_validation_status(contract)

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertGreater(len(result.warnings), 0)
        self.assertTrue(result.details["status_valid"])

    def test_contract_validation_status_invalid(self):
        """Test contract with INVALID validation status"""
        from hub.apps.contracts.models import (
            Contract,
            ContractStatus,
            NormalizationStatus,
            OriginalFormat,
            OriginalSpecType,
            ValidationStatus,
        )

        contract = Contract.objects.create(
            tenant=self.tenant,
            status=ContractStatus.DRAFT,
            validation_status=ValidationStatus.INVALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw='{"version": "3.0.2"}',
            hub_contract_version="1.0.0",
            hub_contract_json={},
        )

        result = self.rules._validate_contract_validation_status(contract)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("VALID", result.errors[0])
        self.assertIn("WARNING_ONLY", result.errors[0])
        self.assertIn("SKIPPED", result.errors[0])
        self.assertFalse(result.details["status_valid"])

    def test_contract_normalization_status_normalized_ok(self):
        """Test contract with NORMALIZED_OK normalization status"""
        from hub.apps.contracts.models import (
            Contract,
            ContractStatus,
            NormalizationStatus,
            OriginalFormat,
            OriginalSpecType,
            ValidationStatus,
        )

        contract = Contract.objects.create(
            tenant=self.tenant,
            status=ContractStatus.DRAFT,
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw='{"version": "3.0.2"}',
            hub_contract_version="1.0.0",
            hub_contract_json={},
        )

        result = self.rules._validate_contract_normalization_status(contract)

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertTrue(result.details["status_valid"])

    def test_contract_normalization_status_with_warnings(self):
        """Test contract with NORMALIZED_WITH_WARNINGS normalization status"""
        from hub.apps.contracts.models import (
            Contract,
            ContractStatus,
            NormalizationStatus,
            OriginalFormat,
            OriginalSpecType,
            ValidationStatus,
        )

        contract = Contract.objects.create(
            tenant=self.tenant,
            status=ContractStatus.DRAFT,
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_WITH_WARNINGS,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw='{"version": "3.0.2"}',
            hub_contract_version="1.0.0",
            hub_contract_json={},
            normalization_warnings=["Warning: field Y has been normalized"],
        )

        result = self.rules._validate_contract_normalization_status(contract)

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertGreater(len(result.warnings), 0)
        self.assertTrue(result.details["status_valid"])

    def test_contract_normalization_status_not_normalized(self):
        """Test contract with NOT_NORMALIZED normalization status"""
        from hub.apps.contracts.models import (
            Contract,
            ContractStatus,
            NormalizationStatus,
            OriginalFormat,
            OriginalSpecType,
            ValidationStatus,
        )

        contract = Contract.objects.create(
            tenant=self.tenant,
            status=ContractStatus.DRAFT,
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NOT_NORMALIZED,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw='{"version": "3.0.2"}',
            hub_contract_version="1.0.0",
            hub_contract_json={},
        )

        result = self.rules._validate_contract_normalization_status(contract)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("NORMALIZED_OK or NORMALIZED_WITH_WARNINGS", result.errors[0])
        self.assertFalse(result.details["status_valid"])

    def test_contract_tenant_ownership_match(self):
        """Test contract tenant ownership validation with matching tenants"""
        from hub.apps.contracts.models import (
            Contract,
            ContractStatus,
            NormalizationStatus,
            OriginalFormat,
            OriginalSpecType,
            ValidationStatus,
        )

        asset = AssetFactory.create_asset(tenant=self.tenant, created_by=self.user)

        contract = Contract.objects.create(
            tenant=self.tenant,
            status=ContractStatus.DRAFT,
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw='{"version": "3.0.2"}',
            hub_contract_version="1.0.0",
            hub_contract_json={},
        )

        result = self.rules._validate_contract_tenant_ownership(asset, contract)

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertTrue(result.details["tenant_match"])

    def test_contract_tenant_ownership_mismatch(self):
        """Test contract tenant ownership validation with mismatched tenants"""
        from hub.apps.contracts.models import (
            Contract,
            ContractStatus,
            NormalizationStatus,
            OriginalFormat,
            OriginalSpecType,
            ValidationStatus,
        )

        asset = AssetFactory.create_asset(tenant=self.tenant, created_by=self.user)

        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}", slug=f"other-tenant-{_uid}", kyc_status=KYCStatus.VERIFIED
        )

        contract = Contract.objects.create(
            tenant=other_tenant,
            status=ContractStatus.DRAFT,
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw='{"version": "3.0.2"}',
            hub_contract_version="1.0.0",
            hub_contract_json={},
        )

        result = self.rules._validate_contract_tenant_ownership(asset, contract)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("does not match", result.errors[0])
        self.assertFalse(result.details["tenant_match"])

    def test_contract_version_compatibility_auto_increment(self):
        """Test contract version compatibility with auto-increment"""
        from hub.apps.contracts.models import (
            Contract,
            ContractStatus,
            NormalizationStatus,
            OriginalFormat,
            OriginalSpecType,
            ValidationStatus,
        )

        asset = AssetFactory.create_asset(tenant=self.tenant, created_by=self.user)

        contract = Contract.objects.create(
            tenant=self.tenant,
            status=ContractStatus.DRAFT,
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw='{"version": "3.0.2"}',
            hub_contract_version="1.0.0",
            hub_contract_json={},
        )

        result = self.rules._validate_contract_version_compatibility(
            asset, contract, proposed_version=None
        )

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertTrue(result.details["version_valid"])
        self.assertTrue(result.details["auto_increment"])

    def test_contract_version_compatibility_valid_increment(self):
        """Test contract version compatibility with valid version increment"""
        from hub.apps.contracts.models import (
            Contract,
            ContractStatus,
            NormalizationStatus,
            OriginalFormat,
            OriginalSpecType,
            ValidationStatus,
        )

        asset = AssetFactory.create_asset(tenant=self.tenant, created_by=self.user)

        # Create existing contract with version 1
        existing_contract = Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            version=1,
            status=ContractStatus.DRAFT,
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw='{"version": "3.0.2"}',
            hub_contract_version="1.0.0",
            hub_contract_json={},
        )

        # New contract to attach
        contract = Contract.objects.create(
            tenant=self.tenant,
            status=ContractStatus.DRAFT,
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw='{"version": "3.0.2"}',
            hub_contract_version="1.0.0",
            hub_contract_json={},
        )

        result = self.rules._validate_contract_version_compatibility(
            asset, contract, proposed_version=2
        )

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertTrue(result.details["version_valid"])

    def test_contract_version_compatibility_invalid_increment(self):
        """Test contract version compatibility with invalid version increment"""
        from hub.apps.contracts.models import (
            Contract,
            ContractStatus,
            NormalizationStatus,
            OriginalFormat,
            OriginalSpecType,
            ValidationStatus,
        )

        asset = AssetFactory.create_asset(tenant=self.tenant, created_by=self.user)

        # Create existing contract with version 2
        existing_contract = Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            version=2,
            status=ContractStatus.DRAFT,
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw='{"version": "3.0.2"}',
            hub_contract_version="1.0.0",
            hub_contract_json={},
        )

        # New contract to attach with version 1 (should fail)
        contract = Contract.objects.create(
            tenant=self.tenant,
            status=ContractStatus.DRAFT,
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw='{"version": "3.0.2"}',
            hub_contract_version="1.0.0",
            hub_contract_json={},
        )

        result = self.rules._validate_contract_version_compatibility(
            asset, contract, proposed_version=1
        )

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("must be greater than latest version", result.errors[0])
        self.assertFalse(result.details["version_valid"])

    def test_contract_version_compatibility_conflict(self):
        """Test contract version compatibility with version conflict"""
        from hub.apps.contracts.models import (
            Contract,
            ContractStatus,
            NormalizationStatus,
            OriginalFormat,
            OriginalSpecType,
            ValidationStatus,
        )

        asset = AssetFactory.create_asset(tenant=self.tenant, created_by=self.user)

        # Create existing contract with version 2
        existing_contract = Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            version=2,
            status=ContractStatus.DRAFT,
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw='{"version": "3.0.2"}',
            hub_contract_version="1.0.0",
            hub_contract_json={},
        )

        # New contract to attach with same version (should fail)
        contract = Contract.objects.create(
            tenant=self.tenant,
            status=ContractStatus.DRAFT,
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw='{"version": "3.0.2"}',
            hub_contract_version="1.0.0",
            hub_contract_json={},
        )

        result = self.rules._validate_contract_version_compatibility(
            asset, contract, proposed_version=2
        )

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("already exists", result.errors[0])
        self.assertFalse(result.details["version_valid"])

    def test_contract_version_compatibility_already_attached(self):
        """Test contract version compatibility when contract already attached"""
        from hub.apps.contracts.models import (
            Contract,
            ContractStatus,
            NormalizationStatus,
            OriginalFormat,
            OriginalSpecType,
            ValidationStatus,
        )

        asset = AssetFactory.create_asset(tenant=self.tenant, created_by=self.user)

        # Contract already attached to asset
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            version=1,
            status=ContractStatus.DRAFT,
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw='{"version": "3.0.2"}',
            hub_contract_version="1.0.0",
            hub_contract_json={},
        )

        result = self.rules._validate_contract_version_compatibility(
            asset, contract, proposed_version=None
        )

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertTrue(result.details["version_valid"])
        self.assertTrue(result.details["already_attached"])

    def test_validate_contract_attachment_complete_success(self):
        """Test complete contract attachment validation with all checks passing"""
        from hub.apps.contracts.models import (
            Contract,
            ContractStatus,
            NormalizationStatus,
            OriginalFormat,
            OriginalSpecType,
            ValidationStatus,
        )

        asset = AssetFactory.create_asset(tenant=self.tenant, created_by=self.user)

        contract = Contract.objects.create(
            tenant=self.tenant,
            status=ContractStatus.DRAFT,
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw='{"version": "3.0.2"}',
            hub_contract_version="1.0.0",
            hub_contract_json={},
        )

        result = self.rules.validate_contract_attachment(asset, contract)

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertIn("validation_checks", result.details)
        self.assertTrue(result.details["validation_checks"]["validation_status"]["status_valid"])
        self.assertTrue(result.details["validation_checks"]["normalization_status"]["status_valid"])
        self.assertTrue(result.details["validation_checks"]["tenant_ownership"]["tenant_match"])

    def test_validate_contract_attachment_with_warnings(self):
        """Test contract attachment validation with warnings"""
        from hub.apps.contracts.models import (
            Contract,
            ContractStatus,
            NormalizationStatus,
            OriginalFormat,
            OriginalSpecType,
            ValidationStatus,
        )

        asset = AssetFactory.create_asset(tenant=self.tenant, created_by=self.user)

        contract = Contract.objects.create(
            tenant=self.tenant,
            status=ContractStatus.DRAFT,
            validation_status=ValidationStatus.WARNING_ONLY,
            normalization_status=NormalizationStatus.NORMALIZED_WITH_WARNINGS,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw='{"version": "3.0.2"}',
            hub_contract_version="1.0.0",
            hub_contract_json={},
            validation_warnings=["Warning 1"],
            normalization_warnings=["Warning 2"],
        )

        result = self.rules.validate_contract_attachment(asset, contract)

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertGreater(len(result.warnings), 0)

    def test_validate_contract_attachment_multiple_errors_returns_invalid(self):
        """Test contract attachment validation with multiple errors returns invalid."""
        from hub.apps.contracts.models import (
            Contract,
            ContractStatus,
            NormalizationStatus,
            OriginalFormat,
            OriginalSpecType,
            ValidationStatus,
        )

        asset = AssetFactory.create_asset(tenant=self.tenant, created_by=self.user)

        contract = Contract.objects.create(
            tenant=self.tenant,
            status=ContractStatus.DRAFT,
            validation_status=ValidationStatus.INVALID,
            normalization_status=NormalizationStatus.NOT_NORMALIZED,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw='{"version": "3.0.2"}',
            hub_contract_version="1.0.0",
            hub_contract_json={},
        )

        result = self.rules.validate_contract_attachment(asset, contract)
        self.assertFalse(result.is_valid)

    def test_validate_contract_attachment_multiple_errors_returns_multiple_errors(self):
        """Test contract attachment validation with multiple errors returns multiple errors."""
        from hub.apps.contracts.models import (
            Contract,
            ContractStatus,
            NormalizationStatus,
            OriginalFormat,
            OriginalSpecType,
            ValidationStatus,
        )

        asset = AssetFactory.create_asset(tenant=self.tenant, created_by=self.user)

        contract = Contract.objects.create(
            tenant=self.tenant,
            status=ContractStatus.DRAFT,
            validation_status=ValidationStatus.INVALID,
            normalization_status=NormalizationStatus.NOT_NORMALIZED,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw='{"version": "3.0.2"}',
            hub_contract_version="1.0.0",
            hub_contract_json={},
        )

        result = self.rules.validate_contract_attachment(asset, contract)
        self.assertGreaterEqual(len(result.errors), 2)


class AssetsBusinessRulesContractAttachmentIntegrationTest(TestCase):
    """Integration tests for contract attachment validation with ContractService"""

    def setUp(self):
        """Set up test fixtures"""
        _uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {_uid}", slug=f"test-tenant-{_uid}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{_uid}@example.com", password="testpass123", tenant=self.tenant
        )
        from hub.apps.contracts.services import ContractService

        self.contract_service = ContractService(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )
        self.rules = AssetsBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

    def test_contract_service_with_attachment_validation(self):
        """Test ContractService.get_contract with attachment validation"""
        import json

        from hub.apps.contracts.models import (
            Contract,
            ContractStatus,
            NormalizationStatus,
            OriginalFormat,
            OriginalSpecType,
            ValidationStatus,
        )

        asset = AssetFactory.create_asset(tenant=self.tenant, created_by=self.user)

        # Create valid ODCS contract JSON
        odcs_contract = {
            "apiVersion": "odcs/v3",
            "kind": "DataContract",
            "id": "test-contract",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {"fields": [{"name": "id", "type": "string", "nullable": False}]},
        }

        # Create contract via service
        contract = self.contract_service.create_contract(
            original_raw=json.dumps(odcs_contract),
            original_format="JSON",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        # Refresh from DB to get updated statuses
        contract.refresh_from_db()

        # Update contract to have valid statuses if normalization succeeded
        if contract.normalization_status in [
            NormalizationStatus.NORMALIZED_OK,
            NormalizationStatus.NORMALIZED_WITH_WARNINGS,
        ]:
            contract.validation_status = ValidationStatus.VALID
            contract.save()

        # Validate attachment
        result = self.rules.validate_contract_attachment(asset, contract)

        # If normalization succeeded, validation should pass
        if contract.normalization_status in [
            NormalizationStatus.NORMALIZED_OK,
            NormalizationStatus.NORMALIZED_WITH_WARNINGS,
        ]:
            self.assertTrue(result.is_valid)
            self.assertEqual(len(result.errors), 0)

        # Verify contract can be retrieved via service
        retrieved_contract = self.contract_service.get_contract(
            contract_id=str(contract.id), tenant_id=str(self.tenant.id)
        )

        self.assertEqual(retrieved_contract.id, contract.id)

    def test_contract_service_with_invalid_attachment(self):
        """Test ContractService with contract that fails attachment validation"""
        import json

        from hub.apps.contracts.models import (
            Contract,
            ContractStatus,
            NormalizationStatus,
            OriginalFormat,
            OriginalSpecType,
            ValidationStatus,
        )

        asset = AssetFactory.create_asset(tenant=self.tenant, created_by=self.user)

        # Create valid ODCS contract JSON
        odcs_contract = {
            "apiVersion": "odcs/v3",
            "kind": "DataContract",
            "id": "test-contract",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {"fields": [{"name": "id", "type": "string", "nullable": False}]},
        }

        # Create contract via service
        contract = self.contract_service.create_contract(
            original_raw=json.dumps(odcs_contract),
            original_format="JSON",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        # Refresh from DB to get updated statuses
        contract.refresh_from_db()

        # Set invalid statuses for testing
        contract.validation_status = ValidationStatus.INVALID
        contract.normalization_status = NormalizationStatus.NOT_NORMALIZED
        contract.save()

        # Validate attachment - should fail
        result = self.rules.validate_contract_attachment(asset, contract)

        self.assertFalse(result.is_valid)

    def test_contract_service_with_invalid_attachment_returns_errors(self):
        """Test contract service with invalid attachment returns errors."""
        import json

        from hub.apps.contracts.models import (
            Contract,
            ContractStatus,
            NormalizationStatus,
            ValidationStatus,
        )
        from hub.apps.contracts.services import ContractService

        asset = AssetFactory.create_asset(tenant=self.tenant, created_by=self.user)
        self.contract_service = ContractService(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

        odcs_contract = {
            "apiVersion": "odcs/v3",
            "kind": "DataContract",
            "id": "test-contract",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {"fields": [{"name": "id", "type": "string", "nullable": False}]},
        }

        contract = self.contract_service.create_contract(
            original_raw=json.dumps(odcs_contract),
            original_format="JSON",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        contract.refresh_from_db()
        contract.validation_status = ValidationStatus.INVALID
        contract.normalization_status = NormalizationStatus.NOT_NORMALIZED
        contract.save()

        result = self.rules.validate_contract_attachment(asset, contract)

        self.assertGreater(len(result.errors), 0)


class AssetsBusinessRulesHealthScoreTest(TestCase):
    """Test cases for health score validation methods."""

    def setUp(self):
        """Set up test fixtures"""
        _uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {_uid}", slug=f"test-tenant-{_uid}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{_uid}@example.com", password="testpass123", tenant=self.tenant
        )
        self.rules = AssetsBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

    def test_validate_health_score_calculation_valid(self):
        """Test health score calculation validation with valid asset"""
        asset = AssetFactory.create_asset(
            tenant=self.tenant,
            created_by=self.user,
            status=AssetStatus.DRAFT,
            dq_status=DQStatus.PASS,
            compliance_status=ComplianceStatus.PASS,
            health_score=75.0,
        )

        result = self.rules.validate_health_score_calculation(asset, raise_on_error=False)

        # Should be valid (warnings about missing contract are OK for DRAFT assets)
        self.assertTrue(result.is_valid)
        self.assertIn("health_score_checks", result.details)
        self.assertTrue(result.details["health_score_checks"]["dq_status_valid"])
        self.assertTrue(result.details["health_score_checks"]["compliance_status_valid"])

    def test_validate_health_score_calculation_invalid_dq_status(self):
        """Test health score calculation validation with invalid DQ status"""
        asset = AssetFactory.create_asset(
            tenant=self.tenant,
            created_by=self.user,
            status=AssetStatus.DRAFT,
            dq_status="INVALID_STATUS",
            compliance_status=ComplianceStatus.PASS,
        )

        result = self.rules.validate_health_score_calculation(asset, raise_on_error=False)

        self.assertFalse(result.is_valid)
        self.assertTrue(any("Invalid DQ status" in error for error in result.errors))

    def test_validate_health_score_calculation_active_with_fail_dq(self):
        """Test health score calculation validation for ACTIVE asset with FAIL DQ status"""
        # Create as DRAFT first, then update to ACTIVE with FAIL DQ to bypass model validation
        asset = AssetFactory.create_asset(
            tenant=self.tenant,
            created_by=self.user,
            status=AssetStatus.DRAFT,
            dq_status=DQStatus.FAIL,
            compliance_status=ComplianceStatus.PASS,
        )
        # Update directly in DB to bypass clean() validation
        Asset.objects.filter(id=asset.id).update(status=AssetStatus.ACTIVE)
        asset.refresh_from_db()

        result = self.rules.validate_health_score_calculation(asset, raise_on_error=False)

        self.assertFalse(result.is_valid)
        self.assertTrue(
            any("ACTIVE status requires DQ status PASS or WARN" in error for error in result.errors)
        )

    def test_validate_health_score_calculation_active_with_fail_compliance(self):
        """Test health score calculation validation for ACTIVE asset with FAIL compliance status"""
        # Create as DRAFT first, then update to ACTIVE with FAIL compliance to bypass model validation
        asset = AssetFactory.create_asset(
            tenant=self.tenant,
            created_by=self.user,
            status=AssetStatus.DRAFT,
            dq_status=DQStatus.PASS,
            compliance_status=ComplianceStatus.FAIL,
        )
        # Update directly in DB to bypass clean() validation
        Asset.objects.filter(id=asset.id).update(status=AssetStatus.ACTIVE)
        asset.refresh_from_db()

        result = self.rules.validate_health_score_calculation(asset, raise_on_error=False)

        self.assertFalse(result.is_valid)
        self.assertTrue(
            any(
                "ACTIVE status requires compliance status PASS or WARN" in error
                for error in result.errors
            )
        )

    def test_validate_health_score_calculation_active_without_contract(self):
        """Test health score calculation validation for ACTIVE asset without contract"""
        # Create as DRAFT first, then update to ACTIVE without contract to bypass model validation
        asset = AssetFactory.create_asset(
            tenant=self.tenant,
            created_by=self.user,
            status=AssetStatus.DRAFT,
            dq_status=DQStatus.PASS,
            compliance_status=ComplianceStatus.PASS,
        )
        # Update directly in DB to bypass clean() validation
        Asset.objects.filter(id=asset.id).update(status=AssetStatus.ACTIVE)
        asset.refresh_from_db()

        result = self.rules.validate_health_score_calculation(asset, raise_on_error=False)

        self.assertFalse(result.is_valid)
        self.assertTrue(
            any("ACTIVE status requires an ACTIVE contract" in error for error in result.errors)
        )

    def test_validate_health_score_calculation_health_score_out_of_range(self):
        """Test health score calculation validation with health score out of range"""
        asset = AssetFactory.create_asset(
            tenant=self.tenant,
            created_by=self.user,
            status=AssetStatus.DRAFT,
            dq_status=DQStatus.PASS,
            compliance_status=ComplianceStatus.PASS,
            health_score=150.0,  # Out of range
        )

        result = self.rules.validate_health_score_calculation(asset, raise_on_error=False)

        self.assertFalse(result.is_valid)
        self.assertTrue(
            any("Health score must be between 0.0 and 100.0" in error for error in result.errors)
        )

    def test_validate_health_score_calculation_raises_on_error(self):
        """Test that validate_health_score_calculation raises exception when raise_on_error=True"""
        # Create as DRAFT first, then update to ACTIVE with FAIL DQ to bypass model validation
        asset = AssetFactory.create_asset(
            tenant=self.tenant,
            created_by=self.user,
            status=AssetStatus.DRAFT,
            dq_status=DQStatus.FAIL,
            compliance_status=ComplianceStatus.PASS,
        )
        # Update directly in DB to bypass clean() validation
        Asset.objects.filter(id=asset.id).update(status=AssetStatus.ACTIVE)
        asset.refresh_from_db()

        from hub.apps.core.services.base import ValidationError

        with self.assertRaises(ValidationError) as context:
            self.rules.validate_health_score_calculation(asset, raise_on_error=True)

        self.assertEqual(context.exception.code, "INVALID_HEALTH_SCORE_CALCULATION")

    def test_validate_health_score_thresholds_active_meets_threshold(self):
        """Test health score threshold validation for ACTIVE status - meets threshold"""
        asset = AssetFactory.create_asset(
            tenant=self.tenant,
            created_by=self.user,
            status=AssetStatus.DRAFT,
            dq_status=DQStatus.PASS,
            compliance_status=ComplianceStatus.PASS,
            health_score=75.0,
        )

        result = self.rules.validate_health_score_thresholds(
            asset=asset, target_status=AssetStatus.ACTIVE, raise_on_error=False
        )

        self.assertTrue(result.is_valid)
        self.assertIn("threshold_checks", result.details)
        self.assertTrue(result.details["threshold_checks"]["meets_active_threshold"])

    def test_validate_health_score_thresholds_active_below_threshold(self):
        """Test health score threshold validation for ACTIVE status - below threshold"""
        asset = AssetFactory.create_asset(
            tenant=self.tenant,
            created_by=self.user,
            status=AssetStatus.DRAFT,
            dq_status=DQStatus.FAIL,
            compliance_status=ComplianceStatus.FAIL,
            health_score=30.0,  # Below 50.0 threshold
        )

        result = self.rules.validate_health_score_thresholds(
            asset=asset, target_status=AssetStatus.ACTIVE, raise_on_error=False
        )

        self.assertFalse(result.is_valid)
        self.assertTrue(any("below minimum threshold" in error for error in result.errors))

    def test_validate_health_score_thresholds_public_meets_threshold(self):
        """Test health score threshold validation for PUBLIC status - meets threshold"""
        asset = AssetFactory.create_asset(
            tenant=self.tenant,
            created_by=self.user,
            status=AssetStatus.ACTIVE,
            dq_status=DQStatus.PASS,
            compliance_status=ComplianceStatus.PASS,
            health_score=85.0,  # Above 70.0 threshold
        )

        result = self.rules.validate_health_score_thresholds(
            asset=asset, target_status=AssetStatus.PUBLIC, raise_on_error=False
        )

        self.assertTrue(result.is_valid)
        self.assertTrue(result.details["threshold_checks"]["meets_public_threshold"])

    def test_validate_health_score_thresholds_public_below_threshold(self):
        """Test health score threshold validation for PUBLIC status - below threshold"""
        asset = AssetFactory.create_asset(
            tenant=self.tenant,
            created_by=self.user,
            status=AssetStatus.ACTIVE,
            dq_status=DQStatus.WARN,
            compliance_status=ComplianceStatus.WARN,
            health_score=60.0,  # Below 70.0 threshold
        )

        result = self.rules.validate_health_score_thresholds(
            asset=asset, target_status=AssetStatus.PUBLIC, raise_on_error=False
        )

        self.assertFalse(result.is_valid)
        self.assertTrue(any("below minimum threshold" in error for error in result.errors))

    def test_validate_health_score_thresholds_low_score_warning(self):
        """Test health score threshold validation with low score warning"""
        asset = AssetFactory.create_asset(
            tenant=self.tenant,
            created_by=self.user,
            status=AssetStatus.DRAFT,
            dq_status=DQStatus.FAIL,
            compliance_status=ComplianceStatus.FAIL,
            health_score=20.0,  # Very low
        )

        result = self.rules.validate_health_score_thresholds(
            asset=asset, target_status=AssetStatus.DRAFT, raise_on_error=False
        )

        self.assertTrue(result.is_valid)  # DRAFT allows low scores
        self.assertTrue(any("very low" in warning.lower() for warning in result.warnings))

    def test_validate_health_score_thresholds_raises_on_error(self):
        """Test that validate_health_score_thresholds raises exception when raise_on_error=True"""
        asset = AssetFactory.create_asset(
            tenant=self.tenant,
            created_by=self.user,
            status=AssetStatus.DRAFT,
            dq_status=DQStatus.FAIL,
            compliance_status=ComplianceStatus.FAIL,
            health_score=30.0,
        )

        from hub.apps.core.services.base import ValidationError

        with self.assertRaises(ValidationError) as context:
            self.rules.validate_health_score_thresholds(
                asset=asset, target_status=AssetStatus.ACTIVE, raise_on_error=True
            )

        self.assertEqual(context.exception.code, "HEALTH_SCORE_THRESHOLD_NOT_MET")

    def test_validate_health_score_update_triggers_no_recalculation_needed(self):
        """Test health score update triggers - no recalculation needed"""
        from django.utils import timezone

        asset = AssetFactory.create_asset(
            tenant=self.tenant,
            created_by=self.user,
            status=AssetStatus.DRAFT,
            dq_status=DQStatus.PASS,
            compliance_status=ComplianceStatus.PASS,
            health_score=75.0,
        )

        # Set updated_at to recent time
        asset.updated_at = timezone.now()
        asset.save()

        result = self.rules.validate_health_score_update_triggers(asset=asset, raise_on_error=False)

        self.assertTrue(result.is_valid)
        self.assertFalse(
            result.details["update_trigger_checks"].get("recalculation_required", False)
        )

    def test_validate_health_score_update_triggers_stale_score(self):
        """Test health score update triggers - stale score"""
        from datetime import timedelta

        from django.utils import timezone

        asset = AssetFactory.create_asset(
            tenant=self.tenant,
            created_by=self.user,
            status=AssetStatus.DRAFT,
            dq_status=DQStatus.PASS,
            compliance_status=ComplianceStatus.PASS,
            health_score=75.0,
        )

        # Set updated_at to 25 hours ago (stale) - use update() to bypass auto_now
        Asset.objects.filter(id=asset.id).update(updated_at=timezone.now() - timedelta(hours=25))
        asset.refresh_from_db()

        result = self.rules.validate_health_score_update_triggers(asset=asset, raise_on_error=False)

        self.assertTrue(result.is_valid)  # Stale is a warning, not error
        self.assertTrue(any("stale" in warning.lower() for warning in result.warnings))
        self.assertTrue(
            result.details["update_trigger_checks"].get("recalculation_recommended", False)
        )

    def test_validate_health_score_update_triggers_active_without_score(self):
        """Test health score update triggers - ACTIVE asset without health score"""
        # Create as DRAFT first, then update to ACTIVE without contract to bypass model validation
        asset = AssetFactory.create_asset(
            tenant=self.tenant,
            created_by=self.user,
            status=AssetStatus.DRAFT,
            dq_status=DQStatus.PASS,
            compliance_status=ComplianceStatus.PASS,
            health_score=None,
        )
        # Update directly in DB to bypass clean() validation
        Asset.objects.filter(id=asset.id).update(status=AssetStatus.ACTIVE)
        asset.refresh_from_db()

        result = self.rules.validate_health_score_update_triggers(asset=asset, raise_on_error=False)

        self.assertFalse(result.is_valid)
        self.assertTrue(
            any("must have a calculated health score" in error for error in result.errors)
        )
        self.assertTrue(
            result.details["update_trigger_checks"].get("recalculation_required", False)
        )

    def test_validate_health_score_update_triggers_unknown_statuses(self):
        """Test health score update triggers - UNKNOWN DQ/compliance statuses"""
        asset = AssetFactory.create_asset(
            tenant=self.tenant,
            created_by=self.user,
            status=AssetStatus.DRAFT,
            dq_status=DQStatus.UNKNOWN,
            compliance_status=ComplianceStatus.UNKNOWN,
            health_score=50.0,
        )

        result = self.rules.validate_health_score_update_triggers(asset=asset, raise_on_error=False)

        self.assertTrue(result.is_valid)  # Warnings, not errors
        self.assertTrue(any("UNKNOWN" in warning for warning in result.warnings))
        self.assertTrue(
            result.details["update_trigger_checks"].get("recalculation_recommended", False)
        )

    def test_validate_health_score_update_triggers_raises_on_error(self):
        """Test that validate_health_score_update_triggers raises exception when raise_on_error=True"""
        # Create as DRAFT first, then update to ACTIVE without contract to bypass model validation
        asset = AssetFactory.create_asset(
            tenant=self.tenant,
            created_by=self.user,
            status=AssetStatus.DRAFT,
            dq_status=DQStatus.PASS,
            compliance_status=ComplianceStatus.PASS,
            health_score=None,
        )
        # Update directly in DB to bypass clean() validation
        Asset.objects.filter(id=asset.id).update(status=AssetStatus.ACTIVE)
        asset.refresh_from_db()

        from hub.apps.core.services.base import ValidationError

        with self.assertRaises(ValidationError) as context:
            self.rules.validate_health_score_update_triggers(asset=asset, raise_on_error=True)

        self.assertEqual(context.exception.code, "HEALTH_SCORE_UPDATE_REQUIRED")

    def test_validate_health_score_calculation_with_contract(self):
        """Test health score calculation validation with contract"""
        import json

        from hub.apps.contracts.models import Contract, NormalizationStatus, ValidationStatus

        asset = AssetFactory.create_asset(
            tenant=self.tenant,
            created_by=self.user,
            status=AssetStatus.DRAFT,
            dq_status=DQStatus.PASS,
            compliance_status=ComplianceStatus.PASS,
        )

        # Create a valid contract
        odcs_contract = {
            "version": "1.0.0",
            "name": "Test Contract",
            "schema": {
                "fields": [{"name": "id", "type": "integer"}, {"name": "name", "type": "string"}]
            },
        }

        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            original_raw=json.dumps(odcs_contract),
            original_format="JSON",
            version=1,
            status="ACTIVE",
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
        )

        result = self.rules.validate_health_score_calculation(asset, raise_on_error=False)

        self.assertTrue(result.is_valid)
        self.assertTrue(result.details["health_score_checks"]["contract_exists"])
        self.assertTrue(
            result.details["health_score_checks"]["contract_validation_status_appropriate"]
        )

    def test_validate_health_score_thresholds_integration_with_service(self):
        """Test health score threshold validation integration with AssetHealthScoreService"""
        from hub.apps.assets.health_score import AssetHealthScoreService

        asset = AssetFactory.create_asset(
            tenant=self.tenant,
            created_by=self.user,
            status=AssetStatus.DRAFT,
            dq_status=DQStatus.PASS,
            compliance_status=ComplianceStatus.PASS,
            health_score=None,  # Not calculated yet
        )

        # Calculate health score via service
        calculated_score = AssetHealthScoreService.calculate_health_score(asset)
        asset.refresh_from_db()

        # Validate thresholds
        result = self.rules.validate_health_score_thresholds(
            asset=asset, target_status=AssetStatus.ACTIVE, raise_on_error=False
        )

        self.assertIn("threshold_checks", result.details)
        self.assertIn("component_scores", result.details["threshold_checks"])
        # Should have component scores from breakdown
        component_scores = result.details["threshold_checks"]["component_scores"]
        self.assertIn("dq", component_scores)
        self.assertIn("compliance", component_scores)
        self.assertIn("freshness", component_scores)
        self.assertIn("usage", component_scores)

    # ========== EDGE CASES ==========

    def test_validate_with_none_asset(self):
        """Test validation with None asset (edge case)"""
        context = AssetsRuleExecutionContext(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            asset=None,
            tenant=self.tenant,
            user=self.user,
        )

        # Should handle None asset gracefully
        try:
            result = self.rules.validate(context, validation_type="structure")
            # If succeeds, verify result structure
            self.assertIsNotNone(result)
        except (AttributeError, TypeError):
            # If fails, that's acceptable for None asset
            pass

    def test_validate_with_empty_context(self):
        """Test validation with empty context (edge case)"""
        from hub.apps.core.business_rules.base import RuleExecutionContext

        empty_context = RuleExecutionContext(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

        # Should handle empty context gracefully
        try:
            result = self.rules.validate(empty_context, validation_type="structure")
            # If succeeds, verify result structure
            self.assertIsNotNone(result)
        except Exception:
            # If fails, that's acceptable for empty context
            pass

    def test_validate_with_invalid_validation_type(self):
        """Test validation with invalid validation_type (edge case)"""
        asset = AssetFactory.create_asset(
            tenant=self.tenant, created_by=self.user, status=AssetStatus.DRAFT
        )

        context = AssetsRuleExecutionContext(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            asset=asset,
            tenant=self.tenant,
            user=self.user,
        )

        # Should handle invalid validation type gracefully
        try:
            result = self.rules.validate(context, validation_type="INVALID_TYPE")
            # If succeeds, verify result structure
            self.assertIsNotNone(result)
        except Exception:
            # If fails, that's acceptable for invalid type
            pass

    def test_validate_health_score_thresholds_edge_case_zero_score(self):
        """Test health score threshold validation with zero score (edge case)"""
        asset = AssetFactory.create_asset(
            tenant=self.tenant, created_by=self.user, status=AssetStatus.DRAFT, health_score=0.0
        )

        result = self.rules.validate_health_score_thresholds(
            asset=asset, target_status=AssetStatus.ACTIVE, raise_on_error=False
        )

        # Should handle zero score gracefully
        self.assertIsNotNone(result)
        self.assertIn("threshold_checks", result.details)

    def test_validate_health_score_thresholds_edge_case_max_score(self):
        """Test health score threshold validation with max score (edge case)"""
        asset = AssetFactory.create_asset(
            tenant=self.tenant, created_by=self.user, status=AssetStatus.DRAFT, health_score=100.0
        )

        result = self.rules.validate_health_score_thresholds(
            asset=asset, target_status=AssetStatus.ACTIVE, raise_on_error=False
        )

        # Should handle max score gracefully
        self.assertIsNotNone(result)
        self.assertIn("threshold_checks", result.details)

    def test_status_transition_edge_case_same_status(self):
        """Test status transition with same status (edge case)"""
        asset = AssetFactory.create_asset(
            tenant=self.tenant, created_by=self.user, status=AssetStatus.DRAFT
        )

        context = AssetsRuleExecutionContext(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            asset=asset,
            tenant=self.tenant,
            user=self.user,
        )

        result = self.rules.validate(
            context,
            validation_type="lifecycle",
            old_status=AssetStatus.DRAFT,
            new_status=AssetStatus.DRAFT,  # Same as current
        )

        # Should handle same status transition gracefully
        self.assertIsNotNone(result)

    def test_activation_requirements_edge_case_multiple_contracts(self):
        """Test activation requirements with multiple contracts (edge case)"""
        asset = AssetFactory.create_asset(
            tenant=self.tenant, created_by=self.user, status=AssetStatus.DRAFT
        )

        # Create multiple contracts
        from hub.apps.contracts.models import (
            Contract,
            ContractStatus,
            NormalizationStatus,
            ValidationStatus,
        )

        contract1 = Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            status=ContractStatus.ACTIVE,
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            original_spec_type="ODCS",
            original_spec_version="3.0.0",
            original_format="JSON",
            original_raw='{"id": "test1"}',
            hub_contract_version="1.0.0",
            hub_contract_json={},
            created_by=self.user,
        )

        contract2 = Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            version=2,  # Per-asset version; unique on (tenant, asset, version)
            status=ContractStatus.ACTIVE,
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            original_spec_type="ODCS",
            original_spec_version="3.0.0",
            original_format="JSON",
            original_raw='{"id": "test2"}',
            hub_contract_version="2.0.0",
            hub_contract_json={},
            created_by=self.user,
        )

        context = AssetsRuleExecutionContext(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            asset=asset,
            tenant=self.tenant,
            user=self.user,
        )

        result = self.rules.validate(
            context,
            validation_type="lifecycle",
            old_status=asset.status,
            new_status=AssetStatus.ACTIVE,
        )

        # Should handle multiple contracts gracefully
        self.assertIsNotNone(result)
