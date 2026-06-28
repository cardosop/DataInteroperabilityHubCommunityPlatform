"""
Unit tests for Job Processors.

Tests all job processors (DQ_RUN, COMPLIANCE_RUN, CONTRACT_VALIDATION, SEMANTIC_MAPPING, CONTRACT_MIGRATION).
Uses real service clients (no mocks) - skips tests if services are unavailable.
"""

import uuid

import pytest
from django.core.cache import cache
from django.test import TestCase, override_settings

from hub.apps.contracts.models import Contract, ContractStatus, OriginalSpecType
from hub.apps.dq.models import DQEngine, DQRun, DQRunStatus
from hub.apps.files.models import File, FileStatus
from hub.apps.jobs.models import JobStatus, JobType
from hub.apps.jobs.tasks import (
    _execute_compliance_run_job,
    _execute_contract_migration_job,
    _execute_contract_validation_job,
    _execute_dq_run_job,
    _execute_job_logic,
    _execute_semantic_mapping_job,
)
from hub.apps.users.models import User, UserStatus
from tests.factories import JobFactory, TenantFactory

pytestmark = pytest.mark.django_db(transaction=True)

# Refused port for "DQ down" without touching the real dq-service container.
_UNREACHABLE_DQ_URL = "http://127.0.0.1:19999"


class JobProcessorsTest(TestCase):
    """Test job processors for all job types"""

    def setUp(self):
        """Set up test fixtures"""
        cache.clear()

        self.tenant = TenantFactory.create_tenant()
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        self.file = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1000,
            status=FileStatus.ACTIVE,
            storage_path="test/test.csv",
            created_by=self.user,
        )

    def tearDown(self):
        """Clean up after tests"""
        cache.clear()

    # DQ_RUN Processor Tests
    def test_execute_dq_run_job_missing_dq_run_id(self):
        """Test DQ_RUN job processor with missing dq_run_id"""
        # Since the Job model requires resource_id (not nullable), we test "missing"
        # by ensuring details_json doesn't have dq_run_id, and the processor falls back
        # to resource_id, which doesn't exist, resulting in "not found" error
        job = JobFactory.create_job(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DQ_RUN",
            resource_id=uuid.uuid4(),  # Dummy ID that doesn't exist (required by model)
            created_by=self.user,
            details_json={},  # No dq_run_id in details_json
        )

        # Processor will use resource_id since details_json is empty
        # Since resource_id points to a non-existent DQ run, it should raise "not found"
        with self.assertRaises(ValueError) as cm:
            _execute_dq_run_job(job)

        # Since details_json is empty, processor uses resource_id, which doesn't exist
        self.assertIn("not found", str(cm.exception).lower())

    def test_execute_dq_run_job_dq_run_not_found(self):
        """Test DQ_RUN job processor with non-existent dq_run_id"""
        non_existent_id = uuid.uuid4()
        job = JobFactory.create_job(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DQ_RUN",
            resource_id=non_existent_id,
            created_by=self.user,
            details_json={"dq_run_id": str(non_existent_id)},
        )

        with self.assertRaises(ValueError) as cm:
            _execute_dq_run_job(job)

        self.assertIn("not found", str(cm.exception).lower())

    def test_execute_dq_run_job_raises_connection_error_when_dq_service_unreachable(self):
        """DQ_RUN raises ConnectionError when DQ microservice fails health check (real client, dead URL)."""
        job = JobFactory.create_job(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DQ_RUN",
            resource_id=uuid.uuid4(),
            created_by=self.user,
            details_json={},
        )
        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            file=self.file,
            job=job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.PENDING,
        )
        job.resource_id = dq_run.id
        job.details_json = {"dq_run_id": str(dq_run.id)}
        job.save(update_fields=["resource_id", "details_json"])
        with override_settings(DQ_SERVICE_URL=_UNREACHABLE_DQ_URL):
            with self.assertRaises(ConnectionError) as cm:
                _execute_dq_run_job(job)
        self.assertIn("unavailable", str(cm.exception).lower())

    # COMPLIANCE_RUN Processor Tests
    def test_execute_compliance_run_job_missing_compliance_run_id(self):
        """Test COMPLIANCE_RUN job processor with missing compliance_run_id"""
        # Since the Job model requires resource_id (not nullable), we cannot truly test
        # "missing" in the traditional sense. However, we can test that when details_json
        # doesn't have compliance_run_id, the processor correctly falls back to resource_id.
        # Since resource_id points to a non-existent compliance run, it should raise "not found".
        # This validates the fallback logic and missing ID handling.
        job = JobFactory.create_job(
            tenant=self.tenant,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.PENDING,
            resource_type="COMPLIANCE_RUN",
            resource_id=uuid.uuid4(),  # Dummy ID that doesn't exist (required by model)
            created_by=self.user,
            details_json={},  # No compliance_run_id in details_json
        )

        # The processor will use resource_id since details_json is empty
        # Since resource_id points to a non-existent compliance run, it should raise "not found"
        with self.assertRaises(ValueError) as cm:
            _execute_compliance_run_job(job)

        # Since details_json is empty, processor uses resource_id, which doesn't exist
        # This validates the missing ID handling (fallback to resource_id)
        self.assertIn("not found", str(cm.exception).lower())

    def test_execute_compliance_run_job_compliance_run_not_found(self):
        """Test COMPLIANCE_RUN job processor with non-existent compliance_run_id"""
        non_existent_id = uuid.uuid4()
        job = JobFactory.create_job(
            tenant=self.tenant,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.PENDING,
            resource_type="COMPLIANCE_RUN",
            resource_id=non_existent_id,
            created_by=self.user,
            details_json={"compliance_run_id": str(non_existent_id)},
        )

        with self.assertRaises(ValueError) as cm:
            _execute_compliance_run_job(job)

        self.assertIn("not found", str(cm.exception).lower())

    # CONTRACT_VALIDATION Processor Tests
    def test_execute_contract_validation_job_missing_contract_id(self):
        """Test CONTRACT_VALIDATION job processor with missing contract_id"""
        # Since the Job model requires resource_id (not nullable), we test "missing"
        # by ensuring resource_id points to a non-existent contract
        # The processor should raise "not found" error
        non_existent_id = uuid.uuid4()
        job = JobFactory.create_job(
            tenant=self.tenant,
            type=JobType.CONTRACT_VALIDATION,
            status=JobStatus.PENDING,
            resource_type="CONTRACT",
            resource_id=non_existent_id,  # Non-existent contract ID (required by model)
            created_by=self.user,
        )

        # Processor will use resource_id, which doesn't exist, so it should raise "not found"
        with self.assertRaises(ValueError) as cm:
            _execute_contract_validation_job(job)

        # Since resource_id points to non-existent contract, expect "not found" error
        self.assertIn("not found", str(cm.exception).lower())

    def test_execute_contract_validation_job_contract_not_found(self):
        """Test CONTRACT_VALIDATION job processor with non-existent contract_id"""
        non_existent_id = uuid.uuid4()
        job = JobFactory.create_job(
            tenant=self.tenant,
            type=JobType.CONTRACT_VALIDATION,
            status=JobStatus.PENDING,
            resource_type="CONTRACT",
            resource_id=non_existent_id,
            created_by=self.user,
        )

        with self.assertRaises(ValueError) as cm:
            _execute_contract_validation_job(job)

        self.assertIn("not found", str(cm.exception).lower())

    def test_execute_contract_validation_job_contract_no_original_raw(self):
        """Test CONTRACT_VALIDATION job processor with contract that has no original_raw"""
        # Since original_raw has a NOT NULL constraint, use empty string to simulate missing content
        contract = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_format="JSON",
            original_raw="",  # Empty string to simulate no original_raw content
            created_by=self.user,
        )

        job = JobFactory.create_job(
            tenant=self.tenant,
            type=JobType.CONTRACT_VALIDATION,
            status=JobStatus.PENDING,
            resource_type="CONTRACT",
            resource_id=contract.id,
            created_by=self.user,
        )

        with self.assertRaises(ValueError) as cm:
            _execute_contract_validation_job(job)

        self.assertIn("no original_raw", str(cm.exception).lower())

    # SEMANTIC_MAPPING Processor Tests
    def test_execute_semantic_mapping_job_missing_resource_type(self):
        """Test SEMANTIC_MAPPING job processor with missing resource_type"""
        job = JobFactory.create_job(
            tenant=self.tenant,
            type=JobType.SEMANTIC_MAPPING,
            status=JobStatus.PENDING,
            resource_type="CONTRACT",
            resource_id=uuid.uuid4(),
            created_by=self.user,
            details_json={},  # No resource_type
        )

        with self.assertRaises(ValueError) as cm:
            _execute_semantic_mapping_job(job)

        self.assertIn("Resource type is required", str(cm.exception))

    def test_execute_semantic_mapping_job_missing_resource_id(self):
        """Test SEMANTIC_MAPPING job processor with missing resource_id"""
        job = JobFactory.create_job(
            tenant=self.tenant,
            type=JobType.SEMANTIC_MAPPING,
            status=JobStatus.PENDING,
            resource_type="CONTRACT",
            resource_id=uuid.uuid4(),
            created_by=self.user,
            details_json={"resource_type": "CONTRACT"},  # No resource_id
        )

        with self.assertRaises(ValueError) as cm:
            _execute_semantic_mapping_job(job)

        self.assertIn("Resource ID is required", str(cm.exception))

    def test_execute_semantic_mapping_job_unknown_resource_type(self):
        """Test SEMANTIC_MAPPING job processor with unknown resource_type"""
        job = JobFactory.create_job(
            tenant=self.tenant,
            type=JobType.SEMANTIC_MAPPING,
            status=JobStatus.PENDING,
            resource_type="UNKNOWN_TYPE",
            resource_id=uuid.uuid4(),
            created_by=self.user,
            details_json={"resource_type": "UNKNOWN_TYPE", "resource_id": str(uuid.uuid4())},
        )

        with self.assertRaises(ValueError) as cm:
            _execute_semantic_mapping_job(job)

        self.assertIn("unknown resource type", str(cm.exception).lower())

    def test_execute_semantic_mapping_job_contract_not_found(self):
        """Test SEMANTIC_MAPPING job processor with non-existent contract"""
        non_existent_id = uuid.uuid4()
        job = JobFactory.create_job(
            tenant=self.tenant,
            type=JobType.SEMANTIC_MAPPING,
            status=JobStatus.PENDING,
            resource_type="CONTRACT",
            resource_id=non_existent_id,
            created_by=self.user,
            details_json={"resource_type": "CONTRACT", "resource_id": str(non_existent_id)},
        )

        with self.assertRaises(ValueError) as cm:
            _execute_semantic_mapping_job(job)

        self.assertIn("not found", str(cm.exception).lower())

    # CONTRACT_MIGRATION Processor Tests
    def test_execute_contract_migration_job_contract_not_found(self):
        """Test CONTRACT_MIGRATION job processor with non-existent contract"""
        non_existent_id = uuid.uuid4()
        job = JobFactory.create_job(
            tenant=self.tenant,
            type=JobType.CONTRACT_MIGRATION,
            status=JobStatus.PENDING,
            resource_type="CONTRACT",
            resource_id=non_existent_id,
            created_by=self.user,
        )

        with self.assertRaises(ValueError) as cm:
            _execute_contract_migration_job(job)

        self.assertIn("not found", str(cm.exception).lower())

    # _execute_job_logic Tests
    def test_execute_job_logic_unknown_job_type(self):
        """Test _execute_job_logic with unknown job type"""
        job = JobFactory.create_job(
            tenant=self.tenant, type="UNKNOWN_TYPE", status=JobStatus.PENDING, created_by=self.user
        )

        with self.assertRaises(ValueError) as cm:
            _execute_job_logic(job, "UNKNOWN_TYPE")

        self.assertIn("Unknown job type", str(cm.exception))

    def test_execute_job_logic_dq_run_raises_value_error_for_missing_run(self):
        """Test _execute_job_logic routes to DQ_RUN processor"""
        dq_run_id = uuid.uuid4()
        job = JobFactory.create_job(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DQ_RUN",
            resource_id=dq_run_id,
            created_by=self.user,
            details_json={"dq_run_id": str(dq_run_id)},
        )

        # Should raise ValueError because DQ run doesn't exist
        with self.assertRaises(ValueError):
            _execute_job_logic(job, JobType.DQ_RUN)

    def test_execute_job_logic_compliance_run_raises_value_error_for_missing_run(self):
        """Test _execute_job_logic routes to COMPLIANCE_RUN processor"""
        compliance_run_id = uuid.uuid4()
        job = JobFactory.create_job(
            tenant=self.tenant,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.PENDING,
            resource_type="COMPLIANCE_RUN",
            resource_id=compliance_run_id,
            created_by=self.user,
            details_json={"compliance_run_id": str(compliance_run_id)},
        )

        # Should raise ValueError because compliance run doesn't exist
        with self.assertRaises(ValueError):
            _execute_job_logic(job, JobType.COMPLIANCE_RUN)

    def test_execute_job_logic_contract_validation_raises_value_error(self):
        """Test _execute_job_logic routes to CONTRACT_VALIDATION processor"""
        contract_id = uuid.uuid4()
        job = JobFactory.create_job(
            tenant=self.tenant,
            type=JobType.CONTRACT_VALIDATION,
            status=JobStatus.PENDING,
            resource_type="CONTRACT",
            resource_id=contract_id,
            created_by=self.user,
        )

        # Should raise ValueError because contract doesn't exist
        with self.assertRaises(ValueError):
            _execute_job_logic(job, JobType.CONTRACT_VALIDATION)

    def test_execute_job_logic_semantic_mapping_raises_value_error(self):
        """Test _execute_job_logic routes to SEMANTIC_MAPPING processor"""
        job = JobFactory.create_job(
            tenant=self.tenant,
            type=JobType.SEMANTIC_MAPPING,
            status=JobStatus.PENDING,
            resource_type="CONTRACT",
            resource_id=uuid.uuid4(),
            created_by=self.user,
            details_json={},  # Missing resource_type
        )

        # Should raise ValueError because resource_type is missing
        with self.assertRaises(ValueError):
            _execute_job_logic(job, JobType.SEMANTIC_MAPPING)

    def test_execute_job_logic_contract_migration_raises_value_error(self):
        """Test _execute_job_logic routes to CONTRACT_MIGRATION processor"""
        contract_id = uuid.uuid4()
        job = JobFactory.create_job(
            tenant=self.tenant,
            type=JobType.CONTRACT_MIGRATION,
            status=JobStatus.PENDING,
            resource_type="CONTRACT",
            resource_id=contract_id,
            created_by=self.user,
        )

        # Should raise ValueError because contract doesn't exist
        with self.assertRaises(ValueError):
            _execute_job_logic(job, JobType.CONTRACT_MIGRATION)
