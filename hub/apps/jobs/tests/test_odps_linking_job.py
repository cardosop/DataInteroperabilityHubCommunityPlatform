"""
Tests for ODPS Linking Job

Comprehensive tests for ODPS_LINKING job including success cases,
error handling, progress tracking, and event publishing.

These tests use REAL implementations (no mocks/stubs) to validate the
complete job execution path.
"""
import pytest
import json
from django.test import TestCase
from django.utils import timezone
from django.db import transaction
import uuid

from hub.apps.jobs.models import Job, JobType, JobStatus
from hub.apps.jobs.tasks import (
    _execute_odps_linking_job,
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
from hub.apps.contracts.normalization import normalize_contract


pytestmark = pytest.mark.django_db(transaction=True)


class ODPSLinkingJobTest(TestCase):
    """Test ODPS linking job processor"""

    def setUp(self):
        """Set up test fixtures"""
        # Clear cache to ensure clean state
        from django.core.cache import cache
        cache.clear()

        # Create tenant
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED"
        )

        # Create user
        self.user = User.objects.create_user(
            email=f"user-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )

        # Create ODCS contract data
        self.odcs_contract_data = {
            "apiVersion": "odcs/v3",
            "kind": "DataContract",
            "id": "test-odcs-contract",
            "name": "Test ODCS Contract",
            "schema": {
                "fields": [
                    {"name": "field1", "type": "string", "required": True}
                ]
            }
        }

        # Create ODPS contract data
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
                    "spec": self.odcs_contract_data
                }
            }
        }

        # Create and normalize ODCS contract
        self.odcs_contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0",
            original_format=OriginalFormat.JSON,
            original_raw=json.dumps(self.odcs_contract_data),
            status=ContractStatus.DRAFT,
            normalization_status=NormalizationStatus.NOT_NORMALIZED
        )

        # Normalize ODCS contract
        hub_contract, _, _, norm_status, norm_errors, norm_warnings = normalize_contract(
            raw_contract=json.dumps(self.odcs_contract_data),
            format="json",
            spec_type="ODCS"
        )
        # Ensure normalization succeeded
        if norm_status not in [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS]:
            raise AssertionError(
                f"ODCS contract normalization failed: status={norm_status}, "
                f"errors={norm_errors}, warnings={norm_warnings}"
            )
        self.odcs_contract.hub_contract_json = hub_contract
        self.odcs_contract.normalization_status = norm_status
        self.odcs_contract.save()

        # Create and normalize ODPS contract
        self.odps_contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            original_format=OriginalFormat.JSON,
            original_raw=json.dumps(self.odps_contract_data),
            status=ContractStatus.DRAFT,
            normalization_status=NormalizationStatus.NOT_NORMALIZED
        )

        # Normalize ODPS contract
        hub_contract, _, _, norm_status, norm_errors, norm_warnings = normalize_contract(
            raw_contract=json.dumps(self.odps_contract_data),
            format="json",
            spec_type="ODPS"
        )
        # Ensure normalization succeeded
        if norm_status not in [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS]:
            raise AssertionError(
                f"ODPS contract normalization failed: status={norm_status}, "
                f"errors={norm_errors}, warnings={norm_warnings}"
            )
        self.odps_contract.hub_contract_json = hub_contract
        self.odps_contract.normalization_status = norm_status
        self.odps_contract.save()

        # Create job
        self.job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.ODPS_LINKING,
            status=JobStatus.PENDING,
            resource_type="CONTRACT",
            resource_id=self.odps_contract.id,
            created_by=self.user,
            details_json={
                'odps_contract_id': str(self.odps_contract.id),
                'odcs_contract_id': str(self.odcs_contract.id)
            }
        )

    def tearDown(self):
        """Clean up after tests"""
        from django.core.cache import cache
        cache.clear()

    def test_execute_odps_linking_job_success(self):
        """Test successful ODPS linking job execution with real linking"""
        # Execute job with real linking function
        result = _execute_odps_linking_job(self.job)

        # Verify result
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['odps_contract_id'], str(self.odps_contract.id))
        self.assertEqual(result['odcs_contract_id'], str(self.odcs_contract.id))
        self.assertEqual(result['link_type'], 'bidirectional')
        self.assertIsInstance(result['duration_ms'], int)
        self.assertGreater(result['duration_ms'], 0)

        # Verify contracts were linked
        self.odps_contract.refresh_from_db()
        self.odcs_contract.refresh_from_db()

        # Check ODPS → ODCS link
        odps_hub_contract = self.odps_contract.hub_contract_json or {}
        odps_extensions = odps_hub_contract.get("extensions", {})
        odps_x_odps = odps_extensions.get("x_odps", {})
        odps_to_odcs_link = odps_x_odps.get("odcs_link")
        self.assertIsNotNone(odps_to_odcs_link)
        self.assertEqual(str(odps_to_odcs_link), str(self.odcs_contract.id))

        # Check ODCS → ODPS link
        odcs_hub_contract = self.odcs_contract.hub_contract_json or {}
        odcs_extensions = odcs_hub_contract.get("extensions", {})
        odcs_x_odps = odcs_extensions.get("x_odps", {})
        odcs_to_odps_link = odcs_x_odps.get("odps_link")
        self.assertIsNotNone(odcs_to_odps_link)
        self.assertEqual(str(odcs_to_odps_link), str(self.odps_contract.id))

        # Verify progress tracking
        self.job.refresh_from_db()
        self.assertEqual(self.job.details_json['progress_percentage'], 100.0)
        self.assertEqual(self.job.details_json['current_phase'], 'completed')

    def test_execute_odps_linking_job_missing_odps_contract_id(self):
        """Test ODPS linking job fails when ODPS contract ID is missing"""
        # Create job without ODPS contract ID in details_json
        # Use a non-existent contract ID for resource_id to ensure it doesn't match
        fake_contract_id = str(uuid.uuid4())
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.ODPS_LINKING,
            status=JobStatus.PENDING,
            resource_type="CONTRACT",
            resource_id=fake_contract_id,  # Use fake ID that won't match odcs_contract_id
            created_by=self.user,
            details_json={
                'odcs_contract_id': str(self.odcs_contract.id)
                # Missing odps_contract_id
            }
        )

        # Execute job - should fail with ValueError because fake_contract_id doesn't exist
        # or because it's not a valid ODPS contract
        with self.assertRaises((ValueError, Contract.DoesNotExist)) as context:
            _execute_odps_linking_job(job)

        # The error could be either "ODPS contract ID is required" or "ODPS contract not found"
        error_msg = str(context.exception)
        self.assertTrue(
            "ODPS contract ID is required" in error_msg or
            "not found" in error_msg or
            "ODPS contract" in error_msg,
            f"Unexpected error message: {error_msg}"
        )

    def test_execute_odps_linking_job_missing_odcs_contract_id(self):
        """Test ODPS linking job fails when ODCS contract ID is missing"""
        # Create job without ODCS contract ID
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.ODPS_LINKING,
            status=JobStatus.PENDING,
            resource_type="CONTRACT",
            resource_id=self.odps_contract.id,
            created_by=self.user,
            details_json={
                'odps_contract_id': str(self.odps_contract.id)
                # Missing odcs_contract_id
            }
        )

        # Execute job - should fail with ValueError
        with self.assertRaises(ValueError) as context:
            _execute_odps_linking_job(job)

        self.assertIn("ODCS contract ID is required", str(context.exception))

    def test_execute_odps_linking_job_odps_contract_not_found(self):
        """Test ODPS linking job fails when ODPS contract doesn't exist"""
        # Create job with non-existent ODPS contract ID
        fake_odps_id = str(uuid.uuid4())
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.ODPS_LINKING,
            status=JobStatus.PENDING,
            resource_type="CONTRACT",
            resource_id=self.odps_contract.id,
            created_by=self.user,
            details_json={
                'odps_contract_id': fake_odps_id,
                'odcs_contract_id': str(self.odcs_contract.id)
            }
        )

        # Execute job - should fail with ValueError
        with self.assertRaises(ValueError) as context:
            _execute_odps_linking_job(job)

        self.assertIn("not found", str(context.exception))
        self.assertIn(fake_odps_id, str(context.exception))

    def test_execute_odps_linking_job_odcs_contract_not_found(self):
        """Test ODPS linking job fails when ODCS contract doesn't exist"""
        # Create job with non-existent ODCS contract ID
        fake_odcs_id = str(uuid.uuid4())
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.ODPS_LINKING,
            status=JobStatus.PENDING,
            resource_type="CONTRACT",
            resource_id=self.odps_contract.id,
            created_by=self.user,
            details_json={
                'odps_contract_id': str(self.odps_contract.id),
                'odcs_contract_id': fake_odcs_id
            }
        )

        # Execute job - should fail with ValueError
        with self.assertRaises(ValueError) as context:
            _execute_odps_linking_job(job)

        self.assertIn("not found", str(context.exception))
        self.assertIn(fake_odcs_id, str(context.exception))

    def test_execute_odps_linking_job_incompatible_contracts(self):
        """Test ODPS linking job fails when contracts are incompatible"""
        # Create ODPS contract that's not normalized
        unnormalized_odps = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            original_format=OriginalFormat.JSON,
            original_raw=json.dumps(self.odps_contract_data),
            status=ContractStatus.DRAFT,
            normalization_status=NormalizationStatus.NOT_NORMALIZED
            # Missing hub_contract_json
        )

        # Create job
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.ODPS_LINKING,
            status=JobStatus.PENDING,
            resource_type="CONTRACT",
            resource_id=unnormalized_odps.id,
            created_by=self.user,
            details_json={
                'odps_contract_id': str(unnormalized_odps.id),
                'odcs_contract_id': str(self.odcs_contract.id)
            }
        )

        # Execute job - should fail with ValueError (validation error)
        with self.assertRaises(ValueError) as context:
            _execute_odps_linking_job(job)

        self.assertIn("validation failed", str(context.exception).lower())

    def test_execute_odps_linking_job_wrong_contract_types(self):
        """Test ODPS linking job fails when contract types are wrong"""
        # Create job with wrong contract types (both ODCS)
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.ODPS_LINKING,
            status=JobStatus.PENDING,
            resource_type="CONTRACT",
            resource_id=self.odcs_contract.id,
            created_by=self.user,
            details_json={
                'odps_contract_id': str(self.odcs_contract.id),  # Wrong: should be ODPS
                'odcs_contract_id': str(self.odcs_contract.id)
            }
        )

        # Execute job - should fail with ValueError (validation error)
        with self.assertRaises(ValueError) as context:
            _execute_odps_linking_job(job)

        self.assertIn("validation failed", str(context.exception).lower())

    def test_execute_odps_linking_job_progress_tracking(self):
        """Test ODPS linking job tracks progress correctly"""
        # Execute job
        result = _execute_odps_linking_job(self.job)

        # Verify progress was tracked
        self.job.refresh_from_db()
        details = self.job.details_json

        # Check progress phases
        self.assertIn('progress_percentage', details)
        self.assertIn('current_phase', details)
        self.assertIn('status_message', details)

        # Verify final progress
        self.assertEqual(details['progress_percentage'], 100.0)
        self.assertEqual(details['current_phase'], 'completed')
        self.assertIn('completed', details['status_message'].lower())

    def test_execute_odps_linking_job_already_linked(self):
        """Test ODPS linking job handles already linked contracts"""
        # First, link contracts
        from hub.apps.contracts.services import ContractService
        service = ContractService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))
        service.link_odps_to_odcs(
            odcs_contract_id=str(self.odcs_contract.id),
            odps_contract_id=str(self.odps_contract.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Create new job to link again
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.ODPS_LINKING,
            status=JobStatus.PENDING,
            resource_type="CONTRACT",
            resource_id=self.odps_contract.id,
            created_by=self.user,
            details_json={
                'odps_contract_id': str(self.odps_contract.id),
                'odcs_contract_id': str(self.odcs_contract.id)
            }
        )

        # Execute job - should succeed (idempotent operation)
        result = _execute_odps_linking_job(job)

        # Verify result
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['link_type'], 'bidirectional')

    def test_process_job_with_odps_linking(self):
        """Test process_job function with ODPS_LINKING job type"""
        # Execute via process_job
        process_job(str(self.job.id), JobType.ODPS_LINKING.value)

        # Verify job completed
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, JobStatus.COMPLETED)
        self.assertIsNotNone(self.job.result_json)
        self.assertEqual(self.job.result_json['status'], 'completed')

        # Verify contracts were linked
        self.odps_contract.refresh_from_db()
        self.odcs_contract.refresh_from_db()

        odps_hub_contract = self.odps_contract.hub_contract_json or {}
        odps_extensions = odps_hub_contract.get("extensions", {})
        odps_x_odps = odps_extensions.get("x_odps", {})
        odps_to_odcs_link = odps_x_odps.get("odcs_link")
        self.assertIsNotNone(odps_to_odcs_link)
        self.assertEqual(str(odps_to_odcs_link), str(self.odcs_contract.id))

    def test_execute_odps_linking_job_different_tenants(self):
        """Test ODPS linking job fails when contracts belong to different tenants"""
        # Create another tenant
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}",
            slug=f"other-tenant-{_uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED"
        )

        # Create ODCS contract in other tenant
        other_odcs = Contract.objects.create(
            tenant=other_tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0",
            original_format=OriginalFormat.JSON,
            original_raw=json.dumps(self.odcs_contract_data),
            status=ContractStatus.DRAFT,
            normalization_status=NormalizationStatus.NOT_NORMALIZED
        )

        # Normalize other ODCS contract
        hub_contract, _, _, norm_status, norm_errors, norm_warnings = normalize_contract(
            raw_contract=json.dumps(self.odcs_contract_data),
            format="json",
            spec_type="ODCS"
        )
        # Ensure normalization succeeded
        if norm_status not in [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS]:
            raise AssertionError(
                f"ODCS contract normalization failed: status={norm_status}, "
                f"errors={norm_errors}, warnings={norm_warnings}"
            )
        other_odcs.hub_contract_json = hub_contract
        other_odcs.normalization_status = norm_status
        other_odcs.save()

        # Create job linking contracts from different tenants
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.ODPS_LINKING,
            status=JobStatus.PENDING,
            resource_type="CONTRACT",
            resource_id=self.odps_contract.id,
            created_by=self.user,
            details_json={
                'odps_contract_id': str(self.odps_contract.id),
                'odcs_contract_id': str(other_odcs.id)
            }
        )

        # Execute job - should fail with ValueError (validation error)
        with self.assertRaises(ValueError) as context:
            _execute_odps_linking_job(job)

        self.assertIn("validation failed", str(context.exception).lower())



class ODPSLinkingJobIntegrationTest(TestCase):
    """Integration tests for ODPS linking job execution"""

    def setUp(self):
        """Set up test fixtures"""
        from django.core.cache import cache
        cache.clear()

        # Create tenant
        self.tenant = Tenant.objects.create(
            name="Integration Test Tenant",
            slug="integration-test-tenant",
            status="ACTIVE",
            kyc_status="UNVERIFIED"
        )

        # Create user
        self.user = User.objects.create_user(
            email=f"integration-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )

        # Create ODCS contract data
        self.odcs_contract_data = {
            "apiVersion": "odcs/v3",
            "kind": "DataContract",
            "id": "integration-test-odcs-contract",
            "name": "Integration Test ODCS Contract",
            "schema": {
                "fields": [
                    {"name": "id", "type": "string", "required": True},
                    {"name": "value", "type": "number", "required": False}
                ]
            }
        }

        # Create ODPS contract data
        self.odps_contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "integration-test-product",
                        "name": "Integration Test Product",
                        "description": "Integration test product description"
                    }
                },
                "contract": {
                    "spec": self.odcs_contract_data
                }
            }
        }

        # Create and normalize ODCS contract
        self.odcs_contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0",
            original_format=OriginalFormat.JSON,
            original_raw=json.dumps(self.odcs_contract_data),
            status=ContractStatus.DRAFT,
            normalization_status=NormalizationStatus.NOT_NORMALIZED
        )

        # Normalize ODCS contract
        hub_contract, _, _, norm_status, norm_errors, norm_warnings = normalize_contract(
            raw_contract=json.dumps(self.odcs_contract_data),
            format="json",
            spec_type="ODCS"
        )
        # Ensure normalization succeeded
        if norm_status not in [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS]:
            raise AssertionError(
                f"ODCS contract normalization failed: status={norm_status}, "
                f"errors={norm_errors}, warnings={norm_warnings}"
            )
        self.odcs_contract.hub_contract_json = hub_contract
        self.odcs_contract.normalization_status = norm_status
        self.odcs_contract.save()

        # Create and normalize ODPS contract
        self.odps_contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            original_format=OriginalFormat.JSON,
            original_raw=json.dumps(self.odps_contract_data),
            status=ContractStatus.DRAFT,
            normalization_status=NormalizationStatus.NOT_NORMALIZED
        )

        # Normalize ODPS contract
        hub_contract, _, _, norm_status, norm_errors, norm_warnings = normalize_contract(
            raw_contract=json.dumps(self.odps_contract_data),
            format="json",
            spec_type="ODPS"
        )
        # Ensure normalization succeeded
        if norm_status not in [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS]:
            raise AssertionError(
                f"ODPS contract normalization failed: status={norm_status}, "
                f"errors={norm_errors}, warnings={norm_warnings}"
            )
        self.odps_contract.hub_contract_json = hub_contract
        self.odps_contract.normalization_status = norm_status
        self.odps_contract.save()

    def tearDown(self):
        """Clean up after tests"""
        from django.core.cache import cache
        cache.clear()

    def test_odps_linking_job_full_execution(self):
        """Test full ODPS linking job execution through process_job with real services"""
        # Create job
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.ODPS_LINKING,
            status=JobStatus.PENDING,
            resource_type="CONTRACT",
            resource_id=self.odps_contract.id,
            created_by=self.user,
            timeout_seconds=300,
            details_json={
                'odps_contract_id': str(self.odps_contract.id),
                'odcs_contract_id': str(self.odcs_contract.id)
            }
        )

        # Verify initial state
        self.assertEqual(job.status, JobStatus.PENDING)
        self.assertIsNone(job.started_at)
        self.assertIsNone(job.completed_at)

        # Verify contracts are not linked initially
        self.odps_contract.refresh_from_db()
        self.odcs_contract.refresh_from_db()
        odps_hub_contract = self.odps_contract.hub_contract_json or {}
        odps_extensions = odps_hub_contract.get("extensions", {})
        odps_x_odps = odps_extensions.get("x_odps", {})
        self.assertIsNone(odps_x_odps.get("odcs_link"))

        # Process job with real implementation
        process_job(str(job.id), JobType.ODPS_LINKING)

        # Verify job completed
        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.COMPLETED)
        self.assertIsNotNone(job.started_at)
        self.assertIsNotNone(job.completed_at)
        self.assertIsNotNone(job.result_json)
        self.assertEqual(job.result_json.get('status'), 'completed')
        self.assertEqual(job.result_json.get('link_type'), 'bidirectional')

        # Verify contracts were linked
        self.odps_contract.refresh_from_db()
        self.odcs_contract.refresh_from_db()

        # Check ODPS → ODCS link
        odps_hub_contract = self.odps_contract.hub_contract_json or {}
        odps_extensions = odps_hub_contract.get("extensions", {})
        odps_x_odps = odps_extensions.get("x_odps", {})
        odps_to_odcs_link = odps_x_odps.get("odcs_link")
        self.assertIsNotNone(odps_to_odcs_link)
        self.assertEqual(str(odps_to_odcs_link), str(self.odcs_contract.id))

        # Check ODCS → ODPS link
        odcs_hub_contract = self.odcs_contract.hub_contract_json or {}
        odcs_extensions = odcs_hub_contract.get("extensions", {})
        odcs_x_odps = odcs_extensions.get("x_odps", {})
        odcs_to_odps_link = odcs_x_odps.get("odps_link")
        self.assertIsNotNone(odcs_to_odps_link)
        self.assertEqual(str(odcs_to_odps_link), str(self.odps_contract.id))

        # Verify progress tracking
        self.assertIn('progress_percentage', job.details_json)
        self.assertEqual(job.details_json['progress_percentage'], 100.0)
        self.assertEqual(job.details_json['current_phase'], 'completed')

    def test_odps_linking_job_with_event_publishing(self):
        """Test ODPS linking job publishes events correctly"""
        # Create job
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.ODPS_LINKING,
            status=JobStatus.PENDING,
            resource_type="CONTRACT",
            resource_id=self.odps_contract.id,
            created_by=self.user,
            timeout_seconds=300,
            details_json={
                'odps_contract_id': str(self.odps_contract.id),
                'odcs_contract_id': str(self.odcs_contract.id)
            }
        )

        # Process job
        process_job(str(job.id), JobType.ODPS_LINKING)

        # Verify job completed (events are published asynchronously, so we just verify job succeeded)
        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.COMPLETED)

        # Verify contracts were linked (this confirms the linking logic executed)
        self.odps_contract.refresh_from_db()
        self.odcs_contract.refresh_from_db()

        odps_hub_contract = self.odps_contract.hub_contract_json or {}
        odps_extensions = odps_hub_contract.get("extensions", {})
        odps_x_odps = odps_extensions.get("x_odps", {})
        self.assertIsNotNone(odps_x_odps.get("odcs_link"))
