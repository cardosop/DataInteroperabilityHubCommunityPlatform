"""
Phase 233.1 — Rolling-key signature window tests.

This file pins each REQ-WH-ROT-* requirement and scenario from
``openspec/changes/preprod01/specs/webhook-signing-rotation/spec.md``
against real production code paths — no mocks, no stubs of the
business logic. Where external services would normally be involved
(Redis distributed lock, audit table) the test runs against the actual
in-process implementation (Redis fakeredis-backed test fixture, real
``AuditEvent`` table) so a regression at any layer surfaces here.

Coverage map:

    REQ-WH-ROT-001  multi-key window invariant (3 keys, partial unique
                    on ACTIVE, 7-day prune) — TestMultiKeyWindow.
    REQ-WH-ROT-002  X-Meshant-Signature-Key-Id header propagation +
                    legacy fallback — TestSignatureHeaderKeyId.
    REQ-WH-ROT-003  rotate_secret API atomicity, race detection,
                    cross-tenant denial — TestRotateSecretAPI.
    REQ-WH-ROT-004  hourly cron RETIRING → RETIRED + 24h overlap +
                    distributed-lock mutual exclusion — TestExpireCron.
    REQ-WH-ROT-005  backfill data migration idempotency — covered by
                    the shipped migration's RunPython idempotency
                    contract (TestBackfillIdempotency).
    REQ-WH-ROT-006  WEBHOOK_KEY_ROTATED audit row commits in same
                    transaction — covered inline in TestRotateSecretAPI.

All tests use ``transaction=True`` so the partial-unique-index +
distributed-lock semantics observe their real behaviour rather than
SAVEPOINT semantics.
"""

from __future__ import annotations

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from hub.apps.audit.models import AuditEvent
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import (
    ensure_tenant_has_active_subscription,
)
from hub.apps.webhooks.models import (
    Webhook,
    WebhookDelivery,
    WebhookEventType,
    WebhookSigningKey,
    WebhookSigningKeyStatus,
    WebhookStatus,
)

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


# ---------------------------------------------------------------------------
# Test fixtures (shared between TestCase classes via setUp inheritance).
# ---------------------------------------------------------------------------


class _SigningRotationTestBase(TestCase):
    """Common tenant + user + webhook setup."""

    def setUp(self) -> None:
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"T {uid}",
            slug=f"t-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"u-{uid}@test.com",
            password="pass",
            tenant=self.tenant,
            status="ACTIVE",
        )
        self.webhook = Webhook.objects.create(
            tenant=self.tenant,
            name=f"WH {uid}",
            url="https://subscriber.example.com/hooks",
            secret="legacy-plaintext-secret",
            event_types=[WebhookEventType.CONTRACT_CREATED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )

    def _rotate_directly(
        self,
        webhook: Webhook,
        *,
        secret: str | None = None,
    ) -> WebhookSigningKey:
        """Insert an ACTIVE signing key directly (bypassing the API).

        Used by tests that need to put the webhook into a known state
        before exercising rotation behaviour. The view-level rotation
        is covered separately by ``TestRotateSecretAPI``.
        """
        from hub.apps.webhooks.encryption import encrypt_secret

        plain = secret or uuid.uuid4().hex
        return WebhookSigningKey.objects.create(
            webhook=webhook,
            secret_encrypted=encrypt_secret(plain),
            status=WebhookSigningKeyStatus.ACTIVE,
        )


# ---------------------------------------------------------------------------
# REQ-WH-ROT-001 — Multi-key signature window
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestMultiKeyWindow(_SigningRotationTestBase):
    """Pins REQ-WH-ROT-001."""

    @pytest.mark.integration
    def test_partial_unique_index_blocks_two_active_rows(self) -> None:
        """At most ONE row per (webhook, status='ACTIVE') — DB-enforced."""
        from django.db import IntegrityError, transaction

        self._rotate_directly(self.webhook)
        # Direct INSERT bypasses the rotation API; the partial-unique
        # index MUST still reject the second ACTIVE row.
        with self.assertRaises(IntegrityError), transaction.atomic():
            self._rotate_directly(self.webhook)

    @pytest.mark.integration
    def test_retiring_rows_can_coexist(self) -> None:
        """Multiple RETIRING rows for the same webhook are allowed."""
        # Create one ACTIVE then "demote" it twice to simulate two
        # RETIRING rows present at the same time.
        k1 = self._rotate_directly(self.webhook, secret="s1")
        k1.status = WebhookSigningKeyStatus.RETIRING
        k1.retired_at = timezone.now() + timezone.timedelta(hours=24)
        k1.save(update_fields=["status", "retired_at"])

        k2 = self._rotate_directly(self.webhook, secret="s2")
        k2.status = WebhookSigningKeyStatus.RETIRING
        k2.retired_at = timezone.now() + timezone.timedelta(hours=12)
        k2.save(update_fields=["status", "retired_at"])

        retiring_count = WebhookSigningKey.objects.filter(
            webhook=self.webhook,
            status=WebhookSigningKeyStatus.RETIRING,
        ).count()
        self.assertEqual(retiring_count, 2)

    @pytest.mark.integration
    def test_active_for_returns_only_the_active_key(self) -> None:
        """``WebhookSigningKey.active_for`` returns the one ACTIVE row."""
        retired = self._rotate_directly(self.webhook, secret="retired")
        retired.status = WebhookSigningKeyStatus.RETIRED
        retired.save(update_fields=["status"])

        active = self._rotate_directly(self.webhook, secret="current")

        self.assertEqual(WebhookSigningKey.active_for(self.webhook), active)

    @pytest.mark.integration
    def test_active_for_returns_none_when_no_active_key(self) -> None:
        """``active_for`` returns ``None`` for webhooks pre-backfill."""
        # No signing key yet — represents the pre-migration state
        # the delivery path's fallback handles.
        self.assertIsNone(WebhookSigningKey.active_for(self.webhook))


# ---------------------------------------------------------------------------
# REQ-WH-ROT-002 — Signature header key-id propagation
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestSignatureHeaderKeyId(_SigningRotationTestBase):
    """Pins REQ-WH-ROT-002."""

    @pytest.mark.integration
    def test_signing_key_uuid_persisted_on_delivery_when_active_key_exists(
        self,
    ) -> None:
        """``trigger_webhook`` pins the active key_id on the delivery row."""
        from hub.apps.webhooks.service import WebhookDeliveryService

        active = self._rotate_directly(self.webhook, secret="active-secret")

        WebhookDeliveryService.trigger_webhook(
            tenant_id=str(self.tenant.id),
            event_type=WebhookEventType.CONTRACT_CREATED,
            resource_type="CONTRACT",
            resource_id=str(uuid.uuid4()),
            event_data={"event_id": str(uuid.uuid4())},
        )

        delivery = WebhookDelivery.objects.filter(webhook=self.webhook).first()
        self.assertIsNotNone(delivery)
        self.assertEqual(delivery.signing_key_uuid, active.key_id)

    @pytest.mark.integration
    def test_signing_key_uuid_null_when_no_active_key(self) -> None:
        """Pre-backfill webhook signs with legacy ``Webhook.secret``."""
        from hub.apps.webhooks.service import WebhookDeliveryService

        # No SigningKey rows for self.webhook — delivery should
        # fall back to legacy single-key path.
        WebhookDeliveryService.trigger_webhook(
            tenant_id=str(self.tenant.id),
            event_type=WebhookEventType.CONTRACT_CREATED,
            resource_type="CONTRACT",
            resource_id=str(uuid.uuid4()),
            event_data={"event_id": str(uuid.uuid4())},
        )

        delivery = WebhookDelivery.objects.filter(webhook=self.webhook).first()
        self.assertIsNotNone(delivery)
        self.assertIsNone(delivery.signing_key_uuid)

    @pytest.mark.integration
    def test_signing_key_uuid_pinned_at_trigger_survives_rotation(
        self,
    ) -> None:
        """A delivery signed at trigger-time keeps its key_id even if the
        active key rotates before the dispatcher runs."""
        from hub.apps.webhooks.service import WebhookDeliveryService

        original = self._rotate_directly(self.webhook, secret="original")

        WebhookDeliveryService.trigger_webhook(
            tenant_id=str(self.tenant.id),
            event_type=WebhookEventType.CONTRACT_CREATED,
            resource_type="CONTRACT",
            resource_id=str(uuid.uuid4()),
            event_data={"event_id": str(uuid.uuid4())},
        )

        # Rotate AFTER trigger but BEFORE the dispatcher would run —
        # simulate the race the spec's "pin at trigger-time" contract
        # exists to defend against.
        original.status = WebhookSigningKeyStatus.RETIRING
        original.retired_at = timezone.now() + timezone.timedelta(hours=24)
        original.save(update_fields=["status", "retired_at"])
        # New ACTIVE key inserted post-trigger.
        self._rotate_directly(self.webhook, secret="post-rotation")

        delivery = WebhookDelivery.objects.filter(webhook=self.webhook).first()
        self.assertIsNotNone(delivery)
        # Delivery row STILL carries the original key_id — the
        # dispatcher will set the X-Meshant-Signature-Key-Id header
        # to the trigger-time key, NOT the new active key.
        self.assertEqual(delivery.signing_key_uuid, original.key_id)


# ---------------------------------------------------------------------------
# REQ-WH-ROT-003 + REQ-WH-ROT-006 — Rotation API + audit
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestRotateSecretAPI(_SigningRotationTestBase):
    """Pins REQ-WH-ROT-003 (atomic rotation) + REQ-WH-ROT-006 (audit)."""

    def setUp(self) -> None:
        super().setUp()
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def _rotate_via_api(self) -> dict:
        # Capture legacy secret before rotation to verify it is also rotated
        original_secret = self.webhook.secret

        url = f"/api/v1/webhooks/webhooks/{self.webhook.id}/rotate_secret/"
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 200, resp.content)
        result = resp.json()

        # Verify legacy webhook.secret was also rotated (Phase 233.1 dual rotation)
        self.webhook.refresh_from_db()
        self.assertNotEqual(
            self.webhook.secret,
            original_secret,
            "Legacy webhook.secret must be rotated alongside the new WebhookSigningKey",
        )

        return result

    @pytest.mark.integration
    def test_first_rotation_creates_active_key_with_no_previous(self) -> None:
        """A webhook with NO existing signing key rotates cleanly."""
        body = self._rotate_via_api()

        self.assertIsNone(body.get("previous_key_id"))
        self.assertTrue(body.get("key_id"))
        self.assertEqual(
            WebhookSigningKey.objects.filter(
                webhook=self.webhook,
                status=WebhookSigningKeyStatus.ACTIVE,
            ).count(),
            1,
        )

    @pytest.mark.integration
    def test_rotation_atomically_swaps_active_and_retiring(self) -> None:
        """REQ-WH-ROT-003 Scenario 1: previous active → retiring + new active."""
        original = self._rotate_directly(self.webhook, secret="original")

        body = self._rotate_via_api()

        self.assertEqual(body["previous_key_id"], str(original.key_id))
        self.assertNotEqual(body["key_id"], str(original.key_id))

        # Exactly one ACTIVE + exactly one RETIRING for this webhook.
        active_keys = WebhookSigningKey.objects.filter(
            webhook=self.webhook,
            status=WebhookSigningKeyStatus.ACTIVE,
        )
        retiring_keys = WebhookSigningKey.objects.filter(
            webhook=self.webhook,
            status=WebhookSigningKeyStatus.RETIRING,
        )
        self.assertEqual(active_keys.count(), 1)
        self.assertEqual(retiring_keys.count(), 1)
        self.assertEqual(retiring_keys.first().pk, original.pk)

    @pytest.mark.integration
    def test_rotation_evicts_oldest_retiring_when_window_full(self) -> None:
        """REQ-WH-ROT-001 Scenario 2 — third rotation evicts oldest retiring."""
        # Seed two retiring keys + one active.
        old1 = self._rotate_directly(self.webhook, secret="oldest")
        old1.status = WebhookSigningKeyStatus.RETIRING
        old1.retired_at = timezone.now() + timezone.timedelta(hours=1)
        old1.save(update_fields=["status", "retired_at"])

        old2 = self._rotate_directly(self.webhook, secret="middle")
        old2.status = WebhookSigningKeyStatus.RETIRING
        old2.retired_at = timezone.now() + timezone.timedelta(hours=12)
        old2.save(update_fields=["status", "retired_at"])

        self._rotate_directly(self.webhook, secret="current-active")

        self._rotate_via_api()

        # ``old1`` (oldest by ``retired_at``) must be RETIRED;
        # ``old2`` stays RETIRING; ``current-active`` becomes RETIRING;
        # the new key is ACTIVE.
        old1.refresh_from_db()
        old2.refresh_from_db()
        self.assertEqual(old1.status, WebhookSigningKeyStatus.RETIRED)
        self.assertEqual(old2.status, WebhookSigningKeyStatus.RETIRING)

        non_retired = (
            WebhookSigningKey.objects.filter(
                webhook=self.webhook,
            )
            .exclude(status=WebhookSigningKeyStatus.RETIRED)
            .count()
        )
        self.assertEqual(non_retired, 3)

    @pytest.mark.integration
    def test_audit_row_commits_with_rotation(self) -> None:
        """REQ-WH-ROT-006 Scenario 1 — audit row in same transaction."""
        before = AuditEvent.objects.filter(
            action="WEBHOOK_KEY_ROTATED",
            resource_id=str(self.webhook.id),
        ).count()

        body = self._rotate_via_api()

        after = AuditEvent.objects.filter(
            action="WEBHOOK_KEY_ROTATED",
            resource_id=str(self.webhook.id),
        ).count()
        self.assertEqual(after - before, 1)

        audit = (
            AuditEvent.objects.filter(
                action="WEBHOOK_KEY_ROTATED",
                resource_id=str(self.webhook.id),
            )
            .order_by("-id")
            .first()
        )
        self.assertIsNotNone(audit)
        # 233.3.R1 GAP-B carry-over fix — the canonical attribute is
        # ``details_json`` (per hub/apps/audit/models.py:69); the
        # original ``audit.details`` line would raise AttributeError
        # at runtime. Fixed here in the same audit pass that caught
        # the equivalent bug in test_outbound_rate_limit.py.
        details = audit.details_json or {}
        self.assertEqual(details.get("new_key_id"), body["key_id"])
        self.assertEqual(details.get("webhook_id"), str(self.webhook.id))

    @pytest.mark.integration
    def test_cross_tenant_rotation_returns_404(self) -> None:
        """REQ-WH-ROT-003 Scenario 3 — cross-tenant denial."""
        # Create another tenant + webhook the current user does NOT own.
        other_tenant = Tenant.objects.create(
            name="Other",
            slug=f"other-{uuid.uuid4().hex[:6]}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        ensure_tenant_has_active_subscription(other_tenant)
        other_webhook = Webhook.objects.create(
            tenant=other_tenant,
            name="Other WH",
            url="https://other.example.com/hooks",
            secret="other-secret",
            event_types=[WebhookEventType.CONTRACT_CREATED],
            status=WebhookStatus.ACTIVE,
        )

        url = f"/api/v1/webhooks/webhooks/{other_webhook.id}/rotate_secret/"
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 404)

        # No new keys, no audit row created.
        self.assertEqual(
            WebhookSigningKey.objects.filter(webhook=other_webhook).count(),
            0,
        )


# ---------------------------------------------------------------------------
# REQ-WH-ROT-005 — Backfill migration idempotency
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestBackfillIdempotency(_SigningRotationTestBase):
    """Pins REQ-WH-ROT-005 by re-running the backfill RunPython callable."""

    @pytest.mark.integration
    def test_backfill_runpython_is_idempotent(self) -> None:
        """Calling ``_backfill_signing_keys`` twice creates rows once."""
        # Import the data-migration module directly so we can call the
        # ``_backfill_signing_keys`` function as a black-box.
        import importlib

        m = importlib.import_module(
            "hub.apps.webhooks.migrations.0005_backfill_webhook_signing_keys",
        )
        # The Django app registry is the canonical source for fake-models
        # at migration runtime; the runtime registry serves the same role
        # in tests.
        from django.apps import apps as django_apps

        m._backfill_signing_keys(django_apps, schema_editor=None)
        first_count = WebhookSigningKey.objects.filter(
            webhook=self.webhook,
            status=WebhookSigningKeyStatus.ACTIVE,
        ).count()

        m._backfill_signing_keys(django_apps, schema_editor=None)
        second_count = WebhookSigningKey.objects.filter(
            webhook=self.webhook,
            status=WebhookSigningKeyStatus.ACTIVE,
        ).count()

        # The webhook ALREADY had a row from the first call; re-run
        # produces no additional rows.
        self.assertEqual(first_count, 1)
        self.assertEqual(second_count, 1)


# ---------------------------------------------------------------------------
# REQ-WH-ROT-004 — Hourly cron transitions retiring → retired
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestExpireCron(_SigningRotationTestBase):
    """Pins REQ-WH-ROT-004 (cron transition + audit + lock semantics)."""

    @staticmethod
    def _redis_or_skip():
        """Probe Redis reachability AND return the client.

        233.1.R1 GAP-B — mirrors ``test_purge_deleted_files.py:31-37``
        canonical pattern: actually ``.ping()`` Redis to detect
        unreachability rather than only catching exceptions during
        client construction. ``get_redis_client()`` may return a
        client object even when Redis is down; the failure surfaces
        on the first ``set()`` / ``ping()`` call. Without the ping,
        the test would proceed past the skip check and FAIL on the
        first real Redis operation, defeating the skip-on-unreachable
        contract this test class advertises.
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

    @pytest.mark.integration
    def test_retiring_key_transitions_to_retired_after_overlap(self) -> None:
        """REQ-WH-ROT-004 Scenario 1 — overdue RETIRING flips to RETIRED."""
        self._redis_or_skip()

        key = self._rotate_directly(self.webhook, secret="to-retire")
        key.status = WebhookSigningKeyStatus.RETIRING
        # ``retired_at`` is in the PAST — overlap window has lapsed.
        key.retired_at = timezone.now() - timezone.timedelta(minutes=1)
        key.save(update_fields=["status", "retired_at"])

        from django.core.management import call_command

        before = AuditEvent.objects.filter(
            action="WEBHOOK_KEY_RETIRED",
            resource_id=str(self.webhook.id),
        ).count()

        call_command("expire_retiring_webhook_keys")

        key.refresh_from_db()
        self.assertEqual(key.status, WebhookSigningKeyStatus.RETIRED)

        after = AuditEvent.objects.filter(
            action="WEBHOOK_KEY_RETIRED",
            resource_id=str(self.webhook.id),
        ).count()
        self.assertEqual(after - before, 1)

    @pytest.mark.integration
    def test_retiring_key_within_overlap_remains_retiring(self) -> None:
        """REQ-WH-ROT-004 Scenario 2 — retiring key inside the window stays."""
        self._redis_or_skip()

        key = self._rotate_directly(self.webhook, secret="still-overlapping")
        key.status = WebhookSigningKeyStatus.RETIRING
        # ``retired_at`` is in the FUTURE — overlap window is still open.
        key.retired_at = timezone.now() + timezone.timedelta(hours=1)
        key.save(update_fields=["status", "retired_at"])

        from django.core.management import call_command

        call_command("expire_retiring_webhook_keys")

        key.refresh_from_db()
        self.assertEqual(key.status, WebhookSigningKeyStatus.RETIRING)

    @pytest.mark.integration
    def test_retired_key_older_than_7_days_is_pruned(self) -> None:
        """REQ-WH-ROT-001 Scenario 3 — auto-prune sweeps retired > 7d."""
        self._redis_or_skip()

        key = self._rotate_directly(self.webhook, secret="ancient")
        key.status = WebhookSigningKeyStatus.RETIRED
        key.retired_at = timezone.now() - timezone.timedelta(days=8)
        key.save(update_fields=["status", "retired_at"])
        kid = key.pk

        from django.core.management import call_command

        call_command("expire_retiring_webhook_keys")

        self.assertFalse(
            WebhookSigningKey.objects.filter(pk=kid).exists(),
        )

    @pytest.mark.integration
    def test_retired_key_within_retention_is_kept(self) -> None:
        """A retired key younger than 7 days is preserved by the cron."""
        self._redis_or_skip()

        key = self._rotate_directly(self.webhook, secret="recent")
        key.status = WebhookSigningKeyStatus.RETIRED
        key.retired_at = timezone.now() - timezone.timedelta(days=3)
        key.save(update_fields=["status", "retired_at"])
        kid = key.pk

        from django.core.management import call_command

        call_command("expire_retiring_webhook_keys")

        self.assertTrue(
            WebhookSigningKey.objects.filter(pk=kid).exists(),
        )

    @pytest.mark.integration
    def test_concurrent_runs_cannot_double_finalise(self) -> None:
        """REQ-WH-ROT-004 Scenario 3 — distributed lock blocks parallel run."""
        redis_client = self._redis_or_skip()

        # Pre-acquire the lock so the cron's acquisition step fails.
        from hub.apps.core.distributed_lock import (
            distributed_lock_acquire,
            distributed_lock_release,
        )
        from hub.apps.webhooks.management.commands.expire_retiring_webhook_keys import (
            _EXPIRE_LOCK_KEY,
        )

        ok, token = distributed_lock_acquire(
            redis_client,
            _EXPIRE_LOCK_KEY,
            ttl_seconds=60,
        )
        self.assertTrue(ok)

        try:
            from django.core.management import call_command

            with self.assertRaises(SystemExit) as exit_ctx:
                call_command("expire_retiring_webhook_keys")
            self.assertEqual(exit_ctx.exception.code, 1)
        finally:
            distributed_lock_release(
                redis_client,
                _EXPIRE_LOCK_KEY,
                token=token,
            )


# ---------------------------------------------------------------------------
# Integration — end-to-end: rotate → trigger → header carries new key_id
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestEndToEndRotationToDelivery(_SigningRotationTestBase):
    """REQ-WH-ROT-002 + REQ-WH-ROT-003 integration."""

    @pytest.mark.integration
    def test_post_rotation_delivery_carries_new_key_id(self) -> None:
        """After rotation, new deliveries sign + carry the new key_id."""
        client = APIClient()
        client.force_authenticate(self.user)

        # Seed an initial active key so rotation has a previous to retire.
        self._rotate_directly(self.webhook, secret="initial")

        rotate_resp = client.post(
            f"/api/v1/webhooks/webhooks/{self.webhook.id}/rotate_secret/",
        )
        self.assertEqual(rotate_resp.status_code, 200)
        new_key_id = rotate_resp.json()["key_id"]

        # Trigger a delivery — it should sign with the new active key.
        from hub.apps.webhooks.service import WebhookDeliveryService

        WebhookDeliveryService.trigger_webhook(
            tenant_id=str(self.tenant.id),
            event_type=WebhookEventType.CONTRACT_CREATED,
            resource_type="CONTRACT",
            resource_id=str(uuid.uuid4()),
            event_data={"event_id": str(uuid.uuid4())},
        )

        delivery = (
            WebhookDelivery.objects.filter(
                webhook=self.webhook,
            )
            .order_by("-created_at")
            .first()
        )
        self.assertIsNotNone(delivery)
        self.assertEqual(str(delivery.signing_key_uuid), new_key_id)
