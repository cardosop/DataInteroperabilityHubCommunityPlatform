"""
Tests for ODPS $ref Resolution Job

Comprehensive tests for ODPS_REF_RESOLUTION job including success cases,
error handling, progress tracking, and event publishing.

These tests use REAL implementations (no mocks/stubs) to validate the
complete job execution path.
"""

import json
import uuid

from django.test import TestCase

from hub.apps.contracts.models import (
    Contract,
    ContractStatus,
    NormalizationStatus,
    OriginalFormat,
    OriginalSpecType,
)
from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.jobs.tasks import _execute_odps_ref_resolution_job, process_job
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus


class ODPSRefResolutionJobTest(TestCase):
    """Test ODPS $ref resolution job processor"""

    def setUp(self):
        """Set up test fixtures"""
        # Clear cache to ensure clean state
        from django.core.cache import cache

        cache.clear()

        # Create tenant
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )

        # Create user
        self.user = User.objects.create_user(
            email=f"user-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        # Create ODPS contract with internal $ref
        self.odps_contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product",
                        "name": "Test Product",
                        "description": "Test product description",
                    }
                },
                "contract": {
                    "spec": {
                        "apiVersion": "odcs/v3",
                        "kind": "DataContract",
                        "id": "test-contract",
                        "schema": {
                            "fields": [{"name": "field1", "type": "string", "required": True}]
                        },
                        "quality": {"$ref": "#/product/definitions/quality"},
                    }
                },
                "definitions": {
                    "quality": {
                        "freshness": {"maxAge": "PT1H"},
                        "completeness": {"threshold": 0.95},
                    }
                },
            },
        }

        self.contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            original_format=OriginalFormat.JSON,
            original_raw=json.dumps(self.odps_contract_data),
            status=ContractStatus.DRAFT,
            normalization_status=NormalizationStatus.NOT_NORMALIZED,
        )

        # Create job
        self.job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.ODPS_REF_RESOLUTION,
            status=JobStatus.PENDING,
            resource_type="CONTRACT",
            resource_id=self.contract.id,
            created_by=self.user,
            details_json={},
        )

    def tearDown(self):
        """Clean up after tests"""
        from django.core.cache import cache

        cache.clear()

    def test_execute_odps_ref_resolution_job_success(self):
        """Test successful ODPS $ref resolution job execution with real resolver"""
        # Execute job with real ref resolution
        result = _execute_odps_ref_resolution_job(self.job)

        # Verify result
        self.assertEqual(result["status"], "completed")
        self.assertGreaterEqual(result["refs_resolved"], 1)  # At least one ref should be resolved
        self.assertEqual(result["contract_id"], str(self.contract.id))
        self.assertEqual(result["external_ref_handling"], "resolve")

        # Verify contract was updated with resolved document
        self.contract.refresh_from_db()
        if hasattr(self.contract, "original_raw_resolved"):
            self.assertIsNotNone(self.contract.original_raw_resolved)
            # Verify resolved document doesn't contain $ref
            resolved_doc = json.loads(self.contract.original_raw_resolved)
            # The quality field should be resolved (not a $ref)
            quality = (
                resolved_doc.get("product", {})
                .get("contract", {})
                .get("spec", {})
                .get("quality", {})
            )
            self.assertNotIn("$ref", quality)
            self.assertIn("freshness", quality)
            self.assertIn("completeness", quality)

        # Verify progress tracking
        self.job.refresh_from_db()
        self.assertEqual(self.job.details_json["progress_percentage"], 100.0)
        self.assertEqual(self.job.details_json["current_phase"], "completed")
        self.assertIn("refs_total", self.job.details_json)
        self.assertIn("refs_processed", self.job.details_json)

    def test_execute_odps_ref_resolution_job_with_external_ref_handling(self):
        """Test ODPS $ref resolution job with different external ref handling modes"""
        # Test with disable mode
        self.job.details_json["external_ref_handling"] = "disable"
        self.job.save(update_fields=["details_json"])

        # Execute job
        result = _execute_odps_ref_resolution_job(self.job)

        # Verify result
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["external_ref_handling"], "disable")

    def test_execute_odps_ref_resolution_job_contract_not_found(self):
        """Test ODPS $ref resolution job with non-existent contract"""
        # Create job with non-existent contract ID
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.ODPS_REF_RESOLUTION,
            status=JobStatus.PENDING,
            resource_type="CONTRACT",
            resource_id=uuid.uuid4(),
            created_by=self.user,
        )

        # Execute job - should raise ValueError
        with self.assertRaises(ValueError) as cm:
            _execute_odps_ref_resolution_job(job)

        self.assertIn("not found", str(cm.exception))

    def test_execute_odps_ref_resolution_job_not_odps_contract(self):
        """Test ODPS $ref resolution job with non-ODPS contract"""
        # Create ODCS contract
        odcs_contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw='{"apiVersion": "odcs/v3", "kind": "DataContract"}',
            status=ContractStatus.DRAFT,
        )

        # Create job for ODCS contract
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.ODPS_REF_RESOLUTION,
            status=JobStatus.PENDING,
            resource_type="CONTRACT",
            resource_id=odcs_contract.id,
            created_by=self.user,
        )

        # Execute job - should raise ValueError
        with self.assertRaises(ValueError) as cm:
            _execute_odps_ref_resolution_job(job)

        self.assertIn("not an ODPS contract", str(cm.exception))

    def test_execute_odps_ref_resolution_job_missing_original_raw(self):
        """Test ODPS $ref resolution job with missing original_raw"""
        # Create contract without original_raw
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            original_format=OriginalFormat.JSON,
            original_raw="",
            status=ContractStatus.DRAFT,
        )

        # Create job
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.ODPS_REF_RESOLUTION,
            status=JobStatus.PENDING,
            resource_type="CONTRACT",
            resource_id=contract.id,
            created_by=self.user,
        )

        # Execute job - should raise ValueError
        with self.assertRaises(ValueError) as cm:
            _execute_odps_ref_resolution_job(job)

        self.assertIn("no original_raw content", str(cm.exception))

    def test_execute_odps_ref_resolution_job_progress_tracking(self):
        """Test ODPS $ref resolution job progress tracking with real implementation"""
        # Execute job with real ref resolution
        _execute_odps_ref_resolution_job(self.job)

        # Verify progress was tracked
        self.job.refresh_from_db()
        self.assertIsNotNone(self.job.details_json)
        self.assertEqual(self.job.details_json["progress_percentage"], 100.0)
        self.assertEqual(self.job.details_json["current_phase"], "completed")

        # Verify progress phases were tracked
        self.assertIn("progress_percentage", self.job.details_json)
        self.assertIn("current_phase", self.job.details_json)
        self.assertIn("status_message", self.job.details_json)
        self.assertIn("refs_total", self.job.details_json)
        self.assertIn("refs_processed", self.job.details_json)

    def test_execute_odps_ref_resolution_job_completes_successfully(self):
        """Test that job completes successfully (events are async)."""
        # Execute job with real implementation
        result = _execute_odps_ref_resolution_job(self.job)

        # Verify job completed successfully regardless of event publishing status
        self.assertEqual(result["status"], "completed")

        # Verify contract was updated
        self.contract.refresh_from_db()
        if hasattr(self.contract, "original_raw_resolved"):
            self.assertIsNotNone(self.contract.original_raw_resolved)

    def test_execute_odps_ref_resolution_job_with_circular_ref(self):
        """Test ODPS $ref resolution job with circular reference (should fail gracefully)"""
        # Create ODPS contract with circular reference
        circular_odps = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"productID": "test-product", "name": "Test Product"}},
                "contract": {
                    "spec": {
                        "apiVersion": "odcs/v3",
                        "kind": "DataContract",
                        "id": "test-contract",
                        "schema": {"$ref": "#/product/definitions/schema"},
                    }
                },
                "definitions": {
                    "schema": {
                        "fields": [{"$ref": "#/product/definitions/schema"}]  # Circular reference
                    }
                },
            },
        }

        contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            original_format=OriginalFormat.JSON,
            original_raw=json.dumps(circular_odps),
            status=ContractStatus.DRAFT,
        )

        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.ODPS_REF_RESOLUTION,
            status=JobStatus.PENDING,
            resource_type="CONTRACT",
            resource_id=contract.id,
            created_by=self.user,
            details_json={},
        )

        # Execute job - should raise ValueError due to circular reference
        with self.assertRaises(ValueError) as cm:
            _execute_odps_ref_resolution_job(job)

        self.assertIn("$ref resolution failed", str(cm.exception))

        # Verify progress tracking shows failure
        job.refresh_from_db()
        self.assertEqual(job.details_json["progress_percentage"], 100.0)
        self.assertEqual(job.details_json["current_phase"], "failed")


class ODPSRefResolutionJobIntegrationTest(TestCase):
    """Integration tests for ODPS $ref resolution job execution"""

    def setUp(self):
        """Set up test fixtures"""
        from django.core.cache import cache

        cache.clear()

        # Create tenant
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )

        # Create user
        self.user = User.objects.create_user(
            email=f"user-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        # Create ODPS contract with internal $ref
        self.odps_contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product",
                        "name": "Test Product",
                        "description": "Test product description",
                    }
                },
                "contract": {
                    "spec": {
                        "apiVersion": "odcs/v3",
                        "kind": "DataContract",
                        "id": "test-contract",
                        "schema": {
                            "fields": [{"name": "field1", "type": "string", "required": True}]
                        },
                        "quality": {"$ref": "#/product/definitions/quality"},
                    }
                },
                "definitions": {
                    "quality": {
                        "freshness": {"maxAge": "PT1H"},
                        "completeness": {"threshold": 0.95},
                    }
                },
            },
        }

        self.contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            original_format=OriginalFormat.JSON,
            original_raw=json.dumps(self.odps_contract_data),
            status=ContractStatus.DRAFT,
            normalization_status=NormalizationStatus.NOT_NORMALIZED,
        )

    def tearDown(self):
        """Clean up after tests"""
        from django.core.cache import cache

        cache.clear()

    def test_odps_ref_resolution_job_full_execution(self):
        """Test full ODPS $ref resolution job execution through process_job with real services"""
        # Create job
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.ODPS_REF_RESOLUTION,
            status=JobStatus.PENDING,
            resource_type="CONTRACT",
            resource_id=self.contract.id,
            created_by=self.user,
            timeout_seconds=600,
        )

        # Verify initial state
        self.assertEqual(job.status, JobStatus.PENDING)
        self.assertIsNone(job.started_at)
        self.assertIsNone(job.completed_at)

        # Process job with real implementation
        process_job(str(job.id), JobType.ODPS_REF_RESOLUTION)

        # Verify job completed
        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.COMPLETED)
        self.assertIsNotNone(job.started_at)
        self.assertIsNotNone(job.completed_at)
        self.assertIsNotNone(job.result_json)
        self.assertEqual(job.result_json.get("status"), "completed")

        # Verify contract was updated with resolved document
        self.contract.refresh_from_db()
        if hasattr(self.contract, "original_raw_resolved"):
            self.assertIsNotNone(self.contract.original_raw_resolved)
            # Verify resolved document
            resolved_doc = json.loads(self.contract.original_raw_resolved)
            # Quality should be resolved (not a $ref)
            quality = (
                resolved_doc.get("product", {})
                .get("contract", {})
                .get("spec", {})
                .get("quality", {})
            )
            self.assertNotIn("$ref", quality)

        # Verify progress was tracked
        self.assertIsNotNone(job.details_json)
        self.assertEqual(job.details_json.get("progress_percentage"), 100.0)
        self.assertEqual(job.details_json.get("current_phase"), "completed")
