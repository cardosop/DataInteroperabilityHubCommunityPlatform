"""
Phase 250.1.G review-pass — AssetService webhook event emission.

The original 250.1.G work wired ``asset.created`` + ``asset.activated``
into the ``AssetCreationWorkflow``. The review pass discovered that
the **simple API paths** through ``AssetService`` (used by
``POST /assets/``, ``PATCH /assets/{id}``, ``DELETE /assets/{id}``)
bypass the workflow and were NOT firing any webhook events. The
runbook had silently claimed they did. This file pins the correct
contract:

* ``AssetService.create_asset`` fires ``asset.created`` on commit.
* ``AssetService.update_asset`` fires ``asset.updated`` on commit;
  if the update transitions ``status`` to ``ACTIVE``, ALSO fires
  ``asset.activated`` (in registration order:
  ``updated`` → ``activated``).
* ``AssetService.delete_asset`` (soft-delete to RETIRED) fires
  ``asset.retired`` on commit.

Tests use the real EventBus via the ``@override_settings`` knob to
trigger synchronous persistence so the events are queryable from
the ``Event`` table immediately after commit. No business-logic
mocking — we exercise the real AssetService against real DB rows.
"""

from __future__ import annotations

import contextlib
import uuid
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.assets.services import AssetService
from hub.apps.core.events.models import Event
from hub.apps.core.services.base import ValidationError
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


def _seed():
    uid = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"Tenant {uid}",
        slug=f"tenant-{uid}",
        status="ACTIVE",
        kyc_status="UNVERIFIED",
    )
    ensure_tenant_has_active_subscription(tenant)
    user = User.objects.create_user(
        email=f"user-{uid}@example.com",
        password="testpass123",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )
    return tenant, user


class _OnCommitImmediateMixin:
    """Mixin: patches ``transaction.on_commit`` to fire its callback
    immediately so Event rows are queryable within TestCase."""

    def setUp(self):
        super().setUp()
        self.__oc_patch = patch(
            "hub.apps.assets.services.transaction.on_commit",
            side_effect=lambda func, *a, **kw: func(),
        )
        self.__oc_patch.start()

    def tearDown(self):
        self.__oc_patch.stop()
        super().tearDown()


@override_settings(
    EVENT_BUS_ENABLE_PERSISTENCE=True,
    EVENT_BUS_ASYNC_PERSISTENCE=False,
)
class AssetServiceCreateAssetEventTest(_OnCommitImmediateMixin, TestCase):
    """``AssetService.create_asset`` MUST fire ``asset.created`` on commit."""

    def test_create_asset_fires_asset_created_event(self):
        tenant, user = _seed()
        before = Event.objects.filter(event_type="asset.created", tenant_id=tenant.id).count()

        service = AssetService(tenant_id=str(tenant.id), user_id=str(user.id))
        asset = service.create_asset(
            tenant_id=str(tenant.id),
            user_id=str(user.id),
            key=f"webhook-{uuid.uuid4().hex[:6]}",
            name="Webhook Test Asset",
            domain="testing",
        )

        after = list(
            Event.objects.filter(event_type="asset.created", tenant_id=tenant.id).order_by(
                "timestamp"
            )
        )
        assert len(after) - before == 1, (
            f"expected exactly 1 asset.created event from "
            f"AssetService.create_asset; got {len(after) - before}"
        )
        ev = after[-1]
        assert ev.data["asset_id"] == str(asset.id)
        assert ev.data["name"] == "Webhook Test Asset"
        assert ev.data["domain"] == "testing"
        # New assets always start in DRAFT regardless of caller intent.
        assert ev.data["status"] == AssetStatus.DRAFT

    def test_create_asset_validation_failure_emits_no_event(self):
        """A validation failure (e.g., duplicate key) MUST NOT emit a stray event."""
        tenant, user = _seed()
        # Pre-create an asset so the next create_asset hits the
        # duplicate-key conflict path.
        Asset.objects.create(tenant=tenant, key="dup-key", name="A")
        before = Event.objects.filter(event_type="asset.created", tenant_id=tenant.id).count()

        service = AssetService(tenant_id=str(tenant.id), user_id=str(user.id))
        from hub.apps.core.services.base import ConflictError

        with pytest.raises(ConflictError):
            service.create_asset(
                tenant_id=str(tenant.id),
                user_id=str(user.id),
                key="dup-key",
                name="Duplicate",
            )

        after = Event.objects.filter(event_type="asset.created", tenant_id=tenant.id).count()
        assert after == before, (
            "asset.created event leaked despite duplicate-key conflict; "
            "the on_commit registration must be discarded by the "
            "atomic block's rollback."
        )


@override_settings(
    EVENT_BUS_ENABLE_PERSISTENCE=True,
    EVENT_BUS_ASYNC_PERSISTENCE=False,
)
class AssetServiceUpdateAssetEventTest(_OnCommitImmediateMixin, TestCase):
    """``AssetService.update_asset`` MUST fire ``asset.updated`` (and
    ``asset.activated`` on a status→ACTIVE transition)."""

    def test_update_asset_fires_asset_updated_event(self):
        tenant, user = _seed()
        asset = Asset.objects.create(tenant=tenant, key="upd", name="U", status=AssetStatus.DRAFT)
        before = Event.objects.filter(event_type="asset.updated", tenant_id=tenant.id).count()

        service = AssetService(tenant_id=str(tenant.id), user_id=str(user.id))
        service.update_asset(
            asset_id=str(asset.id),
            tenant_id=str(tenant.id),
            description="Updated description",
        )

        after = list(
            Event.objects.filter(
                event_type="asset.updated",
                tenant_id=tenant.id,
                data__asset_id=str(asset.id),
            ).order_by("timestamp")
        )
        assert len(after) - before == 1
        ev = after[-1]
        assert ev.data["asset_id"] == str(asset.id)
        # ``changes.fields`` should list the fields that were updated.
        assert "description" in ev.data["changes"]["fields"]

    def test_update_asset_status_to_active_fires_both_updated_and_activated(self):
        """A status transition to ACTIVE fires BOTH events in order."""
        from hub.apps.contracts.models import (
            Contract,
            ContractStatus,
            NormalizationStatus,
            OriginalFormat,
            OriginalSpecType,
            ValidationStatus,
        )

        tenant, user = _seed()
        asset = Asset.objects.create(
            tenant=tenant,
            key="act-via-update",
            name="Activate via update",
            status=AssetStatus.DRAFT,
        )
        # Activation needs an ACTIVE contract per business rules; seed one.
        Contract.objects.create(
            tenant=tenant,
            asset=asset,
            version=1,
            status=ContractStatus.ACTIVE,
            validation_status=ValidationStatus.VALID,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw="{}",
            hub_contract_version="1.0.0",
            hub_contract_json={"id": "test", "name": "n"},
            normalization_status=NormalizationStatus.NORMALIZED_OK,
        )

        service = AssetService(tenant_id=str(tenant.id), user_id=str(user.id))
        # The test seeds an ACTIVE contract with VALID validation status,
        # so the activation business rules must pass. If they don't, the
        # test fails explicitly rather than silently swallowing the error
        # and falling through to a vacuous pass.
        service.update_asset(
            asset_id=str(asset.id),
            tenant_id=str(tenant.id),
            status=AssetStatus.ACTIVE,
        )

        asset.refresh_from_db()

        updated_evs = list(
            Event.objects.filter(
                event_type="asset.updated",
                tenant_id=tenant.id,
                data__asset_id=str(asset.id),
            ).order_by("timestamp")
        )
        activated_evs = list(
            Event.objects.filter(
                event_type="asset.activated",
                tenant_id=tenant.id,
                data__asset_id=str(asset.id),
            ).order_by("timestamp")
        )

        # Activation must have succeeded — both events MUST be present.
        self.assertEqual(
            asset.status,
            AssetStatus.ACTIVE,
            "Asset status must be ACTIVE after successful update.",
        )
        self.assertTrue(updated_evs, "asset.updated event missing after successful activation")
        self.assertTrue(
            activated_evs, "asset.activated event missing after successful activation"
        )
        self.assertLessEqual(
            updated_evs[-1].timestamp,
            activated_evs[-1].timestamp,
            "asset.updated MUST fire BEFORE asset.activated",
        )
        # Activation event should carry the gate snapshot.
        self.assertIn("dq_status", activated_evs[-1].data)
        self.assertIn("compliance_status", activated_evs[-1].data)


@override_settings(
    EVENT_BUS_ENABLE_PERSISTENCE=True,
    EVENT_BUS_ASYNC_PERSISTENCE=False,
)
class AssetServiceDeleteAssetEventTest(_OnCommitImmediateMixin, TestCase):
    """``AssetService.delete_asset`` (soft-delete to RETIRED) MUST fire
    ``asset.retired`` on commit."""

    def test_delete_asset_fires_asset_retired_event(self):
        tenant, user = _seed()
        asset = Asset.objects.create(tenant=tenant, key="del", name="D", status=AssetStatus.DRAFT)
        before = Event.objects.filter(event_type="asset.retired", tenant_id=tenant.id).count()

        service = AssetService(tenant_id=str(tenant.id), user_id=str(user.id))
        # DRAFT → RETIRED is a valid transition for delete; the service
        # must succeed. If business rules reject, the test fails explicitly.
        service.delete_asset(
            asset_id=str(asset.id),
            tenant_id=str(tenant.id),
        )

        after = Event.objects.filter(
            event_type="asset.retired",
            tenant_id=tenant.id,
            data__asset_id=str(asset.id),
        ).count()
        asset.refresh_from_db()
        self.assertEqual(
            asset.status,
            AssetStatus.RETIRED,
            "Asset must be RETIRED after successful delete.",
        )
        self.assertEqual(
            after - before,
            1,
            f"delete succeeded (status=RETIRED) but got {after - before} "
            f"asset.retired events — expected exactly 1.",
        )
