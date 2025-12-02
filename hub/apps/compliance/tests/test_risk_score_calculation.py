"""
Unit tests for risk score calculation and threshold logic.
"""
import pytest
import uuid
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from unittest.mock import patch, MagicMock

from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus, RiskLevel
from hub.apps.jobs.models import Job, JobType
from hub.apps.files.models import File, FileStatus
from hub.apps.users.models import UserStatus
from hub.apps.tenants.models import Tenant


pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class RiskScoreCalculationTest(TestCase):
    """Test risk score calculation and threshold logic"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()
        
        # Create tenant
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            status="ACTIVE",
            kyc_status="UNVERIFIED"
        )
        
        # Create user
        self.user = User.objects.create_user(
            email="user@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        
        # Create file
        self.file = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1024,
            storage_path="test/path/file.csv",
            status=FileStatus.ACTIVE,
            created_by=self.user
        )
    
    def test_risk_level_mapping(self):
        """Test risk level mapping (NONE, LOW, MEDIUM, HIGH, CRITICAL)"""
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.COMPLIANCE_RUN,
            resource_type="COMPLIANCE_RUN",
            resource_id=uuid.uuid4(),
            created_by=self.user
        )
        
        # Test NONE risk level
        compliance_run_none = ComplianceRun.objects.create(
            tenant=self.tenant,
            file=self.file,
            job=job,
            status=ComplianceRunStatus.SUCCEEDED,
            overall_status='PASS',
            risk_level=RiskLevel.NONE,
            allowed_to_store=True
        )
        
        # Test LOW risk level
        compliance_run_low = ComplianceRun.objects.create(
            tenant=self.tenant,
            file=self.file,
            job=job,
            status=ComplianceRunStatus.SUCCEEDED,
            overall_status='PASS',
            risk_level=RiskLevel.LOW,
            allowed_to_store=True
        )
        
        # Test MEDIUM risk level
        compliance_run_medium = ComplianceRun.objects.create(
            tenant=self.tenant,
            file=self.file,
            job=job,
            status=ComplianceRunStatus.SUCCEEDED,
            overall_status='WARN',
            risk_level=RiskLevel.MEDIUM,
            allowed_to_store=True
        )
        
        # Test HIGH risk level
        compliance_run_high = ComplianceRun.objects.create(
            tenant=self.tenant,
            file=self.file,
            job=job,
            status=ComplianceRunStatus.SUCCEEDED,
            overall_status='WARN',
            risk_level=RiskLevel.HIGH,
            allowed_to_store=False
        )
        
        # Test CRITICAL risk level
        compliance_run_critical = ComplianceRun.objects.create(
            tenant=self.tenant,
            file=self.file,
            job=job,
            status=ComplianceRunStatus.SUCCEEDED,
            overall_status='FAIL',
            risk_level=RiskLevel.CRITICAL,
            allowed_to_store=False
        )
        
        self.assertEqual(compliance_run_none.risk_level, RiskLevel.NONE)
        self.assertEqual(compliance_run_low.risk_level, RiskLevel.LOW)
        self.assertEqual(compliance_run_medium.risk_level, RiskLevel.MEDIUM)
        self.assertEqual(compliance_run_high.risk_level, RiskLevel.HIGH)
        self.assertEqual(compliance_run_critical.risk_level, RiskLevel.CRITICAL)
    
    def test_allowed_to_store_threshold_logic(self):
        """Test allowed_to_store threshold logic"""
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.COMPLIANCE_RUN,
            resource_type="COMPLIANCE_RUN",
            resource_id=uuid.uuid4(),
            created_by=self.user
        )
        
        # Test case: allowed_to_store=True (low risk)
        compliance_run_allowed = ComplianceRun.objects.create(
            tenant=self.tenant,
            file=self.file,
            job=job,
            status=ComplianceRunStatus.SUCCEEDED,
            overall_status='PASS',
            risk_level=RiskLevel.LOW,
            allowed_to_store=True,
            detected_categories_json=[
                {'category': 'EMAIL', 'count': 5, 'match_ratio': 0.05}  # 5% < 1% threshold
            ]
        )
        
        # Test case: allowed_to_store=False (high risk, exceeds threshold)
        compliance_run_blocked = ComplianceRun.objects.create(
            tenant=self.tenant,
            file=self.file,
            job=job,
            status=ComplianceRunStatus.SUCCEEDED,
            overall_status='FAIL',
            risk_level=RiskLevel.CRITICAL,
            allowed_to_store=False,
            detected_categories_json=[
                {'category': 'SSN', 'count': 100, 'match_ratio': 1.0}  # 100% > 1% threshold
            ]
        )
        
        self.assertTrue(compliance_run_allowed.allowed_to_store)
        self.assertFalse(compliance_run_blocked.allowed_to_store)
    
    def test_compliance_result_structure(self):
        """Test compliance result structure"""
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.COMPLIANCE_RUN,
            resource_type="COMPLIANCE_RUN",
            resource_id=uuid.uuid4(),
            created_by=self.user
        )
        
        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            file=self.file,
            job=job,
            status=ComplianceRunStatus.SUCCEEDED,
            overall_status='PASS',
            risk_level=RiskLevel.LOW,
            allowed_to_store=True,
            detected_categories_json=[
                {'category': 'EMAIL', 'count': 10, 'match_ratio': 0.1}
            ],
            column_findings_json=[
                {
                    'column': 'email',
                    'pii_categories': ['EMAIL'],
                    'match_ratio': 0.1
                }
            ],
            regulation_mapping_json={
                'GDPR': {'applies': True, 'categories': ['EMAIL']},
                'CCPA': {'applies': True, 'categories': ['EMAIL']}
            },
            regulations=['GDPR', 'CCPA']
        )
        
        # Retrieve compliance run
        self.client.force_authenticate(user=self.user)
        response = self.client.get(f"/api/v1/compliance/compliance-runs/{compliance_run.id}/")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        
        # Verify structure
        self.assertIn('id', data)
        self.assertIn('overall_status', data)
        self.assertIn('risk_level', data)
        self.assertIn('allowed_to_store', data)
        self.assertIn('detected_categories_json', data)
        self.assertIn('column_findings_json', data)
        self.assertIn('regulation_mapping_json', data)
        self.assertIn('regulations', data)
        
        # Verify values
        self.assertEqual(data['overall_status'], 'PASS')
        self.assertEqual(data['risk_level'], RiskLevel.LOW)
        self.assertTrue(data['allowed_to_store'])
        self.assertIsInstance(data['detected_categories_json'], list)
        self.assertIsInstance(data['column_findings_json'], list)
        self.assertIsInstance(data['regulation_mapping_json'], dict)
        self.assertIn('GDPR', data['regulations'])
        self.assertIn('CCPA', data['regulations'])

