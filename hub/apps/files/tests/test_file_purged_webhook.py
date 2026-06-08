"""
Phase 260.7.G — ``file.purged`` webhook + audit event tests
(closes pass-3 B3-14).

Phase 0 audit (260.7.G.1): ``grep -r "fire_webhook" hub/apps/files/``
returned ZERO hits — the files app emitted file events to the
internal event bus only (``file.created``, ``file.updated``,
``file.deleted``, ``file.uploaded``, ``file.downloaded`` via
``FileEventPublisher``) and never fanned them out as webhooks. The
existing publishers do NOT trigger ``WebhookDeliveryService.trigger_webhook``;
external HTTP subscribers had no path to subscribe to file lifecycle.

P1 (260.7.G.2): ``file.purged`` is the FIRST file event registered
for external webhook subscription. Distinct semantic from
``file.deleted``:

* ``file.deleted`` (NOT registered for webhooks) — soft-delete:
  status flips to DELETING, file enters grace window, blob still
  in S3, blob fetch still works for the grace duration.
* ``file.purged`` (THIS event) — hard-delete after grace: S3 object
  deleted, DB row gone, ``Dataset.file_id`` SET_NULL, linked datasets
  transitioned to RETIRED via the ``pre_delete`` signal. External
  subscribers should run cleanup that wasn't safe during the grace
  window — cascading deletes in CRM / downstream warehouses,
  archive-to-cold-storage triggers.

Tests pin three contracts:

1. **Enum registration.** ``WebhookEventType.FILE_PURGED == "file.purged"``
   is in the enum's choices so the public ``POST /api/v1/webhooks/``
   endpoint accepts it as a subscribable event type. A future PR that
   removes / renames it would fail this test before any subscriber
   regression surfaces.

2. **Publisher contract.** ``FileEventPublisher.publish_file_purged(...)``
   (a) emits ``file.purged`` to the internal event bus AND (b)
   triggers ``WebhookDeliveryService.trigger_webhook`` for any active
   subscriber whose ``event_types`` includes ``file.purged``. The
   "two emission paths fan out from one call" pattern mirrors
   ``DataMeshEventPublisher._trigger_webhook_for_event``.

3. **End-to-end via purge command.** Running ``purge_deleted_files``
   on a soft-deleted file past its grace window produces (a) a
   ``FILE_PURGED`` audit row AND (b) a ``WebhookDelivery`` row for
   each active subscriber. Pinning both in ONE test catches the
   class of regression where the audit emission keeps working but
   the webhook trigger silently breaks.
"""
from __future__ import annotations
import pytest

import os
import uuid
from datetime import timedelta
from io import StringIO
from unittest import SkipTest

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from hub.apps.audit.models import AuditEvent
from hub.apps.files.models import File, FileScanStatus, FileStatus
from hub.apps.files.tests.test_base import FilesTestBase
from hub.apps.webhooks.models import (
    Webhook,
    WebhookDelivery,
    WebhookEventType,
    WebhookStatus,
)

pytestmark = pytest.mark.django_db(transaction=True)


def _redis_or_skip() -> None:
    """Skip when Redis is unreachable (purge command needs the lock)."""
    from hub.apps.api.middleware.idempotency_utils import get_redis_client

    try:
        get_redis_client().ping()
    except Exception as exc:  # pragma: no cover — environment-dependent
        raise SkipTest(f"Redis required: {exc}") from exc


# ---------------------------------------------------------------------------
# 260.7.G.2 — Enum registration. Pin that ``file.purged`` is in
# WebhookEventType so the public POST /webhooks/ endpoint accepts it
# as a subscribable event type.
# ---------------------------------------------------------------------------


class FilePurgedWebhookEventTypeTest(TestCase):
    """260.7.G — pin the enum-registration contract."""

    @pytest.mark.integration
    def test_file_purged_is_in_webhook_event_type_enum(self):
        self.assertEqual(
            WebhookEventType.FILE_PURGED.value,
            "file.purged",
            "260.7.G contract: WebhookEventType.FILE_PURGED == 'file.purged'",
        )

    @pytest.mark.integration
    def test_file_purged_is_in_choices(self):
        choices = {value for value, _label in WebhookEventType.choices}
        self.assertIn(
            "file.purged",
            choices,
            "260.7.G contract: 'file.purged' must be in WebhookEventType.choices "
            "so the POST /webhooks/ serializer accepts it",
        )


# ---------------------------------------------------------------------------
# 260.7.G — Publisher contract.
#
# Two emission paths from one call:
#   * Internal event bus (EventPublisher.publish)
#   * External webhook (WebhookDeliveryService.trigger_webhook → WebhookDelivery row)
# ---------------------------------------------------------------------------


class FilePurgedPublisherContractTest(FilesTestBase):
    """260.7.G — pin that publish_file_purged emits BOTH paths."""

    def _seed_subscriber(self, event_types: list[str]) -> Webhook:
        """Seed an active webhook subscription for this tenant."""
        return Webhook.objects.create(
            tenant=self.tenant,
            name="test-subscriber",
            url="https://example.invalid/hook",
            secret="test-secret-32chars-min-len-please",
            event_types=event_types,
            status=WebhookStatus.ACTIVE,
            max_retries=5,
            retry_intervals=[1, 5, 30, 300, 1800],
        )

    @pytest.mark.integration
    def test_publish_file_purged_creates_webhook_delivery_for_subscriber(self):
        """``publish_file_purged`` triggers a WebhookDelivery row for
        every active subscriber whose event_types include 'file.purged'.
        """
        webhook = self._seed_subscriber(event_types=["file.purged"])
        before_deliveries = WebhookDelivery.objects.filter(webhook=webhook).count()

        from hub.apps.files.services import FileService

        file_id = uuid.uuid4()
        service = FileService(tenant_id=str(self.tenant.id))
        event_id = service.publish_file_purged(
            file_id=str(file_id),
            name="purged.csv",
            size=1024,
            content_sha256="a" * 64,
            tenant_id=str(self.tenant.id),
        )

        self.assertIsInstance(event_id, str)
        self.assertGreater(len(event_id), 0)

        after_deliveries = WebhookDelivery.objects.filter(webhook=webhook).count()
        self.assertEqual(
            after_deliveries - before_deliveries, 1,
            "260.7.G contract: file.purged subscribe must produce exactly one "
            f"WebhookDelivery; got delta={after_deliveries - before_deliveries}",
        )
        delivery = WebhookDelivery.objects.filter(webhook=webhook).order_by(
            "-created_at"
        ).first()
        self.assertEqual(delivery.event_type, "file.purged")
        self.assertEqual(delivery.payload["resource_type"], "FILE")
        self.assertEqual(delivery.payload["resource_id"], str(file_id))
        # The FILE-purged data envelope ('data' key in WebhookDeliveryService payload).
        data = delivery.payload.get("data", {})
        self.assertEqual(data.get("file_id"), str(file_id))
        self.assertEqual(data.get("name"), "purged.csv")
        self.assertEqual(data.get("size"), 1024)
        self.assertEqual(data.get("content_sha256"), "a" * 64)
        self.assertIn("purged_at", data)

    @pytest.mark.integration
    def test_publish_file_purged_skips_subscriber_for_other_event_type(self):
        """Regression guard: a webhook subscribed to 'asset.created'
        (NOT file.purged) must NOT receive a delivery — verifies the
        WebhookDeliveryService event-type filter actually scopes."""
        webhook = self._seed_subscriber(event_types=["asset.created"])
        before_deliveries = WebhookDelivery.objects.filter(webhook=webhook).count()

        from hub.apps.files.services import FileService

        service = FileService(tenant_id=str(self.tenant.id))
        service.publish_file_purged(
            file_id=str(uuid.uuid4()),
            name="purged.csv",
            tenant_id=str(self.tenant.id),
        )

        after_deliveries = WebhookDelivery.objects.filter(webhook=webhook).count()
        self.assertEqual(
            after_deliveries, before_deliveries,
            "subscribers without 'file.purged' in event_types must NOT receive "
            "a WebhookDelivery from publish_file_purged",
        )

    @pytest.mark.integration
    def test_publish_file_purged_skips_inactive_subscriber(self):
        """Regression guard: a webhook with status=DISABLED must NOT
        receive a delivery — verifies the active-status filter
        (``WebhookDeliveryService.trigger_webhook`` filters
        ``status=ACTIVE`` only)."""
        # Create directly with status=DISABLED to avoid double-encrypt
        # on save() (encrypt_secret runs in save()'s pre-write step).
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="disabled-subscriber",
            url="https://example.invalid/hook",
            secret="test-secret-32chars-min-len-please",
            event_types=["file.purged"],
            status=WebhookStatus.DISABLED,
            max_retries=5,
            retry_intervals=[1, 5, 30, 300, 1800],
        )
        before_deliveries = WebhookDelivery.objects.filter(webhook=webhook).count()

        from hub.apps.files.services import FileService

        service = FileService(tenant_id=str(self.tenant.id))
        service.publish_file_purged(
            file_id=str(uuid.uuid4()),
            name="purged.csv",
            tenant_id=str(self.tenant.id),
        )

        after_deliveries = WebhookDelivery.objects.filter(webhook=webhook).count()
        self.assertEqual(
            after_deliveries, before_deliveries,
            "INACTIVE subscribers must NOT receive a WebhookDelivery",
        )

    @pytest.mark.integration
    def test_publish_file_purged_skips_other_tenant_subscriber(self):
        """Regression guard: a webhook in a DIFFERENT tenant subscribed
        to 'file.purged' must NOT receive a delivery from this tenant's
        purge — verifies tenant-scoping."""
        from hub.apps.tenants.models import KYCStatus, Tenant

        other_tenant = Tenant.objects.create(
            name=f"Other-{uuid.uuid4().hex[:8]}",
            slug=f"other-{uuid.uuid4().hex[:8]}",
            kyc_status=KYCStatus.VERIFIED,
        )
        cross_webhook = Webhook.objects.create(
            tenant=other_tenant,
            name="cross-tenant",
            url="https://example.invalid/hook",
            secret="test-secret-32chars-min-len-please",
            event_types=["file.purged"],
            status=WebhookStatus.ACTIVE,
        )
        before_deliveries = WebhookDelivery.objects.filter(
            webhook=cross_webhook,
        ).count()

        from hub.apps.files.services import FileService

        service = FileService(tenant_id=str(self.tenant.id))
        service.publish_file_purged(
            file_id=str(uuid.uuid4()),
            tenant_id=str(self.tenant.id),
        )

        after_deliveries = WebhookDelivery.objects.filter(
            webhook=cross_webhook,
        ).count()
        self.assertEqual(
            after_deliveries, before_deliveries,
            "cross-tenant webhook must NOT receive a delivery",
        )


# ---------------------------------------------------------------------------
# 260.7.G — End-to-end: purge_deleted_files command emits BOTH the
# audit AND the webhook delivery.
# ---------------------------------------------------------------------------


class PurgeCommandFiresAuditAndWebhookTest(FilesTestBase):
    """260.7.G — end-to-end pin through the production cron path."""

    @pytest.mark.integration
    def test_purge_command_emits_audit_and_webhook(self):
        """Running ``purge_deleted_files`` on a soft-deleted file past
        its grace window produces BOTH a FILE_PURGED audit row AND a
        WebhookDelivery row for each active 'file.purged' subscriber.
        """
        _redis_or_skip()

        # Seed a subscriber for file.purged.
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="purge-subscriber",
            url="https://example.invalid/hook",
            secret="test-secret-32chars-min-len-please",
            event_types=["file.purged"],
            status=WebhookStatus.ACTIVE,
            max_retries=5,
            retry_intervals=[1, 5, 30, 300, 1800],
        )

        # Seed a soft-deleted file that's past the grace window.
        old = timezone.now() - timedelta(days=60)
        f = File.objects.create(
            tenant=self.tenant,
            name="purge-me.csv",
            content_type="text/csv",
            size=64,
            status=FileStatus.DELETING,
            scan_status=FileScanStatus.CLEAN,
            content_sha256="b" * 64,
            storage_path=f"{self.tenant.id}/purge-me.csv",
            deleted_at=old,
            created_by=self.user,
        )
        fid = f.id

        before_audit = AuditEvent.objects.filter(
            tenant=self.tenant, action="FILE_PURGED", resource_id=fid,
        ).count()
        before_deliveries = WebhookDelivery.objects.filter(webhook=webhook).count()

        # Force destructive-mode (mirrors test_purge_deleted_files.py:115).
        prev = os.environ.pop("FILE_PURGE_DRY_RUN_REQUIRED", None)
        try:
            out = StringIO()
            call_command(
                "purge_deleted_files",
                "--no-dry-run",
                "--tenant-id",
                str(self.tenant.id),
                stdout=out,
            )
        finally:
            if prev is not None:
                os.environ["FILE_PURGE_DRY_RUN_REQUIRED"] = prev

        self.assertIn("purged 1 file", out.getvalue())
        # File row physically gone.
        self.assertFalse(File.objects.filter(pk=fid).exists())

        # Audit emitted (existing pre-260.7.G behaviour preserved).
        after_audit = AuditEvent.objects.filter(
            tenant=self.tenant, action="FILE_PURGED", resource_id=fid,
        ).count()
        self.assertEqual(
            after_audit - before_audit, 1,
            "260.7.G must NOT regress the existing FILE_PURGED audit emission",
        )

        # Webhook delivery emitted (NEW 260.7.G contract).
        after_deliveries = WebhookDelivery.objects.filter(webhook=webhook).count()
        self.assertEqual(
            after_deliveries - before_deliveries, 1,
            "260.7.G contract: purge command MUST trigger one WebhookDelivery "
            f"per active subscriber; got delta={after_deliveries - before_deliveries}",
        )
        delivery = WebhookDelivery.objects.filter(webhook=webhook).order_by(
            "-created_at",
        ).first()
        self.assertEqual(delivery.event_type, "file.purged")
        self.assertEqual(delivery.payload["resource_type"], "FILE")
        self.assertEqual(delivery.payload["resource_id"], str(fid))
        data = delivery.payload.get("data", {})
        self.assertEqual(data.get("file_id"), str(fid))
        self.assertEqual(data.get("name"), "purge-me.csv")
        self.assertEqual(data.get("size"), 64)
        self.assertEqual(data.get("content_sha256"), "b" * 64)

    @pytest.mark.integration
    def test_gdpr_hard_purge_emits_audit_and_webhook(self):
        """Phase 260.7.G.R1 GAP-A — ``hard_purge_file_for_erasure``
        (the GDPR / offboarding hard-delete path used by
        ``delete_files_for_user`` and ``delete_files_for_tenant``
        commands) MUST emit BOTH the ``FILE_PURGED`` audit AND the
        ``file.purged`` webhook delivery. Pre-R1 only the
        ``purge_deleted_files`` cron path emitted the webhook —
        symmetric-bug class (same shape as 260.7.E.R1 GAP-A): one
        call site of FILE_PURGED audit got the webhook, the other
        didn't.

        External subscribers MUST see GDPR-driven hard-deletes the
        SAME way they see grace-period purges: a row removed via the
        right-to-erasure flow needs the same downstream cleanup
        (cascading deletes, archive triggers) that a grace-purged
        row needs. Symmetric audit emission → symmetric webhook
        emission.
        """
        from hub.apps.files.gdpr_hard_delete import hard_purge_file_for_erasure
        from hub.apps.files.storage import S3StorageClient

        # Seed a subscriber for file.purged.
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="gdpr-subscriber",
            url="https://example.invalid/hook",
            secret="test-secret-32chars-min-len-please",
            event_types=["file.purged"],
            status=WebhookStatus.ACTIVE,
            max_retries=5,
            retry_intervals=[1, 5, 30, 300, 1800],
        )

        # Seed a file to GDPR-purge. Status doesn't have to be DELETING
        # for hard_purge_file_for_erasure — that's the purge_deleted_files
        # cron's precondition; GDPR can erase from ANY state.
        f = File.objects.create(
            tenant=self.tenant,
            name="gdpr-purge-me.csv",
            content_type="text/csv",
            size=128,
            status=FileStatus.ACTIVE,
            scan_status=FileScanStatus.CLEAN,
            content_sha256="d" * 64,
            storage_path=f"{self.tenant.id}/gdpr-purge-me.csv",
            created_by=self.user,
        )
        fid = f.id

        before_audit = AuditEvent.objects.filter(
            tenant=self.tenant, action="FILE_PURGED", resource_id=fid,
        ).count()
        before_deliveries = WebhookDelivery.objects.filter(webhook=webhook).count()

        # Storage client; tolerated failure if MinIO isn't reachable
        # (S3 delete in hard_purge_file_for_erasure is wrapped in try/except).
        try:
            storage = S3StorageClient()
        except Exception:
            storage = None

        hard_purge_file_for_erasure(
            file_obj=f,
            tenant_id_str=str(self.tenant.id),
            storage=storage,
            reason="gdpr_data_subject_erasure_request",
            subject_user_id=str(self.user.id),
        )

        # File row physically gone.
        self.assertFalse(File.objects.filter(pk=fid).exists())

        # Audit emitted (existing pre-260.7.G.R1 behaviour preserved).
        after_audit = AuditEvent.objects.filter(
            tenant=self.tenant, action="FILE_PURGED", resource_id=fid,
        ).count()
        self.assertEqual(
            after_audit - before_audit, 1,
            "260.7.G.R1 must NOT regress the existing GDPR FILE_PURGED audit",
        )

        # Webhook delivery emitted (NEW 260.7.G.R1 contract — GDPR path
        # symmetric with cron path).
        after_deliveries = WebhookDelivery.objects.filter(webhook=webhook).count()
        self.assertEqual(
            after_deliveries - before_deliveries, 1,
            "260.7.G.R1: GDPR hard-purge MUST trigger one WebhookDelivery "
            f"per active subscriber; got delta={after_deliveries - before_deliveries}",
        )
        delivery = WebhookDelivery.objects.filter(webhook=webhook).order_by(
            "-created_at",
        ).first()
        assert delivery is not None  # narrow Optional[WebhookDelivery] for the asserts below
        self.assertEqual(delivery.event_type, "file.purged")
        self.assertEqual(delivery.payload["resource_type"], "FILE")
        self.assertEqual(delivery.payload["resource_id"], str(fid))
        data = delivery.payload.get("data", {})
        self.assertEqual(data.get("file_id"), str(fid))
        self.assertEqual(data.get("name"), "gdpr-purge-me.csv")

    @pytest.mark.integration
    def test_purge_command_emits_audit_when_no_subscribers(self):
        """Regression guard: purge with NO active subscribers still
        emits the audit + completes the delete (the webhook fan-out
        is best-effort observability; absence of subscribers is the
        normal case for tenants that haven't registered any).
        """
        _redis_or_skip()

        # No webhook subscribers seeded.
        old = timezone.now() - timedelta(days=60)
        f = File.objects.create(
            tenant=self.tenant,
            name="purge-no-subs.csv",
            content_type="text/csv",
            size=42,
            status=FileStatus.DELETING,
            scan_status=FileScanStatus.CLEAN,
            content_sha256="c" * 64,
            storage_path=f"{self.tenant.id}/purge-no-subs.csv",
            deleted_at=old,
            created_by=self.user,
        )
        fid = f.id
        before_audit = AuditEvent.objects.filter(
            tenant=self.tenant, action="FILE_PURGED", resource_id=fid,
        ).count()

        prev = os.environ.pop("FILE_PURGE_DRY_RUN_REQUIRED", None)
        try:
            out = StringIO()
            call_command(
                "purge_deleted_files",
                "--no-dry-run",
                "--tenant-id",
                str(self.tenant.id),
                stdout=out,
            )
        finally:
            if prev is not None:
                os.environ["FILE_PURGE_DRY_RUN_REQUIRED"] = prev

        # File purged + audit emitted regardless of subscriber presence.
        self.assertFalse(File.objects.filter(pk=fid).exists())
        self.assertEqual(
            AuditEvent.objects.filter(
                tenant=self.tenant, action="FILE_PURGED", resource_id=fid,
            ).count() - before_audit,
            1,
        )
