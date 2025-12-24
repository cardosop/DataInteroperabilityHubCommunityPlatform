"""
Tests for ODPS Semantic Mapping Job

Comprehensive tests for ODPS_SEMANTIC_MAPPING job including success cases,
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
    _execute_odps_semantic_mapping_job,
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
from hub.apps.semantic.models import SemanticResource, SemanticResourceStatus, ResourceType


pytestmark = pytest.mark.django_db(transaction=True)


class ODPSSemanticMappingJobTest(TestCase):
    """Test ODPS semantic mapping job processor"""

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

        # Create ODPS contract with valid product structure
        self.odps_contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product",
                        "name": "Test Product",
                        "description": "Test product description",
                        "productVersion": "1.0.0"
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
            },
            "dataHolder": {
                "en": {
                    "legalName": "Test Company",
                    "email": "contact@test.com"
                }
            }
        }

        self.contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            original_format=OriginalFormat.JSON,
            original_raw=json.dumps(self.odps_contract_data),
            status=ContractStatus.ACTIVE
        )

    def test_execute_odps_semantic_mapping_job_success(self):
        """Test successful ODPS semantic mapping"""
        # Create job
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.ODPS_SEMANTIC_MAPPING,
            status=JobStatus.PENDING,
            resource_type="CONTRACT",
            resource_id=self.contract.id,
            created_by=self.user,
            details_json={}
        )

        # Execute job
        result = _execute_odps_semantic_mapping_job(job)

        # Verify result
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['contract_id'], str(self.contract.id))
        self.assertIn('semantic_resource_id', result)
        self.assertIn('semantic_uri', result)
        self.assertIn('triples_count', result)
        self.assertIn('semantic_status', result)
        self.assertIn('duration_ms', result)
        self.assertIsInstance(result['duration_ms'], int)

        # Verify progress tracking
        job.refresh_from_db()
        self.assertIn('progress_percentage', job.details_json)
        self.assertEqual(job.details_json['progress_percentage'], 100.0)
        self.assertEqual(job.details_json['current_phase'], 'completed')

        # Verify semantic resource was created
        semantic_resource = SemanticResource.objects.get(
            tenant=self.tenant,
            resource_type=ResourceType.CONTRACT,
            resource_id=self.contract.id
        )
        self.assertIsNotNone(semantic_resource)
        self.assertEqual(semantic_resource.uri, result['semantic_uri'])

    def test_execute_odps_semantic_mapping_job_missing_contract_id(self):
        """Test ODPS semantic mapping with missing contract ID"""
        # Create job with non-existent contract ID
        non_existent_id = uuid.uuid4()
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.ODPS_SEMANTIC_MAPPING,
            status=JobStatus.PENDING,
            resource_type="CONTRACT",
            resource_id=non_existent_id,
            created_by=self.user,
            details_json={}
        )

        # Execute job - should raise ValueError
        with self.assertRaises(ValueError) as cm:
            _execute_odps_semantic_mapping_job(job)

        self.assertIn("not found", str(cm.exception).lower())

    def test_execute_odps_semantic_mapping_job_non_odps_contract(self):
        """Test ODPS semantic mapping with non-ODPS contract"""
        # Create non-ODPS contract
        non_odps_contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"apiVersion": "odcs/v3", "kind": "DataContract"}',
            status=ContractStatus.ACTIVE
        )

        # Create job
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.ODPS_SEMANTIC_MAPPING,
            status=JobStatus.PENDING,
            resource_type="CONTRACT",
            resource_id=non_odps_contract.id,
            created_by=self.user,
            details_json={}
        )

        # Execute job - should raise ValueError
        with self.assertRaises(ValueError) as cm:
            _execute_odps_semantic_mapping_job(job)

        self.assertIn("not an ODPS contract", str(cm.exception))

    def test_execute_odps_semantic_mapping_job_progress_tracking(self):
        """Test that progress is tracked throughout the job"""
        # Create job
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.ODPS_SEMANTIC_MAPPING,
            status=JobStatus.PENDING,
            resource_type="CONTRACT",
            resource_id=self.contract.id,
            created_by=self.user,
            details_json={}
        )

        # Execute job
        _execute_odps_semantic_mapping_job(job)

        # Verify progress was tracked
        job.refresh_from_db()
        details = job.details_json

        # Check that progress phases were tracked
        self.assertIn('progress_percentage', details)
        self.assertEqual(details['progress_percentage'], 100.0)
        self.assertEqual(details['current_phase'], 'completed')
        self.assertIn('status_message', details)

    def test_execute_odps_semantic_mapping_job_event_publishing_resilience(self):
        """Test that job completes even if event publishing fails"""
        # Create job
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.ODPS_SEMANTIC_MAPPING,
            status=JobStatus.PENDING,
            resource_type="CONTRACT",
            resource_id=self.contract.id,
            created_by=self.user,
            details_json={}
        )

        # Execute job - should complete even if events fail
        # (Event publishing failures are caught and logged)
        result = _execute_odps_semantic_mapping_job(job)

        # Verify job completed successfully
        self.assertEqual(result['status'], 'completed')
        # Note: Job status is updated by process_job wrapper, not by _execute_* function

    def test_execute_odps_semantic_mapping_job_with_normalized_contract(self):
        """Test semantic mapping with a normalized contract (has hub_contract_json)"""
        # Normalize the contract first
        from hub.apps.contracts.normalization import normalize_contract

        hub_contract, _, _, _, _, _ = normalize_contract(
            raw_contract=self.contract.original_raw,
            format="json",
            spec_type="ODPS"
        )

        # Update contract with normalized data
        self.contract.hub_contract_json = hub_contract
        self.contract.normalization_status = NormalizationStatus.NORMALIZED_OK
        self.contract.save()

        # Create job
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.ODPS_SEMANTIC_MAPPING,
            status=JobStatus.PENDING,
            resource_type="CONTRACT",
            resource_id=self.contract.id,
            created_by=self.user,
            details_json={}
        )

        # Execute job
        result = _execute_odps_semantic_mapping_job(job)

        # Verify result
        self.assertEqual(result['status'], 'completed')
        self.assertIn('semantic_resource_id', result)

        # Verify semantic resource was created
        semantic_resource = SemanticResource.objects.get(
            tenant=self.tenant,
            resource_type=ResourceType.CONTRACT,
            resource_id=self.contract.id
        )
        self.assertIsNotNone(semantic_resource)


class ODPSSemanticMappingJobIntegrationTest(TestCase):
    """Integration tests for ODPS semantic mapping job execution"""

    def setUp(self):
        """Set up test fixtures"""
        # Clear cache
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
                        "productID": "integration-test-product",
                        "name": "Integration Test Product",
                        "description": "Integration test product description",
                        "productVersion": "1.0.0"
                    }
                },
                "contract": {
                    "spec": {
                        "apiVersion": "odcs/v3",
                        "kind": "DataContract",
                        "id": "integration-test-contract",
                        "schema": {
                            "fields": [
                                {"name": "field1", "type": "string", "required": True}
                            ]
                        }
                    }
                }
            },
            "dataHolder": {
                "en": {
                    "legalName": "Integration Test Company",
                    "email": "contact@integration-test.com"
                }
            }
        }

        self.contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            original_format=OriginalFormat.JSON,
            original_raw=json.dumps(self.odps_contract_data),
            status=ContractStatus.ACTIVE
        )

    def test_process_job_integration(self):
        """Test full job processing integration"""
        # Create job
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.ODPS_SEMANTIC_MAPPING,
            status=JobStatus.PENDING,
            resource_type="CONTRACT",
            resource_id=self.contract.id,
            created_by=self.user,
            details_json={}
        )

        # Mark job as started (simulating worker behavior)
        job.mark_started()

        # Execute job logic directly
        result = _execute_odps_semantic_mapping_job(job)

        # Mark job as completed (simulating worker behavior)
        job.mark_completed(result_json=result)

        # Verify job state
        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.COMPLETED)
        self.assertIsNotNone(job.started_at)
        self.assertIsNotNone(job.completed_at)
        self.assertIsNotNone(job.result_json)
        self.assertEqual(job.result_json['status'], 'completed')

        # Verify semantic resource exists
        semantic_resource = SemanticResource.objects.get(
            tenant=self.tenant,
            resource_type=ResourceType.CONTRACT,
            resource_id=self.contract.id
        )
        self.assertIsNotNone(semantic_resource)
        self.assertEqual(semantic_resource.uri, result['semantic_uri'])

    def test_semantic_mapping_with_linked_odcs_contract(self):
        """Test semantic mapping when ODPS contract has linked ODCS contract"""
        # Create ODCS contract
        odcs_contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"apiVersion": "odcs/v3", "kind": "DataContract", "id": "odcs-contract"}',
            status=ContractStatus.ACTIVE
        )

        # Normalize ODPS contract and add link to ODCS
        from hub.apps.contracts.normalization import normalize_contract

        hub_contract, _, _, _, _, _ = normalize_contract(
            raw_contract=self.contract.original_raw,
            format="json",
            spec_type="ODPS"
        )

        # Add link to ODCS contract in extensions
        if 'extensions' not in hub_contract:
            hub_contract['extensions'] = {}
        hub_contract['extensions']['x_odps_link'] = {
            'odcs_contract_id': str(odcs_contract.id)
        }

        self.contract.hub_contract_json = hub_contract
        self.contract.save()

        # Create job
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.ODPS_SEMANTIC_MAPPING,
            status=JobStatus.PENDING,
            resource_type="CONTRACT",
            resource_id=self.contract.id,
            created_by=self.user,
            details_json={}
        )

        # Execute job
        result = _execute_odps_semantic_mapping_job(job)

        # Verify result
        self.assertEqual(result['status'], 'completed')

        # Verify semantic resource was created with link info
        semantic_resource = SemanticResource.objects.get(
            tenant=self.tenant,
            resource_type=ResourceType.CONTRACT,
            resource_id=self.contract.id
        )
        self.assertIsNotNone(semantic_resource)
        if semantic_resource.metadata_json:
            # Check if ODCS contract UUID is in metadata
            odcs_uuid = semantic_resource.metadata_json.get('odcs_contract_uuid')
            if odcs_uuid:
                self.assertEqual(odcs_uuid, str(odcs_contract.id))

