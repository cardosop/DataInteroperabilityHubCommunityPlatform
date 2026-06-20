"""
Phase 233.3 — Per-tenant outbound rate-limiting tests.

Pins each REQ-WH-RL-* requirement and scenario from
``openspec/changes/preprod01/specs/webhook-rate-limiting/spec.md`` against
real production code paths. Cron tests use real Redis via the canonical
``_redis_or_skip()`` pattern (probe-via-ping; mirrors
``test_purge_deleted_files.py:31-37`` and ``test_signing_rotation.py``
post-233.1.R1).

Coverage map:

    REQ-WH-RL-001  Tenant field + default 300 + kill-switch at 0 →
                   ``TestTenantField`` + ``TestKillSwitch``.
    REQ-WH-RL-002  Redis INCR enforcement + 90s TTL + minute-truncated
                   bucket + atomic concurrent semantics →
                   ``TestRedisCounterEnforcement``.
    REQ-WH-RL-003  ``RATE_LIMITED`` terminal state + retry-suppression →
                   ``TestRateLimitedIsTerminal``.
    REQ-WH-RL-004  ``WEBHOOK_RATE_LIMIT_EXCEEDED`` audit row in same
                   transaction with structured metadata →
                   ``TestRateLimitAudit``.
    REQ-WH-RL-005  Prometheus counter ``meshant_webhook_rate_limit_blocks_total``
                   increments on block → ``TestPrometheusCounter``.

All tests use ``transaction=True`` so Redis state + audit emission
observe their real behaviour (not SAVEPOINT semantics).
"""

from __future__ import annotations

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.audit.models import AuditEvent
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import (
    ensure_tenant_has_active_subscription,
)
from hub.apps.webhooks.models import (
    DeliveryStatus,
    Webhook,
    WebhookDelivery,
    WebhookEventType,
    WebhookStatus,
)

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


def _redis_or_skip():
    """Probe Redis reachability AND return the client.

    Mirrors the canonical pattern at ``test_purge_deleted_files.py:31-37``
    + ``test_signing_rotation.py`` post-233.1.R1: actually ``.ping()``
    Redis to detect unreachability rather than only catching exceptions
    during client construction. Without the ping, a client object
    returned for a Redis-down environment would let the test proceed
    past the skip and FAIL on the first real Redis op.
    """
    try:
        from hub.apps.api.middleware.idempotency_utils import (
            get_redis_client,
        )

        client = get_redis_client()
        client.ping()
        return client
    except Exception as exc:  # pragma: no cover — env-dependent
        import unittest

        raise unittest.SkipTest(f"Redis required: {exc}") from exc


class _RateLimitTestBase(TestCase):
    """Common tenant + user + webhook + Redis-cleanup setup."""

    def setUp(self) -> None:
        self.uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"T {self.uid}",
            slug=f"t-{self.uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"u-{self.uid}@test.com",
            password="pass",
            tenant=self.tenant,
            status="ACTIVE",
        )
        self.webhook = Webhook.objects.create(
            tenant=self.tenant,
            name=f"WH {self.uid}",
            url="https://subscriber.example.com/hooks",
            secret="legacy-plaintext-secret",
            event_types=[WebhookEventType.CONTRACT_CREATED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        # Async delivery MUST stay ON for these tests. The contract
        # being pinned is the rate-limit decision at ``trigger_webhook``
        # time: allowed → row created with ``status=PENDING`` (then a
        # worker would deliver), blocked → ``status=RATE_LIMITED`` +
        # no dispatch. With async OFF, ``_attempt_delivery`` runs
        # synchronously inside ``trigger_webhook`` and tries a real
        # HTTPS POST to ``https://subscriber.example.com/hooks`` —
        # which fails (DNS) and rewrites the row to ``FAILED`` before
        # the test can observe ``PENDING``. The test harness has no
        # RQ worker so the on-commit task never fires, leaving rows
        # in ``PENDING`` exactly where the contract pins them.
        from django.test.utils import override_settings

        self._override = override_settings(WEBHOOK_ASYNC_DELIVERY=True)
        self._override.enable()

    def tearDown(self) -> None:
        self._override.disable()
        # Clean up any Redis counter keys this tenant's tests may have
        # written so a re-run starts fresh (and so a parallel test
        # against a different tenant doesn't see stale keys for OUR
        # tenant in a flaky way).
        try:
            from hub.apps.api.middleware.idempotency_utils import (
                get_redis_client,
            )

            client = get_redis_client()
            for key in client.scan_iter(match=f"webhook:outbound:{self.tenant.id}:*"):
                client.delete(key)
        except Exception:  # pragma: no cover
            pass

    def _trigger_one(self) -> None:
        """Trigger a single webhook delivery against this tenant's webhook."""
        from hub.apps.webhooks.service import WebhookDeliveryService

        WebhookDeliveryService.trigger_webhook(
            tenant_id=str(self.tenant.id),
            event_type=WebhookEventType.CONTRACT_CREATED,
            resource_type="CONTRACT",
            resource_id=str(uuid.uuid4()),
            event_data={"event_id": str(uuid.uuid4())},
        )


# ---------------------------------------------------------------------------
# REQ-WH-RL-001 — Tenant field + default
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestTenantField(_RateLimitTestBase):
    """Pins REQ-WH-RL-001 (per-tenant field + default)."""

    @pytest.mark.integration
    def test_default_value_is_300_on_new_tenants(self) -> None:
        """Newly-created tenants have ``webhook_outbound_rate_limit_per_minute=300``."""
        fresh = Tenant.objects.create(
            name=f"Fresh {uuid.uuid4().hex[:6]}",
            slug=f"fresh-{uuid.uuid4().hex[:6]}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        self.assertEqual(fresh.webhook_outbound_rate_limit_per_minute, 300)

    @pytest.mark.integration
    def test_field_settable_to_custom_value(self) -> None:
        """Operators can set a custom per-tenant cap."""
        self.tenant.webhook_outbound_rate_limit_per_minute = 600
        self.tenant.save(update_fields=["webhook_outbound_rate_limit_per_minute"])

        reloaded = Tenant.objects.get(pk=self.tenant.pk)
        self.assertEqual(reloaded.webhook_outbound_rate_limit_per_minute, 600)


# ---------------------------------------------------------------------------
# REQ-WH-RL-001 Scenario 3 — Kill-switch at 0
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestKillSwitch(_RateLimitTestBase):
    """Pins REQ-WH-RL-001 Scenario 3 (limit=0 disables outbound)."""

    @pytest.mark.integration
    def test_zero_limit_blocks_all_deliveries(self) -> None:
        """Setting the limit to 0 marks every delivery RATE_LIMITED."""
        _redis_or_skip()
        self.tenant.webhook_outbound_rate_limit_per_minute = 0
        self.tenant.save(update_fields=["webhook_outbound_rate_limit_per_minute"])

        self._trigger_one()

        delivery = WebhookDelivery.objects.filter(webhook=self.webhook).first()
        self.assertIsNotNone(delivery)
        self.assertEqual(delivery.status, DeliveryStatus.RATE_LIMITED)
        # No HTTP attempt — fields that the dispatcher would populate
        # remain NULL.
        self.assertIsNone(delivery.http_status_code)
        self.assertIsNone(delivery.delivered_at)


# ---------------------------------------------------------------------------
# REQ-WH-RL-002 — Redis INCR enforcement
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestRedisCounterEnforcement(_RateLimitTestBase):
    """Pins REQ-WH-RL-002 (Redis INCR + 90s TTL + minute bucket)."""

    @pytest.mark.integration
    def test_delivery_at_limit_is_allowed(self) -> None:
        """Deliveries 1..N where N=limit are NOT rate-limited."""
        _redis_or_skip()
        self.tenant.webhook_outbound_rate_limit_per_minute = 2
        self.tenant.save(update_fields=["webhook_outbound_rate_limit_per_minute"])

        self._trigger_one()
        self._trigger_one()

        statuses = list(
            WebhookDelivery.objects.filter(webhook=self.webhook)
            .order_by("created_at")
            .values_list("status", flat=True)
        )
        self.assertEqual(statuses, [DeliveryStatus.PENDING, DeliveryStatus.PENDING])

    @pytest.mark.integration
    def test_delivery_above_limit_is_rate_limited(self) -> None:
        """REQ-WH-RL-002 Scenario 1 — the (limit+1)th delivery is RATE_LIMITED."""
        _redis_or_skip()
        self.tenant.webhook_outbound_rate_limit_per_minute = 2
        self.tenant.save(update_fields=["webhook_outbound_rate_limit_per_minute"])

        self._trigger_one()
        self._trigger_one()
        self._trigger_one()  # The 3rd — exceeds limit of 2

        statuses = list(
            WebhookDelivery.objects.filter(webhook=self.webhook)
            .order_by("created_at")
            .values_list("status", flat=True)
        )
        self.assertEqual(
            statuses,
            [DeliveryStatus.PENDING, DeliveryStatus.PENDING, DeliveryStatus.RATE_LIMITED],
        )

    @pytest.mark.integration
    def test_counter_resets_at_minute_boundary(self) -> None:
        """REQ-WH-RL-002 Scenario 2 — deleting the bucket key (simulating
        clock-advance to the next minute) lets a delivery proceed."""
        client = _redis_or_skip()
        self.tenant.webhook_outbound_rate_limit_per_minute = 1
        self.tenant.save(update_fields=["webhook_outbound_rate_limit_per_minute"])

        self._trigger_one()  # count=1, allowed
        self._trigger_one()  # count=2, blocked

        # Simulate the minute-boundary by deleting all per-tenant keys.
        for key in client.scan_iter(match=f"webhook:outbound:{self.tenant.id}:*"):
            client.delete(key)

        self._trigger_one()  # count=1 again, allowed

        statuses = list(
            WebhookDelivery.objects.filter(webhook=self.webhook)
            .order_by("created_at")
            .values_list("status", flat=True)
        )
        self.assertEqual(
            statuses,
            [DeliveryStatus.PENDING, DeliveryStatus.RATE_LIMITED, DeliveryStatus.PENDING],
        )

    @pytest.mark.integration
    def test_counter_ttl_is_90_seconds(self) -> None:
        """REQ-WH-RL-002 Scenario 3 — Redis sets a 90-second TTL on the bucket."""
        client = _redis_or_skip()
        self.tenant.webhook_outbound_rate_limit_per_minute = 100
        self.tenant.save(update_fields=["webhook_outbound_rate_limit_per_minute"])

        self._trigger_one()

        # Find the bucket key for this tenant + check its TTL.
        keys = list(client.scan_iter(match=f"webhook:outbound:{self.tenant.id}:*"))
        self.assertEqual(len(keys), 1)
        ttl = client.ttl(keys[0])
        # TTL within (0, 90] window — Redis MAY return 90 OR slightly
        # less depending on round-trip timing.
        self.assertGreater(ttl, 0)
        self.assertLessEqual(ttl, 90)

    @pytest.mark.integration
    def test_minute_bucket_key_format(self) -> None:
        """The Redis key format is ``webhook:outbound:{tenant_id}:{YYYY-MM-DDTHH:MM}``."""

        client = _redis_or_skip()
        self.tenant.webhook_outbound_rate_limit_per_minute = 100
        self.tenant.save(update_fields=["webhook_outbound_rate_limit_per_minute"])

        self._trigger_one()

        keys = list(client.scan_iter(match=f"webhook:outbound:{self.tenant.id}:*"))
        self.assertEqual(len(keys), 1)
        key = keys[0].decode() if isinstance(keys[0], bytes) else keys[0]

        # Format:  webhook:outbound:<uuid>:<YYYY-MM-DDTHH:MM>
        pattern = (
            r"^webhook:outbound:"
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}:"
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$"
        )
        self.assertRegex(key, pattern)

    @pytest.mark.integration
    def test_concurrent_incrs_see_consistent_post_increment_counts(
        self,
    ) -> None:
        """REQ-WH-RL-002 Scenario 4 — atomic INCR semantics.

        Two threads that concurrently call ``check_outbound_rate_limit``
        against the same tenant + minute bucket MUST see distinct
        post-increment counts (one gets N, the other N+1; never both
        get N). Pins the load-bearing atomicity guarantee that lets
        rate-limiting work without an application-level lock.
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        from django.db import connections

        from hub.apps.webhooks.rate_limit import check_outbound_rate_limit

        _redis_or_skip()
        self.tenant.webhook_outbound_rate_limit_per_minute = 1_000_000
        self.tenant.save(update_fields=["webhook_outbound_rate_limit_per_minute"])

        def _one_check():
            try:
                return check_outbound_rate_limit(self.tenant)
            finally:
                # Thread-local DB connection cleanup — Django opens a
                # new connection per thread; close it so the test
                # harness doesn't leak connections.
                connections.close_all()

        # Run 8 concurrent check_outbound_rate_limit calls. Each call
        # does ONE INCR on the same key. Atomic semantics imply the
        # 8 returned counts MUST be a contiguous run of integers
        # (e.g. 1..8 or whatever the starting count was).
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(_one_check) for _ in range(8)]
            results = [f.result() for f in as_completed(futures)]

        observed_counts = sorted(r[1] for r in results)
        # No two calls saw the same count.
        self.assertEqual(len(observed_counts), len(set(observed_counts)))
        # The counts are a contiguous run.
        first, last = observed_counts[0], observed_counts[-1]
        self.assertEqual(observed_counts, list(range(first, last + 1)))


# ---------------------------------------------------------------------------
# REQ-WH-RL-003 — RATE_LIMITED is terminal
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestRateLimitedIsTerminal(_RateLimitTestBase):
    """Pins REQ-WH-RL-003 (RATE_LIMITED is terminal; retry suppressed)."""

    @pytest.mark.integration
    def test_process_pending_deliveries_skips_rate_limited_rows(self) -> None:
        """The retry scheduler does NOT pick up RATE_LIMITED rows."""
        _redis_or_skip()
        from hub.apps.webhooks.service import WebhookDeliveryService

        # Persist a RATE_LIMITED row directly so the test doesn't depend
        # on Redis behaviour for the assertion.
        rate_limited = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=WebhookEventType.CONTRACT_CREATED,
            payload={},
            signature="x",
            status=DeliveryStatus.RATE_LIMITED,
            attempt_number=0,
        )

        # The retry scheduler at process_pending_deliveries filters by
        # status__in=[PENDING, FAILED] — RATE_LIMITED MUST NOT be in
        # the picked-up set.
        WebhookDeliveryService.process_pending_deliveries(limit=10)
        rate_limited.refresh_from_db()
        self.assertEqual(
            rate_limited.status,
            DeliveryStatus.RATE_LIMITED,
            "RATE_LIMITED delivery must not be picked up by retry scheduler",
        )

    @pytest.mark.integration
    def test_manual_retry_rejects_rate_limited_rows(self) -> None:
        """``WebhookDeliveryService.retry_delivery`` returns False for RATE_LIMITED."""
        _redis_or_skip()
        from hub.apps.webhooks.service import WebhookDeliveryService

        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=WebhookEventType.CONTRACT_CREATED,
            payload={},
            signature="x",
            status=DeliveryStatus.RATE_LIMITED,
            attempt_number=0,
        )
        success = WebhookDeliveryService.retry_delivery(str(delivery.id))
        self.assertFalse(success)

        # The row is still RATE_LIMITED — retry_delivery did not transition it.
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, DeliveryStatus.RATE_LIMITED)


# ---------------------------------------------------------------------------
# REQ-WH-RL-004 — Audit emission
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestRateLimitAudit(_RateLimitTestBase):
    """Pins REQ-WH-RL-004 (transactional audit + structured metadata)."""

    @pytest.mark.integration
    def test_rate_limited_delivery_emits_audit_event(self) -> None:
        """Each RATE_LIMITED transition emits ``WEBHOOK_RATE_LIMIT_EXCEEDED``."""
        _redis_or_skip()
        self.tenant.webhook_outbound_rate_limit_per_minute = 1
        self.tenant.save(update_fields=["webhook_outbound_rate_limit_per_minute"])

        before = AuditEvent.objects.filter(
            action="WEBHOOK_RATE_LIMIT_EXCEEDED",
            resource_id=str(self.webhook.id),
        ).count()

        self._trigger_one()  # allowed
        self._trigger_one()  # blocked → audit row #1

        after = AuditEvent.objects.filter(
            action="WEBHOOK_RATE_LIMIT_EXCEEDED",
            resource_id=str(self.webhook.id),
        ).count()
        self.assertEqual(after - before, 1)

    @pytest.mark.integration
    def test_audit_metadata_carries_required_fields(self) -> None:
        """REQ-WH-RL-004 structured shape: tenant_id, webhook_id, delivery_id,
        event_type, observed_count, limit, minute_bucket."""
        _redis_or_skip()
        self.tenant.webhook_outbound_rate_limit_per_minute = 1
        self.tenant.save(update_fields=["webhook_outbound_rate_limit_per_minute"])

        self._trigger_one()  # allowed
        self._trigger_one()  # blocked

        audit = (
            AuditEvent.objects.filter(action="WEBHOOK_RATE_LIMIT_EXCEEDED").order_by("-id").first()
        )
        self.assertIsNotNone(audit)
        # The canonical AuditEvent metadata attribute is ``details_json``
        # (see hub/apps/audit/models.py:69 — the field on the model is
        # ``details_json = models.JSONField(...)``); ``audit.details``
        # is NOT a property + would raise AttributeError. 233.3.R1
        # GAP-B caught this; the equivalent line in
        # ``test_signing_rotation.py`` was fixed in the same audit.
        details = audit.details_json or {}
        # All required keys present.
        for key in (
            "tenant_id",
            "webhook_id",
            "delivery_id",
            "event_type",
            "observed_count",
            "limit",
            "minute_bucket",
        ):
            self.assertIn(key, details, f"missing key {key} in audit details")
        # Limit is 1 (the value we set on the tenant).
        self.assertEqual(details.get("limit"), 1)
        # Observed count for the BLOCKED delivery is 2 (the post-INCR
        # count that exceeded the limit of 1).
        self.assertEqual(details.get("observed_count"), 2)
        # Event type matches.
        self.assertEqual(details.get("event_type"), WebhookEventType.CONTRACT_CREATED)
        # Bucket format YYYY-MM-DDTHH:MM (sanity check).
        self.assertRegex(
            str(details.get("minute_bucket", "")),
            r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$",
        )


# ---------------------------------------------------------------------------
# REQ-WH-RL-005 — Prometheus counter
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestPrometheusCounter(_RateLimitTestBase):
    """Pins REQ-WH-RL-005 (counter increments on rate-limit hit)."""

    @pytest.mark.integration
    def test_counter_increments_on_rate_limit_hit(self) -> None:
        """``meshant_webhook_rate_limit_blocks_total`` increments by 1 per block."""
        _redis_or_skip()
        from hub.apps.webhooks.rate_limit import (
            webhook_rate_limit_blocks_total,
        )

        self.tenant.webhook_outbound_rate_limit_per_minute = 1
        self.tenant.save(update_fields=["webhook_outbound_rate_limit_per_minute"])

        # Read the counter before the block. Use ``_value.get()`` for
        # the prometheus_client Counter primitive; for the stub fallback
        # there's no value to read so the test skips gracefully.
        labelled = webhook_rate_limit_blocks_total.labels(
            tenant_id=str(self.tenant.id),
            webhook_id=str(self.webhook.id),
            event_type=WebhookEventType.CONTRACT_CREATED,
        )
        try:
            before = labelled._value.get()  # type: ignore[attr-defined]  # test: edge-case type exercise
        except AttributeError:
            self.skipTest("prometheus_client not installed; counter is a stub")

        self._trigger_one()  # allowed (count=1)
        self._trigger_one()  # blocked (count=2 > 1) → counter +1

        after = labelled._value.get()  # type: ignore[attr-defined]  # test: edge-case type exercise
        self.assertEqual(after - before, 1)

    @pytest.mark.integration
    def test_counter_does_not_increment_on_allowed_delivery(self) -> None:
        """Allowed deliveries DO NOT bump the rate-limit-blocks counter."""
        _redis_or_skip()
        from hub.apps.webhooks.rate_limit import (
            webhook_rate_limit_blocks_total,
        )

        self.tenant.webhook_outbound_rate_limit_per_minute = 100
        self.tenant.save(update_fields=["webhook_outbound_rate_limit_per_minute"])

        labelled = webhook_rate_limit_blocks_total.labels(
            tenant_id=str(self.tenant.id),
            webhook_id=str(self.webhook.id),
            event_type=WebhookEventType.CONTRACT_CREATED,
        )
        try:
            before = labelled._value.get()  # type: ignore[attr-defined]  # test: edge-case type exercise
        except AttributeError:
            self.skipTest("prometheus_client not installed; counter is a stub")

        self._trigger_one()  # allowed — counter must not bump

        after = labelled._value.get()  # type: ignore[attr-defined]  # test: edge-case type exercise
        self.assertEqual(after - before, 0)
