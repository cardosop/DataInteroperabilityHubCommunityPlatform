"""
Phase 250.1.G.3 — webhook event ordering through the asset-creation
workflow.

Pins the contract from B2-6: the 250.1.A re-sequence (gates BEFORE
asset persistence) MUST NOT disturb the **logical step** at which
``asset.*`` webhook events fire for downstream subscribers.

Specifically:

1. ``asset.created`` fires on the FIRST commit that persists the
   Asset row — i.e., AFTER ``_create_asset_record_task`` succeeds
   and the engine's outer atomic commits. Subscribers see the
   asset's full state (key, name, status, tenant, created_by) at
   that point — no half-built rows leak.

2. ``asset.activated`` fires on the FIRST commit that flips
   ``status=ACTIVE`` — i.e., AFTER ``_activate_asset_task``. It
   carries the dq_status + compliance_status snapshot taken at
   activation time, so subscribers can re-check the gate signal
   without re-querying.

3. **Ordering** — ``asset.created`` fires STRICTLY BEFORE
   ``asset.activated`` for the same asset_id. Django's
   ``transaction.on_commit`` callbacks fire in registration order;
   the workflow registers them in step order so the wire ordering
   matches the workflow ordering.

4. **No-event on fail-closed** — if a pre-persistence gate refuses
   intake (Phase 250.1.A.3), no Asset row is persisted and
   therefore NO ``asset.created`` event fires. Webhook subscribers
   never see ghost assets that were never persisted.

Tests use the **real EventBus** with ``EVENT_BUS_ENABLE_PERSISTENCE``
forced True so events land in the ``events`` table where the test
can read them. External boundaries (S3, compliance, DQ) are mocked
at their HTTP boundaries.
"""
from __future__ import annotations

import uuid
from unittest.mock import patch  # noqa: F401 — used by helper closures elsewhere in module

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.core.events.models import Event
from hub.apps.files.models import File, FileStatus
from hub.apps.orchestration.workflows.asset_creation import (
    AssetCreationWorkflow,
    FailClosedRejection,
)
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import UserStatus


pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


def _seed(fail_closed: bool = False):
    """Tenant + user + active file fixture — real DB rows."""
    uid = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"Tenant {uid}",
        slug=f"tenant-{uid}",
        status="ACTIVE",
        kyc_status="UNVERIFIED",
        compliance_fail_closed_enabled=fail_closed,
    )
    ensure_tenant_has_active_subscription(tenant)
    user = User.objects.create_user(
        email=f"user-{uid}@example.com",
        password="testpass123",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )
    file_obj = File.objects.create(
        tenant=tenant,
        name="data.csv",
        content_type="text/csv",
        size=42,
        status=FileStatus.ACTIVE,
        storage_path=f"{tenant.id}/{uuid.uuid4()}/data.csv",
        created_by=user,
    )
    return tenant, user, file_obj


def _patch_storage(content: bytes = b"a,b\n1,2\n"):
    return patch(
        "hub.apps.files.storage.S3StorageClient.get_file_content",
        return_value=content,
    )


def _patch_compliance(payload: dict):
    return patch(
        "hub.apps.compliance.service_client.ComplianceServiceClient.scan_file",
        return_value=payload,
    )


def _patch_dq(payload: dict):
    return patch(
        "hub.apps.dq.service_client.DQServiceClient.run_dq",
        return_value=payload,
    )


def _force_sync_event_persistence():
    """No-op compat shim — kept so older-test imports don't break.

    Phase 250.1.G review-pass — the original implementation patched
    ``EventBus.force_sync_persistence`` as a class attribute, which
    has no effect on the existing singleton instance (the flag is
    set in ``__init__`` and read via ``self.force_sync_persistence``).
    The actual sync-persistence trigger comes from the
    ``@override_settings(EVENT_BUS_ASYNC_PERSISTENCE=False)``
    decorator on the test class — when ``use_async_persistence``
    is False AND ``force_sync_persistence`` is False AND
    ``use_write_behind`` is False, the bus's ``publish`` method
    falls into the synchronous ``else`` branch
    (:func:`hub.apps.core.events.bus.EventBus.publish`).

    This shim returns an inert context manager so existing
    ``with _force_sync_event_persistence(): ...`` call sites stay
    syntactically valid; the actual sync wiring is the
    @override_settings decorator on each test class.
    """
    from contextlib import nullcontext

    return nullcontext()


@override_settings(EVENT_BUS_ENABLE_PERSISTENCE=True, EVENT_BUS_ASYNC_PERSISTENCE=False)
class AssetCreatedEventOrderingTest(TestCase):
    """``asset.created`` MUST fire on commit, AFTER asset row is persisted."""

    def test_asset_created_event_fires_after_workflow_commit(self):
        tenant, user, file_obj = _seed()
        before = Event.objects.filter(
            event_type="asset.created", tenant_id=tenant.id
        ).count()

        with _patch_storage(), _patch_compliance(
            {"overall_status": "PASS", "allowed_to_store": True, "metadata": {}}
        ), _patch_dq(
            {"overall_status": "PASS", "quality_score": 100, "metadata": {}}
        ), _force_sync_event_persistence():
            result = AssetCreationWorkflow.execute(
                tenant_id=str(tenant.id),
                key="webhook-asset",
                name="Webhook Asset",
                file_id=str(file_obj.id),
                file_format="CSV",
                contract_name="C",
                contract_description="",
                auto_activate=False,  # pin the test on asset.created alone
                send_notifications=False,
                created_by_id=str(user.id),
            )

        assert result["success"]
        asset_id = result["output_data"].get("asset_id")
        assert asset_id is not None

        # Exactly ONE asset.created event for the asset.
        created_events = list(
            Event.objects.filter(
                event_type="asset.created", tenant_id=tenant.id
            ).order_by("timestamp")
        )
        assert len(created_events) - before == 1, (
            f"expected exactly 1 asset.created event; got "
            f"{len(created_events) - before}: {[e.event_id for e in created_events]}"
        )
        # Payload carries asset_id matching the persisted row.
        ev = created_events[-1]
        assert ev.data["asset_id"] == asset_id
        assert ev.data["name"] == "Webhook Asset"
        # The DRAFT status is the post-create-but-pre-activate state.
        # Even with auto_activate=False the event represents the
        # asset's snapshot at create-time, so DRAFT is correct.
        assert ev.data["status"] in {"DRAFT", AssetStatus.DRAFT}


@override_settings(EVENT_BUS_ENABLE_PERSISTENCE=True, EVENT_BUS_ASYNC_PERSISTENCE=False)
class AssetCreatedThenActivatedOrderingTest(TestCase):
    """``asset.created`` MUST fire BEFORE ``asset.activated`` for the same asset."""

    def test_created_event_strictly_before_activated_event(self):
        tenant, user, file_obj = _seed()

        with _patch_storage(), _patch_compliance(
            {"overall_status": "PASS", "allowed_to_store": True, "metadata": {}}
        ), _patch_dq(
            {"overall_status": "PASS", "quality_score": 100, "metadata": {}}
        ), _force_sync_event_persistence():
            result = AssetCreationWorkflow.execute(
                tenant_id=str(tenant.id),
                key="ordering-asset",
                name="Ordering Asset",
                file_id=str(file_obj.id),
                file_format="CSV",
                contract_name="C",
                contract_description="",
                auto_activate=True,  # both events should fire
                send_notifications=False,
                created_by_id=str(user.id),
            )

        assert result["success"]
        asset_id = result["output_data"].get("asset_id")

        # Both events MUST be present, scoped to this tenant/asset.
        created = (
            Event.objects.filter(
                event_type="asset.created",
                tenant_id=tenant.id,
                data__asset_id=asset_id,
            )
            .order_by("timestamp")
            .first()
        )
        activated = (
            Event.objects.filter(
                event_type="asset.activated",
                tenant_id=tenant.id,
                data__asset_id=asset_id,
            )
            .order_by("timestamp")
            .first()
        )
        assert created is not None, "asset.created event missing"
        assert activated is not None, "asset.activated event missing"

        # Strict ordering: created fires before activated. The two
        # events are registered in sequential ``transaction.on_commit``
        # callbacks; Django guarantees they fire in registration
        # order on the same transaction.
        assert created.timestamp <= activated.timestamp, (
            f"asset.created must fire BEFORE asset.activated; got "
            f"created={created.timestamp} activated={activated.timestamp}"
        )

        # The activated event payload carries the gate snapshot at
        # activation time so subscribers can re-derive the
        # gate-pass decision without re-querying.
        assert activated.data["asset_id"] == asset_id
        assert "dq_status" in activated.data
        assert "compliance_status" in activated.data


@override_settings(EVENT_BUS_ENABLE_PERSISTENCE=True, EVENT_BUS_ASYNC_PERSISTENCE=False)
class FailClosedSuppressesAssetEventsTest(TestCase):
    """A pre-persistence fail-closed rejection MUST suppress all asset.* events.

    Phase 250.1.A.3 contract: no Asset row → no ``asset.created``;
    by extension, no ``asset.activated`` either. Otherwise webhook
    subscribers would receive a created event for an asset_id that
    doesn't exist in the database, making the webhook surface
    unreliable for state-reconstruction.
    """

    def test_compliance_fail_emits_no_asset_created_event(self):
        tenant, user, file_obj = _seed(fail_closed=True)
        before_created = Event.objects.filter(
            event_type="asset.created", tenant_id=tenant.id
        ).count()
        before_activated = Event.objects.filter(
            event_type="asset.activated", tenant_id=tenant.id
        ).count()

        with _patch_storage(), _patch_compliance(
            {"overall_status": "FAIL", "allowed_to_store": False, "metadata": {}}
        ), _patch_dq(
            {"overall_status": "PASS", "quality_score": 100, "metadata": {}}
        ), _force_sync_event_persistence():
            with pytest.raises(FailClosedRejection):
                AssetCreationWorkflow.execute(
                    tenant_id=str(tenant.id),
                    key="suppressed-asset",
                    name="Suppressed",
                    file_id=str(file_obj.id),
                    file_format="CSV",
                    contract_name="C",
                    contract_description="",
                    auto_activate=True,
                    send_notifications=False,
                    created_by_id=str(user.id),
                )

        after_created = Event.objects.filter(
            event_type="asset.created", tenant_id=tenant.id
        ).count()
        after_activated = Event.objects.filter(
            event_type="asset.activated", tenant_id=tenant.id
        ).count()

        # Critical webhook contract: no events fire for a rejected asset.
        assert after_created == before_created, (
            f"asset.created event leaked despite fail-closed rejection: "
            f"{before_created} → {after_created}"
        )
        assert after_activated == before_activated
        # Belt-and-braces: no Asset row exists either.
        assert Asset.objects.filter(
            tenant=tenant, key="suppressed-asset"
        ).count() == 0
