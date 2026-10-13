"""W2.8 (R2 B-10) — job Redis counters fail-closed + reconciliation.

The tenant job-concurrency gate reads ``job:tenant:{id}:running`` /
``job:tenant:{id}:queued`` from Redis with ``cache.get(key, 0)`` — a
failed write, an expired key, or a Redis outage silently read as ZERO,
so the gate failed OPEN (any drift let tenants exceed their limits; the
outer error handler even returned "allow"). The Job table is the source
of truth and was never consulted.

Evidence pins:

* **missing/drifted counters reconcile from the Job table on read** —
  the gate enforces the DB truth, not an absent Redis key.
* **Redis down → DB fallback (fail-closed)** — an unreachable counter
  store no longer means "allow"; the gate still enforces (and a
  completely failed check BLOCKS instead of allowing).
* **``reconcile_tenant_job_counters`` rebuilds both keys** from the DB,
  and the ``reconcile_job_counters`` management command repairs every
  tenant's counters.

Real Redis, real DB — no mocks/stubs. The "Redis down" pin points the
cache at a dead port: a REAL connection failure raises the REAL
RedisError path.
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings

from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.jobs.utils import (
    check_tenant_job_limits,
    reconcile_tenant_job_counters,
)
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()

_DEAD_REDIS_CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://127.0.0.1:63999/0",  # nothing listens here
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "IGNORE_EXCEPTIONS": False,
        },
        "KEY_PREFIX": "hub",
        "TIMEOUT": 300,
    }
}


def _make_job(tenant, job_status, job_type=JobType.CONTRACT_VALIDATION):
    return Job.objects.create(
        tenant=tenant,
        type=job_type,
        status=job_status,
        resource_type="CONTRACT",
        resource_id=uuid.uuid4(),
    )


class JobCounterReconciliationTest(TestCase):
    """The counters rebuild from the Job table — the DB is the truth."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(name=f"Tenant {uid}", slug=f"t-{uid}", status="ACTIVE")
        self.user = User.objects.create_user(
            email=f"u-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.running_key = f"job:tenant:{self.tenant.id}:running"
        self.queued_key = f"job:tenant:{self.tenant.id}:queued"
        self.addCleanup(cache.delete, self.running_key)
        self.addCleanup(cache.delete, self.queued_key)

    def test_reconcile_rebuilds_both_counters_from_db(self):
        _make_job(self.tenant, JobStatus.RUNNING)
        _make_job(self.tenant, JobStatus.RUNNING)
        _make_job(self.tenant, JobStatus.PENDING)
        _make_job(self.tenant, JobStatus.PENDING)
        _make_job(self.tenant, JobStatus.PENDING)
        # Corrupt the Redis view.
        cache.set(self.running_key, 0, timeout=86400)
        cache.set(self.queued_key, 99, timeout=86400)

        result = reconcile_tenant_job_counters(str(self.tenant.id))

        self.assertEqual(result, {"running": 2, "queued": 3})
        self.assertEqual(cache.get(self.running_key), 2)
        self.assertEqual(cache.get(self.queued_key), 3)

    def test_gate_reconciles_missing_keys_and_enforces(self):
        """THE pin: absent counters no longer read as zero = allow-all."""
        # 6 RUNNING jobs exceed the platform-default concurrency of 5.
        for _ in range(6):
            _make_job(self.tenant, JobStatus.RUNNING)
        cache.delete(self.running_key)
        cache.delete(self.queued_key)

        can_create, message = check_tenant_job_limits(str(self.tenant.id))

        self.assertFalse(can_create)
        self.assertIn("maximum concurrent job limit", message)
        # The gate repaired the counter from the DB while enforcing.
        self.assertEqual(cache.get(self.running_key), 6)

    def test_gate_allows_when_db_is_under_limit_after_reconcile(self):
        for _ in range(4):
            _make_job(self.tenant, JobStatus.RUNNING)
        cache.delete(self.running_key)
        cache.delete(self.queued_key)

        can_create, message = check_tenant_job_limits(str(self.tenant.id))

        self.assertTrue(can_create, message)
        self.assertIsNone(message)
        self.assertEqual(cache.get(self.running_key), 4)

    def test_redis_down_falls_back_to_db_fail_closed(self):
        """Redis unreachable → the DB still enforces (pre-fix: allow-all)."""
        for _ in range(6):
            _make_job(self.tenant, JobStatus.RUNNING)
        cache.delete(self.running_key)
        cache.delete(self.queued_key)

        with override_settings(CACHES=_DEAD_REDIS_CACHES):
            can_create, message = check_tenant_job_limits(str(self.tenant.id))

        self.assertFalse(can_create)
        self.assertIn("maximum concurrent job limit", message)

    def test_redis_down_under_limit_still_allows_via_db(self):
        for _ in range(2):
            _make_job(self.tenant, JobStatus.RUNNING)
        cache.delete(self.running_key)
        cache.delete(self.queued_key)

        with override_settings(CACHES=_DEAD_REDIS_CACHES):
            can_create, message = check_tenant_job_limits(str(self.tenant.id))

        self.assertTrue(can_create, message)
        self.assertIsNone(message)

    def test_management_command_reconciles_all_tenants(self):
        other = Tenant.objects.create(
            name=f"Other {uuid.uuid4().hex[:6]}",
            slug=f"o-{uuid.uuid4().hex[:6]}",
            status="ACTIVE",
        )
        _make_job(self.tenant, JobStatus.RUNNING)
        _make_job(other, JobStatus.PENDING)
        _make_job(other, JobStatus.PENDING)
        cache.set(self.running_key, 0, timeout=86400)
        cache.set(self.queued_key, 42, timeout=86400)
        other_queued_key = f"job:tenant:{other.id}:queued"
        self.addCleanup(cache.delete, other_queued_key)

        call_command("reconcile_job_counters")

        self.assertEqual(cache.get(self.running_key), 1)
        self.assertEqual(cache.get(self.queued_key), 0)
        self.assertEqual(cache.get(other_queued_key), 2)
