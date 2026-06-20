"""
Tests for Jobs Business Rules

Comprehensive tests for JobsBusinessRules validation, following engineering best practices:
- No mocks/stubs - use real services and models
- Fix root causes, not symptoms
- Comprehensive test coverage
- Follow DRY, SOLID, and clean code principles
"""

import uuid

import pytest
from django.test import TestCase
from django.utils import timezone

pytestmark = pytest.mark.django_db(transaction=True)

from hub.apps.core.business_rules.registry import get_registry
from hub.apps.jobs.business_rules import (
    JobsBusinessRules,
    JobsRuleExecutionContext,
)
from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.users.models import User


class JobsBusinessRulesInitializationTest(TestCase):
    """Test JobsBusinessRules initialization"""

    def setUp(self):
        """Set up test fixtures"""
        from hub.apps.users.models import UserStatus

        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

    def test_jobs_business_rules_initialization(self):
        """Test JobsBusinessRules can be initialized with tenant and user"""
        rules = JobsBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))
        self.assertIsInstance(rules, JobsBusinessRules)
        self.assertEqual(rules.get_rule_name(), "JobsBusinessRules")
        self.assertEqual(rules.tenant_id, str(self.tenant.id))
        self.assertEqual(rules.user_id, str(self.user.id))

    def test_jobs_business_rules_initialization_without_user(self):
        """Test JobsBusinessRules can be initialized without user"""
        rules = JobsBusinessRules(tenant_id=str(self.tenant.id))
        self.assertIsInstance(rules, JobsBusinessRules)
        self.assertEqual(rules.tenant_id, str(self.tenant.id))
        self.assertIsNone(rules.user_id)

    def test_jobs_business_rules_initialization_without_tenant(self):
        """Test JobsBusinessRules can be initialized without tenant"""
        rules = JobsBusinessRules(user_id=str(self.user.id))
        self.assertIsInstance(rules, JobsBusinessRules)
        self.assertIsNone(rules.tenant_id)
        self.assertEqual(rules.user_id, str(self.user.id))

    def test_jobs_business_rules_initialization_without_context(self):
        """Test JobsBusinessRules can be initialized without tenant or user"""
        rules = JobsBusinessRules()
        self.assertIsInstance(rules, JobsBusinessRules)
        self.assertIsNone(rules.tenant_id)
        self.assertIsNone(rules.user_id)

    def test_jobs_business_rules_enable_caching(self):
        """Test JobsBusinessRules can be initialized with caching enabled/disabled"""
        rules_with_cache = JobsBusinessRules(enable_caching=True)
        self.assertTrue(rules_with_cache.enable_caching)

        rules_without_cache = JobsBusinessRules(enable_caching=False)
        self.assertFalse(rules_without_cache.enable_caching)

    def test_jobs_business_rules_enable_metrics(self):
        """Test JobsBusinessRules can be initialized with metrics enabled/disabled"""
        rules_with_metrics = JobsBusinessRules(enable_metrics=True)
        self.assertTrue(rules_with_metrics.enable_metrics)

        rules_without_metrics = JobsBusinessRules(enable_metrics=False)
        self.assertFalse(rules_without_metrics.enable_metrics)

    def test_jobs_business_rules_enable_tracing(self):
        """Test JobsBusinessRules can be initialized with tracing enabled/disabled"""
        rules_with_tracing = JobsBusinessRules(enable_tracing=True)
        self.assertTrue(rules_with_tracing.enable_tracing)

        rules_without_tracing = JobsBusinessRules(enable_tracing=False)
        self.assertFalse(rules_without_tracing.enable_tracing)

    def test_jobs_business_rules_enable_logging(self):
        """Test JobsBusinessRules can be initialized with logging enabled/disabled"""
        rules_with_logging = JobsBusinessRules(enable_logging=True)
        self.assertTrue(rules_with_logging.enable_logging)

        rules_without_logging = JobsBusinessRules(enable_logging=False)
        self.assertFalse(rules_without_logging.enable_logging)


class JobsBusinessRulesRegistrationTest(TestCase):
    """Test JobsBusinessRules registration in business rules registry"""

    def test_jobs_business_rules_registered(self):
        """Test JobsBusinessRules is registered in the registry"""
        registry = get_registry()
        rule = registry.get_rule("jobs_validation")
        self.assertIsNotNone(rule)
        self.assertEqual(rule.rule_name, "jobs_validation")
        self.assertEqual(rule.rule_class, JobsBusinessRules)
        self.assertIn("jobs", rule.tags)
        self.assertIn("validation", rule.tags)

    def test_jobs_business_rules_priority(self):
        """Test JobsBusinessRules has correct priority"""
        registry = get_registry()
        rule = registry.get_rule("jobs_validation")
        self.assertIsNotNone(rule)
        self.assertEqual(rule.priority, 10)

    def test_jobs_business_rules_description(self):
        """Test JobsBusinessRules has correct description"""
        registry = get_registry()
        rule = registry.get_rule("jobs_validation")
        self.assertIsNotNone(rule)
        self.assertIsNotNone(rule.description)
        self.assertIn("job", rule.description.lower())
        self.assertIn("validates", rule.description.lower())

    def test_jobs_business_rules_enabled(self):
        """Test JobsBusinessRules is enabled by default"""
        registry = get_registry()
        rule = registry.get_rule("jobs_validation")
        self.assertIsNotNone(rule)
        self.assertTrue(rule.enabled)


class JobsRuleExecutionContextTest(TestCase):
    """Test JobsRuleExecutionContext"""

    def setUp(self):
        """Set up test fixtures"""
        from hub.apps.users.models import UserStatus

        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
            created_by=self.user,
        )

    def test_jobs_rule_execution_context_creation(self):
        """Test JobsRuleExecutionContext can be created"""
        context = JobsRuleExecutionContext(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            job=self.job,
            tenant=self.tenant,
            user=self.user,
        )
        self.assertIsInstance(context, JobsRuleExecutionContext)
        self.assertEqual(context.tenant_id, str(self.tenant.id))
        self.assertEqual(context.user_id, str(self.user.id))
        self.assertEqual(context.job, self.job)
        self.assertEqual(context.tenant, self.tenant)
        self.assertEqual(context.user, self.user)

    def test_jobs_rule_execution_context_to_dict(self):
        """Test JobsRuleExecutionContext to_dict method"""
        context = JobsRuleExecutionContext(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            job=self.job,
            tenant=self.tenant,
            user=self.user,
        )
        context_dict = context.to_dict()
        self.assertIsInstance(context_dict, dict)
        self.assertEqual(context_dict["tenant_id"], str(self.tenant.id))
        self.assertEqual(context_dict["user_id"], str(self.user.id))
        self.assertEqual(context_dict["job_id"], str(self.job.id))
        self.assertEqual(context_dict["job_type"], self.job.type)
        self.assertEqual(context_dict["job_status"], self.job.status)
        self.assertEqual(context_dict["tenant_id"], str(self.tenant.id))
        self.assertEqual(context_dict["user_id"], str(self.user.id))

    def test_jobs_rule_execution_context_without_job(self):
        """Test JobsRuleExecutionContext can be created without job"""
        context = JobsRuleExecutionContext(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            tenant=self.tenant,
            user=self.user,
        )
        self.assertIsNone(context.job)
        context_dict = context.to_dict()
        self.assertIsNone(context_dict["job_id"])
        self.assertIsNone(context_dict["job_type"])
        self.assertIsNone(context_dict["job_status"])

    def test_jobs_rule_execution_context_without_tenant(self):
        """Test JobsRuleExecutionContext can be created without tenant instance"""
        context = JobsRuleExecutionContext(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id), job=self.job, user=self.user
        )
        self.assertIsNone(context.tenant)
        context_dict = context.to_dict()
        self.assertIsNone(context_dict.get("tenant_id"))  # tenant_id comes from base class

    def test_jobs_rule_execution_context_without_user(self):
        """Test JobsRuleExecutionContext can be created without user instance"""
        context = JobsRuleExecutionContext(
            tenant_id=str(self.tenant.id), job=self.job, tenant=self.tenant
        )
        self.assertIsNone(context.user)
        context_dict = context.to_dict()
        self.assertIsNone(context_dict.get("user_id"))  # user_id comes from base class


class JobsBusinessRulesValidationTest(TestCase):
    """Test JobsBusinessRules validation methods"""

    def setUp(self):
        """Set up test fixtures"""
        from hub.apps.users.models import UserStatus

        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
            created_by=self.user,
        )
        self.rules = JobsBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

    def test_validate_with_jobs_rule_execution_context(self):
        """Test validate method with JobsRuleExecutionContext"""
        context = JobsRuleExecutionContext(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            job=self.job,
            tenant=self.tenant,
            user=self.user,
        )
        result = self.rules.validate(context)
        self.assertIsInstance(result.is_valid, bool)
        self.assertTrue(result.is_valid)

    def test_validate_with_standard_context(self):
        """Test validate method with standard RuleExecutionContext"""
        from hub.apps.core.business_rules.base import RuleExecutionContext

        context = RuleExecutionContext(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id), resource=self.job
        )
        result = self.rules.validate(context)
        self.assertIsInstance(result.is_valid, bool)
        # Should still validate basic job structure
        self.assertTrue(result.is_valid)

    def test_validate_with_kwargs(self):
        """Test validate method with kwargs"""
        result = self.rules.validate(job=self.job, tenant=self.tenant, user=self.user)
        self.assertIsInstance(result.is_valid, bool)
        self.assertTrue(result.is_valid)

    def test_validate_without_job(self):
        """Test validate method without job"""
        result = self.rules.validate(tenant=self.tenant, user=self.user)
        self.assertIsInstance(result.is_valid, bool)
        # Should validate tenant and user context
        self.assertTrue(result.is_valid)

    def test_validate_without_any_context(self):
        """Test validate method without any context"""
        result = self.rules.validate()
        self.assertIsInstance(result.is_valid, bool)
        # Should return error indicating at least one context is required
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)


class JobsBusinessRulesJobCreationValidationTest(TestCase):
    """Test JobsBusinessRules job creation validation"""

    def setUp(self):
        """Set up test fixtures"""
        from hub.apps.users.models import UserStatus

        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.rules = JobsBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

    def test_validate_job_creation_valid_job(self):
        """Test validate_job_creation with valid job"""
        # Create a real resource (Contract) for the job
        from hub.apps.contracts.models import Contract, ContractStatus

        contract = Contract.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            status=ContractStatus.ACTIVE,
            validation_status="VALID",
        )

        job = Job(
            tenant=self.tenant,
            type=JobType.CONTRACT_VALIDATION,
            status=JobStatus.PENDING,
            resource_type="CONTRACT",
            resource_id=contract.id,
            created_by=self.user,
            details_json={"contract_id": str(contract.id)},
        )

        result = self.rules.validate_job_creation(job, self.tenant, self.user)
        self.assertIsInstance(result.is_valid, bool)
        self.assertTrue(result.is_valid)
        self.assertIn("job_type_validated", result.details)
        self.assertIn("job_configuration_validated", result.details)
        self.assertIn("job_resource_validated", result.details)
        self.assertIn("job_quota_validated", result.details)

    def test_validate_job_type_valid(self):
        """Test _validate_job_type with valid job type"""
        job = Job(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
        )

        result = self.rules._validate_job_type(job)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertTrue(result.details["has_type"])
        self.assertTrue(result.details["job_type_valid"])

    def test_validate_job_type_invalid(self):
        """Test _validate_job_type with invalid job type"""
        job = Job(
            tenant=self.tenant,
            type="INVALID_JOB_TYPE",
            status=JobStatus.PENDING,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
        )

        result = self.rules._validate_job_type(job)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("invalid type", result.errors[0].lower())

    def test_validate_job_type_missing(self):
        """Test _validate_job_type with missing job type"""
        job = Job(
            tenant=self.tenant,
            type="",
            status=JobStatus.PENDING,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
        )

        result = self.rules._validate_job_type(job)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("must have a type", result.errors[0].lower())

    def test_validate_job_configuration_valid(self):
        """Test _validate_job_configuration with valid configuration"""
        job = Job(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
            details_json={"profile_key": "test_profile"},
            timeout_seconds=300,
        )

        result = self.rules._validate_job_configuration(job)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertTrue(result.details["has_resource_type"])
        self.assertTrue(result.details["has_resource_id"])
        self.assertTrue(result.details["details_json_valid"])
        self.assertTrue(result.details["timeout_seconds_valid"])

    def test_validate_job_configuration_missing_resource_type(self):
        """Test _validate_job_configuration with missing resource_type"""
        job = Job(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="",
            resource_id=uuid.uuid4(),
        )

        result = self.rules._validate_job_configuration(job)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("resource_type", result.errors[0].lower())

    def test_validate_job_configuration_missing_resource_id(self):
        """Test _validate_job_configuration with missing resource_id"""
        job = Job(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DATASET",
            resource_id=None,
        )

        result = self.rules._validate_job_configuration(job)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("resource_id", result.errors[0].lower())

    def test_validate_job_configuration_invalid_details_json(self):
        """Test _validate_job_configuration with invalid details_json"""
        job = Job(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
            details_json="not a dict",  # Invalid type
        )

        result = self.rules._validate_job_configuration(job)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("details_json", result.errors[0].lower())

    def test_validate_job_configuration_invalid_timeout(self):
        """Test _validate_job_configuration with invalid timeout_seconds"""
        job = Job(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
            timeout_seconds=-1,  # Invalid: negative
        )

        result = self.rules._validate_job_configuration(job)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("timeout_seconds", result.errors[0].lower())

    def test_validate_job_configuration_long_timeout_warning(self):
        """Test _validate_job_configuration warns on very long timeout"""
        job = Job(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
            timeout_seconds=100000,  # > 24 hours
        )

        result = self.rules._validate_job_configuration(job)
        self.assertTrue(result.is_valid)  # Still valid, just warning
        self.assertGreater(len(result.warnings), 0)
        self.assertIn("timeout", result.warnings[0].lower())

    def test_validate_job_configuration_job_type_specific_checks(self):
        """Test _validate_job_configuration with job type-specific checks"""
        # Test CONTRACT_VALIDATION job with contract_id
        job = Job(
            tenant=self.tenant,
            type=JobType.CONTRACT_VALIDATION,
            status=JobStatus.PENDING,
            resource_type="CONTRACT",
            resource_id=uuid.uuid4(),
            details_json={"contract_id": str(uuid.uuid4())},
        )

        result = self.rules._validate_job_configuration(job)
        self.assertTrue(result.is_valid)
        self.assertTrue(result.details.get("contract_id_in_details", False))

        # Test CONTRACT_VALIDATION job without contract_id (warning)
        job.details_json = {}
        result = self.rules._validate_job_configuration(job)
        self.assertTrue(result.is_valid)  # Still valid, just warning
        self.assertGreater(len(result.warnings), 0)
        self.assertIn("contract_id", result.warnings[0].lower())

    def test_validate_job_resource_valid_contract(self):
        """Test _validate_job_resource with valid contract resource"""
        from hub.apps.contracts.models import Contract, ContractStatus

        contract = Contract.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            status=ContractStatus.ACTIVE,
            validation_status="VALID",
        )

        job = Job(
            tenant=self.tenant,
            type=JobType.CONTRACT_VALIDATION,
            status=JobStatus.PENDING,
            resource_type="CONTRACT",
            resource_id=contract.id,
            created_by=self.user,
        )

        result = self.rules._validate_job_resource(job, self.tenant, self.user)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertTrue(result.details["resource_exists"])
        self.assertTrue(result.details["resource_tenant_match"])

    def test_validate_job_resource_valid_dataset(self):
        """Test _validate_job_resource with valid dataset resource"""
        from hub.apps.assets.models import Asset, AssetStatus
        from hub.apps.datasets.models import Dataset
        from hub.apps.files.models import File, FileStatus

        file_obj = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            size=1024,
            content_type="text/csv",
            status=FileStatus.ACTIVE,
            storage_path="test/test.csv",
            created_by=self.user,
        )

        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=asset,
            file=file_obj,
            version=1,
            format="CSV",
            created_by=self.user,
        )

        job = Job(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DATASET",
            resource_id=dataset.id,
            created_by=self.user,
        )

        result = self.rules._validate_job_resource(job, self.tenant, self.user)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertTrue(result.details["resource_exists"])
        self.assertTrue(result.details["resource_tenant_match"])

    def test_validate_job_resource_nonexistent(self):
        """Test _validate_job_resource with nonexistent resource"""
        job = Job(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),  # Non-existent ID
            created_by=self.user,
        )

        result = self.rules._validate_job_resource(job, self.tenant, self.user)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("does not exist", result.errors[0].lower())

    def test_validate_job_resource_wrong_tenant(self):
        """Test _validate_job_resource with resource from different tenant"""
        from hub.apps.contracts.models import Contract, ContractStatus

        # Create another tenant
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}", slug=f"other-tenant-{_uid}", kyc_status=KYCStatus.VERIFIED
        )
        contract = Contract.objects.create(
            tenant=other_tenant,
            created_by=self.user,
            status=ContractStatus.ACTIVE,
            validation_status="VALID",
        )

        job = Job(
            tenant=self.tenant,
            type=JobType.CONTRACT_VALIDATION,
            status=JobStatus.PENDING,
            resource_type="CONTRACT",
            resource_id=contract.id,
            created_by=self.user,
        )

        result = self.rules._validate_job_resource(job, self.tenant, self.user)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("belongs to tenant", result.errors[0].lower())

    def test_validate_job_resource_inaccessible_status(self):
        """Test _validate_job_resource with resource in inaccessible status"""
        from hub.apps.contracts.models import Contract, ContractStatus

        contract = Contract.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            status=ContractStatus.RETIRED,  # Inaccessible status (RETIRED is in inaccessible_statuses)
            validation_status="VALID",
        )

        job = Job(
            tenant=self.tenant,
            type=JobType.CONTRACT_VALIDATION,
            status=JobStatus.PENDING,
            resource_type="CONTRACT",
            resource_id=contract.id,
            created_by=self.user,
        )

        result = self.rules._validate_job_resource(job, self.tenant, self.user)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("not accessible", result.errors[0].lower())

    def test_validate_job_resource_unknown_type(self):
        """Test _validate_job_resource with unknown resource type"""
        job = Job(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="UNKNOWN_TYPE",
            resource_id=uuid.uuid4(),
            created_by=self.user,
        )

        result = self.rules._validate_job_resource(job, self.tenant, self.user)
        self.assertTrue(result.is_valid)  # Not an error, just can't validate
        self.assertGreater(len(result.warnings), 0)
        self.assertIn("unknown resource_type", result.warnings[0].lower())

    def test_validate_job_quota_within_limits(self):
        """Test _validate_job_quota when tenant is within limits"""
        job = Job(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
            created_by=self.user,
        )

        result = self.rules._validate_job_quota(job, self.tenant)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertIn("quota_validated", result.details)
        self.assertFalse(result.details.get("concurrency_limit_exceeded", False))
        self.assertFalse(result.details.get("queued_limit_exceeded", False))

    def test_validate_job_quota_uses_real_quota_check(self):
        """Test _validate_job_quota uses real quota checking from jobs.utils"""
        job = Job(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
            created_by=self.user,
        )

        result = self.rules._validate_job_quota(job, self.tenant)
        self.assertIsInstance(result.details, dict)
        # Should have quota details
        self.assertIn("max_job_concurrency", result.details)
        self.assertIn("max_queued_jobs", result.details)
        self.assertIn("running_jobs", result.details)
        self.assertIn("queued_jobs", result.details)

    def test_validate_job_creation_with_all_validations(self):
        """Test validate_job_creation orchestrates all validations"""
        from hub.apps.contracts.models import Contract, ContractStatus

        contract = Contract.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            status=ContractStatus.ACTIVE,
            validation_status="VALID",
        )

        job = Job(
            tenant=self.tenant,
            type=JobType.CONTRACT_VALIDATION,
            status=JobStatus.PENDING,
            resource_type="CONTRACT",
            resource_id=contract.id,
            created_by=self.user,
            details_json={"contract_id": str(contract.id)},
            timeout_seconds=300,
        )

        result = self.rules.validate_job_creation(job, self.tenant, self.user)
        self.assertIsInstance(result.is_valid, bool)
        self.assertTrue(result.is_valid)
        # Check all validations were performed
        self.assertTrue(result.details["job_type_validated"])
        self.assertTrue(result.details["job_configuration_validated"])
        self.assertTrue(result.details["job_resource_validated"])
        self.assertTrue(result.details["job_quota_validated"])
        self.assertEqual(result.details["validation_type"], "job_creation")

    def test_validate_job_creation_without_tenant(self):
        """Test validate_job_creation without tenant (skips resource and quota validation)"""
        job = Job(
            tenant=None,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
            created_by=self.user,
        )

        result = self.rules.validate_job_creation(job, None, self.user)
        self.assertIsInstance(result.details, dict)
        # Type and configuration should still be validated
        self.assertTrue(result.details["job_type_validated"])
        self.assertTrue(result.details["job_configuration_validated"])
        # Resource and quota validation should be skipped
        self.assertFalse(result.details["job_resource_validated"])
        self.assertFalse(result.details["job_quota_validated"])

    def test_validate_with_job_creation_type(self):
        """Test validate method with validation_type='job_creation'"""
        from hub.apps.contracts.models import Contract, ContractStatus

        contract = Contract.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            status=ContractStatus.ACTIVE,
            validation_status="VALID",
        )

        job = Job(
            tenant=self.tenant,
            type=JobType.CONTRACT_VALIDATION,
            status=JobStatus.PENDING,
            resource_type="CONTRACT",
            resource_id=contract.id,
            created_by=self.user,
        )

        result = self.rules.validate(
            job=job, tenant=self.tenant, user=self.user, validation_type="job_creation"
        )
        self.assertIsInstance(result.is_valid, bool)
        self.assertTrue(result.is_valid)
        self.assertIn("job_creation", result.details["validated_items"])


class JobsBusinessRulesJobCreationIntegrationTest(TestCase):
    """Integration tests for JobsBusinessRules with create_job utility"""

    def setUp(self):
        """Set up test fixtures"""
        from hub.apps.users.models import UserStatus

        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.rules = JobsBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

    def test_integration_with_create_job_valid(self):
        """Integration test: validate job created via create_job utility"""
        from hub.apps.contracts.models import Contract, ContractStatus
        from hub.apps.jobs.utils import create_job

        # Create a real resource
        contract = Contract.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            status=ContractStatus.ACTIVE,
            validation_status="VALID",
        )

        # Create job using create_job utility
        job = create_job(
            tenant=self.tenant,
            user=self.user,
            job_type=JobType.CONTRACT_VALIDATION,
            resource_type="CONTRACT",
            resource_id=str(contract.id),
            details_json={"contract_id": str(contract.id)},
            timeout_seconds=300,
        )

        # Validate the created job using business rules
        result = self.rules.validate_job_creation(job, self.tenant, self.user)
        self.assertIsInstance(result.is_valid, bool)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        # All validations should pass
        self.assertTrue(result.details["job_type_validated"])
        self.assertTrue(result.details["job_configuration_validated"])
        self.assertTrue(result.details["job_resource_validated"])
        self.assertTrue(result.details["job_quota_validated"])

    def test_integration_with_create_job_invalid_resource(self):
        """Integration test: validate job with invalid resource fails validation"""
        from hub.apps.jobs.utils import create_job

        # Create job with non-existent resource
        non_existent_id = uuid.uuid4()
        job = create_job(
            tenant=self.tenant,
            user=self.user,
            job_type=JobType.DQ_RUN,
            resource_type="DATASET",
            resource_id=str(non_existent_id),
            details_json={},
        )

        # Validate the created job - should fail resource validation
        result = self.rules.validate_job_creation(job, self.tenant, self.user)
        self.assertIsInstance(result.is_valid, bool)
        # Job creation should fail due to invalid resource
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("does not exist", result.errors[0].lower())

    def test_integration_with_create_job_wrong_tenant_resource(self):
        """Integration test: validate job with resource from different tenant fails"""
        from hub.apps.contracts.models import Contract, ContractStatus
        from hub.apps.jobs.utils import create_job

        # Create another tenant and contract
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}", slug=f"other-tenant-{_uid}", kyc_status=KYCStatus.VERIFIED
        )
        contract = Contract.objects.create(
            tenant=other_tenant,
            created_by=self.user,
            status=ContractStatus.ACTIVE,
            validation_status="VALID",
        )

        # Create job for self.tenant but with resource from other_tenant
        job = create_job(
            tenant=self.tenant,
            user=self.user,
            job_type=JobType.CONTRACT_VALIDATION,
            resource_type="CONTRACT",
            resource_id=str(contract.id),
            details_json={"contract_id": str(contract.id)},
        )

        # Validate the created job - should fail tenant mismatch
        result = self.rules.validate_job_creation(job, self.tenant, self.user)
        self.assertIsInstance(result.is_valid, bool)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("belongs to tenant", result.errors[0].lower())

    def test_integration_validate_before_create_job(self):
        """Integration test: validate job before creating via create_job"""
        from hub.apps.contracts.models import Contract, ContractStatus

        # Create a real resource
        contract = Contract.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            status=ContractStatus.ACTIVE,
            validation_status="VALID",
        )

        # Create job instance (not saved yet)
        job = Job(
            tenant=self.tenant,
            type=JobType.CONTRACT_VALIDATION,
            status=JobStatus.PENDING,
            resource_type="CONTRACT",
            resource_id=contract.id,
            created_by=self.user,
            details_json={"contract_id": str(contract.id)},
            timeout_seconds=300,
        )

        # Validate before creating
        result = self.rules.validate_job_creation(job, self.tenant, self.user)
        self.assertIsInstance(result.is_valid, bool)
        self.assertTrue(result.is_valid)

        # If validation passes, create the job
        if result.is_valid:
            job.save()
            self.assertIsNotNone(job.id)
            # Verify job was created successfully
            created_job = Job.objects.get(id=job.id)
            self.assertEqual(created_job.type, JobType.CONTRACT_VALIDATION)
            self.assertEqual(created_job.resource_type, "CONTRACT")
            self.assertEqual(created_job.resource_id, contract.id)


class JobExecutionValidationTest(TestCase):
    """Test job execution validation methods"""

    def setUp(self):
        """Set up test fixtures"""
        from hub.apps.users.models import UserStatus

        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.rules = JobsBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))
        self.job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
            created_by=self.user,
        )

    def test_validate_job_execution_comprehensive(self):
        """Test validate_job_execution orchestrates all validations"""
        result = self.rules.validate_job_execution(
            self.job, current_status="PENDING", new_status="RUNNING"
        )
        self.assertIsInstance(result.is_valid, bool)
        self.assertTrue(result.is_valid)
        self.assertEqual(result.details["validation_type"], "job_execution")
        self.assertTrue(result.details["status_transition_validated"])
        self.assertTrue(result.details["retry_validated"])
        self.assertTrue(result.details["timeout_validated"])

    def test_validate_job_status_transition_valid(self):
        """Test status transition validation with valid transition"""
        result = self.rules._validate_job_status_transition(
            self.job, current_status="PENDING", new_status="RUNNING"
        )
        self.assertTrue(result.is_valid)
        self.assertTrue(result.details["transition_allowed"])

    def test_validate_job_status_transition_invalid(self):
        """Test status transition validation with invalid transition"""
        result = self.rules._validate_job_status_transition(
            self.job,
            current_status="PENDING",
            new_status="COMPLETED",  # Cannot go directly from PENDING to COMPLETED
        )
        self.assertFalse(result.is_valid)
        self.assertFalse(result.details["transition_allowed"])
        self.assertGreater(len(result.errors), 0)

    def test_validate_job_status_transition_pending_to_running(self):
        """Test PENDING → RUNNING transition"""
        self.job.started_at = timezone.now()
        result = self.rules._validate_job_status_transition(
            self.job, current_status="PENDING", new_status="RUNNING"
        )
        self.assertTrue(result.is_valid)
        self.assertTrue(result.details["started_at_set"])

    def test_validate_job_status_transition_running_to_completed(self):
        """Test RUNNING → COMPLETED transition"""
        self.job.status = JobStatus.RUNNING
        self.job.started_at = timezone.now() - timezone.timedelta(minutes=5)
        self.job.completed_at = timezone.now()
        result = self.rules._validate_job_status_transition(
            self.job, current_status="RUNNING", new_status="COMPLETED"
        )
        self.assertTrue(result.is_valid)
        self.assertTrue(result.details["started_at_set"])
        self.assertTrue(result.details["completed_at_set"])

    def test_validate_job_status_transition_with_timestamps(self):
        """Test status transition validation with proper timestamps"""
        self.job.status = JobStatus.RUNNING
        self.job.started_at = timezone.now() - timezone.timedelta(minutes=5)
        self.job.completed_at = timezone.now()
        result = self.rules._validate_job_status_transition(
            self.job, current_status="RUNNING", new_status="COMPLETED"
        )
        self.assertTrue(result.is_valid)
        self.assertTrue(result.details["date_order_valid"])

    def test_validate_job_status_transition_invalid_timestamp_order(self):
        """Test status transition with invalid timestamp order"""
        self.job.status = JobStatus.RUNNING
        self.job.started_at = timezone.now()
        self.job.completed_at = timezone.now() - timezone.timedelta(minutes=5)  # Before started_at
        result = self.rules._validate_job_status_transition(
            self.job, current_status="RUNNING", new_status="COMPLETED"
        )
        self.assertFalse(result.is_valid)
        self.assertFalse(result.details["date_order_valid"])

    def test_validate_job_status_transition_terminal_state(self):
        """Test status transition from terminal state"""
        self.job.status = JobStatus.COMPLETED
        result = self.rules._validate_job_status_transition(
            self.job,
            current_status="COMPLETED",
            new_status="RUNNING",  # Cannot transition from terminal state
        )
        self.assertFalse(result.is_valid)
        self.assertFalse(result.details["transition_allowed"])

    def test_validate_job_status_transition_pending_to_cancelled(self):
        """Test PENDING → CANCELLED transition"""
        self.job.completed_at = timezone.now()
        result = self.rules._validate_job_status_transition(
            self.job, current_status="PENDING", new_status="CANCELLED"
        )
        self.assertTrue(result.is_valid)
        self.assertTrue(result.details["transition_allowed"])

    def test_validate_job_status_transition_running_to_cancelled(self):
        """Test RUNNING → CANCELLED transition"""
        self.job.status = JobStatus.RUNNING
        self.job.started_at = timezone.now() - timezone.timedelta(minutes=5)
        self.job.completed_at = timezone.now()
        result = self.rules._validate_job_status_transition(
            self.job, current_status="RUNNING", new_status="CANCELLED"
        )
        self.assertTrue(result.is_valid)
        self.assertTrue(result.details["transition_allowed"])

    def test_validate_job_cancellation_pending(self):
        """Test cancellation validation for PENDING job"""
        result = self.rules._validate_job_cancellation(self.job)
        self.assertTrue(result.is_valid)
        self.assertTrue(result.details["can_cancel"])

    def test_validate_job_cancellation_running(self):
        """Test cancellation validation for RUNNING job"""
        self.job.status = JobStatus.RUNNING
        result = self.rules._validate_job_cancellation(self.job)
        self.assertTrue(result.is_valid)
        self.assertTrue(result.details["can_cancel"])

    def test_validate_job_cancellation_completed(self):
        """Test cancellation validation for COMPLETED job"""
        self.job.status = JobStatus.COMPLETED
        result = self.rules._validate_job_cancellation(self.job)
        self.assertFalse(result.is_valid)
        self.assertFalse(result.details["can_cancel"])
        self.assertTrue(result.details["is_terminal"])

    def test_validate_job_cancellation_already_cancelled(self):
        """Test cancellation validation for already cancelled job"""
        self.job.status = JobStatus.CANCELLED
        result = self.rules._validate_job_cancellation(self.job)
        self.assertFalse(result.is_valid)
        self.assertTrue(result.details["already_cancelled"])

    def test_validate_job_retry_valid(self):
        """Test retry validation with valid retry configuration"""
        self.job.details_json = {"retry_count": 1, "max_retries": 3}
        result = self.rules._validate_job_retry(self.job)
        self.assertTrue(result.is_valid)
        self.assertTrue(result.details["retry_count_valid"])
        self.assertTrue(result.details["max_retries_valid"])

    def test_validate_job_retry_exceeds_max(self):
        """Test retry validation when retry_count exceeds max_retries"""
        self.job.details_json = {"retry_count": 5, "max_retries": 3}
        result = self.rules._validate_job_retry(self.job)
        self.assertFalse(result.is_valid)
        self.assertTrue(result.details["retry_limit_exceeded"])

    def test_validate_job_retry_negative_count(self):
        """Test retry validation with negative retry_count"""
        self.job.details_json = {"retry_count": -1, "max_retries": 3}
        result = self.rules._validate_job_retry(self.job)
        self.assertFalse(result.is_valid)
        self.assertFalse(result.details["retry_count_valid"])

    def test_validate_job_retry_exceeds_max_allowed(self):
        """Test retry validation when max_retries exceeds maximum allowed"""
        self.job.details_json = {
            "retry_count": 0,
            "max_retries": 15,  # Exceeds MAX_ALLOWED_RETRIES (10)
        }
        result = self.rules._validate_job_retry(self.job)
        self.assertFalse(result.is_valid)
        self.assertFalse(result.details["max_retries_valid"])

    def test_validate_job_retry_high_usage_warning(self):
        """Test retry validation warns when approaching retry limit"""
        self.job.details_json = {
            "retry_count": 8,
            "max_retries": 10,  # 80% usage
        }
        result = self.rules._validate_job_retry(self.job)
        self.assertTrue(result.is_valid)
        self.assertTrue(result.details["retry_usage_high"])
        self.assertGreater(len(result.warnings), 0)

    def test_validate_job_retry_no_details_json(self):
        """Test retry validation when details_json is None"""
        self.job.details_json = None
        result = self.rules._validate_job_retry(self.job)
        self.assertTrue(result.is_valid)
        self.assertEqual(result.details["retry_count"], 0)
        self.assertEqual(result.details["max_retries"], 3)  # Default

    def test_validate_job_timeout_valid(self):
        """Test timeout validation with valid timeout"""
        self.job.timeout_seconds = 3600
        result = self.rules._validate_job_timeout(self.job)
        self.assertTrue(result.is_valid)
        self.assertTrue(result.details["timeout_valid"])

    def test_validate_job_timeout_not_set(self):
        """Test timeout validation when timeout is not set"""
        self.job.timeout_seconds = None
        result = self.rules._validate_job_timeout(self.job)
        self.assertTrue(result.is_valid)
        self.assertFalse(result.details["timeout_set"])
        self.assertGreater(len(result.warnings), 0)

    def test_validate_job_timeout_below_minimum(self):
        """Test timeout validation when timeout is below minimum"""
        self.job.timeout_seconds = 0
        result = self.rules._validate_job_timeout(self.job)
        self.assertFalse(result.is_valid)
        self.assertFalse(result.details["timeout_valid"])

    def test_validate_job_timeout_exceeds_maximum(self):
        """Test timeout validation when timeout exceeds maximum"""
        self.job.timeout_seconds = 86400 * 8  # 8 days, exceeds 7 days max
        result = self.rules._validate_job_timeout(self.job)
        self.assertFalse(result.is_valid)
        self.assertFalse(result.details["timeout_valid"])

    def test_validate_job_timeout_exceeded(self):
        """Test timeout validation when timeout has been exceeded"""
        from django.utils import timezone

        self.job.status = JobStatus.RUNNING
        self.job.timeout_seconds = 60  # 1 minute
        self.job.started_at = timezone.now() - timezone.timedelta(
            minutes=2
        )  # Started 2 minutes ago
        result = self.rules._validate_job_timeout(self.job)
        self.assertFalse(result.is_valid)
        self.assertTrue(result.details["timeout_exceeded"])

    def test_validate_job_timeout_high_usage_warning(self):
        """Test timeout validation warns when approaching timeout"""
        from django.utils import timezone

        self.job.status = JobStatus.RUNNING
        self.job.timeout_seconds = 100  # 100 seconds
        self.job.started_at = timezone.now() - timezone.timedelta(seconds=85)  # 85% usage
        result = self.rules._validate_job_timeout(self.job)
        self.assertTrue(result.is_valid)
        self.assertTrue(result.details["timeout_usage_high"])
        self.assertGreater(len(result.warnings), 0)

    def test_validate_job_execution_with_cancellation(self):
        """Test validate_job_execution includes cancellation validation when cancelling"""
        result = self.rules.validate_job_execution(
            self.job, current_status="PENDING", new_status="CANCELLED"
        )
        self.assertIsInstance(result.details, dict)
        self.assertTrue(result.details["cancellation_validated"])

    def test_validate_job_execution_without_cancellation(self):
        """Test validate_job_execution skips cancellation validation when not cancelling"""
        result = self.rules.validate_job_execution(
            self.job, current_status="PENDING", new_status="RUNNING"
        )
        self.assertIsInstance(result.details, dict)
        self.assertFalse(result.details["cancellation_validated"])


class JobExecutionValidationIntegrationTest(TestCase):
    """Integration tests for job execution validation with job lifecycle"""

    def setUp(self):
        """Set up test fixtures"""
        from hub.apps.users.models import UserStatus

        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.rules = JobsBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

    def test_integration_job_lifecycle_validation(self):
        """Integration test: validate job through complete lifecycle"""
        from hub.apps.jobs.utils import create_job

        # Create a job
        job = create_job(
            tenant=self.tenant,
            user=self.user,
            job_type=JobType.DQ_RUN,
            resource_type="DATASET",
            resource_id=str(uuid.uuid4()),
            details_json={"profile_key": "test_profile"},
            timeout_seconds=3600,
        )

        # Validate job execution before starting (PENDING state)
        result = self.rules.validate_job_execution(job)
        self.assertTrue(result.is_valid)
        self.assertEqual(result.details["validation_type"], "job_execution")

        # Mark job as started
        job.mark_started()

        # Validate job execution while running
        result = self.rules.validate_job_execution(job, current_status="RUNNING")
        self.assertTrue(result.is_valid)

        # Mark job as completed
        job.mark_completed()

        # Validate job execution after completion
        result = self.rules.validate_job_execution(job, current_status="COMPLETED")
        self.assertTrue(result.is_valid)

    def test_integration_job_cancellation_validation(self):
        """Integration test: validate job cancellation through lifecycle"""
        from hub.apps.jobs.utils import create_job

        # Create a job
        job = create_job(
            tenant=self.tenant,
            user=self.user,
            job_type=JobType.DQ_RUN,
            resource_type="DATASET",
            resource_id=str(uuid.uuid4()),
            details_json={},
            timeout_seconds=3600,
        )

        # Validate cancellation from PENDING state
        result = self.rules.validate_job_execution(
            job, current_status="PENDING", new_status="CANCELLED"
        )
        self.assertTrue(result.is_valid)
        self.assertTrue(result.details["cancellation_validated"])

        # Mark job as started
        job.mark_started()

        # Validate cancellation from RUNNING state
        result = self.rules.validate_job_execution(
            job, current_status="RUNNING", new_status="CANCELLED"
        )
        self.assertTrue(result.is_valid)
        self.assertTrue(result.details["cancellation_validated"])

    def test_integration_job_timeout_validation_during_execution(self):
        """Integration test: validate job timeout during execution"""
        from hub.apps.jobs.utils import create_job

        # Create a job with short timeout
        job = create_job(
            tenant=self.tenant,
            user=self.user,
            job_type=JobType.DQ_RUN,
            resource_type="DATASET",
            resource_id=str(uuid.uuid4()),
            details_json={},
            timeout_seconds=60,  # 1 minute
        )

        # Mark job as started
        job.mark_started()

        # Validate timeout (should pass initially)
        result = self.rules._validate_job_timeout(job)
        self.assertTrue(result.is_valid)

        # Simulate job running for longer than timeout
        from django.utils import timezone

        job.started_at = timezone.now() - timezone.timedelta(minutes=2)
        job.save()

        # Validate timeout (should fail)
        result = self.rules._validate_job_timeout(job)
        self.assertFalse(result.is_valid)
        self.assertTrue(result.details["timeout_exceeded"])

    def test_integration_job_retry_validation(self):
        """Integration test: validate job retry logic"""
        from hub.apps.jobs.utils import create_job

        # Create a job with retry configuration
        job = create_job(
            tenant=self.tenant,
            user=self.user,
            job_type=JobType.DQ_RUN,
            resource_type="DATASET",
            resource_id=str(uuid.uuid4()),
            details_json={"retry_count": 2, "max_retries": 3},
            timeout_seconds=3600,
        )

        # Validate retry configuration
        result = self.rules._validate_job_retry(job)
        self.assertTrue(result.is_valid)
        self.assertEqual(result.details["retry_count"], 2)
        self.assertEqual(result.details["max_retries"], 3)

        # Simulate retry count exceeding max
        job.details_json["retry_count"] = 5
        job.save()

        # Validate retry (should fail)
        result = self.rules._validate_job_retry(job)
        self.assertFalse(result.is_valid)
        self.assertTrue(result.details["retry_limit_exceeded"])


class JobsBusinessRulesJobPriorityValidationTest(TestCase):
    """Test JobsBusinessRules job priority validation"""

    def setUp(self):
        """Set up test fixtures"""
        from hub.apps.users.models import Role, UserStatus

        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        # Create tenant admin user
        self.tenant_admin = User.objects.create_user(
            email=f"admin-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        # Create tenant admin role
        tenant_admin_role, _ = Role.objects.get_or_create(tenant=self.tenant, name="TENANT_ADMIN")
        # Assign role to tenant admin user
        from hub.apps.users.models import UserRole

        UserRole.objects.get_or_create(user=self.tenant_admin, role=tenant_admin_role)
        # Create platform admin user
        self.platform_admin = User.objects.create_user(
            email=f"platform-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=None,
            status=UserStatus.ACTIVE,
            is_platform_admin=True,
        )
        self.rules = JobsBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

    def test_validate_job_priority_valid_low(self):
        """Test validate_job_priority with LOW priority"""
        job = Job(
            tenant=self.tenant,
            type=JobType.CONTRACT_VALIDATION,
            status=JobStatus.PENDING,
            resource_type="CONTRACT",
            resource_id=uuid.uuid4(),
            created_by=self.user,
            details_json={"priority": "LOW"},
        )

        result = self.rules.validate_job_priority(job, self.tenant, self.user)
        self.assertIsInstance(result.is_valid, bool)
        self.assertTrue(result.is_valid)
        self.assertIn("priority_level_validated", result.details)
        self.assertIn("priority_assignment_validated", result.details)
        self.assertIn("priority_queue_validated", result.details)

    def test_validate_job_priority_valid_normal(self):
        """Test validate_job_priority with NORMAL priority"""
        job = Job(
            tenant=self.tenant,
            type=JobType.SEMANTIC_MAPPING,
            status=JobStatus.PENDING,
            resource_type="CONTRACT",
            resource_id=uuid.uuid4(),
            created_by=self.user,
            details_json={"priority": "NORMAL"},
        )

        result = self.rules.validate_job_priority(job, self.tenant, self.user)
        self.assertIsInstance(result.is_valid, bool)
        self.assertTrue(result.is_valid)

    def test_validate_job_priority_valid_high(self):
        """Test validate_job_priority with HIGH priority (requires TENANT_ADMIN)"""
        job = Job(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
            created_by=self.tenant_admin,
            details_json={"priority": "HIGH"},
        )

        result = self.rules.validate_job_priority(job, self.tenant, self.tenant_admin)
        self.assertIsInstance(result.is_valid, bool)
        self.assertTrue(result.is_valid)

    def test_validate_job_priority_valid_critical(self):
        """Test validate_job_priority with CRITICAL priority (requires TENANT_ADMIN)"""
        job = Job(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
            created_by=self.tenant_admin,
            details_json={"priority": "CRITICAL"},
        )

        result = self.rules.validate_job_priority(job, self.tenant, self.tenant_admin)
        self.assertIsInstance(result.is_valid, bool)
        self.assertTrue(result.is_valid)

    def test_validate_priority_level_valid(self):
        """Test _validate_priority_level with valid priority"""
        job = Job(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
            details_json={"priority": "HIGH"},
        )

        result = self.rules._validate_priority_level(job)
        self.assertTrue(result.is_valid, f"Validation failed: {result.errors}")
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(result.details["priority"], "HIGH")
        self.assertEqual(result.details["priority_source"], "details_json")

    def test_validate_priority_level_invalid(self):
        """Test _validate_priority_level with invalid priority"""
        job = Job(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
            details_json={"priority": "INVALID_PRIORITY"},
        )

        result = self.rules._validate_priority_level(job)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("invalid priority", result.errors[0].lower())

    def test_validate_priority_level_inferred_from_job_type(self):
        """Test _validate_priority_level infers priority from job type"""
        # DQ_RUN maps to HIGH priority (job_critical queue)
        job = Job(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
        )

        result = self.rules._validate_priority_level(job)
        self.assertTrue(result.is_valid)
        self.assertEqual(result.details["priority"], "HIGH")
        self.assertEqual(result.details["priority_source"], "inferred_from_job_type")

    def test_validate_priority_level_defaults_to_normal(self):
        """Test _validate_priority_level defaults to NORMAL when not specified"""
        job = Job(
            tenant=self.tenant,
            type=JobType.SEMANTIC_MAPPING,
            status=JobStatus.PENDING,
            resource_type="CONTRACT",
            resource_id=uuid.uuid4(),
        )

        result = self.rules._validate_priority_level(job)
        self.assertTrue(result.is_valid)
        self.assertEqual(result.details["priority"], "NORMAL")
        self.assertIn("priority_source", result.details)

    def test_validate_priority_assignment_low_allowed(self):
        """Test _validate_priority_assignment allows LOW priority for any user"""
        job = Job(
            tenant=self.tenant,
            type=JobType.CONTRACT_VALIDATION,
            status=JobStatus.PENDING,
            resource_type="CONTRACT",
            resource_id=uuid.uuid4(),
            created_by=self.user,
            details_json={"priority": "LOW"},
        )

        result = self.rules._validate_priority_assignment(job, self.user, self.tenant)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(result.details["permission_check"], "any_user")

    def test_validate_priority_assignment_normal_allowed(self):
        """Test _validate_priority_assignment allows NORMAL priority for any user"""
        job = Job(
            tenant=self.tenant,
            type=JobType.SEMANTIC_MAPPING,
            status=JobStatus.PENDING,
            resource_type="CONTRACT",
            resource_id=uuid.uuid4(),
            created_by=self.user,
            details_json={"priority": "NORMAL"},
        )

        result = self.rules._validate_priority_assignment(job, self.user, self.tenant)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(result.details["permission_check"], "any_user")

    def test_validate_priority_assignment_high_requires_tenant_admin(self):
        """Test _validate_priority_assignment requires TENANT_ADMIN for HIGH priority"""
        job = Job(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
            created_by=self.user,
            details_json={"priority": "HIGH"},
        )

        result = self.rules._validate_priority_assignment(job, self.user, self.tenant)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("permission", result.errors[0].lower())
        self.assertIn("TENANT_ADMIN", result.errors[0])

    def test_validate_priority_assignment_high_allowed_for_tenant_admin(self):
        """Test _validate_priority_assignment allows HIGH priority for TENANT_ADMIN"""
        job = Job(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
            created_by=self.tenant_admin,
            details_json={"priority": "HIGH"},
        )

        result = self.rules._validate_priority_assignment(job, self.tenant_admin, self.tenant)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(result.details["permission_check"], "tenant_admin")

    def test_validate_priority_assignment_critical_requires_tenant_admin(self):
        """Test _validate_priority_assignment requires TENANT_ADMIN for CRITICAL priority"""
        job = Job(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
            created_by=self.user,
            details_json={"priority": "CRITICAL"},
        )

        result = self.rules._validate_priority_assignment(job, self.user, self.tenant)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("permission", result.errors[0].lower())
        self.assertIn("TENANT_ADMIN", result.errors[0])

    def test_validate_priority_assignment_critical_allowed_for_tenant_admin(self):
        """Test _validate_priority_assignment allows CRITICAL priority for TENANT_ADMIN"""
        job = Job(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
            created_by=self.tenant_admin,
            details_json={"priority": "CRITICAL"},
        )

        result = self.rules._validate_priority_assignment(job, self.tenant_admin, self.tenant)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(result.details["permission_check"], "tenant_admin")

    def test_validate_priority_assignment_platform_admin_allowed(self):
        """Test _validate_priority_assignment allows any priority for platform admin"""
        job = Job(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
            created_by=self.platform_admin,
            details_json={"priority": "CRITICAL"},
        )

        result = self.rules._validate_priority_assignment(job, self.platform_admin, self.tenant)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(result.details["permission_check"], "platform_admin")
        self.assertTrue(result.details["is_platform_admin"])

    def test_validate_priority_queue_valid_mapping(self):
        """Test _validate_priority_queue with valid priority-queue mapping"""
        # HIGH priority job (DQ_RUN) should map to job_critical queue
        job = Job(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
            details_json={"priority": "HIGH"},
        )

        result = self.rules._validate_priority_queue(job)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(result.details["queue_name"], "job_critical")
        self.assertTrue(result.details["queue_match"])

    def test_validate_priority_queue_normal_mapping(self):
        """Test _validate_priority_queue with NORMAL priority mapping"""
        # NORMAL priority job (SEMANTIC_MAPPING) should map to job_default queue
        job = Job(
            tenant=self.tenant,
            type=JobType.SEMANTIC_MAPPING,
            status=JobStatus.PENDING,
            resource_type="CONTRACT",
            resource_id=uuid.uuid4(),
            details_json={"priority": "NORMAL"},
        )

        result = self.rules._validate_priority_queue(job)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(result.details["queue_name"], "job_default")
        self.assertTrue(result.details["queue_match"])

    def test_validate_priority_queue_low_mapping(self):
        """Test _validate_priority_queue with LOW priority mapping"""
        # LOW priority job (CONTRACT_VALIDATION) should map to job_low queue
        job = Job(
            tenant=self.tenant,
            type=JobType.CONTRACT_VALIDATION,
            status=JobStatus.PENDING,
            resource_type="CONTRACT",
            resource_id=uuid.uuid4(),
            details_json={"priority": "LOW"},
        )

        result = self.rules._validate_priority_queue(job)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(result.details["queue_name"], "job_low")
        self.assertTrue(result.details["queue_match"])

    def test_validate_priority_queue_critical_mapping(self):
        """Test _validate_priority_queue with CRITICAL priority mapping"""
        # CRITICAL priority job should map to job_critical queue
        job = Job(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
            details_json={"priority": "CRITICAL"},
        )

        result = self.rules._validate_priority_queue(job)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(result.details["queue_name"], "job_critical")
        self.assertTrue(result.details["queue_match"])

    def test_validate_priority_queue_inferred_from_queue(self):
        """Test _validate_priority_queue infers priority from queue when not specified"""
        # DQ_RUN maps to job_critical queue, which implies HIGH priority
        job = Job(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
        )

        result = self.rules._validate_priority_queue(job)
        self.assertTrue(result.is_valid)
        self.assertEqual(result.details["queue_name"], "job_critical")
        self.assertEqual(result.details["priority"], "HIGH")
        self.assertTrue(result.details["priority_inferred"])

    def test_validate_job_priority_without_user(self):
        """Test validate_job_priority without user (skips assignment validation)"""
        job = Job(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
            details_json={"priority": "HIGH"},
        )

        result = self.rules.validate_job_priority(job, self.tenant, None)
        self.assertIsInstance(result.details, dict)
        # Priority level and queue should still be validated
        self.assertTrue(result.details["priority_level_validated"])
        self.assertTrue(result.details["priority_queue_validated"])
        # Assignment validation should be skipped
        self.assertFalse(result.details["priority_assignment_validated"])

    def test_validate_job_priority_with_all_validations(self):
        """Test validate_job_priority orchestrates all validations"""
        job = Job(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
            created_by=self.tenant_admin,
            details_json={"priority": "HIGH"},
        )

        result = self.rules.validate_job_priority(job, self.tenant, self.tenant_admin)
        self.assertIsInstance(result.is_valid, bool)
        self.assertTrue(result.is_valid)
        # Check all validations were performed
        self.assertTrue(result.details["priority_level_validated"])
        self.assertTrue(result.details["priority_assignment_validated"])
        self.assertTrue(result.details["priority_queue_validated"])
        self.assertEqual(result.details["validation_type"], "job_priority")


class JobsBusinessRulesJobPriorityIntegrationTest(TestCase):
    """Integration tests for JobsBusinessRules job priority validation with create_job"""

    def setUp(self):
        """Set up test fixtures"""
        from hub.apps.users.models import Role, UserStatus

        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        # Create tenant admin user
        self.tenant_admin = User.objects.create_user(
            email=f"admin-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        # Create tenant admin role
        tenant_admin_role, _ = Role.objects.get_or_create(tenant=self.tenant, name="TENANT_ADMIN")
        # Assign role to tenant admin user
        from hub.apps.users.models import UserRole

        UserRole.objects.get_or_create(user=self.tenant_admin, role=tenant_admin_role)
        self.rules = JobsBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

    def test_integration_priority_validation_with_create_job(self):
        """Integration test: validate priority for job created via create_job"""
        from hub.apps.contracts.models import Contract, ContractStatus
        from hub.apps.jobs.utils import create_job

        # Create a real resource
        contract = Contract.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            status=ContractStatus.ACTIVE,
            validation_status="VALID",
        )

        # Create job with LOW priority (any user can create)
        job = create_job(
            tenant=self.tenant,
            user=self.user,
            job_type=JobType.CONTRACT_VALIDATION,
            resource_type="CONTRACT",
            resource_id=str(contract.id),
            details_json={"priority": "LOW", "contract_id": str(contract.id)},
        )

        # Validate priority
        result = self.rules.validate_job_priority(job, self.tenant, self.user)
        self.assertIsInstance(result.is_valid, bool)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

    def test_integration_priority_validation_high_priority_tenant_admin(self):
        """Integration test: validate HIGH priority job created by tenant admin"""
        from hub.apps.contracts.models import Contract, ContractStatus
        from hub.apps.jobs.utils import create_job

        # Create a real resource
        contract = Contract.objects.create(
            tenant=self.tenant,
            created_by=self.tenant_admin,
            status=ContractStatus.ACTIVE,
            validation_status="VALID",
        )

        # Create job with HIGH priority (requires TENANT_ADMIN)
        job = create_job(
            tenant=self.tenant,
            user=self.tenant_admin,
            job_type=JobType.DQ_RUN,
            resource_type="CONTRACT",
            resource_id=str(contract.id),
            details_json={"priority": "HIGH"},
        )

        # Validate priority
        result = self.rules.validate_job_priority(job, self.tenant, self.tenant_admin)
        self.assertIsInstance(result.is_valid, bool)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

    def test_integration_priority_validation_high_priority_regular_user_fails(self):
        """Integration test: validate HIGH priority job fails for regular user"""
        from hub.apps.contracts.models import Contract, ContractStatus
        from hub.apps.jobs.utils import create_job

        # Create a real resource
        contract = Contract.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            status=ContractStatus.ACTIVE,
            validation_status="VALID",
        )

        # Create job with HIGH priority (regular user cannot create)
        job = create_job(
            tenant=self.tenant,
            user=self.user,
            job_type=JobType.DQ_RUN,
            resource_type="CONTRACT",
            resource_id=str(contract.id),
            details_json={"priority": "HIGH"},
        )

        # Validate priority - should fail permission check
        result = self.rules.validate_job_priority(job, self.tenant, self.user)
        self.assertIsInstance(result.is_valid, bool)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("permission", result.errors[0].lower())
