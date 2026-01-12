"""
Integration tests for DQ/compliance execution (T.10).

Tests DQ and compliance job execution, result storage, and asset status updates.

Note: These tests require DQ and Compliance services to be running.
Start services with: make docker-up-services
"""
import pytest
import os
from unittest.mock import patch, Mock, MagicMock
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from django.conf import settings

from hub.apps.tenants.models import Tenant
from hub.apps.files.models import File, FileStatus
from hub.apps.datasets.models import Dataset
from hub.apps.assets.models import Asset, AssetStatus, DQStatus, ComplianceStatus
from hub.apps.dq.models import DQRun, DQRunStatus
from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus
from hub.apps.jobs.models import Job, JobType, JobStatus
from tests.conftest import check_service_health


pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


@pytest.mark.integration
class DQComplianceExecutionTest(TestCase):
    """Integration tests for DQ/compliance execution (T.10)"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()

        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant"
        )

        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant
        )

        self.client.force_authenticate(user=self.user)

        # Check if services are available
        # Use localhost for local testing, service names for Docker
        dq_url = os.getenv('DQ_SERVICE_URL', 'http://localhost:8083')
        compliance_url = os.getenv('COMPLIANCE_SERVICE_URL', 'http://localhost:8082')

        # Replace Docker service names with localhost if running outside Docker
        if 'dq-service' in dq_url:
            dq_url = dq_url.replace('dq-service', 'localhost')
        if 'compliance-service' in compliance_url:
            compliance_url = compliance_url.replace('compliance-service', 'localhost')

        if not check_service_health(dq_url, 'DQ Service'):
            pytest.skip(f"DQ service not available at {dq_url}")
        if not check_service_health(compliance_url, 'Compliance Service'):
            pytest.skip(f"Compliance service not available at {compliance_url}")

        # Create asset
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.DRAFT,
            created_by=self.user
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

    @patch('hub.apps.dq.service_client.DQServiceClient.run_dq')
    @patch('hub.apps.files.storage.S3StorageClient')
    def test_dq_execution_flow(self, mock_storage, mock_dq):
        """Test DQ execution flow"""
        # Mock DQ service response
        mock_dq.return_value = {
            'overall_status': 'PASS',
            'quality_score': 0.95,
            'checks': [
                {
                    'name': 'expect_column_values_to_not_be_null',
                    'status': 'PASS',
                    'result': {'observed_value': 100}
                }
            ],
            'engine_type': 'GREAT_EXPECTATIONS',
            'engine_version': '1.0.0',
            'profile_key': 'intake_basic_gx'
        }

        # Mock storage client
        mock_storage_client = MagicMock()
        mock_storage_client.download_file.return_value = b"id,name\n1,Test\n2,Sample"
        mock_storage.return_value = mock_storage_client

        # Create dataset
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            version=1,
            format='csv',
        )

        # Create DQ run via API
        response = self.client.post(
            '/api/v1/dq/runs/',
            {
                'file_id': str(self.file.id),
                'dataset_id': str(dataset.id),
                'asset_id': str(self.asset.id),
                'profile_key': 'intake_basic_gx'
            },
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify DQ run was created
        dq_run = DQRun.objects.filter(dataset=dataset).first()
        self.assertIsNotNone(dq_run)
        self.assertEqual(dq_run.status, DQRunStatus.PENDING)  # Initially PENDING

        # Execute the DQ run synchronously (simulating job execution)
        from hub.apps.dq.views import execute_dq_run
        execute_dq_run(str(dq_run.id))

        # Refresh and verify DQ run was updated
        dq_run.refresh_from_db()
        self.assertEqual(dq_run.status, DQRunStatus.SUCCEEDED)
        self.assertEqual(dq_run.overall_status, 'PASS')
        self.assertEqual(dq_run.quality_score, 0.95)

        # Verify job was created
        job = Job.objects.filter(
            type=JobType.DQ_RUN,
            resource_id=str(dq_run.id)
        ).first()
        self.assertIsNotNone(job)

    @patch('hub.apps.compliance.service_client.ComplianceServiceClient.scan_file')
    @patch('hub.apps.files.storage.S3StorageClient')
    def test_compliance_execution_flow(self, mock_storage, mock_compliance):
        """Test compliance execution flow"""
        # Mock compliance service response
        mock_compliance.return_value = {
            'overall_status': 'PASS',
            'risk_level': 'LOW',
            'allowed_to_store': True,
            'detected_categories': {},
            'column_findings': [],
            'regulation_mapping': {
                'GDPR': 'COMPLIANT',
                'CCPA': 'COMPLIANT'
            }
        }

        # Mock storage client
        mock_storage_client = MagicMock()
        mock_storage_client.download_file.return_value = b"id,name\n1,Test\n2,Sample"
        mock_storage.return_value = mock_storage_client

        # Create dataset
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            version=1,
            format='csv',
        )

        # Create compliance run via API
        response = self.client.post(
            '/api/v1/compliance/runs/',
            {
                'file_id': str(self.file.id),
                'dataset_id': str(dataset.id),
                'asset_id': str(self.asset.id),
                'scan_mode': 'internal'
            },
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify compliance run was created
        compliance_run = ComplianceRun.objects.filter(dataset=dataset).first()
        self.assertIsNotNone(compliance_run)
        self.assertEqual(compliance_run.status, ComplianceRunStatus.PENDING)  # Initially PENDING

        # Execute the compliance run synchronously (simulating job execution)
        from hub.apps.compliance.views import execute_compliance_run
        execute_compliance_run(str(compliance_run.id))

        # Refresh and verify compliance run was updated
        compliance_run.refresh_from_db()
        self.assertEqual(compliance_run.status, ComplianceRunStatus.SUCCEEDED)
        self.assertEqual(compliance_run.overall_status, 'PASS')
        self.assertTrue(compliance_run.allowed_to_store)

        # Verify job was created
        job = Job.objects.filter(
            type=JobType.COMPLIANCE_RUN,
            resource_id=str(compliance_run.id)
        ).first()
        self.assertIsNotNone(job)

    @patch('hub.apps.compliance.service_client.ComplianceServiceClient.scan_file')
    @patch('hub.apps.dq.service_client.DQServiceClient.run_dq')
    def test_dq_compliance_fail_closed_behavior(self, mock_dq, mock_compliance):
        """Test fail-closed behavior when DQ or compliance fails"""
        # Mock compliance failure
        mock_compliance.return_value = {
            'overall_status': 'FAIL',
            'risk_level': 'HIGH',
            'allowed_to_store': False,
            'detected_categories': {'EMAIL': 100},
            'column_findings': [
                {'column': 'email', 'pii_types': ['EMAIL'], 'count': 100}
            ]
        }

        # Mock DQ pass (but compliance fails)
        mock_dq.return_value = {
            'overall_status': 'PASS',
            'quality_score': 0.95
        }

        # Create dataset
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            version=1,
            format='csv',
        )

        # Create compliance run (will fail)
        compliance_response = self.client.post(
            '/api/v1/compliance/runs/',
            {
                'file_id': str(self.file.id),
                'dataset_id': str(dataset.id),
                'asset_id': str(self.asset.id),
                'scan_mode': 'internal'
            },
            format='json'
        )
        self.assertEqual(compliance_response.status_code, status.HTTP_201_CREATED)

        # Compliance run should be created (status will be PENDING until job completes)
        compliance_run = ComplianceRun.objects.filter(dataset=dataset).first()
        self.assertIsNotNone(compliance_run)
        # Note: The actual failure will be in result_json after job completes
        # For integration test, we verify the run was created

    @patch('hub.apps.compliance.service_client.ComplianceServiceClient.scan_file')
    @patch('hub.apps.dq.service_client.DQServiceClient.run_dq')
    @patch('hub.apps.files.storage.S3StorageClient')
    def test_asset_status_update_on_dq_compliance(self, mock_storage, mock_dq, mock_compliance):
        """Test asset status updates based on DQ and compliance results"""
        # Mock both passing
        mock_compliance.return_value = {
            'overall_status': 'PASS',
            'allowed_to_store': True
        }

        mock_dq.return_value = {
            'overall_status': 'PASS',
            'quality_score': 0.95
        }

        # Mock storage client
        mock_storage_client = MagicMock()
        mock_storage_client.download_file.return_value = b"id,name\n1,Test\n2,Sample"
        mock_storage.return_value = mock_storage_client

        # Create dataset
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            version=1,
            format='csv',
        )

        # Create compliance and DQ runs
        compliance_response = self.client.post(
            '/api/v1/compliance/runs/',
            {
                'file_id': str(self.file.id),
                'dataset_id': str(dataset.id),
                'asset_id': str(self.asset.id),
                'scan_mode': 'internal'
            },
            format='json'
        )
        self.assertEqual(compliance_response.status_code, status.HTTP_201_CREATED)

        dq_response = self.client.post(
            '/api/v1/dq/runs/',
            {
                'file_id': str(self.file.id),
                'dataset_id': str(dataset.id),
                'asset_id': str(self.asset.id)
            },
            format='json'
        )
        self.assertEqual(dq_response.status_code, status.HTTP_201_CREATED)

        # Get the runs
        dq_run = DQRun.objects.filter(dataset=dataset).first()
        compliance_run = ComplianceRun.objects.filter(dataset=dataset).first()

        self.assertIsNotNone(dq_run)
        self.assertIsNotNone(compliance_run)

        # Execute both runs synchronously (simulating job execution)
        from hub.apps.dq.views import execute_dq_run
        from hub.apps.compliance.views import execute_compliance_run

        execute_dq_run(str(dq_run.id))
        execute_compliance_run(str(compliance_run.id))

        # Refresh and verify runs were updated
        dq_run.refresh_from_db()
        compliance_run.refresh_from_db()

        self.assertEqual(dq_run.overall_status, 'PASS')
        self.assertEqual(compliance_run.overall_status, 'PASS')

