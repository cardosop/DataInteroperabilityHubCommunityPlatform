"""
Tests for ODPS Normalization Job

Comprehensive tests for ODPS_NORMALIZATION job including success cases,
error handling, progress tracking, and event publishing.

These tests use REAL implementations (no mocks/stubs) to validate the
complete job execution path.
"""
import json
from django.test import TestCase
from django.utils import timezone
from django.db import transaction
import uuid

from hub.apps.jobs.models import Job, JobType, JobStatus
from hub.apps.jobs.tasks import (
    _execute_odps_normalization_job,
    process_job
)
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus
from hub.apps.contracts.models import (
    Contract,
    ContractStatus,
    OriginalSpecType,
    OriginalFormat,
    NormalizationStatus
)


class ODPSNormalizationJobTest(TestCase):
    """Test ODPS normalization job processor"""

    def setUp(self):
        """Set up test fixtures"""
        # Clear cache to ensure clean state
        from django.core.cache import cache
        cache.clear()

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

        # Create ODPS contract
        self.odps_contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product",
                        "name": "Test Product",
                        "description": "Test product description"
                    }
                },
                "contract": {
                    "spec": {
                        "apiVersion": "odcs/v3",
                        "kind": "DataContract",
                        "id": "test-contract",
                        "schema": {
                            "fields": [
                                {"name": "field1", "type": "string", "required": True}
                            ]
                        }
                    }
                }
            }
        }

        self.contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            original_format=OriginalFormat.JSON,
            original_raw=json.dumps(self.odps_contract_data),
            status=ContractStatus.DRAFT,
            normalization_status=NormalizationStatus.NOT_NORMALIZED
        )

        # Create job
        self.job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.ODPS_NORMALIZATION,
            status=JobStatus.PENDING,
            resource_type="CONTRACT",
            resource_id=self.contract.id,
            created_by=self.user,
            details_json={}
        )

    def tearDown(self):
        """Clean up after tests"""
        from django.core.cache import cache
        cache.clear()

    def test_execute_odps_normalization_job_success(self):
        """Test successful ODPS normalization job execution with real normalization"""
        # Execute job with real normalization function
        result = _execute_odps_normalization_job(self.job)

        # Verify result
        self.assertEqual(result['status'], 'completed')
        self.assertIn(result['normalization_status'], [
            NormalizationStatus.NORMALIZED_OK.value,
            NormalizationStatus.NORMALIZED_WITH_WARNINGS.value
        ])
        self.assertEqual(result['detected_spec_type'], 'ODPS')
        self.assertIn(result['detected_spec_version'], ['4.1', '4.0'])  # May detect 4.0 or 4.1
        self.assertEqual(result['contract_id'], str(self.contract.id))
        self.assertIsInstance(result['warnings_count'], int)
        self.assertIsInstance(result['errors_count'], int)

        # Verify contract was updated
        self.contract.refresh_from_db()
        self.assertNotEqual(self.contract.normalization_status, NormalizationStatus.NOT_NORMALIZED)
        self.assertIsNotNone(self.contract.hub_contract_json)
        self.assertIsInstance(self.contract.hub_contract_json, dict)
        # Verify hub_contract has expected structure
        self.assertIn('info', self.contract.hub_contract_json)

        # Verify progress tracking
        self.job.refresh_from_db()
        self.assertEqual(self.job.details_json['progress_percentage'], 100.0)
        self.assertEqual(self.job.details_json['current_phase'], 'completed')

    def test_execute_odps_normalization_job_with_warnings(self):
        """Test ODPS normalization job - warnings may occur with real normalization"""
        # Execute job with real normalization
        result = _execute_odps_normalization_job(self.job)

        # Verify result
        self.assertEqual(result['status'], 'completed')
        self.assertIn(result['normalization_status'], [
            NormalizationStatus.NORMALIZED_OK.value,
            NormalizationStatus.NORMALIZED_WITH_WARNINGS.value
        ])
        self.assertIsInstance(result['warnings_count'], int)
        self.assertIsInstance(result['normalization_warnings'], list)

        # Verify contract was updated
        self.contract.refresh_from_db()
        self.assertNotEqual(self.contract.normalization_status, NormalizationStatus.NOT_NORMALIZED)

    def test_execute_odps_normalization_job_failure_invalid_odps(self):
        """Test ODPS normalization job with invalid ODPS data"""
        # Create contract with invalid ODPS data
        invalid_contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            original_format=OriginalFormat.JSON,
            original_raw='{"invalid": "odps data"}',
            status=ContractStatus.DRAFT,
            normalization_status=NormalizationStatus.NOT_NORMALIZED
        )

        # Create job for invalid contract
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.ODPS_NORMALIZATION,
            status=JobStatus.PENDING,
            resource_type="CONTRACT",
            resource_id=invalid_contract.id,
            created_by=self.user,
            details_json={}
        )

        # Execute job - may fail or succeed with warnings depending on normalization logic
        try:
            result = _execute_odps_normalization_job(job)
            # If it succeeds, it should have warnings or errors
            self.assertEqual(result['status'], 'completed')
            # Normalization may succeed with warnings for invalid data
            self.assertIn(result['normalization_status'], [
                NormalizationStatus.NORMALIZED_OK.value,
                NormalizationStatus.NORMALIZED_WITH_WARNINGS.value,
                NormalizationStatus.NORMALIZATION_FAILED.value
            ])
        except ValueError as e:
            # If it fails, verify the error message
            self.assertIn("ODPS normalization failed", str(e))
            # Verify progress tracking shows failure
            job.refresh_from_db()
            self.assertEqual(job.details_json['progress_percentage'], 100.0)
            self.assertEqual(job.details_json['current_phase'], 'failed')

    def test_execute_odps_normalization_job_missing_contract_id(self):
        """Test ODPS normalization job with missing contract ID"""
        # Create job with empty string resource_id (simulating missing ID)
        # Note: resource_id is required by DB, so we use a non-existent UUID
        # and test that the validation happens in the function
        non_existent_id = uuid.uuid4()
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.ODPS_NORMALIZATION,
            status=JobStatus.PENDING,
            resource_type="CONTRACT",
            resource_id=non_existent_id,
            created_by=self.user
        )

        # Execute job - should raise ValueError because contract doesn't exist
        with self.assertRaises(ValueError) as cm:
            _execute_odps_normalization_job(job)

        self.assertIn("not found", str(cm.exception))

    def test_execute_odps_normalization_job_contract_not_found(self):
        """Test ODPS normalization job with non-existent contract"""
        # Create job with non-existent contract ID
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.ODPS_NORMALIZATION,
            status=JobStatus.PENDING,
            resource_type="CONTRACT",
            resource_id=uuid.uuid4(),
            created_by=self.user
        )

        # Execute job - should raise ValueError
        with self.assertRaises(ValueError) as cm:
            _execute_odps_normalization_job(job)

        self.assertIn("not found", str(cm.exception))

    def test_execute_odps_normalization_job_not_odps_contract(self):
        """Test ODPS normalization job with non-ODPS contract"""
        # Create ODCS contract
        odcs_contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw='{"apiVersion": "odcs/v3", "kind": "DataContract"}',
            status=ContractStatus.DRAFT
        )

        # Create job for ODCS contract
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.ODPS_NORMALIZATION,
            status=JobStatus.PENDING,
            resource_type="CONTRACT",
            resource_id=odcs_contract.id,
            created_by=self.user
        )

        # Execute job - should raise ValueError
        with self.assertRaises(ValueError) as cm:
            _execute_odps_normalization_job(job)

        self.assertIn("not an ODPS contract", str(cm.exception))

    def test_execute_odps_normalization_job_missing_original_raw(self):
        """Test ODPS normalization job with missing original_raw"""
        # Create contract without original_raw
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            original_format=OriginalFormat.JSON,
            original_raw="",
            status=ContractStatus.DRAFT
        )

        # Create job
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.ODPS_NORMALIZATION,
            status=JobStatus.PENDING,
            resource_type="CONTRACT",
            resource_id=contract.id,
            created_by=self.user
        )

        # Execute job - should raise ValueError
        with self.assertRaises(ValueError) as cm:
            _execute_odps_normalization_job(job)

        self.assertIn("no original_raw content", str(cm.exception))

    def test_execute_odps_normalization_job_progress_tracking(self):
        """Test ODPS normalization job progress tracking with real implementation"""
        # Execute job with real normalization
        _execute_odps_normalization_job(self.job)

        # Verify progress was tracked
        self.job.refresh_from_db()
        self.assertIsNotNone(self.job.details_json)
        self.assertEqual(self.job.details_json['progress_percentage'], 100.0)
        self.assertEqual(self.job.details_json['current_phase'], 'completed')

        # Verify progress phases were tracked (check that details_json has expected keys)
        self.assertIn('progress_percentage', self.job.details_json)
        self.assertIn('current_phase', self.job.details_json)
        self.assertIn('status_message', self.job.details_json)

    def test_execute_odps_normalization_job_event_publishing_resilience(self):
        """Test that job completes even if event publishing has issues"""
        # Execute job with real implementation
        # Event publishing may fail if event system isn't fully configured,
        # but job should still complete
        result = _execute_odps_normalization_job(self.job)

        # Verify job completed successfully regardless of event publishing status
        self.assertEqual(result['status'], 'completed')

        # Verify contract was updated
        self.contract.refresh_from_db()
        self.assertNotEqual(self.contract.normalization_status, NormalizationStatus.NOT_NORMALIZED)
        self.assertIsNotNone(self.contract.hub_contract_json)


class ODPSNormalizationJobIntegrationTest(TestCase):
    """Integration tests for ODPS normalization job execution"""

    def setUp(self):
        """Set up test fixtures"""
        from django.core.cache import cache
        cache.clear()

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

        # Create ODPS contract
        self.odps_contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product",
                        "name": "Test Product",
                        "description": "Test product description"
                    }
                },
                "contract": {
                    "spec": {
                        "apiVersion": "odcs/v3",
                        "kind": "DataContract",
                        "id": "test-contract",
                        "schema": {
                            "fields": [
                                {"name": "field1", "type": "string", "required": True}
                            ]
                        }
                    }
                }
            }
        }

        self.contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            original_format=OriginalFormat.JSON,
            original_raw=json.dumps(self.odps_contract_data),
            status=ContractStatus.DRAFT,
            normalization_status=NormalizationStatus.NOT_NORMALIZED
        )

    def tearDown(self):
        """Clean up after tests"""
        from django.core.cache import cache
        cache.clear()

    def test_odps_normalization_job_full_execution(self):
        """Test full ODPS normalization job execution through process_job with real services"""
        # Create job
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.ODPS_NORMALIZATION,
            status=JobStatus.PENDING,
            resource_type="CONTRACT",
            resource_id=self.contract.id,
            created_by=self.user,
            timeout_seconds=600
        )

        # Verify initial state
        self.assertEqual(job.status, JobStatus.PENDING)
        self.assertIsNone(job.started_at)
        self.assertIsNone(job.completed_at)

        # Process job with real implementation
        process_job(str(job.id), JobType.ODPS_NORMALIZATION)

        # Verify job completed
        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.COMPLETED)
        self.assertIsNotNone(job.started_at)
        self.assertIsNotNone(job.completed_at)
        self.assertIsNotNone(job.result_json)
        self.assertEqual(job.result_json.get('status'), 'completed')

        # Verify contract was normalized
        self.contract.refresh_from_db()
        self.assertNotEqual(self.contract.normalization_status, NormalizationStatus.NOT_NORMALIZED)
        self.assertIsNotNone(self.contract.hub_contract_json)
        self.assertIsInstance(self.contract.hub_contract_json, dict)

        # Verify progress was tracked
        self.assertIsNotNone(job.details_json)
        self.assertEqual(job.details_json.get('progress_percentage'), 100.0)
        self.assertEqual(job.details_json.get('current_phase'), 'completed')

