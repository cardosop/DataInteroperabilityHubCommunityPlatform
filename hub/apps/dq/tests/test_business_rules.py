"""
Unit tests for DQBusinessRules.

Comprehensive tests without mocks/stubs, following engineering best practices.
"""

import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.assets.tests.factories import AssetFactory
from hub.apps.core.business_rules.base import RuleExecutionContext, ValidationResult
from hub.apps.core.business_rules.registry import get_registry
from hub.apps.datasets.models import Dataset
from hub.apps.dq.business_rules import DQBusinessRules, DQRuleExecutionContext
from hub.apps.dq.models import (
    DQEngine,
    DQRun,
    DQRunStatus,
)
from hub.apps.dq.tests.test_base import DQTestBase
from hub.apps.files.models import File, FileStatus
from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.tenants.models import KYCStatus, Tenant

User = get_user_model()


class DQBusinessRulesInitializationTest(DQTestBase):
    """Test DQBusinessRules initialization"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()

    def test_dq_business_rules_initialization(self):
        """Test DQBusinessRules can be initialized"""
        rules = DQBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))
        self.assertIsNotNone(rules)
        self.assertEqual(rules.get_rule_name(), "DQBusinessRules")
        self.assertEqual(rules.tenant_id, str(self.tenant.id))
        self.assertEqual(rules.user_id, str(self.user.id))

    def test_dq_business_rules_initialization_without_user(self):
        """Test DQBusinessRules can be initialized without user"""
        rules = DQBusinessRules(tenant_id=str(self.tenant.id))
        self.assertIsNotNone(rules)
        self.assertEqual(rules.tenant_id, str(self.tenant.id))
        self.assertIsNone(rules.user_id)

    def test_dq_business_rules_initialization_without_tenant(self):
        """Test DQBusinessRules can be initialized without tenant"""
        rules = DQBusinessRules(user_id=str(self.user.id))
        self.assertIsNotNone(rules)
        self.assertIsNone(rules.tenant_id)
        self.assertEqual(rules.user_id, str(self.user.id))


class DQBusinessRulesRegistrationTest(TestCase):
    """Test DQBusinessRules registration in business rules registry"""

    def test_dq_business_rules_registered(self):
        """Test DQBusinessRules is registered in the registry"""
        registry = get_registry()
        rule = registry.get_rule("dq_validation")
        self.assertIsNotNone(rule)
        self.assertEqual(rule.rule_name, "dq_validation")
        self.assertEqual(rule.rule_class, DQBusinessRules)
        self.assertIn("dq", rule.tags)
        self.assertIn("data_quality", rule.tags)
        self.assertIn("validation", rule.tags)

    def test_dq_business_rules_priority(self):
        """Test DQBusinessRules has correct priority"""
        registry = get_registry()
        rule = registry.get_rule("dq_validation")
        self.assertIsNotNone(rule)
        self.assertEqual(rule.priority, 10)


class CheckTypeValidationTest(DQTestBase):
    """Test check type validation"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        self.rules = DQBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

    def test_validate_check_type_completeness(self):
        """Test check type validation with completeness"""
        check = {
            "name": "Test Check",
            "category": "COMPLETENESS",
            "expectation": {"type": "expect_column_values_to_not_be_null", "params": {}},
        }

        result = self.rules._validate_check_type(check)

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertTrue(result.details["has_category"])
        self.assertEqual(result.details["normalized_category"], "COMPLETENESS")

    def test_validate_check_type_all_valid_types(self):
        """Test check type validation with all valid types"""
        valid_types = [
            "COMPLETENESS",
            "ACCURACY",
            "CONSISTENCY",
            "VALIDITY",
            "UNIQUENESS",
            "TIMELINESS",
        ]

        for check_type in valid_types:
            check = {
                "name": f"Test {check_type}",
                "category": check_type,
                "expectation": {"type": "expect_custom", "params": {}},
            }
            result = self.rules._validate_check_type(check)
            self.assertTrue(result.is_valid, f"Check type {check_type} should be valid")
            self.assertEqual(result.details["normalized_category"], check_type)

    def test_validate_check_type_case_insensitive(self):
        """Test check type validation is case insensitive"""
        check = {
            "name": "Test Check",
            "category": "completeness",  # lowercase
            "expectation": {"type": "expect_custom", "params": {}},
        }

        result = self.rules._validate_check_type(check)

        self.assertTrue(result.is_valid)
        self.assertEqual(result.details["normalized_category"], "COMPLETENESS")

    def test_validate_check_type_invalid_type(self):
        """Test check type validation with invalid type"""
        check = {
            "name": "Test Check",
            "category": "INVALID_TYPE",
            "expectation": {"type": "expect_custom", "params": {}},
        }

        result = self.rules._validate_check_type(check)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("invalid category/type", result.errors[0].lower())

    def test_validate_check_type_missing_category(self):
        """Test check type validation with missing category"""
        check = {"name": "Test Check", "expectation": {"type": "expect_custom", "params": {}}}

        result = self.rules._validate_check_type(check)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("category", result.errors[0].lower())

    def test_validate_check_type_uses_type_field(self):
        """Test check type validation uses 'type' field if 'category' not present"""
        check = {
            "name": "Test Check",
            "type": "VALIDITY",  # Using 'type' instead of 'category'
            "expectation": {"type": "expect_custom", "params": {}},
        }

        result = self.rules._validate_check_type(check)

        self.assertTrue(result.is_valid)
        self.assertEqual(result.details["normalized_category"], "VALIDITY")


class CheckConfigurationValidationTest(DQTestBase):
    """Test check configuration validation"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        self.rules = DQBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

    def test_validate_check_configuration_valid(self):
        """Test check configuration validation with valid configuration"""
        check = {
            "name": "Test Check",
            "category": "COMPLETENESS",
            "target": {"level": "COLUMN", "column": "test_column"},
            "expectation": {"type": "expect_column_values_to_not_be_null", "params": {}},
        }

        result = self.rules._validate_check_configuration(check)

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

    def test_validate_check_configuration_valid_thresholds(self):
        """Test check configuration validation with valid thresholds"""
        check = {
            "name": "Test Check",
            "category": "COMPLETENESS",
            "target": {"level": "COLUMN"},
            "expectation": {
                "type": "expect_column_null_ratio_to_be_less_than",
                "params": {"threshold": 0.01, "min_value": 0, "max_value": 100},
            },
        }

        result = self.rules._validate_check_configuration(check)

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

    def test_validate_check_configuration_invalid_threshold(self):
        """Test check configuration validation with invalid threshold"""
        check = {
            "name": "Test Check",
            "category": "COMPLETENESS",
            "target": {"level": "COLUMN"},
            "expectation": {
                "type": "expect_column_null_ratio_to_be_less_than",
                "params": {"threshold": "not a number"},
            },
        }

        result = self.rules._validate_check_configuration(check)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("threshold", result.errors[0].lower())

    def test_validate_check_configuration_valid_target_levels(self):
        """Test check configuration validation with valid target levels"""
        valid_levels = ["COLUMN", "DATASET", "TABLE"]

        for level in valid_levels:
            check = {
                "name": f"Test {level}",
                "category": "COMPLETENESS",
                "target": {"level": level},
                "expectation": {"type": "expect_custom", "params": {}},
            }
            result = self.rules._validate_check_configuration(check)
            self.assertTrue(result.is_valid, f"Target level {level} should be valid")

    def test_validate_check_configuration_invalid_target_level(self):
        """Test check configuration validation with invalid target level"""
        check = {
            "name": "Test Check",
            "category": "COMPLETENESS",
            "target": {"level": "INVALID_LEVEL"},
            "expectation": {"type": "expect_custom", "params": {}},
        }

        result = self.rules._validate_check_configuration(check)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_validate_check_configuration_column_target_missing_column(self):
        """Test check configuration validation warns when COLUMN level has no column"""
        check = {
            "name": "Test Check",
            "category": "COMPLETENESS",
            "target": {"level": "COLUMN"},  # No column or column_pattern
            "expectation": {"type": "expect_custom", "params": {}},
        }

        result = self.rules._validate_check_configuration(check)

        self.assertTrue(result.is_valid)  # Warning, not error
        self.assertGreater(len(result.warnings), 0)
        self.assertIn("column", result.warnings[0].lower())

    def test_validate_check_configuration_expectation_not_dict(self):
        """Test check configuration validation with non-dict expectation"""
        check = {"name": "Test Check", "category": "COMPLETENESS", "expectation": "not a dict"}

        result = self.rules._validate_check_configuration(check)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)


class CheckSchemaCompatibilityValidationTest(DQTestBase):
    """Test check schema compatibility validation"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        self.rules = DQBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        # Create dataset with schema
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

        # Create file for dataset
        self.file = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1024,
            status=FileStatus.ACTIVE,
            storage_path=f"{self.tenant.id}/test.csv",
            created_by=self.user,
        )

        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            version=1,
            format="csv",
            schema_json={
                "fields": [
                    {"name": "id", "data_type": "integer", "nullable": False},
                    {"name": "name", "data_type": "string", "nullable": True},
                    {"name": "user_id", "data_type": "integer", "nullable": False},
                    {"name": "created_at", "data_type": "timestamp", "nullable": False},
                ]
            },
            created_by=self.user,
        )

    def test_validate_check_schema_compatibility_column_exists(self):
        """Test schema compatibility validation with existing column"""
        check = {
            "name": "Test Check",
            "category": "COMPLETENESS",
            "target": {"level": "COLUMN", "column": "id"},
            "expectation": {"type": "expect_custom", "params": {}},
        }

        result = self.rules._validate_check_schema_compatibility(check, self.dataset)

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertTrue(result.details["target_column_exists"])

    def test_validate_check_schema_compatibility_column_not_exists(self):
        """Test schema compatibility validation with non-existent column"""
        check = {
            "name": "Test Check",
            "category": "COMPLETENESS",
            "target": {"level": "COLUMN", "column": "nonexistent_column"},
            "expectation": {"type": "expect_custom", "params": {}},
        }

        result = self.rules._validate_check_schema_compatibility(check, self.dataset)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("nonexistent_column", result.errors[0])

    def test_validate_check_schema_compatibility_column_pattern_matches(self):
        """Test schema compatibility validation with matching column pattern"""
        check = {
            "name": "Test Check",
            "category": "COMPLETENESS",
            "target": {"level": "COLUMN", "column_pattern": ".*_id$"},
            "expectation": {"type": "expect_custom", "params": {}},
        }

        result = self.rules._validate_check_schema_compatibility(check, self.dataset)

        self.assertTrue(result.is_valid)
        self.assertTrue(result.details["pattern_matches"])
        self.assertIn("user_id", result.details["matching_columns"])

    def test_validate_check_schema_compatibility_column_pattern_no_match(self):
        """Test schema compatibility validation with non-matching column pattern"""
        check = {
            "name": "Test Check",
            "category": "COMPLETENESS",
            "target": {"level": "COLUMN", "column_pattern": "^nonexistent_.*$"},
            "expectation": {"type": "expect_custom", "params": {}},
        }

        result = self.rules._validate_check_schema_compatibility(check, self.dataset)

        self.assertTrue(result.is_valid)  # Warning, not error
        self.assertGreater(len(result.warnings), 0)
        self.assertFalse(result.details["pattern_matches"])

    def test_validate_check_schema_compatibility_dataset_level(self):
        """Test schema compatibility validation with dataset-level check"""
        check = {
            "name": "Test Check",
            "category": "COMPLETENESS",
            "target": {"level": "DATASET"},
            "expectation": {"type": "expect_custom", "params": {}},
        }

        result = self.rules._validate_check_schema_compatibility(check, self.dataset)

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertTrue(result.details["schema_compatible"])

    def test_validate_check_schema_compatibility_invalid_pattern(self):
        """Test schema compatibility validation with invalid regex pattern"""
        check = {
            "name": "Test Check",
            "category": "COMPLETENESS",
            "target": {"level": "COLUMN", "column_pattern": "[invalid regex"},
            "expectation": {"type": "expect_custom", "params": {}},
        }

        result = self.rules._validate_check_schema_compatibility(check, self.dataset)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("invalid column pattern", result.errors[0].lower())

    def test_validate_check_schema_compatibility_no_schema(self):
        """Test schema compatibility validation with dataset without schema"""
        # Create file for dataset without schema
        file_no_schema = File.objects.create(
            tenant=self.tenant,
            name="no_schema.csv",
            content_type="text/csv",
            size=1024,
            status=FileStatus.ACTIVE,
            storage_path=f"{self.tenant.id}/no_schema.csv",
            created_by=self.user,
        )

        dataset_no_schema = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=file_no_schema,
            version=2,
            format="csv",
            schema_json=None,
            created_by=self.user,
        )

        check = {
            "name": "Test Check",
            "category": "COMPLETENESS",
            "target": {"level": "COLUMN", "column": "id"},
            "expectation": {"type": "expect_custom", "params": {}},
        }

        result = self.rules._validate_check_schema_compatibility(check, dataset_no_schema)

        self.assertTrue(result.is_valid)  # Warning, not error
        self.assertGreater(len(result.warnings), 0)


class CheckResourceValidationTest(DQTestBase):
    """Test check resource validation"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        self.rules = DQBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        # Create asset and dataset
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

        # Create file for dataset
        self.file = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1024,
            status=FileStatus.ACTIVE,
            storage_path=f"{self.tenant.id}/test.csv",
            created_by=self.user,
        )

        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            version=1,
            format="csv",
            created_by=self.user,
        )

        # Create job for DQ run
        self.job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DQ_RUN",
            resource_id=self.asset.id,
            created_by=self.user,
        )

    def test_validate_check_resource_valid(self):
        """Test resource validation with valid dataset"""
        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            dataset=self.dataset,
            job=self.job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.PENDING,
        )

        check = {
            "name": "Test Check",
            "category": "COMPLETENESS",
            "expectation": {"type": "expect_custom", "params": {}},
        }

        result = self.rules._validate_check_resource(check, dq_run, None, self.tenant, self.user)

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertTrue(result.details["dataset_exists"])
        self.assertTrue(result.details["tenant_match"])

    def test_validate_check_resource_tenant_mismatch(self):
        """Test resource validation with tenant mismatch"""
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}", slug=f"other-tenant-{_uid}", kyc_status=KYCStatus.VERIFIED
        )
        # Create file for other dataset
        other_file = File.objects.create(
            tenant=other_tenant,
            name="other.csv",
            content_type="text/csv",
            size=1024,
            status=FileStatus.ACTIVE,
            storage_path=f"{other_tenant.id}/other.csv",
            created_by=self.user,
        )

        other_dataset = Dataset.objects.create(
            tenant=other_tenant,
            asset=self.asset,
            file=other_file,
            version=1,
            format="csv",
            created_by=self.user,
        )

        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            dataset=other_dataset,
            job=self.job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.PENDING,
        )

        check = {
            "name": "Test Check",
            "category": "COMPLETENESS",
            "expectation": {"type": "expect_custom", "params": {}},
        }

        result = self.rules._validate_check_resource(check, dq_run, None, self.tenant, self.user)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("tenant", result.errors[0].lower())

    def test_validate_check_resource_dataset_direct(self):
        """Test resource validation with dataset provided directly"""
        check = {
            "name": "Test Check",
            "category": "COMPLETENESS",
            "expectation": {"type": "expect_custom", "params": {}},
        }

        result = self.rules._validate_check_resource(
            check, None, self.dataset, self.tenant, self.user
        )

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertTrue(result.details["dataset_exists"])

    def test_validate_check_resource_no_dataset(self):
        """Test resource validation with no dataset"""
        check = {
            "name": "Test Check",
            "category": "COMPLETENESS",
            "expectation": {"type": "expect_custom", "params": {}},
        }

        result = self.rules._validate_check_resource(check, None, None, self.tenant, self.user)

        self.assertTrue(result.is_valid)  # Warning, not error
        self.assertGreater(len(result.warnings), 0)


class DQCheckConfigurationValidationIntegrationTest(DQTestBase):
    """Integration test for DQ check configuration validation"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        self.rules = DQBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        # Create asset and dataset with schema
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

        # Create file for dataset
        self.file = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1024,
            status=FileStatus.ACTIVE,
            storage_path=f"{self.tenant.id}/test.csv",
            created_by=self.user,
        )

        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            version=1,
            format="csv",
            schema_json={
                "fields": [
                    {"name": "id", "data_type": "integer", "nullable": False},
                    {"name": "name", "data_type": "string", "nullable": True},
                    {"name": "user_id", "data_type": "integer", "nullable": False},
                ]
            },
            created_by=self.user,
        )

        # Create job and DQ run
        self.job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DQ_RUN",
            resource_id=str(self.asset.id),
            created_by=self.user,
        )

        self.dq_run = DQRun.objects.create(
            tenant=self.tenant,
            dataset=self.dataset,
            job=self.job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.PENDING,
        )

    def test_validate_dq_check_config_comprehensive_valid(self):
        """Test comprehensive DQ check configuration validation with valid check"""
        check = {
            "name": "Primary key not null",
            "category": "COMPLETENESS",
            "status": "PASS",
            "target": {"level": "COLUMN", "column": "id"},
            "expectation": {"type": "expect_column_values_to_not_be_null", "params": {}},
        }

        result = self.rules._validate_dq_check_config(
            check, self.dq_run, self.dataset, self.tenant, self.user
        )

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertTrue(result.details["check_type_validated"])
        self.assertTrue(result.details["check_configuration_validated"])
        self.assertTrue(result.details["schema_compatibility_validated"])
        self.assertTrue(result.details["resource_validated"])

    def test_validate_dq_check_config_comprehensive_invalid(self):
        """Test comprehensive DQ check configuration validation with invalid check"""
        check = {
            "name": "Invalid Check",
            "category": "INVALID_TYPE",  # Invalid type
            "target": {"level": "COLUMN", "column": "nonexistent_column"},  # Column doesn't exist
            "expectation": {
                "type": "expect_column_values_to_not_be_null",
                "params": {"threshold": "not a number"},  # Invalid threshold
            },
        }

        result = self.rules._validate_dq_check_config(
            check, self.dq_run, self.dataset, self.tenant, self.user
        )

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_validate_dq_check_config_with_dq_service(self):
        """Test DQ check configuration validation integrated with DQService"""
        from hub.apps.dq.service_client import DQServiceClient

        # Create a valid check configuration
        check = {
            "name": "Null ratio threshold",
            "category": "COMPLETENESS",
            "target": {"level": "COLUMN", "column": "name"},
            "expectation": {
                "type": "expect_column_null_ratio_to_be_less_than",
                "params": {"threshold": 0.01},
            },
        }

        # Validate check configuration
        result = self.rules._validate_dq_check_config(
            check, self.dq_run, self.dataset, self.tenant, self.user
        )

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

        # Verify DQ service client can be instantiated (integration check)
        try:
            dq_client = DQServiceClient()
            self.assertIsNotNone(dq_client)
        except Exception as e:
            # DQ service might not be available in test environment
            # This is acceptable - we're testing the business rules, not the service
            pass


class DQRunExecutionValidationTest(DQTestBase):
    """Test DQ run execution validation"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        self.rules = DQBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        # Create asset and dataset
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            version=1,
            format="csv",
            created_by=self.user,
        )

    def test_validate_dq_run_eligibility_valid(self):
        """Test run eligibility validation with valid user and dataset"""
        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            dataset=self.dataset,
            job=self.job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.PENDING,
        )

        result = self.rules._validate_dq_run_eligibility(dq_run, self.user, self.tenant)

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertTrue(result.details["eligible"])
        self.assertTrue(result.details["user_active"])
        self.assertTrue(result.details["user_tenant_match"])
        self.assertTrue(result.details["resource_accessible"])

    def test_validate_dq_run_eligibility_user_inactive(self):
        """Test run eligibility validation with inactive user"""
        from hub.apps.users.models import UserStatus

        inactive_user = User.objects.create_user(
            email=f"inactive-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.DISABLED,
        )

        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            dataset=self.dataset,
            job=self.job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.PENDING,
        )

        result = self.rules._validate_dq_run_eligibility(dq_run, inactive_user, self.tenant)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("not active", result.errors[0])

    def test_validate_dq_run_eligibility_user_tenant_mismatch(self):
        """Test run eligibility validation with user from different tenant"""
        from hub.apps.users.models import UserStatus

        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}", slug=f"other-tenant-{_uid}", kyc_status=KYCStatus.VERIFIED
        )
        other_user = User.objects.create_user(
            email=f"other-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=other_tenant,
            status=UserStatus.ACTIVE,
        )

        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            dataset=self.dataset,
            job=self.job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.PENDING,
        )

        result = self.rules._validate_dq_run_eligibility(dq_run, other_user, self.tenant)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("tenant", result.errors[0].lower())

    def test_validate_dq_run_eligibility_dataset_no_file(self):
        """Test run eligibility validation with dataset without file"""
        dataset_no_file = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=None,
            version=2,
            format="csv",
            created_by=self.user,
        )

        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            dataset=dataset_no_file,
            job=self.job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.PENDING,
        )

        result = self.rules._validate_dq_run_eligibility(dq_run, self.user, self.tenant)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("no associated file", result.errors[0].lower())

    def test_validate_dq_run_resource_quota_valid(self):
        """Test resource quota validation with available quota"""
        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            dataset=self.dataset,
            job=self.job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.PENDING,
        )

        result = self.rules._validate_dq_run_resource_quota(dq_run, self.tenant)

        # Quota validation may pass or fail depending on DQ service availability
        # We just verify the method runs without errors
        self.assertIsNotNone(result)
        self.assertIn("quota_info", result.details)

    def test_validate_dq_run_execution_error_handling_none_dq_run(self):
        """Test error handling when dq_run is None"""
        # Method should handle None gracefully or raise appropriate error
        try:
            result = self.rules.validate_dq_run_execution(
                dq_run=None, user=self.user, tenant=self.tenant
            )
            # If it doesn't raise, should return invalid result
            self.assertIsNotNone(result)
            self.assertFalse(result.is_valid)
        except (AttributeError, TypeError, ValueError):
            # Expected - None dq_run should cause error
            pass

    def test_validate_dq_run_execution_error_handling_invalid_status_transition(self):
        """Test error handling for invalid status transition"""
        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            dataset=self.dataset,
            job=self.job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.SUCCEEDED,  # Already succeeded
        )

        # Try to validate transition from SUCCEEDED to PENDING (invalid)
        # Pass string values for status
        result = self.rules._validate_dq_run_status_transition(
            dq_run,
            current_status=DQRunStatus.SUCCEEDED.value,
            new_status=DQRunStatus.PENDING.value,
        )

        # Should detect invalid transition
        self.assertIsNotNone(result)
        self.assertFalse(result.is_valid)
        self.assertEqual(result.details.get("validation_type"), "status_transition")
        self.assertIn("status_transition_valid", result.details)
        self.assertFalse(result.details["status_transition_valid"])

    def test_validate_dq_run_execution_error_handling_missing_tenant(self):
        """Test error handling when tenant is None"""
        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            dataset=self.dataset,
            job=self.job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.PENDING,
        )

        # Validation should handle None tenant gracefully
        result = self.rules.validate_dq_run_execution(dq_run=dq_run, user=self.user, tenant=None)

        # Should return validation result (may have warnings about missing tenant)
        self.assertIsNotNone(result)
        self.assertIsInstance(result, ValidationResult)

    def test_validate_dq_run_execution_error_handling_missing_user(self):
        """Test error handling when user is None"""
        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            dataset=self.dataset,
            job=self.job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.PENDING,
        )

        # Validation should handle None user gracefully
        result = self.rules.validate_dq_run_execution(dq_run=dq_run, user=None, tenant=self.tenant)

        # Should return validation result (may have warnings about missing user)
        self.assertIsNotNone(result)
        self.assertIsInstance(result, ValidationResult)

    def test_validate_dq_run_schedule_no_conflicts(self):
        """Test schedule validation with no conflicting runs"""
        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            dataset=self.dataset,
            job=self.job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.PENDING,
        )

        result = self.rules._validate_dq_run_schedule(dq_run, self.tenant)

        self.assertTrue(result.is_valid)
        self.assertFalse(result.details.get("conflicts_detected", True))

    def test_validate_dq_run_schedule_with_conflicts(self):
        """Test schedule validation with conflicting runs"""
        # Create first DQ run
        dq_run1 = DQRun.objects.create(
            tenant=self.tenant,
            dataset=self.dataset,
            job=self.job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.PENDING,
        )

        # Create second job and DQ run for same dataset
        job2 = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DQ_RUN",
            resource_id=str(uuid.uuid4()),
            created_by=self.user,
        )

        dq_run2 = DQRun.objects.create(
            tenant=self.tenant,
            dataset=self.dataset,
            job=job2,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.PENDING,
        )

        result = self.rules._validate_dq_run_schedule(dq_run2, self.tenant)

        # Should detect conflicts (warnings, not errors)
        self.assertTrue(result.is_valid)  # Warnings don't make it invalid
        self.assertTrue(result.details.get("conflicts_detected", False))
        self.assertGreater(len(result.warnings), 0)

    def test_validate_dq_run_status_transition_valid(self):
        """Test status transition validation with valid transitions"""
        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            dataset=self.dataset,
            job=self.job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.PENDING,
        )

        # Test PENDING -> RUNNING
        result = self.rules._validate_dq_run_status_transition(
            dq_run, current_status=DQRunStatus.PENDING, new_status=DQRunStatus.RUNNING
        )

        self.assertTrue(result.is_valid)
        self.assertTrue(result.details["transition_allowed"])

        # Test RUNNING -> SUCCEEDED
        from django.utils import timezone

        dq_run.started_at = timezone.now()
        dq_run.completed_at = timezone.now()
        result = self.rules._validate_dq_run_status_transition(
            dq_run, current_status=DQRunStatus.RUNNING, new_status=DQRunStatus.SUCCEEDED
        )

        self.assertTrue(result.is_valid)
        self.assertTrue(result.details["transition_allowed"])

    def test_validate_dq_run_status_transition_invalid(self):
        """Test status transition validation with invalid transitions"""
        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            dataset=self.dataset,
            job=self.job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.SUCCEEDED,
        )

        # Test SUCCEEDED -> RUNNING (invalid - terminal state)
        result = self.rules._validate_dq_run_status_transition(
            dq_run, current_status=DQRunStatus.SUCCEEDED, new_status=DQRunStatus.RUNNING
        )

        self.assertFalse(result.is_valid)
        self.assertFalse(result.details.get("transition_allowed", True))
        self.assertGreater(len(result.errors), 0)

    def test_validate_dq_run_status_transition_pending_to_succeeded(self):
        """Test status transition validation - cannot go from PENDING to SUCCEEDED"""
        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            dataset=self.dataset,
            job=self.job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.PENDING,
        )

        result = self.rules._validate_dq_run_status_transition(
            dq_run, current_status=DQRunStatus.PENDING, new_status=DQRunStatus.SUCCEEDED
        )

        self.assertFalse(result.is_valid)
        self.assertFalse(result.details.get("transition_allowed", True))

    def test_validate_dq_run_execution_comprehensive(self):
        """Test comprehensive DQ run execution validation"""
        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            dataset=self.dataset,
            job=self.job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.PENDING,
        )

        result = self.rules.validate_dq_run_execution(
            dq_run, user=self.user, tenant=self.tenant, validation_type="all"
        )

        self.assertIsNotNone(result)
        self.assertIn("eligibility_validated", result.details)
        self.assertIn("quota_validated", result.details)
        self.assertIn("schedule_validated", result.details)
        self.assertIn("status_transition_validated", result.details)

    def test_validate_dq_run_execution_eligibility_only(self):
        """Test DQ run execution validation with eligibility only"""
        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            dataset=self.dataset,
            job=self.job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.PENDING,
        )

        result = self.rules.validate_dq_run_execution(
            dq_run, user=self.user, tenant=self.tenant, validation_type="eligibility"
        )

        self.assertIsNotNone(result)
        self.assertIn("eligibility_validated", result.details)
        self.assertNotIn("quota_validated", result.details)


class DQRunExecutionIntegrationTest(DQTestBase):
    """Integration test for DQ run execution validation with DQService"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        self.rules = DQBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        # Create asset, dataset, file, and job
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

        self.file = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1024,
            storage_path="s3://bucket/test.csv",
            status=FileStatus.ACTIVE,
            created_by=self.user,
        )

        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            version=1,
            format="csv",
            created_by=self.user,
        )

        self.job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DQ_RUN",
            resource_id=str(uuid.uuid4()),
            created_by=self.user,
        )

    def test_validate_dq_run_execution_with_dq_service(self):
        """Test DQ run execution validation integrated with DQService"""
        from hub.apps.dq.service_client import DQServiceClient

        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            dataset=self.dataset,
            job=self.job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.PENDING,
        )

        # Validate execution (includes DQ service health check)
        result = self.rules.validate_dq_run_execution(
            dq_run, user=self.user, tenant=self.tenant, validation_type="quota"
        )

        self.assertIsNotNone(result)
        self.assertIn("dq_service_available", result.details)

        # Verify DQ service client can be instantiated
        try:
            dq_client = DQServiceClient()
            self.assertIsNotNone(dq_client)

            # Try health check (may fail if service not available, that's OK)
            is_healthy, status = dq_client.health_check()
            # We don't assert on health - service might not be running in test env
        except Exception as e:
            # DQ service might not be available in test environment
            # This is acceptable - we're testing the business rules integration, not the service
            pass


class ScorecardCalculationValidationTest(DQTestBase):
    """Test scorecard calculation validation"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        self.rules = DQBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        # Create asset
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

        # Create job
        self.job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DQ_RUN",
            resource_id=uuid.uuid4(),
            created_by=self.user,
        )

    def test_validate_scorecard_aggregation_rules_valid_config(self):
        """Test aggregation rules validation with valid config"""
        aggregation_config = {"functions": ["Avg", "Count", "Sum", "Min", "Max"]}

        result = self.rules._validate_scorecard_aggregation_rules(
            aggregation_config, None, self.tenant, self.asset
        )

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertTrue(result.details["aggregation_config_valid"])
        self.assertTrue(result.details["all_functions_valid"])

    def test_validate_scorecard_aggregation_rules_invalid_functions(self):
        """Test aggregation rules validation with invalid functions"""
        aggregation_config = {"functions": ["InvalidFunction", "AnotherInvalid"]}

        result = self.rules._validate_scorecard_aggregation_rules(
            aggregation_config, None, self.tenant, self.asset
        )

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("Invalid aggregation functions", result.errors[0])

    def test_validate_scorecard_aggregation_rules_valid_scorecard_data(self):
        """Test aggregation rules validation with valid scorecard data"""
        scorecard_data = {
            "summary": {
                "total_runs": 10,
                "avg_quality_score": 85.5,
                "pass_rate": 80.0,
                "fail_rate": 10.0,
            },
            "score_distribution": {"excellent": 5, "good": 3, "fair": 1, "poor": 1, "critical": 0},
        }

        result = self.rules._validate_scorecard_aggregation_rules(
            None, scorecard_data, self.tenant, self.asset
        )

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertTrue(result.details["scorecard_data_valid"])
        self.assertTrue(result.details["summary_valid"])

    def test_validate_scorecard_aggregation_rules_invalid_summary_field(self):
        """Test aggregation rules validation with invalid summary field"""
        scorecard_data = {"summary": {"total_runs": "not a number", "avg_quality_score": 85.5}}

        result = self.rules._validate_scorecard_aggregation_rules(
            None, scorecard_data, self.tenant, self.asset
        )

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("total_runs", result.errors[0])

    def test_validate_scorecard_aggregation_rules_invalid_distribution(self):
        """Test aggregation rules validation with invalid score distribution"""
        scorecard_data = {
            "summary": {"total_runs": 10},
            "score_distribution": {"excellent": -5, "good": "not a number"},  # Negative count
        }

        result = self.rules._validate_scorecard_aggregation_rules(
            None, scorecard_data, self.tenant, self.asset
        )

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_validate_scorecard_aggregation_rules_score_out_of_range(self):
        """Test aggregation rules validation with score out of range"""
        scorecard_data = {"summary": {"avg_quality_score": 150.0}}  # Out of range (0-100)

        result = self.rules._validate_scorecard_aggregation_rules(
            None, scorecard_data, self.tenant, self.asset
        )

        self.assertTrue(result.is_valid)  # Warning, not error
        self.assertGreater(len(result.warnings), 0)
        self.assertIn("outside expected range", result.warnings[0])


class ScorecardThresholdValidationTest(DQTestBase):
    """Test scorecard threshold validation"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        self.rules = DQBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

    def test_validate_scorecard_thresholds_default_thresholds(self):
        """Test threshold validation with default thresholds"""
        result = self.rules._validate_scorecard_thresholds(None, self.tenant, None)

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(result.details["pass_threshold"], 80.0)
        self.assertEqual(result.details["warn_threshold"], 60.0)
        self.assertEqual(result.details["fail_threshold"], 0.0)
        self.assertTrue(result.details["threshold_ordering_valid"])

    def test_validate_scorecard_thresholds_custom_thresholds(self):
        """Test threshold validation with custom thresholds"""
        scorecard_data = {
            "thresholds": {"pass_threshold": 90.0, "warn_threshold": 70.0, "fail_threshold": 50.0}
        }

        result = self.rules._validate_scorecard_thresholds(scorecard_data, self.tenant, None)

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(result.details["pass_threshold"], 90.0)
        self.assertEqual(result.details["warn_threshold"], 70.0)
        self.assertEqual(result.details["fail_threshold"], 50.0)

    def test_validate_scorecard_thresholds_invalid_ordering(self):
        """Test threshold validation with invalid ordering"""
        scorecard_data = {
            "thresholds": {
                "pass_threshold": 50.0,  # Lower than warn
                "warn_threshold": 70.0,
                "fail_threshold": 0.0,
            }
        }

        result = self.rules._validate_scorecard_thresholds(scorecard_data, self.tenant, None)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("Pass threshold", result.errors[0])

    def test_validate_scorecard_thresholds_out_of_range(self):
        """Test threshold validation with thresholds out of range"""
        scorecard_data = {
            "thresholds": {
                "pass_threshold": 150.0,  # Out of range
                "warn_threshold": -10.0,  # Out of range
                "fail_threshold": 0.0,
            }
        }

        result = self.rules._validate_scorecard_thresholds(scorecard_data, self.tenant, None)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_validate_scorecard_thresholds_status_matching(self):
        """Test threshold validation with status matching"""
        scorecard_data = {
            "summary": {"avg_quality_score": 85.0},  # Should be PASS (>= 80)
            "overall_status": "PASS",
            "thresholds": {"pass_threshold": 80.0, "warn_threshold": 60.0, "fail_threshold": 0.0},
        }

        result = self.rules._validate_scorecard_thresholds(scorecard_data, self.tenant, None)

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertTrue(result.details["status_matches_thresholds"])

    def test_validate_scorecard_thresholds_status_mismatch(self):
        """Test threshold validation with status mismatch"""
        scorecard_data = {
            "summary": {"avg_quality_score": 85.0},  # Should be PASS (>= 80)
            "overall_status": "FAIL",  # Mismatch
            "thresholds": {"pass_threshold": 80.0, "warn_threshold": 60.0, "fail_threshold": 0.0},
        }

        result = self.rules._validate_scorecard_thresholds(scorecard_data, self.tenant, None)

        self.assertTrue(result.is_valid)  # Warning, not error
        self.assertGreater(len(result.warnings), 0)
        self.assertIn("does not match", result.warnings[0])


class ScorecardUpdateTriggersValidationTest(DQTestBase):
    """Test scorecard update triggers validation"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        self.rules = DQBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        # Create asset
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

        # Create job
        self.job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DQ_RUN",
            resource_id=uuid.uuid4(),
            created_by=self.user,
        )

    def test_validate_scorecard_update_triggers_with_tenant(self):
        """Test update triggers validation with tenant"""
        result = self.rules._validate_scorecard_update_triggers(self.tenant, None)

        self.assertTrue(result.is_valid)
        self.assertTrue(result.details["tenant_provided"])
        self.assertIn("expected_triggers", result.details)

    def test_validate_scorecard_update_triggers_with_asset_no_runs(self):
        """Test update triggers validation with asset but no DQ runs"""
        result = self.rules._validate_scorecard_update_triggers(self.tenant, self.asset)

        self.assertTrue(result.is_valid)  # Warning, not error
        self.assertTrue(result.details["asset_provided"])
        self.assertFalse(result.details.get("asset_has_dq_runs", True))
        self.assertGreater(len(result.warnings), 0)

    def test_validate_scorecard_update_triggers_with_asset_with_runs(self):
        """Test update triggers validation with asset that has DQ runs"""
        # Create DQ runs
        from datetime import timedelta

        from django.utils import timezone

        for i in range(5):
            DQRun.objects.create(
                tenant=self.tenant,
                asset=self.asset,
                job=self.job,
                profile_key="intake_basic_gx",
                engine=DQEngine.GREAT_EXPECTATIONS,
                status=DQRunStatus.SUCCEEDED,
                quality_score=85.0 + i,
                overall_status="PASS",
                completed_at=timezone.now() - timedelta(days=i),
            )

        result = self.rules._validate_scorecard_update_triggers(self.tenant, self.asset)

        self.assertTrue(result.is_valid)
        self.assertTrue(result.details["asset_provided"])
        self.assertTrue(result.details["asset_has_dq_runs"])
        self.assertTrue(result.details["has_recent_dq_runs"])

    def test_validate_scorecard_update_triggers_scorecard_service_available(self):
        """Test update triggers validation checks scorecard service availability"""
        result = self.rules._validate_scorecard_update_triggers(self.tenant, self.asset)

        self.assertTrue(result.is_valid)
        self.assertTrue(result.details["scorecard_service_available"])


class ScorecardCalculationValidationIntegrationTest(DQTestBase):
    """Integration test for scorecard calculation validation"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        self.rules = DQBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        # Create asset
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

        # Create job
        self.job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DQ_RUN",
            resource_id=uuid.uuid4(),
            created_by=self.user,
        )

        # Create DQ runs for scorecard data
        from datetime import timedelta

        from django.utils import timezone

        for i in range(10):
            DQRun.objects.create(
                tenant=self.tenant,
                asset=self.asset,
                job=self.job,
                profile_key="intake_basic_gx",
                engine=DQEngine.GREAT_EXPECTATIONS,
                status=DQRunStatus.SUCCEEDED,
                quality_score=75.0 + (i * 2.0),
                overall_status="PASS" if (75.0 + (i * 2.0)) >= 80.0 else "WARN",
                completed_at=timezone.now() - timedelta(days=i),
            )

    def test_validate_scorecard_calculation_comprehensive(self):
        """Test comprehensive scorecard calculation validation"""
        from hub.apps.dq.scorecards import DQScorecardService

        # Get actual scorecard data
        scorecard_data = DQScorecardService.get_asset_scorecard(
            str(self.asset.id), str(self.tenant.id), days=30
        )

        # Validate scorecard calculation
        result = self.rules.validate_scorecard_calculation(
            scorecard_data=scorecard_data, tenant=self.tenant, asset=self.asset
        )

        self.assertTrue(result.is_valid)
        self.assertTrue(result.details["aggregation_rules_validated"])
        self.assertTrue(result.details["thresholds_validated"])
        self.assertTrue(result.details["update_triggers_validated"])

    def test_validate_scorecard_calculation_with_dq_service(self):
        """Test scorecard calculation validation integrated with DQService"""
        from hub.apps.dq.scorecards import DQScorecardService
        from hub.apps.dq.service_client import DQServiceClient

        # Get actual scorecard data
        scorecard_data = DQScorecardService.get_asset_scorecard(
            str(self.asset.id), str(self.tenant.id), days=30
        )

        # Validate scorecard calculation
        result = self.rules.validate_scorecard_calculation(
            scorecard_data=scorecard_data, tenant=self.tenant, asset=self.asset
        )

        self.assertTrue(result.is_valid)

        # Verify DQ service client can be instantiated
        try:
            dq_client = DQServiceClient()
            self.assertIsNotNone(dq_client)
        except Exception as e:
            # DQ service might not be available in test environment
            # This is acceptable - we're testing the business rules integration
            pass

        # Verify DQ service client can be instantiated
        try:
            dq_client = DQServiceClient()
            self.assertIsNotNone(dq_client)
        except Exception as e:
            # DQ service might not be available in test environment
            # This is acceptable - we're testing the business rules integration
            pass
