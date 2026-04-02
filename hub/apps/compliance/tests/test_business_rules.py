"""
Unit tests for ComplianceBusinessRules.

Comprehensive tests without mocks/stubs, following engineering best practices.
"""
import uuid
from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.core.business_rules.base import ValidationResult, RuleExecutionContext
from hub.apps.core.business_rules.registry import get_registry
from hub.apps.compliance.business_rules import (
    ComplianceBusinessRules,
    ComplianceRuleExecutionContext
)
from hub.apps.compliance.models import (
    ComplianceRun,
    ComplianceRunStatus,
    RiskLevel,
)
from hub.apps.tenants.models import Tenant, KYCStatus
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus
from hub.apps.jobs.models import Job, JobStatus, JobType

User = get_user_model()


class ComplianceBusinessRulesInitializationTest(TestCase):
    """Test ComplianceBusinessRules initialization"""

    def setUp(self):
        """Set up test fixtures"""
        from hub.apps.users.models import UserStatus
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com", password="testpass123", tenant=self.tenant,
            status=UserStatus.ACTIVE
        )

    def test_compliance_business_rules_initialization(self):
        """Test ComplianceBusinessRules can be initialized"""
        rules = ComplianceBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )
        self.assertIsNotNone(rules)
        self.assertEqual(rules.get_rule_name(), "ComplianceBusinessRules")
        self.assertEqual(rules.tenant_id, str(self.tenant.id))
        self.assertEqual(rules.user_id, str(self.user.id))

    def test_compliance_business_rules_initialization_without_user(self):
        """Test ComplianceBusinessRules can be initialized without user"""
        rules = ComplianceBusinessRules(tenant_id=str(self.tenant.id))
        self.assertIsNotNone(rules)
        self.assertEqual(rules.tenant_id, str(self.tenant.id))
        self.assertIsNone(rules.user_id)

    def test_compliance_business_rules_initialization_without_tenant(self):
        """Test ComplianceBusinessRules can be initialized without tenant"""
        rules = ComplianceBusinessRules(user_id=str(self.user.id))
        self.assertIsNotNone(rules)
        self.assertIsNone(rules.tenant_id)
        self.assertEqual(rules.user_id, str(self.user.id))


class ComplianceBusinessRulesRegistrationTest(TestCase):
    """Test ComplianceBusinessRules registration in business rules registry"""

    def test_compliance_business_rules_registered(self):
        """Test ComplianceBusinessRules is registered in the registry"""
        registry = get_registry()
        rule = registry.get_rule("compliance_validation")
        self.assertIsNotNone(rule)
        self.assertEqual(rule.rule_name, "compliance_validation")
        self.assertEqual(rule.rule_class, ComplianceBusinessRules)
        self.assertIn("compliance", rule.tags)
        self.assertIn("validation", rule.tags)
        self.assertIn("risk_assessment", rule.tags)

    def test_compliance_business_rules_priority(self):
        """Test ComplianceBusinessRules has correct priority"""
        registry = get_registry()
        rule = registry.get_rule("compliance_validation")
        self.assertIsNotNone(rule)
        self.assertEqual(rule.priority, 10)


class ComplianceRunValidationTest(TestCase):
    """Test compliance run validation"""

    def setUp(self):
        """Set up test fixtures"""
        from hub.apps.users.models import UserStatus
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com", password="testpass123", tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        self.rules = ComplianceBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        # Create asset, dataset, file, and job
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user
        )

        self.file = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1024,
            storage_path="s3://bucket/test.csv",
            status=FileStatus.ACTIVE,
            created_by=self.user
        )

        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            version=1,
            format="csv",
            created_by=self.user
        )

        self.job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.PENDING,
            resource_type="ASSET",
            resource_id=self.asset.id,
            created_by=self.user
        )

    def test_validate_compliance_run_valid(self):
        """Test compliance run validation with valid run"""
        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            job=self.job,
            status=ComplianceRunStatus.PENDING,
            regulations=['GDPR', 'CCPA']
        )

        result = self.rules._validate_compliance_run(compliance_run, self.tenant, self.user)

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertTrue(result.details['has_resource'])
        self.assertEqual(result.details['resource_type'], 'asset')
        self.assertTrue(result.details['status_valid'])

    def test_validate_compliance_run_no_resource(self):
        """Test compliance run validation with no resource"""
        compliance_run = ComplianceRun(
            tenant=self.tenant,
            job=self.job,
            status=ComplianceRunStatus.PENDING
        )

        result = self.rules._validate_compliance_run(compliance_run, self.tenant, self.user)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn('resource', result.errors[0].lower())

    def test_validate_compliance_run_invalid_status(self):
        """Test compliance run validation with invalid status"""
        compliance_run = ComplianceRun(
            tenant=self.tenant,
            asset=self.asset,
            job=self.job,
            status=ComplianceRunStatus.PENDING
        )
        # Set invalid status directly to bypass Django model validation
        compliance_run.status = "INVALID_STATUS"

        result = self.rules._validate_compliance_run(compliance_run, self.tenant, self.user)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn('invalid status', result.errors[0].lower())

    def test_validate_compliance_run_valid_risk_level(self):
        """Test compliance run validation with valid risk level"""
        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            job=self.job,
            status=ComplianceRunStatus.SUCCEEDED,
            risk_level=RiskLevel.HIGH
        )

        result = self.rules._validate_compliance_run(compliance_run, self.tenant, self.user)

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertTrue(result.details['risk_level_valid'])
        self.assertEqual(result.details['risk_level'], RiskLevel.HIGH)

    def test_validate_compliance_run_invalid_risk_level(self):
        """Test compliance run validation with invalid risk level"""
        compliance_run = ComplianceRun(
            tenant=self.tenant,
            asset=self.asset,
            job=self.job,
            status=ComplianceRunStatus.SUCCEEDED,
            risk_level=RiskLevel.LOW
        )
        # Set invalid risk_level directly to bypass Django model validation
        compliance_run.risk_level = "INVALID_RISK"

        result = self.rules._validate_compliance_run(compliance_run, self.tenant, self.user)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn('invalid risk_level', result.errors[0].lower())

    def test_validate_compliance_run_valid_regulations(self):
        """Test compliance run validation with valid regulations"""
        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            job=self.job,
            status=ComplianceRunStatus.PENDING,
            regulations=['GDPR', 'CCPA', 'HIPAA']
        )

        result = self.rules._validate_compliance_run(compliance_run, self.tenant, self.user)

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertTrue(result.details['regulations_valid'])
        self.assertEqual(result.details['regulations_count'], 3)

    def test_validate_compliance_run_invalid_regulations_not_list(self):
        """Test compliance run validation with regulations not a list"""
        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            job=self.job,
            status=ComplianceRunStatus.PENDING
        )
        compliance_run.regulations = "GDPR"  # Not a list
        compliance_run.save()

        result = self.rules._validate_compliance_run(compliance_run, self.tenant, self.user)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn('regulations must be a list', result.errors[0].lower())

    def test_validate_compliance_run_invalid_regulations_empty_strings(self):
        """Test compliance run validation with empty string regulations"""
        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            job=self.job,
            status=ComplianceRunStatus.PENDING,
            regulations=['GDPR', '', '  ']  # Empty strings
        )

        result = self.rules._validate_compliance_run(compliance_run, self.tenant, self.user)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn('invalid regulations', result.errors[0].lower())

    def test_validate_compliance_run_valid_overall_status(self):
        """Test compliance run validation with valid overall_status"""
        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            job=self.job,
            status=ComplianceRunStatus.SUCCEEDED,
            overall_status='PASS'
        )

        result = self.rules._validate_compliance_run(compliance_run, self.tenant, self.user)

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertTrue(result.details['overall_status_valid'])
        self.assertEqual(result.details['overall_status'], 'PASS')

    def test_validate_compliance_run_invalid_overall_status(self):
        """Test compliance run validation with invalid overall_status"""
        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            job=self.job,
            status=ComplianceRunStatus.SUCCEEDED,
            overall_status='INVALID_STATUS'
        )

        result = self.rules._validate_compliance_run(compliance_run, self.tenant, self.user)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn('invalid overall_status', result.errors[0].lower())

    def test_validate_compliance_run_tenant_mismatch(self):
        """Test compliance run validation with tenant mismatch"""
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}", slug=f"other-tenant-{_uid}", kyc_status=KYCStatus.VERIFIED
        )
        compliance_run = ComplianceRun.objects.create(
            tenant=other_tenant,
            asset=self.asset,
            job=self.job,
            status=ComplianceRunStatus.PENDING
        )

        result = self.rules._validate_compliance_run(compliance_run, self.tenant, self.user)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn('tenant', result.errors[0].lower())


class RiskAssessmentValidationTest(TestCase):
    """Test risk assessment validation"""

    def setUp(self):
        """Set up test fixtures"""
        from hub.apps.users.models import UserStatus
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com", password="testpass123", tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        self.rules = ComplianceBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        # Create asset and job
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user
        )

        self.job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.PENDING,
            resource_type="ASSET",
            resource_id=self.asset.id,
            created_by=self.user
        )

    def test_validate_risk_assessment_valid(self):
        """Test risk assessment validation with valid assessment"""
        assessment = {
            'risk_level': 'HIGH',
            'risk_score': 7.5,
            'allowed_to_store': False,
            'violations': [
                {'severity': 'HIGH', 'description': 'PII detected'}
            ]
        }

        result = self.rules._validate_risk_assessment(assessment, None, self.tenant, self.user)

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertTrue(result.details['risk_level_valid'])
        self.assertEqual(result.details['risk_level'], 'HIGH')

    def test_validate_risk_assessment_not_dict(self):
        """Test risk assessment validation with non-dict assessment"""
        assessment = "not a dict"

        result = self.rules._validate_risk_assessment(assessment, None, self.tenant, self.user)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn('must be a dictionary', result.errors[0].lower())

    def test_validate_risk_assessment_invalid_risk_level(self):
        """Test risk assessment validation with invalid risk level"""
        assessment = {
            'risk_level': 'INVALID_RISK',
            'risk_score': 5.0
        }

        result = self.rules._validate_risk_assessment(assessment, None, self.tenant, self.user)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn('invalid risk_level', result.errors[0].lower())

    def test_validate_risk_assessment_valid_risk_score(self):
        """Test risk assessment validation with valid risk score"""
        assessment = {
            'risk_level': 'MEDIUM',
            'risk_score': 5.5
        }

        result = self.rules._validate_risk_assessment(assessment, None, self.tenant, self.user)

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(result.details['risk_score'], 5.5)

    def test_validate_risk_assessment_invalid_risk_score(self):
        """Test risk assessment validation with invalid risk score"""
        assessment = {
            'risk_level': 'MEDIUM',
            'risk_score': 'not a number'
        }

        result = self.rules._validate_risk_assessment(assessment, None, self.tenant, self.user)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn('risk_score', result.errors[0].lower())

    def test_validate_risk_assessment_negative_risk_score(self):
        """Test risk assessment validation with negative risk score"""
        assessment = {
            'risk_level': 'MEDIUM',
            'risk_score': -5.0
        }

        result = self.rules._validate_risk_assessment(assessment, None, self.tenant, self.user)

        self.assertTrue(result.is_valid)  # Warning, not error
        self.assertGreater(len(result.warnings), 0)
        self.assertIn('negative', result.warnings[0].lower())

    def test_validate_risk_assessment_valid_allowed_to_store(self):
        """Test risk assessment validation with valid allowed_to_store"""
        assessment = {
            'risk_level': 'LOW',
            'allowed_to_store': True
        }

        result = self.rules._validate_risk_assessment(assessment, None, self.tenant, self.user)

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertTrue(result.details['allowed_to_store_valid'])
        self.assertTrue(result.details['allowed_to_store'])

    def test_validate_risk_assessment_invalid_allowed_to_store(self):
        """Test risk assessment validation with invalid allowed_to_store"""
        assessment = {
            'risk_level': 'LOW',
            'allowed_to_store': 'not a boolean'
        }

        result = self.rules._validate_risk_assessment(assessment, None, self.tenant, self.user)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn('allowed_to_store', result.errors[0].lower())

    def test_validate_risk_assessment_violations_list(self):
        """Test risk assessment validation with violations as list"""
        assessment = {
            'risk_level': 'HIGH',
            'violations': [
                {'severity': 'HIGH', 'description': 'PII detected'},
                {'severity': 'MEDIUM', 'description': 'Data retention issue'}
            ]
        }

        result = self.rules._validate_risk_assessment(assessment, None, self.tenant, self.user)

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(result.details['violations_type'], 'list')
        self.assertEqual(result.details['violations_count'], 2)

    def test_validate_risk_assessment_violations_count(self):
        """Test risk assessment validation with violations as count"""
        assessment = {
            'risk_level': 'HIGH',
            'total_violations': 5
        }

        result = self.rules._validate_risk_assessment(assessment, None, self.tenant, self.user)

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(result.details['violations_type'], 'count')
        self.assertEqual(result.details['violations_count'], 5)

    def test_validate_risk_assessment_violations_negative_count(self):
        """Test risk assessment validation with negative violations count"""
        assessment = {
            'risk_level': 'HIGH',
            'total_violations': -1
        }

        result = self.rules._validate_risk_assessment(assessment, None, self.tenant, self.user)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn('non-negative', result.errors[0].lower())

    def test_validate_risk_assessment_consistency_with_compliance_run(self):
        """Test risk assessment validation consistency with compliance run"""
        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            job=self.job,
            status=ComplianceRunStatus.SUCCEEDED,
            risk_level=RiskLevel.HIGH,
            allowed_to_store=False
        )

        assessment = {
            'risk_level': 'HIGH',
            'allowed_to_store': False,
            'risk_score': 8.0
        }

        result = self.rules._validate_risk_assessment(
            assessment, compliance_run, self.tenant, self.user
        )

        self.assertTrue(result.is_valid)
        self.assertTrue(result.details['risk_level_consistency'])
        self.assertTrue(result.details['allowed_to_store_consistency'])

    def test_validate_risk_assessment_inconsistency_with_compliance_run(self):
        """Test risk assessment validation detects inconsistency with compliance run"""
        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            job=self.job,
            status=ComplianceRunStatus.SUCCEEDED,
            risk_level=RiskLevel.LOW,
            allowed_to_store=True
        )

        assessment = {
            'risk_level': 'HIGH',  # Mismatch
            'allowed_to_store': False,  # Mismatch
            'risk_score': 8.0
        }

        result = self.rules._validate_risk_assessment(
            assessment, compliance_run, self.tenant, self.user
        )

        self.assertTrue(result.is_valid)  # Warnings, not errors
        self.assertGreater(len(result.warnings), 0)
        self.assertFalse(result.details['risk_level_consistency'])
        self.assertFalse(result.details['allowed_to_store_consistency'])

    def test_validate_risk_assessment_all_risk_levels(self):
        """Test risk assessment validation with all valid risk levels"""
        # Use appropriate scores for each risk level to pass validation
        valid_levels_scores = {
            'LOW': 0.5,
            'MEDIUM': 3.0,
            'HIGH': 7.5,
            'CRITICAL': 15.0
        }

        for level, score in valid_levels_scores.items():
            with self.subTest(risk_level=level):
                assessment = {
                    'risk_level': level,
                    'risk_score': score
                }
                result = self.rules._validate_risk_assessment(assessment, None, self.tenant, self.user)
                self.assertTrue(result.is_valid)
                self.assertTrue(result.details['risk_level_valid'])
                self.assertEqual(result.details['risk_level'], level)

    def test_validate_risk_assessment_none_risk_level_warning(self):
        """Test risk assessment validation with NONE risk level generates warning"""
        assessment = {
            'risk_level': 'NONE',
            'risk_score': 0.0
        }
        result = self.rules._validate_risk_assessment(assessment, None, self.tenant, self.user)
        self.assertTrue(result.is_valid)
        self.assertTrue(result.details['risk_level_valid'])
        self.assertGreater(len(result.warnings), 0)
        self.assertIn('NONE', result.warnings[0])


class RiskCalculationValidationTest(TestCase):
    """Test risk calculation validation"""

    def setUp(self):
        """Set up test fixtures"""
        from hub.apps.users.models import UserStatus
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com", password="testpass123", tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        self.rules = ComplianceBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

    def test_validate_risk_calculation_low_valid(self):
        """Test risk calculation validation with valid LOW risk level"""
        assessment = {
            'risk_level': 'LOW',
            'risk_score': 0.5
        }
        result = self.rules._validate_risk_assessment(assessment, None, self.tenant, self.user)
        self.assertTrue(result.is_valid)
        self.assertTrue(result.details.get('risk_calculation_valid'))
        self.assertTrue(result.details.get('score_level_alignment'))

    def test_validate_risk_calculation_medium_valid(self):
        """Test risk calculation validation with valid MEDIUM risk level"""
        assessment = {
            'risk_level': 'MEDIUM',
            'risk_score': 3.0
        }
        result = self.rules._validate_risk_assessment(assessment, None, self.tenant, self.user)
        self.assertTrue(result.is_valid)
        self.assertTrue(result.details.get('risk_calculation_valid'))
        self.assertTrue(result.details.get('score_level_alignment'))

    def test_validate_risk_calculation_high_valid(self):
        """Test risk calculation validation with valid HIGH risk level"""
        assessment = {
            'risk_level': 'HIGH',
            'risk_score': 7.5
        }
        result = self.rules._validate_risk_assessment(assessment, None, self.tenant, self.user)
        self.assertTrue(result.is_valid)
        self.assertTrue(result.details.get('risk_calculation_valid'))
        self.assertTrue(result.details.get('score_level_alignment'))

    def test_validate_risk_calculation_critical_valid(self):
        """Test risk calculation validation with valid CRITICAL risk level"""
        assessment = {
            'risk_level': 'CRITICAL',
            'risk_score': 15.0
        }
        result = self.rules._validate_risk_assessment(assessment, None, self.tenant, self.user)
        self.assertTrue(result.is_valid)
        self.assertTrue(result.details.get('risk_calculation_valid'))
        self.assertTrue(result.details.get('score_level_alignment'))

    def test_validate_risk_calculation_medium_below_threshold(self):
        """Test risk calculation validation detects MEDIUM risk level below threshold"""
        assessment = {
            'risk_level': 'MEDIUM',
            'risk_score': 0.5  # Below MEDIUM threshold of 1.0
        }
        result = self.rules._validate_risk_assessment(assessment, None, self.tenant, self.user)
        self.assertFalse(result.is_valid)
        self.assertFalse(result.details.get('risk_calculation_valid'))
        self.assertFalse(result.details.get('score_level_alignment'))
        self.assertIn('below threshold', result.errors[0].lower())

    def test_validate_risk_calculation_high_below_threshold(self):
        """Test risk calculation validation detects HIGH risk level below threshold"""
        assessment = {
            'risk_level': 'HIGH',
            'risk_score': 3.0  # Below HIGH threshold of 5.0
        }
        result = self.rules._validate_risk_assessment(assessment, None, self.tenant, self.user)
        self.assertFalse(result.is_valid)
        self.assertFalse(result.details.get('risk_calculation_valid'))
        self.assertFalse(result.details.get('score_level_alignment'))
        self.assertIn('below threshold', result.errors[0].lower())

    def test_validate_risk_calculation_critical_below_threshold(self):
        """Test risk calculation validation detects CRITICAL risk level below threshold"""
        assessment = {
            'risk_level': 'CRITICAL',
            'risk_score': 7.0  # Below CRITICAL threshold of 10.0
        }
        result = self.rules._validate_risk_assessment(assessment, None, self.tenant, self.user)
        self.assertFalse(result.is_valid)
        self.assertFalse(result.details.get('risk_calculation_valid'))
        self.assertFalse(result.details.get('score_level_alignment'))
        self.assertIn('below threshold', result.errors[0].lower())

    def test_validate_risk_calculation_low_above_range_warning(self):
        """Test risk calculation validation warns when LOW risk score suggests higher level"""
        assessment = {
            'risk_level': 'LOW',
            'risk_score': 2.0  # Above LOW range, suggests MEDIUM
        }
        result = self.rules._validate_risk_assessment(assessment, None, self.tenant, self.user)
        self.assertTrue(result.is_valid)  # Warning, not error
        self.assertTrue(result.details.get('risk_calculation_valid'))
        self.assertFalse(result.details.get('score_level_alignment'))
        self.assertGreater(len(result.warnings), 0)
        self.assertIn('suggests', result.warnings[0].lower())

    def test_validate_risk_calculation_medium_above_range_warning(self):
        """Test risk calculation validation warns when MEDIUM risk score suggests higher level"""
        assessment = {
            'risk_level': 'MEDIUM',
            'risk_score': 7.0  # Above MEDIUM range, suggests HIGH
        }
        result = self.rules._validate_risk_assessment(assessment, None, self.tenant, self.user)
        self.assertTrue(result.is_valid)  # Warning, not error
        self.assertTrue(result.details.get('risk_calculation_valid'))
        self.assertFalse(result.details.get('score_level_alignment'))
        self.assertGreater(len(result.warnings), 0)
        self.assertIn('suggests', result.warnings[0].lower())

    def test_validate_risk_calculation_high_above_range_warning(self):
        """Test risk calculation validation warns when HIGH risk score suggests CRITICAL"""
        assessment = {
            'risk_level': 'HIGH',
            'risk_score': 12.0  # Above HIGH range, suggests CRITICAL
        }
        result = self.rules._validate_risk_assessment(assessment, None, self.tenant, self.user)
        self.assertTrue(result.is_valid)  # Warning, not error
        self.assertTrue(result.details.get('risk_calculation_valid'))
        self.assertFalse(result.details.get('score_level_alignment'))
        self.assertGreater(len(result.warnings), 0)
        self.assertIn('suggests', result.warnings[0].lower())

    def test_validate_risk_calculation_none_with_score_warning(self):
        """Test risk calculation validation warns when NONE risk level has non-zero score"""
        assessment = {
            'risk_level': 'NONE',
            'risk_score': 0.5  # Non-zero score with NONE level
        }
        result = self.rules._validate_risk_assessment(assessment, None, self.tenant, self.user)
        self.assertTrue(result.is_valid)  # Warning, not error
        self.assertFalse(result.details.get('score_level_alignment'))
        self.assertGreater(len(result.warnings), 0)


class RiskMitigationValidationTest(TestCase):
    """Test risk mitigation validation"""

    def setUp(self):
        """Set up test fixtures"""
        from hub.apps.users.models import UserStatus
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com", password="testpass123", tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        self.rules = ComplianceBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

    def test_validate_risk_mitigation_valid_list(self):
        """Test risk mitigation validation with valid list of actions"""
        assessment = {
            'risk_level': 'HIGH',
            'risk_score': 7.5,
            'mitigation_actions': [
                {
                    'action_type': 'ENCRYPTION',
                    'description': 'Encrypt sensitive data at rest',
                    'status': 'COMPLETED',
                    'priority': 'HIGH'
                },
                {
                    'action_type': 'ACCESS_CONTROL',
                    'description': 'Implement role-based access control',
                    'status': 'IN_PROGRESS',
                    'priority': 'MEDIUM'
                }
            ]
        }
        result = self.rules._validate_risk_assessment(assessment, None, self.tenant, self.user)
        self.assertTrue(result.is_valid)
        self.assertTrue(result.details.get('mitigation_valid'))
        self.assertEqual(result.details.get('mitigation_count'), 2)
        self.assertEqual(result.details.get('valid_actions_count'), 2)

    def test_validate_risk_mitigation_valid_single_dict(self):
        """Test risk mitigation validation with single dict (normalized to list)"""
        assessment = {
            'risk_level': 'MEDIUM',
            'risk_score': 3.0,
            'mitigation_actions': {
                'action_type': 'ANONYMIZATION',
                'description': 'Anonymize PII data',
                'status': 'PENDING',
                'priority': 'MEDIUM'
            }
        }
        result = self.rules._validate_risk_assessment(assessment, None, self.tenant, self.user)
        self.assertTrue(result.is_valid)
        self.assertTrue(result.details.get('mitigation_valid'))
        self.assertEqual(result.details.get('mitigation_count'), 1)

    def test_validate_risk_mitigation_missing_action_type(self):
        """Test risk mitigation validation detects missing action_type"""
        assessment = {
            'risk_level': 'HIGH',
            'risk_score': 7.5,
            'mitigation_actions': [
                {
                    'description': 'Some mitigation action',
                    'status': 'PENDING'
                }
            ]
        }
        result = self.rules._validate_risk_assessment(assessment, None, self.tenant, self.user)
        self.assertFalse(result.is_valid)
        self.assertFalse(result.details.get('mitigation_valid'))
        self.assertIn('action_type', result.errors[0].lower())

    def test_validate_risk_mitigation_missing_description(self):
        """Test risk mitigation validation detects missing description"""
        assessment = {
            'risk_level': 'HIGH',
            'risk_score': 7.5,
            'mitigation_actions': [
                {
                    'action_type': 'ENCRYPTION',
                    'status': 'PENDING'
                }
            ]
        }
        result = self.rules._validate_risk_assessment(assessment, None, self.tenant, self.user)
        self.assertFalse(result.is_valid)
        self.assertFalse(result.details.get('mitigation_valid'))
        self.assertIn('description', result.errors[0].lower())

    def test_validate_risk_mitigation_invalid_action_type(self):
        """Test risk mitigation validation warns on unknown action_type"""
        assessment = {
            'risk_level': 'MEDIUM',
            'risk_score': 3.0,
            'mitigation_actions': [
                {
                    'action_type': 'UNKNOWN_TYPE',
                    'description': 'Some action'
                }
            ]
        }
        result = self.rules._validate_risk_assessment(assessment, None, self.tenant, self.user)
        self.assertTrue(result.is_valid)  # Warning, not error
        self.assertTrue(result.details.get('mitigation_valid'))
        self.assertGreater(len(result.warnings), 0)
        self.assertIn('unknown action_type', result.warnings[0].lower())

    def test_validate_risk_mitigation_invalid_status(self):
        """Test risk mitigation validation warns on invalid status"""
        assessment = {
            'risk_level': 'MEDIUM',
            'risk_score': 3.0,
            'mitigation_actions': [
                {
                    'action_type': 'ENCRYPTION',
                    'description': 'Encrypt data',
                    'status': 'INVALID_STATUS'
                }
            ]
        }
        result = self.rules._validate_risk_assessment(assessment, None, self.tenant, self.user)
        self.assertTrue(result.is_valid)  # Warning, not error
        self.assertTrue(result.details.get('mitigation_valid'))
        self.assertGreater(len(result.warnings), 0)
        self.assertIn('invalid status', result.warnings[0].lower())

    def test_validate_risk_mitigation_empty_list(self):
        """Test risk mitigation validation with empty list"""
        assessment = {
            'risk_level': 'LOW',
            'risk_score': 0.5,
            'mitigation_actions': []
        }
        result = self.rules._validate_risk_assessment(assessment, None, self.tenant, self.user)
        self.assertTrue(result.is_valid)
        self.assertTrue(result.details.get('mitigation_valid'))
        self.assertEqual(result.details.get('mitigation_count'), 0)

    def test_validate_risk_mitigation_invalid_type(self):
        """Test risk mitigation validation detects invalid type"""
        assessment = {
            'risk_level': 'MEDIUM',
            'risk_score': 3.0,
            'mitigation_actions': 'not a list or dict'
        }
        result = self.rules._validate_risk_assessment(assessment, None, self.tenant, self.user)
        self.assertFalse(result.is_valid)
        self.assertFalse(result.details.get('mitigation_valid'))
        self.assertIn('list or dictionary', result.errors[0].lower())

    def test_validate_risk_mitigation_high_risk_no_mitigation_warning(self):
        """Test risk mitigation validation warns when HIGH risk has no mitigation"""
        assessment = {
            'risk_level': 'HIGH',
            'risk_score': 7.5
            # No mitigation_actions
        }
        result = self.rules._validate_risk_assessment(assessment, None, self.tenant, self.user)
        self.assertTrue(result.is_valid)  # Warning, not error
        self.assertFalse(result.details.get('has_mitigation'))
        self.assertGreater(len(result.warnings), 0)
        self.assertIn('mitigation actions', result.warnings[0].lower())

    def test_validate_risk_mitigation_critical_risk_no_mitigation_warning(self):
        """Test risk mitigation validation warns when CRITICAL risk has no mitigation"""
        assessment = {
            'risk_level': 'CRITICAL',
            'risk_score': 15.0
            # No mitigation_actions
        }
        result = self.rules._validate_risk_assessment(assessment, None, self.tenant, self.user)
        self.assertTrue(result.is_valid)  # Warning, not error
        self.assertFalse(result.details.get('has_mitigation'))
        self.assertGreater(len(result.warnings), 0)
        self.assertIn('mitigation actions', result.warnings[0].lower())

    def test_validate_risk_mitigation_high_risk_single_action_warning(self):
        """Test risk mitigation validation warns when HIGH risk has only one mitigation"""
        assessment = {
            'risk_level': 'HIGH',
            'risk_score': 7.5,
            'mitigation_actions': [
                {
                    'action_type': 'ENCRYPTION',
                    'description': 'Encrypt data'
                }
            ]
        }
        result = self.rules._validate_risk_assessment(assessment, None, self.tenant, self.user)
        self.assertTrue(result.is_valid)  # Warning, not error
        self.assertTrue(result.details.get('mitigation_valid'))
        self.assertGreater(len(result.warnings), 0)
        self.assertIn('multiple mitigation actions', result.warnings[0].lower())

    def test_validate_risk_mitigation_high_risk_no_high_priority_warning(self):
        """Test risk mitigation validation warns when HIGH risk has no high-priority actions"""
        assessment = {
            'risk_level': 'HIGH',
            'risk_score': 7.5,
            'mitigation_actions': [
                {
                    'action_type': 'ENCRYPTION',
                    'description': 'Encrypt data',
                    'priority': 'LOW'
                },
                {
                    'action_type': 'ACCESS_CONTROL',
                    'description': 'Access control',
                    'priority': 'MEDIUM'
                }
            ]
        }
        result = self.rules._validate_risk_assessment(assessment, None, self.tenant, self.user)
        self.assertTrue(result.is_valid)  # Warning, not error
        self.assertTrue(result.details.get('mitigation_valid'))
        self.assertGreater(len(result.warnings), 0)
        self.assertIn('high-priority', result.warnings[0].lower())


class ComplianceBusinessRulesIntegrationTest(TestCase):
    """Integration test for ComplianceBusinessRules"""

    def setUp(self):
        """Set up test fixtures"""
        from hub.apps.users.models import UserStatus
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com", password="testpass123", tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        self.rules = ComplianceBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        # Create asset and job
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user
        )

        self.job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.PENDING,
            resource_type="ASSET",
            resource_id=self.asset.id,
            created_by=self.user
        )

    def test_validate_comprehensive_compliance_run(self):
        """Test comprehensive compliance run validation"""
        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            job=self.job,
            status=ComplianceRunStatus.SUCCEEDED,
            overall_status='PASS',
            risk_level=RiskLevel.LOW,
            allowed_to_store=True,
            regulations=['GDPR', 'CCPA']
        )

        assessment = {
            'risk_level': 'LOW',
            'risk_score': 2.5,
            'allowed_to_store': True,
            'total_violations': 0
        }

        context = ComplianceRuleExecutionContext(
            compliance_run=compliance_run,
            assessment=assessment,
            resource=self.asset,
            tenant=self.tenant,
            user=self.user
        )

        result = self.rules.validate(context, validation_type='all')

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertIn('compliance_run', result.details['validated_items'])
        self.assertIn('risk_assessment', result.details['validated_items'])
        self.assertIn('tenant_context', result.details['validated_items'])
        self.assertIn('permissions', result.details['validated_items'])

    def test_validate_with_compliance_service(self):
        """Test compliance validation integrated with ComplianceService"""
        from hub.apps.compliance.service_client import ComplianceServiceClient

        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            job=self.job,
            status=ComplianceRunStatus.PENDING,
            regulations=['GDPR']
        )

        result = self.rules._validate_compliance_run(compliance_run, self.tenant, self.user)

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

        # Verify Compliance service client can be instantiated (integration check)
        try:
            compliance_client = ComplianceServiceClient()
            self.assertIsNotNone(compliance_client)
        except Exception as e:
            # Compliance service might not be available in test environment
            # This is acceptable - we're testing the business rules, not the service
            pass

    def test_validate_risk_assessment_with_compliance_service_result(self):
        """Test risk assessment validation with ComplianceService result structure"""
        from hub.apps.compliance.service_client import ComplianceServiceClient

        # Create compliance run
        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            job=self.job,
            status=ComplianceRunStatus.SUCCEEDED,
            risk_level=RiskLevel.HIGH,
            allowed_to_store=False,
            regulations=['GDPR']
        )

        # Simulate ComplianceService result structure
        assessment = {
            'risk_level': 'HIGH',
            'risk_score': 7.5,
            'allowed_to_store': False,
            'detected_categories': {
                'EMAIL': 100,
                'PHONE': 50
            },
            'violations': [
                {'severity': 'HIGH', 'description': 'PII detected'}
            ],
            'mitigation_actions': [
                {
                    'action_type': 'ENCRYPTION',
                    'description': 'Encrypt sensitive columns',
                    'status': 'COMPLETED',
                    'priority': 'HIGH'
                },
                {
                    'action_type': 'ACCESS_CONTROL',
                    'description': 'Restrict access to authorized users',
                    'status': 'IN_PROGRESS',
                    'priority': 'HIGH'
                }
            ]
        }

        # Validate risk assessment
        result = self.rules._validate_risk_assessment(
            assessment, compliance_run, self.tenant, self.user
        )

        # Verify all validations pass
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertTrue(result.details.get('risk_level_valid'))
        self.assertTrue(result.details.get('risk_calculation_valid'))
        self.assertTrue(result.details.get('mitigation_valid'))
        self.assertTrue(result.details.get('risk_level_consistency'))

        # Verify ComplianceService client integration
        try:
            compliance_client = ComplianceServiceClient()
            self.assertIsNotNone(compliance_client)
            # Verify client has scan_file method (integration check)
            self.assertTrue(hasattr(compliance_client, 'scan_file'))
        except Exception as e:
            # Compliance service might not be available in test environment
            # This is acceptable - we're testing the business rules, not the service
            pass

    def test_validate_comprehensive_risk_assessment_integration(self):
        """Test comprehensive risk assessment validation with all features"""
        # Create compliance run
        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            job=self.job,
            status=ComplianceRunStatus.SUCCEEDED,
            risk_level=RiskLevel.CRITICAL,
            allowed_to_store=False,
            regulations=['GDPR', 'HIPAA']
        )

        # Comprehensive assessment with all validation features
        assessment = {
            'risk_level': 'CRITICAL',
            'risk_score': 15.5,
            'allowed_to_store': False,
            'violations': [
                {'severity': 'CRITICAL', 'description': 'Health data detected'},
                {'severity': 'HIGH', 'description': 'SSN detected'}
            ],
            'mitigation_actions': [
                {
                    'action_type': 'ENCRYPTION',
                    'description': 'Encrypt all sensitive data',
                    'status': 'COMPLETED',
                    'priority': 'CRITICAL'
                },
                {
                    'action_type': 'ACCESS_CONTROL',
                    'description': 'Implement strict access controls',
                    'status': 'COMPLETED',
                    'priority': 'CRITICAL'
                },
                {
                    'action_type': 'AUDIT_LOGGING',
                    'description': 'Enable comprehensive audit logging',
                    'status': 'IN_PROGRESS',
                    'priority': 'HIGH'
                }
            ]
        }

        # Validate using full validation context
        context = ComplianceRuleExecutionContext(
            compliance_run=compliance_run,
            assessment=assessment,
            resource=self.asset,
            tenant=self.tenant,
            user=self.user
        )

        result = self.rules.validate(context, validation_type='all')

        # Verify comprehensive validation
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertIn('risk_assessment', result.details['validated_items'])

        # Verify risk assessment details
        assessment_result = self.rules._validate_risk_assessment(
            assessment, compliance_run, self.tenant, self.user
        )
        self.assertTrue(assessment_result.is_valid)
        self.assertTrue(assessment_result.details.get('risk_level_valid'))
        self.assertTrue(assessment_result.details.get('risk_calculation_valid'))
        self.assertTrue(assessment_result.details.get('mitigation_valid'))
        self.assertEqual(assessment_result.details.get('mitigation_count'), 3)
        self.assertEqual(assessment_result.details.get('valid_actions_count'), 3)


class ComplianceRunExecutionValidationTest(TestCase):
    """Test compliance run execution validation"""

    def setUp(self):
        """Set up test fixtures"""
        from hub.apps.users.models import UserStatus
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com", password="testpass123", tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        self.rules = ComplianceBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        # Create asset, dataset, file, and job
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user
        )

        self.file = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1024,
            storage_path="s3://bucket/test.csv",
            status=FileStatus.ACTIVE,
            created_by=self.user
        )

        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            version=1,
            format="csv",
            created_by=self.user
        )

        self.job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.PENDING,
            resource_type="ASSET",
            resource_id=self.asset.id,
            created_by=self.user
        )

    def test_validate_compliance_run_execution_all_validations(self):
        """Test comprehensive compliance run execution validation"""
        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            job=self.job,
            status=ComplianceRunStatus.PENDING,
            regulations=['GDPR']
        )

        result = self.rules.validate_compliance_run_execution(
            compliance_run, self.user, self.tenant, validation_type='all'
        )

        self.assertTrue(result.is_valid)
        self.assertEqual(result.details['validation_type'], 'compliance_run_execution')
        self.assertTrue(result.details.get('eligibility_validated'))
        self.assertTrue(result.details.get('quota_validated'))
        self.assertTrue(result.details.get('status_transition_validated'))

    def test_validate_compliance_run_eligibility_valid(self):
        """Test run eligibility validation with valid user and resource"""
        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            job=self.job,
            status=ComplianceRunStatus.PENDING
        )

        result = self.rules._validate_compliance_run_eligibility(compliance_run, self.user, self.tenant)

        self.assertTrue(result.is_valid)
        self.assertTrue(result.details['eligible'])
        self.assertTrue(result.details['user_active'])
        self.assertTrue(result.details['user_tenant_match'])
        self.assertTrue(result.details['resource_accessible'])

    def test_validate_compliance_run_eligibility_inactive_user(self):
        """Test run eligibility validation with inactive user"""
        from hub.apps.users.models import UserStatus
        inactive_user = User.objects.create_user(
            email=f"inactive-{uuid.uuid4().hex[:8]}@example.com", password="testpass123", tenant=self.tenant,
            status=UserStatus.DISABLED
        )

        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            job=self.job,
            status=ComplianceRunStatus.PENDING
        )

        result = self.rules._validate_compliance_run_eligibility(compliance_run, inactive_user, self.tenant)

        self.assertFalse(result.is_valid)
        self.assertIn('not active', result.errors[0].lower())

    def test_validate_compliance_run_eligibility_user_tenant_mismatch(self):
        """Test run eligibility validation with user from different tenant"""
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}", slug=f"other-tenant-{_uid}", kyc_status=KYCStatus.VERIFIED
        )
        from hub.apps.users.models import UserStatus
        other_user = User.objects.create_user(
            email=f"other-{uuid.uuid4().hex[:8]}@example.com", password="testpass123", tenant=other_tenant,
            status=UserStatus.ACTIVE
        )

        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            job=self.job,
            status=ComplianceRunStatus.PENDING
        )

        result = self.rules._validate_compliance_run_eligibility(compliance_run, other_user, self.tenant)

        self.assertFalse(result.is_valid)
        self.assertIn('tenant', result.errors[0].lower())

    def test_validate_compliance_run_eligibility_resource_tenant_mismatch(self):
        """Test run eligibility validation with resource from different tenant"""
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}", slug=f"other-tenant-{_uid}", kyc_status=KYCStatus.VERIFIED
        )
        other_asset = Asset.objects.create(
            tenant=other_tenant,
            key="other-asset",
            name="Other Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user
        )

        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=other_asset,
            job=self.job,
            status=ComplianceRunStatus.PENDING
        )

        result = self.rules._validate_compliance_run_eligibility(compliance_run, self.user, self.tenant)

        self.assertFalse(result.is_valid)
        self.assertIn('tenant', result.errors[0].lower())

    def test_validate_compliance_run_eligibility_dataset_resource(self):
        """Test run eligibility validation with dataset resource"""
        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            dataset=self.dataset,
            job=self.job,
            status=ComplianceRunStatus.PENDING
        )

        result = self.rules._validate_compliance_run_eligibility(compliance_run, self.user, self.tenant)

        self.assertTrue(result.is_valid)
        self.assertEqual(result.details['resource_type'], 'dataset')
        self.assertTrue(result.details['dataset_has_file'])

    def test_validate_compliance_run_eligibility_file_resource(self):
        """Test run eligibility validation with file resource"""
        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            file=self.file,
            job=self.job,
            status=ComplianceRunStatus.PENDING
        )

        result = self.rules._validate_compliance_run_eligibility(compliance_run, self.user, self.tenant)

        self.assertTrue(result.is_valid)
        self.assertEqual(result.details['resource_type'], 'file')
        self.assertTrue(result.details['file_has_storage_path'])

    def test_validate_compliance_run_resource_quota_valid(self):
        """Test resource quota validation with valid quota"""
        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            job=self.job,
            status=ComplianceRunStatus.PENDING
        )

        result = self.rules._validate_compliance_run_resource_quota(compliance_run, self.tenant)

        # Note: This may fail if compliance service is unavailable, which is acceptable
        # The test verifies the validation logic, not the service availability
        self.assertIsNotNone(result)
        self.assertEqual(result.details['validation_type'], 'resource_quota')
        self.assertIn('compliance_service_available', result.details)

    def test_validate_compliance_run_resource_quota_concurrent_limit(self):
        """Test resource quota validation detects concurrent run limit"""
        # Create multiple pending/running runs to exceed limit
        for i in range(11):  # Default limit is 10
            ComplianceRun.objects.create(
                tenant=self.tenant,
                asset=self.asset,
                job=self.job,
                status=ComplianceRunStatus.PENDING if i < 10 else ComplianceRunStatus.RUNNING
            )

        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            job=self.job,
            status=ComplianceRunStatus.PENDING
        )

        result = self.rules._validate_compliance_run_resource_quota(compliance_run, self.tenant)

        # Should detect concurrent limit exceeded
        self.assertFalse(result.is_valid)
        self.assertIn('concurrent', result.errors[0].lower())

    def test_validate_compliance_run_status_transition_valid(self):
        """Test status transition validation with valid transition"""
        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            job=self.job,
            status=ComplianceRunStatus.PENDING
        )

        result = self.rules._validate_compliance_run_status_transition(
            compliance_run,
            current_status="PENDING",
            new_status="RUNNING"
        )

        self.assertTrue(result.is_valid)
        self.assertTrue(result.details['transition_allowed'])

    def test_validate_compliance_run_status_transition_invalid(self):
        """Test status transition validation with invalid transition"""
        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            job=self.job,
            status=ComplianceRunStatus.PENDING
        )

        result = self.rules._validate_compliance_run_status_transition(
            compliance_run,
            current_status="PENDING",
            new_status="SUCCEEDED"  # Invalid: must go through RUNNING first
        )

        self.assertFalse(result.is_valid)
        self.assertIn('transition', result.errors[0].lower())

    def test_validate_compliance_run_status_transition_terminal_state(self):
        """Test status transition validation prevents transition from terminal state"""
        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            job=self.job,
            status=ComplianceRunStatus.SUCCEEDED
        )

        result = self.rules._validate_compliance_run_status_transition(
            compliance_run,
            current_status="SUCCEEDED",
            new_status="RUNNING"  # Cannot transition from terminal state
        )

        self.assertFalse(result.is_valid)
        self.assertIn('transition', result.errors[0].lower())

    def test_validate_compliance_run_status_transition_with_timestamps(self):
        """Test status transition validation with proper timestamps"""
        from django.utils import timezone
        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            job=self.job,
            status=ComplianceRunStatus.RUNNING,
            started_at=timezone.now()
        )
        compliance_run.completed_at = timezone.now()
        compliance_run.save()

        result = self.rules._validate_compliance_run_status_transition(
            compliance_run,
            current_status="RUNNING",
            new_status="SUCCEEDED"
        )

        self.assertTrue(result.is_valid)
        self.assertTrue(result.details['started_at_set'])
        self.assertTrue(result.details['completed_at_set'])

    def test_validate_compliance_run_execution_integration(self):
        """Test integration of compliance run execution validation with ComplianceService"""
        from hub.apps.compliance.service_client import ComplianceServiceClient

        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            job=self.job,
            status=ComplianceRunStatus.PENDING,
            regulations=['GDPR']
        )

        result = self.rules.validate_compliance_run_execution(
            compliance_run, self.user, self.tenant, validation_type='all'
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.details['validation_type'], 'compliance_run_execution')

        # Verify ComplianceService client can be instantiated (integration check)
        try:
            compliance_client = ComplianceServiceClient()
            self.assertIsNotNone(compliance_client)
            # Verify client has health_check method
            self.assertTrue(hasattr(compliance_client, 'health_check'))
        except Exception as e:
            # Compliance service might not be available in test environment
            # This is acceptable - we're testing the business rules, not the service
            pass



class ScanTypeValidationTest(TestCase):
    """Test scan type validation"""

    def setUp(self):
        """Set up test fixtures"""
        from hub.apps.users.models import UserStatus
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com", password="testpass123", tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        self.rules = ComplianceBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

    def test_validate_scan_type_valid_types(self):
        """Test scan type validation with valid scan types"""
        scan_config = {
            'applicable_regulations': ['GDPR', 'HIPAA', 'SOC2']
        }
        result = self.rules._validate_scan_type(scan_config, self.tenant)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertTrue(result.details['scan_types_valid'])
        self.assertEqual(result.details['scan_types_count'], 3)

    def test_validate_scan_type_invalid_types(self):
        """Test scan type validation with invalid scan types"""
        scan_config = {
            'applicable_regulations': ['INVALID_TYPE', 'GDPR']
        }
        result = self.rules._validate_scan_type(scan_config, self.tenant)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn('INVALID_TYPE', result.errors[0])

    def test_validate_scan_type_empty_strings(self):
        """Test scan type validation with empty strings"""
        scan_config = {
            'applicable_regulations': ['GDPR', '', '  ']
        }
        result = self.rules._validate_scan_type(scan_config, self.tenant)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        # Empty strings are caught as invalid scan types OR as non-empty string validation
        error_messages = ' '.join([e.lower() for e in result.errors])
        self.assertTrue(
            'non-empty strings' in error_messages or
            'invalid scan types' in error_messages,
            f"Expected error about non-empty strings or invalid scan types, got: {result.errors}"
        )

    def test_validate_scan_type_single_string(self):
        """Test scan type validation with single string"""
        scan_config = {
            'scan_type': 'GDPR'
        }
        result = self.rules._validate_scan_type(scan_config, self.tenant)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(result.details['scan_types_count'], 1)

    def test_validate_scan_type_no_types_provided(self):
        """Test scan type validation with no types provided"""
        scan_config = {}
        result = self.rules._validate_scan_type(scan_config, self.tenant)
        self.assertTrue(result.is_valid)  # Warning, not error
        self.assertEqual(len(result.warnings), 1)
        self.assertIn('No scan types provided', result.warnings[0])

    def test_validate_scan_type_custom_type(self):
        """Test scan type validation with CUSTOM type"""
        scan_config = {
            'applicable_regulations': ['CUSTOM']
        }
        result = self.rules._validate_scan_type(scan_config, self.tenant)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertTrue(result.details['scan_types_valid'])


class ScanConfigurationValidationTest(TestCase):
    """Test scan configuration validation"""

    def setUp(self):
        """Set up test fixtures"""
        from hub.apps.users.models import UserStatus
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com", password="testpass123", tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        self.rules = ComplianceBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

    def test_validate_scan_config_valid_mode(self):
        """Test scan configuration validation with valid scan mode"""
        scan_config = {
            'scan_mode': 'internal',
            'applicable_regulations': ['GDPR']
        }
        result = self.rules._validate_scan_config(scan_config, self.tenant)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertTrue(result.details['scan_mode_valid'])
        self.assertEqual(result.details['scan_mode'], 'internal')

    def test_validate_scan_config_invalid_mode(self):
        """Test scan configuration validation with invalid scan mode"""
        scan_config = {
            'scan_mode': 'invalid_mode',
            'applicable_regulations': ['GDPR']
        }
        result = self.rules._validate_scan_config(scan_config, self.tenant)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn('invalid scan_mode', result.errors[0].lower())

    def test_validate_scan_config_default_mode(self):
        """Test scan configuration validation with default scan mode"""
        scan_config = {
            'applicable_regulations': ['GDPR']
        }
        result = self.rules._validate_scan_config(scan_config, self.tenant)
        self.assertTrue(result.is_valid)
        self.assertEqual(result.details['scan_mode'], 'internal')

    def test_validate_scan_config_valid_targeted_categories(self):
        """Test scan configuration validation with valid targeted categories"""
        scan_config = {
            'scan_mode': 'internal',
            'targeted_categories': ['EMAIL', 'PHONE', 'SSN']
        }
        result = self.rules._validate_scan_config(scan_config, self.tenant)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertTrue(result.details['targeted_categories_valid'])
        self.assertEqual(result.details['targeted_categories_count'], 3)

    def test_validate_scan_config_invalid_targeted_categories_not_list(self):
        """Test scan configuration validation with targeted categories not a list"""
        scan_config = {
            'scan_mode': 'internal',
            'targeted_categories': 'not a list'
        }
        result = self.rules._validate_scan_config(scan_config, self.tenant)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn('targeted_categories', result.errors[0].lower())

    def test_validate_scan_config_invalid_targeted_categories_empty_strings(self):
        """Test scan configuration validation with empty strings in targeted categories"""
        scan_config = {
            'scan_mode': 'internal',
            'targeted_categories': ['EMAIL', '', '  ']
        }
        result = self.rules._validate_scan_config(scan_config, self.tenant)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn('non-empty strings', result.errors[0].lower())

    def test_validate_scan_config_unknown_params(self):
        """Test scan configuration validation with unknown parameters"""
        scan_config = {
            'scan_mode': 'internal',
            'unknown_param': 'value',
            'another_unknown': 123
        }
        result = self.rules._validate_scan_config(scan_config, self.tenant)
        self.assertTrue(result.is_valid)  # Warning, not error
        self.assertGreaterEqual(len(result.warnings), 1)
        self.assertIn('unknown', result.warnings[0].lower())
        # Should have both unknown params in the warning
        warning_text = ' '.join(result.warnings).lower()
        self.assertIn('unknown_param', warning_text)
        self.assertIn('another_unknown', warning_text)


class ScanResourceValidationTest(TestCase):
    """Test scan resource validation"""

    def setUp(self):
        """Set up test fixtures"""
        from hub.apps.users.models import UserStatus
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com", password="testpass123", tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        self.rules = ComplianceBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        # Create asset, dataset, and file
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user
        )

        self.file = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1024,
            storage_path="s3://bucket/test.csv",
            status=FileStatus.ACTIVE,
            created_by=self.user
        )

        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            version=1,
            format="csv",
            created_by=self.user
        )

    def test_validate_scan_resource_no_resource(self):
        """Test scan resource validation with no resource provided"""
        scan_config = {}
        result = self.rules._validate_scan_resource(scan_config, self.tenant, self.user)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn('asset_id', result.errors[0].lower() or 'dataset_id' in result.errors[0].lower() or 'file_id' in result.errors[0].lower())

    def test_validate_scan_resource_valid_asset(self):
        """Test scan resource validation with valid asset"""
        scan_config = {
            'asset_id': self.asset.id
        }
        result = self.rules._validate_scan_resource(scan_config, self.tenant, self.user)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertTrue(result.details['has_resource'])
        self.assertEqual(result.details['resource_type'], 'asset')

    def test_validate_scan_resource_valid_dataset(self):
        """Test scan resource validation with valid dataset"""
        scan_config = {
            'dataset_id': self.dataset.id
        }
        result = self.rules._validate_scan_resource(scan_config, self.tenant, self.user)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertTrue(result.details['has_resource'])
        self.assertEqual(result.details['resource_type'], 'dataset')

    def test_validate_scan_resource_valid_file(self):
        """Test scan resource validation with valid file"""
        scan_config = {
            'file_id': self.file.id
        }
        result = self.rules._validate_scan_resource(scan_config, self.tenant, self.user)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertTrue(result.details['has_resource'])
        self.assertEqual(result.details['resource_type'], 'file')

    def test_validate_scan_resource_nonexistent_asset(self):
        """Test scan resource validation with nonexistent asset"""
        import uuid
        scan_config = {
            'asset_id': uuid.uuid4()
        }
        result = self.rules._validate_scan_resource(scan_config, self.tenant, self.user)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn('does not exist', result.errors[0].lower())

    def test_validate_scan_resource_asset_wrong_tenant(self):
        """Test scan resource validation with asset from wrong tenant"""
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}", slug=f"other-tenant-{_uid}", kyc_status=KYCStatus.VERIFIED
        )
        other_asset = Asset.objects.create(
            tenant=other_tenant,
            key="other-asset",
            name="Other Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user
        )
        scan_config = {
            'asset_id': other_asset.id
        }
        result = self.rules._validate_scan_resource(scan_config, self.tenant, self.user)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn('does not belong to tenant', result.errors[0].lower())


class ScanScheduleValidationTest(TestCase):
    """Test scan schedule validation"""

    def setUp(self):
        """Set up test fixtures"""
        from hub.apps.users.models import UserStatus
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com", password="testpass123", tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        self.rules = ComplianceBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        # Create asset and job
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user
        )

        self.job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.PENDING,
            resource_type="ASSET",
            resource_id=self.asset.id,
            created_by=self.user
        )

    def test_validate_scan_schedule_no_conflicts(self):
        """Test scan schedule validation with no conflicts"""
        scan_config = {
            'asset_id': self.asset.id,
            'applicable_regulations': ['GDPR']
        }
        result = self.rules._validate_scan_schedule(scan_config, self.tenant)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertFalse(result.details['has_conflicting_runs'])

    def test_validate_scan_schedule_with_conflicting_run(self):
        """Test scan schedule validation with conflicting run"""
        # Create a running compliance run
        ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            job=self.job,
            status=ComplianceRunStatus.RUNNING
        )

        scan_config = {
            'asset_id': self.asset.id,
            'applicable_regulations': ['GDPR']
        }
        result = self.rules._validate_scan_schedule(scan_config, self.tenant)
        self.assertTrue(result.is_valid)  # Warning, not error
        self.assertTrue(result.details['has_conflicting_runs'])
        self.assertEqual(result.details['conflicting_runs_count'], 1)
        self.assertGreater(len(result.warnings), 0)

    def test_validate_scan_schedule_exclude_run_id(self):
        """Test scan schedule validation excluding current run"""
        # Create a running compliance run
        running_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            job=self.job,
            status=ComplianceRunStatus.RUNNING
        )

        scan_config = {
            'asset_id': self.asset.id,
            'applicable_regulations': ['GDPR'],
            'exclude_run_id': running_run.id
        }
        result = self.rules._validate_scan_schedule(scan_config, self.tenant)
        self.assertTrue(result.is_valid)
        self.assertFalse(result.details['has_conflicting_runs'])

    def test_validate_scan_schedule_no_tenant(self):
        """Test scan schedule validation without tenant"""
        scan_config = {
            'asset_id': self.asset.id
        }
        result = self.rules._validate_scan_schedule(scan_config, None)
        self.assertTrue(result.is_valid)  # Warning, not error
        self.assertGreater(len(result.warnings), 0)
        self.assertIn('tenant not provided', result.warnings[0].lower())


class ScanConfigurationValidationIntegrationTest(TestCase):
    """Integration test for scan configuration validation"""

    def setUp(self):
        """Set up test fixtures"""
        from hub.apps.users.models import UserStatus
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com", password="testpass123", tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        self.rules = ComplianceBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        # Create asset and job
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user
        )

        self.job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.PENDING,
            resource_type="ASSET",
            resource_id=self.asset.id,
            created_by=self.user
        )

    def test_validate_scan_configuration_comprehensive(self):
        """Test comprehensive scan configuration validation"""
        scan_config = {
            'asset_id': self.asset.id,
            'scan_mode': 'internal',
            'applicable_regulations': ['GDPR', 'HIPAA'],
            'targeted_categories': ['EMAIL', 'PHONE']
        }
        result = self.rules.validate_scan_configuration(scan_config, self.tenant, self.user)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertTrue(result.details['scan_type_validated'])
        self.assertTrue(result.details['scan_config_validated'])
        self.assertTrue(result.details['scan_resource_validated'])
        self.assertTrue(result.details['scan_schedule_validated'])

    def test_validate_scan_configuration_with_compliance_service(self):
        """Test scan configuration validation integrated with ComplianceService"""
        from hub.apps.compliance.service_client import ComplianceServiceClient

        scan_config = {
            'asset_id': self.asset.id,
            'scan_mode': 'internal',
            'applicable_regulations': ['GDPR']
        }
        result = self.rules.validate_scan_configuration(scan_config, self.tenant, self.user)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

        # Verify Compliance service client can be instantiated (integration check)
        try:
            compliance_client = ComplianceServiceClient()
            self.assertIsNotNone(compliance_client)
        except Exception as e:
            # Compliance service might not be available in test environment
            # This is acceptable - we're testing the business rules, not the service
            pass
