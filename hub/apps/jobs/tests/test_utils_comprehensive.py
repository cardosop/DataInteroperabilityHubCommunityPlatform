"""Comprehensive tests for jobs/utils.py — Phase 100.3"""

import uuid

import pytest

pytestmark = pytest.mark.slow
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase

from hub.apps.jobs.models import JobType
from hub.apps.jobs.utils import (
    JOB_MAX_RETRIES,
    decrement_tenant_job_counter,
    get_job_timeout,
    get_queue_for_job_type,
    increment_tenant_job_counter,
)
from hub.apps.tenants.models import Tenant

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class JobTimeoutTest(TestCase):
    """Test timeout configuration per job type."""

    def test_dq_run_timeout_is_30_minutes(self):
        self.assertEqual(get_job_timeout(JobType.DQ_RUN), 1800)

    def test_contract_validation_timeout_is_5_minutes(self):
        self.assertEqual(get_job_timeout(JobType.CONTRACT_VALIDATION), 300)

    def test_scheduled_ingestion_timeout_is_1_hour(self):
        self.assertEqual(get_job_timeout(JobType.SCHEDULED_INGESTION), 3600)

    def test_all_job_types_have_timeouts(self):
        """Every JobType has a configured timeout."""
        for jt in JobType:
            timeout = get_job_timeout(jt.value)
            self.assertIsInstance(timeout, int)
            self.assertGreater(timeout, 0, f"{jt.value} has no timeout")


class QueueMappingTest(TestCase):
    """Test queue assignment per job type and priority."""

    def test_dq_run_maps_to_critical_queue(self):
        queue = get_queue_for_job_type(JobType.DQ_RUN)
        self.assertEqual(queue, "job_critical")

    def test_compliance_run_maps_to_critical_queue(self):
        queue = get_queue_for_job_type(JobType.COMPLIANCE_RUN)
        self.assertEqual(queue, "job_critical")

    def test_contract_validation_maps_to_low_queue(self):
        queue = get_queue_for_job_type(JobType.CONTRACT_VALIDATION)
        self.assertEqual(queue, "job_low")

    def test_search_index_update_maps_to_default_queue(self):
        queue = get_queue_for_job_type(JobType.SEARCH_INDEX_UPDATE)
        self.assertEqual(queue, "job_default")

    def test_odps_normalization_maps_to_default_queue(self):
        queue = get_queue_for_job_type(JobType.ODPS_NORMALIZATION)
        self.assertEqual(queue, "job_default")


class RetryConfigTest(TestCase):
    """Test retry configuration per job type."""

    def test_dq_run_max_retries_is_3(self):
        self.assertEqual(JOB_MAX_RETRIES.get(JobType.DQ_RUN), 3)

    def test_contract_migration_max_retries_is_1(self):
        self.assertEqual(JOB_MAX_RETRIES.get(JobType.CONTRACT_MIGRATION), 1)

    def test_most_job_types_have_retry_config(self):
        """Core job types have max retry config."""
        configured = 0
        for jt in JobType:
            retries = JOB_MAX_RETRIES.get(jt.value, JOB_MAX_RETRIES.get(jt))
            if retries is not None:
                configured += 1
                self.assertGreaterEqual(retries, 1)
        self.assertGreaterEqual(configured, 10, "Most job types should have retry config")


class TenantJobCounterTest(TestCase):
    """Test tenant job counter increment/decrement."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"T {uid}", slug=f"t-{uid}", status="ACTIVE", kyc_status="UNVERIFIED"
        )
        self.tenant_id = str(self.tenant.id)
        # Clear counters
        cache.delete(f"job:tenant:{self.tenant_id}:running")

    def test_increment_then_decrement_returns_to_zero(self):
        """Counter goes up by 1 then back to 0."""
        increment_tenant_job_counter(self.tenant_id, "running")
        val = cache.get(f"job:tenant:{self.tenant_id}:running")
        self.assertEqual(int(val or 0), 1)
        decrement_tenant_job_counter(self.tenant_id, "running")
        val = cache.get(f"job:tenant:{self.tenant_id}:running")
        self.assertIn(int(val or 0), [0, None])

    def test_multiple_increments_stack(self):
        """Multiple increments accumulate."""
        increment_tenant_job_counter(self.tenant_id, "running")
        increment_tenant_job_counter(self.tenant_id, "running")
        increment_tenant_job_counter(self.tenant_id, "running")
        val = cache.get(f"job:tenant:{self.tenant_id}:running")
        self.assertEqual(int(val or 0), 3)
