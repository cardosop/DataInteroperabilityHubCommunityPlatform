"""
Phase 13 Tests — P2 Correctness: Job Atomicity, Structured Logging,
Webhook Async, API Design

Covers:
  13.1  Atomic job claim: concurrent workers cannot double-claim a PENDING job
  13.2  recover_stuck_jobs management command marks orphaned RUNNING jobs FAILED
  13.5  StructlogContextMiddleware binds tenant_id/user_id BEFORE the view runs
  13.6  Webhook async delivery: trigger_webhook enqueues RQ task, not sync call
  13.8  WebhookViewSet.deliveries() returns paginated response (not [:100] slice)
  13.9  UserRole bulk_create: N roles assigned in a single INSERT (create +
        update + invite code paths)
  13.10 Registration returns 409 on duplicate email (IntegrityError → response)
"""

import threading
import uuid
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.db import connections
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from hub.apps.auth.jwt_utils import JWTTokenGenerator
from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.users.models import User


# ── Helpers ─────────────────────────────────────────────────────────────────

def _make_tenant(name=None):
    from hub.apps.tenants.models import Tenant
    slug = f"t-{uuid.uuid4().hex[:8]}"
    return Tenant.objects.create(
        name=name or f"Tenant-{slug}",
        slug=slug,
        status="ACTIVE",
    )


def _make_user(email=None, password="Pass1234!", tenant=None, **kwargs):
    email = email or f"user_{uuid.uuid4().hex[:8]}@test.local"
    user = User.objects.create_user(
        email=email,
        password=password,
        tenant=tenant,
        **kwargs,
    )
    user.status = "ACTIVE"
    user.save(update_fields=["status"])
    return user, password


def _make_job(tenant=None, status=JobStatus.PENDING):
    t = tenant or _make_tenant()
    return Job.objects.create(
        tenant=t,
        type=JobType.DQ_RUN,
        status=status,
        resource_type="DATASET",
        resource_id=uuid.uuid4(),
    )


def _get_access_token(client, email, password):
    resp = client.post(
        "/api/v1/auth/login/",
        {"email": email, "password": password},
        content_type="application/json",
    )
    return resp.data.get("access_token", "")


# ── 13.1 — Atomic job claim ──────────────────────────────────────────────────

@pytest.mark.timeout(600)  # Concurrent TRUNCATE from other tests on shared DB
class TestAtomicJobClaim(TransactionTestCase):
    """
    Two concurrent workers must not both transition the same PENDING job to
    RUNNING.  The UPDATE WHERE status='PENDING' pattern (13.1) ensures at most
    one gets claimed_count == 1.

    Uses TransactionTestCase (not TestCase) so that rows committed inside spawned
    threads are immediately visible across connections — TestCase wraps everything
    in a transaction that other DB connections cannot see.
    """

    @classmethod
    def _fixture_setup(cls):
        # Skip TransactionTestCase's default pre-test flush (TRUNCATE ... CASCADE).
        # TRUNCATE + post_migrate deadlocks on the shared test DB under concurrent
        # load from other test containers.  Isolation via UUIDs instead.
        # NOTE: @pytest.mark.django_db(transaction=True) must NOT be used on this
        # class — it causes pytest-django to add a second flush finalizer that
        # bypasses this override and deadlocks identically.
        pass

    def _fixture_teardown(self):
        # Manual cleanup instead of flush — same pattern as
        # hub/apps/jobs/tests/test_job_processors.py.
        # Delete users referencing target tenants first — User.tenant is
        # on_delete=RESTRICT, so tenant deletion fails while users exist.
        from hub.apps.tenants.models import Tenant
        from hub.apps.users.models import User
        Job.objects.all().delete()
        User.objects.filter(tenant__slug__startswith="t-").delete()
        Tenant.objects.filter(slug__startswith="t-").delete()

    def tearDown(self):
        connections.close_all()
        super().tearDown()

    def test_concurrent_workers_claim_at_most_once(self):
        """Only one of N concurrent claimers should win the PENDING→RUNNING race."""
        job = _make_job()
        job_id = str(job.id)

        winners = []
        lock = threading.Lock()
        # Barrier ensures all 5 threads reach the DB update simultaneously,
        # preventing serialisation on single-core CI runners.
        barrier = threading.Barrier(5)

        def attempt_claim():
            from django.db import connection, transaction
            from hub.apps.jobs.models import JobStatus

            try:
                barrier.wait()  # synchronise before the UPDATE
                with transaction.atomic():
                    count = Job.objects.filter(
                        id=job_id,
                        status=JobStatus.PENDING,
                    ).update(
                        status=JobStatus.RUNNING,
                        started_at=timezone.now(),
                    )
                if count == 1:
                    with lock:
                        winners.append(True)
            finally:
                # Close the per-thread DB connection so TransactionTestCase
                # teardown TRUNCATE does not deadlock with open connections.
                connection.close()

        threads = [threading.Thread(target=attempt_claim) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        # Close any lingering per-thread DB connections so that
        # TransactionTestCase teardown's TRUNCATE doesn't deadlock.
        connections.close_all()

        self.assertEqual(len(winners), 1, "Exactly one worker should claim the job")
        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.RUNNING)

    def test_already_running_job_not_double_claimed(self):
        """A job already in RUNNING state must not be claimed a second time."""
        from django.db import transaction

        job = _make_job(status=JobStatus.RUNNING)
        job_id = str(job.id)

        with transaction.atomic():
            claimed = Job.objects.filter(
                id=job_id, status=JobStatus.PENDING
            ).update(status=JobStatus.RUNNING, started_at=timezone.now())

        self.assertEqual(claimed, 0)
        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.RUNNING)


# ── 13.2 — recover_stuck_jobs management command ─────────────────────────────

@pytest.mark.django_db
class TestRecoverStuckJobs(TestCase):
    """recover_stuck_jobs marks orphaned RUNNING jobs as FAILED."""

    def _call_command(self, **kwargs):
        from django.core.management import call_command
        from io import StringIO

        out = StringIO()
        call_command("recover_stuck_jobs", stdout=out, **kwargs)
        return out.getvalue()

    def test_marks_old_running_job_failed(self):
        """A RUNNING job started > threshold ago should be marked FAILED."""
        job = _make_job(status=JobStatus.RUNNING)
        # Back-date started_at beyond the default 120-minute threshold
        Job.objects.filter(id=job.id).update(
            started_at=timezone.now() - timedelta(minutes=130)
        )

        output = self._call_command(threshold_minutes=120)

        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.FAILED)
        self.assertIn("WORKER_DIED", job.result_json.get("error_code", ""))
        self.assertIn("Recovered 1", output)

    def test_ignores_recently_started_running_job(self):
        """A RUNNING job started recently should NOT be touched."""
        job = _make_job(status=JobStatus.RUNNING)
        Job.objects.filter(id=job.id).update(
            started_at=timezone.now() - timedelta(minutes=10)
        )

        output = self._call_command(threshold_minutes=120)

        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.RUNNING)
        self.assertIn("No stuck jobs found", output)

    def test_dry_run_does_not_mutate(self):
        """--dry-run must not change any job status."""
        job = _make_job(status=JobStatus.RUNNING)
        Job.objects.filter(id=job.id).update(
            started_at=timezone.now() - timedelta(minutes=130)
        )

        self._call_command(threshold_minutes=120, dry_run=True)

        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.RUNNING)


# ── 25.24.3 — recover_stuck_jobs syncs ScheduledIngestionRun ──────────────────

@pytest.mark.django_db
class TestRecoverStuckJobsSyncsIngestionRun(TestCase):
    """
    When recover_stuck_jobs marks a SCHEDULED_INGESTION Job as FAILED,
    the matching ScheduledIngestionRun must also transition to FAILED.
    """

    def _call_command(self, **kwargs):
        from django.core.management import call_command
        from io import StringIO

        out = StringIO()
        call_command("recover_stuck_jobs", stdout=out, **kwargs)
        return out.getvalue()

    def test_recover_stuck_jobs_updates_ingestion_run(self):
        """
        Seed a SCHEDULED_INGESTION Job (RUNNING, started 3h ago) with a
        matching ScheduledIngestionRun (RUNNING). Run the management command.
        Assert both transition to FAILED.
        """
        from hub.apps.scheduled_ingestion.models import (
            ScheduledIngestion,
            ScheduledIngestionRun,
            ScheduledIngestionRunStatus,
            ScheduleType,
            SourceType,
        )

        tenant = _make_tenant()
        user, _ = _make_user(tenant=tenant)

        # Create the scheduled ingestion
        si = ScheduledIngestion.objects.create(
            tenant=tenant,
            name="Test Ingestion for Recovery",
            source_type=SourceType.S3,
            source_config={"bucket": "test-bucket"},
            schedule_type=ScheduleType.DAILY,
            schedule_config={"time": "02:00"},
            file_pattern=".*\\.csv",
            created_by=user,
        )

        # Create the Job
        three_hours_ago = timezone.now() - timedelta(hours=3)
        job = Job.objects.create(
            tenant=tenant,
            type=JobType.SCHEDULED_INGESTION,
            status=JobStatus.RUNNING,
            resource_type="SCHEDULED_INGESTION",
            resource_id=si.id,
            started_at=three_hours_ago,
            created_by=user,
        )

        # Create the matching ScheduledIngestionRun
        run = ScheduledIngestionRun.objects.create(
            scheduled_ingestion=si,
            status=ScheduledIngestionRunStatus.RUNNING,
            started_at=three_hours_ago,
            job_id=job.id,
        )

        output = self._call_command(threshold_minutes=120)

        # Assert Job is FAILED
        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.FAILED)

        # Assert ScheduledIngestionRun is also FAILED
        run.refresh_from_db()
        self.assertEqual(run.status, ScheduledIngestionRunStatus.FAILED)
        self.assertIn("Worker process died", run.error_message)


# ── 13.6 — Async webhook delivery ────────────────────────────────────────────

@pytest.mark.django_db(transaction=True)
@override_settings(WEBHOOK_SSRF_ENABLED=False, WEBHOOK_ASYNC_DELIVERY=True)
class TestWebhookAsyncDelivery(TransactionTestCase):
    """
    With WEBHOOK_ASYNC_DELIVERY=True, trigger_webhook() must enqueue an RQ
    task rather than calling _attempt_delivery() in the request thread.
    """
    databases = "__all__"

    def _make_webhook(self, tenant):
        from hub.apps.webhooks.models import Webhook, WebhookStatus

        return Webhook.objects.create(
            tenant=tenant,
            name=f"wh-{uuid.uuid4().hex[:6]}",
            url="https://example.com/hook",
            secret="test-secret",
            event_types=["asset.created"],
            status=WebhookStatus.ACTIVE,
        )

    def test_trigger_enqueues_rq_task_not_sync_delivery(self):
        """trigger_webhook must enqueue deliver_webhook RQ task, not call _attempt_delivery."""
        tenant = _make_tenant()
        self._make_webhook(tenant)

        with (
            patch(
                "hub.apps.webhooks.tasks.deliver_webhook.delay"
            ) as mock_delay,
            patch.object(
                __import__(
                    "hub.apps.webhooks.service",
                    fromlist=["WebhookDeliveryService"],
                ).WebhookDeliveryService,
                "_attempt_delivery",
            ) as mock_sync,
        ):
            from hub.apps.webhooks.service import WebhookDeliveryService

            WebhookDeliveryService.trigger_webhook(
                tenant_id=str(tenant.id),
                event_type="asset.created",
                resource_type="ASSET",
                resource_id=str(uuid.uuid4()),
                event_data={"name": "test-asset"},
            )

        mock_delay.assert_called_once()
        mock_sync.assert_not_called()


# ── 13.8 — Webhook deliveries pagination ─────────────────────────────────────

@pytest.mark.django_db
@override_settings(JWT_ALGORITHM="HS256", JWT_SECRET_KEY="test-hs256-secret-key-phase13-xx")
class TestWebhookDeliveriesPagination(TestCase):
    """
    GET /webhooks/{id}/deliveries/ must return a paginated envelope, not a
    raw list capped at 100.
    """

    def setUp(self):
        from hub.apps.webhooks.models import (
            DeliveryStatus,
            Webhook,
            WebhookDelivery,
            WebhookStatus,
        )

        from hub.apps.users.services import UserTenantMembershipService

        self.tenant = _make_tenant()
        self.user, self.password = _make_user(tenant=self.tenant)
        # TenantScopingMiddleware validates UserTenantMembership when X-Tenant-ID is present
        UserTenantMembershipService().add_membership(self.user, self.tenant)
        self.client = APIClient()

        self.webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="test-wh",
            url="https://example.com/hook",
            secret="s3cr3t",
            event_types=["asset.created"],
            status=WebhookStatus.ACTIVE,
        )
        # Create 5 deliveries
        for _ in range(5):
            WebhookDelivery.objects.create(
                webhook=self.webhook,
                event_type="asset.created",
                payload={"data": "x"},
                signature="sig",
                status=DeliveryStatus.SUCCESS,
                attempt_number=1,
            )

    def _auth(self):
        # Generate token directly to avoid login-endpoint rate limiting from
        # concurrent auth security tests running on the same IP (127.0.0.1).
        token = JWTTokenGenerator.generate_access_token(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        self.client.defaults["HTTP_X_TENANT_ID"] = str(self.tenant.id)

    def test_deliveries_returns_paginated_envelope(self):
        self._auth()
        resp = self.client.get(f"/api/v1/webhooks/webhooks/{self.webhook.id}/deliveries/")

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        # Paginated response must have count/results keys
        self.assertIn("count", data)
        self.assertIn("results", data)
        self.assertEqual(data["count"], 5)


# ── 13.9 — UserRole bulk_create ──────────────────────────────────────────────

@pytest.mark.django_db
class TestUserRoleBulkCreate(TestCase):
    """
    Assigning multiple roles to a newly created user must use a single
    bulk_create(ignore_conflicts=True) call, not N individual get_or_create
    round-trips.
    """

    def test_bulk_create_roles_in_single_query(self):
        from hub.apps.users.models import Role, UserRole
        from hub.apps.users.services import UserService

        tenant = _make_tenant()
        roles = [
            Role.objects.create(
                tenant=tenant,
                name=f"ROLE_{uuid.uuid4().hex[:6].upper()}",
            )
            for _ in range(3)
        ]
        role_ids = [str(r.id) for r in roles]

        actor, _ = _make_user(tenant=tenant)
        # Patch bulk_create to count calls
        original_bulk_create = UserRole.objects.bulk_create

        calls = []

        def counting_bulk_create(objs, **kwargs):
            calls.append(len(objs))
            return original_bulk_create(objs, **kwargs)

        with patch.object(UserRole.objects, "bulk_create", side_effect=counting_bulk_create):
            new_user = UserService().create_user(
                tenant_id=str(tenant.id),
                actor_user_id=str(actor.id),
                email=f"u_{uuid.uuid4().hex[:8]}@test.local",
                role_ids=role_ids,
            )

        # Exactly one bulk_create call for all N roles
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0], len(roles))
        assigned = UserRole.objects.filter(user=new_user)
        self.assertEqual(assigned.count(), len(roles))

    def test_bulk_create_is_idempotent_on_conflict(self):
        """Calling bulk_create twice for the same roles should not raise."""
        from hub.apps.users.models import Role, UserRole

        tenant = _make_tenant()
        role = Role.objects.create(tenant=tenant, name="DUPLICATE_TEST_ROLE")
        user, _ = _make_user(tenant=tenant)

        UserRole.objects.bulk_create(
            [UserRole(user=user, tenant=tenant, role=role)],
            ignore_conflicts=True,
        )
        # Second call must not raise IntegrityError
        UserRole.objects.bulk_create(
            [UserRole(user=user, tenant=tenant, role=role)],
            ignore_conflicts=True,
        )
        self.assertEqual(
            UserRole.objects.filter(user=user, role=role).count(), 1
        )


# ── 13.10 — Registration 409 on duplicate email ───────────────────────────────

@pytest.mark.django_db
@override_settings(
    JWT_ALGORITHM="HS256",
    PERSONAL_TENANT_ON_REGISTRATION=False,
)
class TestRegistrationDuplicateEmail(TestCase):
    """POST /auth/register/ with a duplicate email must return 409."""

    def setUp(self):
        self.client = APIClient()
        self.tenant = _make_tenant()
        # Pre-create a user to cause a duplicate on second registration
        self.existing_email = f"dup_{uuid.uuid4().hex[:8]}@test.local"
        User.objects.create_user(
            email=self.existing_email,
            password="Pass1234!",
            tenant=self.tenant,
        )

    def test_returns_409_on_duplicate_email(self):
        resp = self.client.post(
            "/api/v1/auth/register/",
            {
                "email": self.existing_email,
                "password": "AnotherPass1!",
                "name": "Duplicate User",
                "tenant_id": str(self.tenant.id),
            },
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 409)
        data = resp.json()
        self.assertIn("EMAIL_ALREADY_EXISTS", str(data))

    def test_unique_email_registration_succeeds(self):
        fresh_email = f"fresh_{uuid.uuid4().hex[:8]}@test.local"
        resp = self.client.post(
            "/api/v1/auth/register/",
            {
                "email": fresh_email,
                "password": "AnotherPass1!",
                "name": "New User",
                "tenant_id": str(self.tenant.id),
            },
            content_type="application/json",
        )
        self.assertIn(resp.status_code, [200, 201])


# ── 13.5 — StructlogContextMiddleware ────────────────────────────────────────

@pytest.mark.django_db
class TestStructlogContextMiddleware(TestCase):
    """
    StructlogContextMiddleware must bind tenant_id and user_id into the
    structlog contextvars *before* calling get_response (i.e. before the
    view runs), so that every log line emitted during request handling
    carries those fields without manual passing.
    """

    def _make_request_with_tenant(self, tenant, user=None):
        """Build a minimal Django request-like object with tenant/user set."""
        from django.test import RequestFactory
        from django.contrib.auth.models import AnonymousUser

        factory = RequestFactory()
        request = factory.get("/api/v1/assets/")
        request.tenant = tenant
        request.user = user if user else AnonymousUser()
        return request

    def test_binds_tenant_id_before_view(self):
        """tenant_id must appear in structlog contextvars during get_response."""
        import structlog
        from hub.apps.api.middleware import StructlogContextMiddleware

        tenant = _make_tenant()
        request = self._make_request_with_tenant(tenant)

        captured = {}

        def fake_get_response(req):
            captured.update(structlog.contextvars.get_contextvars())
            from django.http import HttpResponse
            return HttpResponse()

        middleware = StructlogContextMiddleware(fake_get_response)
        structlog.contextvars.clear_contextvars()
        middleware(request)

        self.assertIn("tenant_id", captured, "tenant_id must be bound before the view runs")
        self.assertEqual(captured["tenant_id"], str(tenant.id))

    def test_binds_user_id_before_view(self):
        """user_id must appear in structlog contextvars for authenticated users."""
        import structlog
        from hub.apps.api.middleware import StructlogContextMiddleware

        tenant = _make_tenant()
        user, _ = _make_user(tenant=tenant)
        request = self._make_request_with_tenant(tenant, user=user)

        captured = {}

        def fake_get_response(req):
            captured.update(structlog.contextvars.get_contextvars())
            from django.http import HttpResponse
            return HttpResponse()

        middleware = StructlogContextMiddleware(fake_get_response)
        structlog.contextvars.clear_contextvars()
        middleware(request)

        self.assertIn("user_id", captured, "user_id must be bound before the view runs")
        self.assertEqual(captured["user_id"], str(user.id))

    def test_anonymous_user_not_bound(self):
        """Anonymous (unauthenticated) requests must not bind user_id."""
        import structlog
        from hub.apps.api.middleware import StructlogContextMiddleware

        tenant = _make_tenant()
        request = self._make_request_with_tenant(tenant)  # AnonymousUser

        captured = {}

        def fake_get_response(req):
            captured.update(structlog.contextvars.get_contextvars())
            from django.http import HttpResponse
            return HttpResponse()

        middleware = StructlogContextMiddleware(fake_get_response)
        structlog.contextvars.clear_contextvars()
        middleware(request)

        self.assertNotIn("user_id", captured, "AnonymousUser must not bind user_id")
        self.assertIn("tenant_id", captured)


# ── 13.9 (extended) — UserRole bulk_create in update + invite paths ───────────

@pytest.mark.django_db
class TestUserRoleBulkCreateAllPaths(TestCase):
    """
    All code paths that assign UserRole objects must use a single
    bulk_create(ignore_conflicts=True) call, not N individual get_or_create
    round-trips.  This covers update_user and invite_user_to_tenant in
    addition to create_user (already covered by TestUserRoleBulkCreate).
    """

    def test_update_user_bulk_create_roles(self):
        """update_user must replace roles with a single bulk_create, not N get_or_create."""
        from hub.apps.users.models import Role, UserRole
        from hub.apps.users.services import UserService

        tenant = _make_tenant()
        user, _ = _make_user(tenant=tenant)
        actor, _ = _make_user(tenant=tenant)

        roles = [
            Role.objects.create(tenant=tenant, name=f"UPD_{uuid.uuid4().hex[:6].upper()}")
            for _ in range(3)
        ]
        role_ids = [str(r.id) for r in roles]

        original_bulk_create = UserRole.objects.bulk_create
        calls = []

        def counting_bulk_create(objs, **kwargs):
            calls.append(len(objs))
            return original_bulk_create(objs, **kwargs)

        with patch.object(UserRole.objects, "bulk_create", side_effect=counting_bulk_create):
            # update_user takes **update_data kwargs; role_ids is passed as a kwarg
            UserService().update_user(
                user_id=str(user.id),
                tenant_id=str(tenant.id),
                actor_user_id=str(actor.id),
                role_ids=role_ids,
            )

        self.assertEqual(len(calls), 1, "update_user must issue exactly one bulk_create")
        self.assertEqual(calls[0], len(roles))
        self.assertEqual(UserRole.objects.filter(user=user).count(), len(roles))

    def test_invite_user_bulk_create_roles(self):
        """invite_user_to_tenant must use bulk_create for role assignment."""
        from hub.apps.users.models import Role, UserRole
        from hub.apps.users.services import UserService

        tenant = _make_tenant()
        actor, _ = _make_user(tenant=tenant)
        # Create user in a *different* tenant so the invite path adds them
        # to `tenant` (the "existing user, new membership" branch).
        other_tenant = _make_tenant()
        existing_email = f"existing_{uuid.uuid4().hex[:8]}@test.local"
        User.objects.create_user(email=existing_email, password="Pass1234!", tenant=other_tenant)

        roles = [
            Role.objects.create(tenant=tenant, name=f"INV_{uuid.uuid4().hex[:6].upper()}")
            for _ in range(2)
        ]
        role_ids = [str(r.id) for r in roles]

        original_bulk_create = UserRole.objects.bulk_create
        calls = []

        def counting_bulk_create(objs, **kwargs):
            calls.append(len(objs))
            return original_bulk_create(objs, **kwargs)

        with patch.object(UserRole.objects, "bulk_create", side_effect=counting_bulk_create):
            UserService().invite_user_to_tenant(
                email=existing_email,
                tenant_id=str(tenant.id),
                actor_user_id=str(actor.id),
                role_ids=role_ids,
            )

        self.assertGreaterEqual(len(calls), 1, "invite_user_to_tenant must use bulk_create")
        # All N roles should be assigned in a single batch call
        role_call_sizes = [c for c in calls if c > 0]
        self.assertIn(len(roles), role_call_sizes, "All roles must be assigned in one INSERT")
