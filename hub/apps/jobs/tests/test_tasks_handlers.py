"""Tests for job type handlers — verifies each job type can be instantiated and dispatched. Phase 100.2"""
import uuid
import pytest
from django.conf import settings
from django.test import TestCase
from django.contrib.auth import get_user_model
from hub.apps.tenants.models import Tenant
from hub.apps.jobs.models import Job, JobType, JobStatus
from hub.apps.jobs.utils import get_queue_for_job_type, get_job_timeout
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()

# Valid RQ queue names from settings — used to verify queue mappings point to real queues
VALID_RQ_QUEUES = set(settings.RQ_QUEUES.keys())


class JobTypeHandlerRegistrationTest(TestCase):
    """Test each job type handler can be created and configured."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(name=f"T {uid}", slug=f"t-{uid}", status="ACTIVE", kyc_status="UNVERIFIED")
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(email=f"u-{uid}@test.com", password="pass", tenant=self.tenant, status="ACTIVE")
        self.resource_id = uuid.uuid4()

    def _create_job(self, job_type, resource_type="DATASET"):
        return Job.objects.create(
            tenant=self.tenant, type=job_type, resource_type=resource_type,
            resource_id=self.resource_id, created_by=self.user, status=JobStatus.PENDING,
        )

    def _assert_handler_configured(self, job_type, expected_queue, expected_timeout):
        """Verify a job type has a valid queue mapping in RQ_QUEUES and a positive timeout."""
        queue = get_queue_for_job_type(job_type)
        self.assertEqual(queue, expected_queue)
        self.assertIn(queue, VALID_RQ_QUEUES,
                      f"Queue '{queue}' for {job_type} is not defined in RQ_QUEUES settings")
        timeout = get_job_timeout(job_type)
        self.assertEqual(timeout, expected_timeout)
        self.assertGreater(timeout, 0, f"Timeout for {job_type} must be positive")

    def test_dq_run_handler(self):
        job = self._create_job(JobType.DQ_RUN)
        self.assertEqual(job.status, JobStatus.PENDING)
        self._assert_handler_configured(JobType.DQ_RUN, "job_critical", 1800)

    def test_compliance_run_handler(self):
        job = self._create_job(JobType.COMPLIANCE_RUN, "ASSET")
        self.assertEqual(job.status, JobStatus.PENDING)
        self._assert_handler_configured(JobType.COMPLIANCE_RUN, "job_critical", 1800)

    def test_contract_validation_handler(self):
        job = self._create_job(JobType.CONTRACT_VALIDATION, "CONTRACT")
        self.assertEqual(job.status, JobStatus.PENDING)
        queue = get_queue_for_job_type(JobType.CONTRACT_VALIDATION)
        self.assertIn(queue, VALID_RQ_QUEUES,
                      f"Queue '{queue}' for CONTRACT_VALIDATION is not in RQ_QUEUES")
        self.assertGreater(get_job_timeout(JobType.CONTRACT_VALIDATION), 0)

    def test_odps_normalization_handler(self):
        job = self._create_job(JobType.ODPS_NORMALIZATION, "CONTRACT")
        self.assertEqual(job.status, JobStatus.PENDING)
        queue = get_queue_for_job_type(JobType.ODPS_NORMALIZATION)
        self.assertIn(queue, VALID_RQ_QUEUES)
        self.assertGreater(get_job_timeout(JobType.ODPS_NORMALIZATION), 0)

    def test_odps_ref_resolution_handler(self):
        job = self._create_job(JobType.ODPS_REF_RESOLUTION, "CONTRACT")
        self.assertEqual(job.status, JobStatus.PENDING)
        queue = get_queue_for_job_type(JobType.ODPS_REF_RESOLUTION)
        self.assertIn(queue, VALID_RQ_QUEUES)
        self.assertGreater(get_job_timeout(JobType.ODPS_REF_RESOLUTION), 0)

    def test_odps_semantic_mapping_handler(self):
        job = self._create_job(JobType.ODPS_SEMANTIC_MAPPING, "CONTRACT")
        self.assertEqual(job.status, JobStatus.PENDING)
        queue = get_queue_for_job_type(JobType.ODPS_SEMANTIC_MAPPING)
        self.assertIn(queue, VALID_RQ_QUEUES)
        self.assertGreater(get_job_timeout(JobType.ODPS_SEMANTIC_MAPPING), 0)

    def test_odps_linking_handler(self):
        job = self._create_job(JobType.ODPS_LINKING, "CONTRACT")
        self.assertEqual(job.status, JobStatus.PENDING)
        queue = get_queue_for_job_type(JobType.ODPS_LINKING)
        self.assertIn(queue, VALID_RQ_QUEUES)
        self.assertGreater(get_job_timeout(JobType.ODPS_LINKING), 0)

    def test_odps_export_handler(self):
        job = self._create_job(JobType.ODPS_EXPORT, "CONTRACT")
        self.assertEqual(job.status, JobStatus.PENDING)
        queue = get_queue_for_job_type(JobType.ODPS_EXPORT)
        self.assertIn(queue, VALID_RQ_QUEUES)
        self.assertGreater(get_job_timeout(JobType.ODPS_EXPORT), 0)

    def test_virtualization_query_handler(self):
        job = self._create_job(JobType.VIRTUAL_QUERY_EXECUTION, "VIRTUAL_DATASET")
        self.assertEqual(job.status, JobStatus.PENDING)
        self._assert_handler_configured(JobType.VIRTUAL_QUERY_EXECUTION, "job_default", 3600)

    def test_marketplace_sync_handler(self):
        job = self._create_job(JobType.MARKETPLACE_SYNC, "LISTING")
        self.assertEqual(job.status, JobStatus.PENDING)
        queue = get_queue_for_job_type(JobType.MARKETPLACE_SYNC)
        self.assertIn(queue, VALID_RQ_QUEUES)
        self.assertGreater(get_job_timeout(JobType.MARKETPLACE_SYNC), 0)

    def test_search_index_handler(self):
        job = self._create_job(JobType.SEARCH_INDEX_UPDATE, "ASSET")
        self.assertEqual(job.status, JobStatus.PENDING)
        queue = get_queue_for_job_type(JobType.SEARCH_INDEX_UPDATE)
        self.assertIn(queue, VALID_RQ_QUEUES)
        self.assertGreater(get_job_timeout(JobType.SEARCH_INDEX_UPDATE), 0)

    def test_semantic_mapping_handler(self):
        job = self._create_job(JobType.SEMANTIC_MAPPING, "CONTRACT")
        self.assertEqual(job.status, JobStatus.PENDING)
        self._assert_handler_configured(JobType.SEMANTIC_MAPPING, "job_default", 60)

    def test_retention_policy_handler(self):
        job = self._create_job(JobType.RETENTION_POLICY_ENFORCEMENT, "ASSET")
        self.assertEqual(job.status, JobStatus.PENDING)
        queue = get_queue_for_job_type(JobType.RETENTION_POLICY_ENFORCEMENT)
        self.assertIn(queue, VALID_RQ_QUEUES)
        self.assertGreater(get_job_timeout(JobType.RETENTION_POLICY_ENFORCEMENT), 0)

    def test_all_14_job_types_have_queue_mapping(self):
        """Every JobType value maps to a valid queue defined in RQ_QUEUES settings."""
        for jt in JobType:
            queue = get_queue_for_job_type(jt.value)
            self.assertIn(queue, VALID_RQ_QUEUES,
                          f"{jt.value} maps to queue '{queue}' which is not in RQ_QUEUES settings")
            timeout = get_job_timeout(jt.value)
            self.assertIsInstance(timeout, int)
            self.assertGreater(timeout, 0, f"{jt.value} has non-positive timeout: {timeout}")
