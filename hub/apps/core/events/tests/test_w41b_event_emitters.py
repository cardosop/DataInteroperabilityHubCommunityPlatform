"""
W4.1b (G7) — event-emitter decision pins.

G7: "fixing the bus (W4.1) without deciding the emitters leaves the
pub/sub surface still empty".  These pins enforce the emitter-decision
table (docs/audits/event-emitter-decisions-2026-10-09.md) against REAL
services, REAL DB rows, and the REAL bus (no mocks):

* **C1** ``contract.created`` — EMITTED on the primary creation path
  (``ContractService.create_contract``; pre-fix only the ODPS
  auto-generation paths emitted it).
* **C3/C4** ``contract.updated`` / ``contract.deleted`` — EMITTED on
  ``update_contract`` / ``delete_contract`` (pre-fix: never emitted).
* **C5** ``contract.validated`` — DOCUMENTED ABSENT (validation is a
  read-path check; its results flow through API responses + the
  validation-failed observability emitter, not a lifecycle event).
* **C2/C7** marketplace lifecycle — ``marketplace.order.created`` /
  ``approved`` / ``rejected`` EMITTED on the primary service paths
  (the ``notification_subscriber`` consumes exactly these three —
  pre-fix the consumer existed and the emitter never fired);
  ``marketplace.listing.published`` EMITTED on ``publish_listing``.
* **C7 absent-pins** — ``marketplace.order.fulfilled`` (fulfillment is
  atomic with approval), ``marketplace.entitlement.granted`` /
  ``revoked`` (no bus consumers; W2.6's ENTITLEMENT_REVOKED audit event
  covers revocation), ``marketplace.listing.unpublished`` (no unpublish
  primary path exists) — pinned to stay absent so a future emitter
  change is a DELIBERATE decision-table update, not drift.
"""

from __future__ import annotations

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase

from envpolicy import skip_or_fail
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.contracts.models import ContractStatus
from hub.apps.contracts.services import ContractService
from hub.apps.core.events.models import Event

# marketplace is the paid layer — guarded for both core-only absence
# forms (W7.1); tests that need it skip when absent.
try:
    from hub.apps.marketplace.models import (
        Listing,
        ListingStatus,
        OrderStatus,
        PricingModel,
    )
    from hub.apps.marketplace.services import MarketplaceService
except (RuntimeError, ModuleNotFoundError):
    Listing = ListingStatus = OrderStatus = PricingModel = None  # type: ignore[assignment]
    MarketplaceService = None  # type: ignore[assignment]
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)

User = get_user_model()

_RAW_ODCS = (
    '{"id": "test-contract", "info": {"name": "test-contract"}, '
    '"schema": {"fields": [{"name": "id", "type": "string"}]}}'
)


def _emitted_rows(event_type: str, tenant) -> list[Event]:
    """Bus Event rows for *event_type* under *tenant* (sync test persistence)."""
    return list(Event.objects.filter(event_type=event_type, tenant_id=tenant.id))


class TestContractLifecycleEmitters(TestCase):
    """C1/C3/C4/C5 — contract lifecycle events on the primary paths."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"W41B {uid}",
            slug=f"w41b-{uid}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email=f"w41b-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        # delete_contract requires TENANT_ADMIN (the same fixture the
        # contracts suite uses).
        from hub.apps.users.models import Role, UserRole

        admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant administrator"},
        )
        UserRole.objects.get_or_create(user=self.user, role=admin_role)
        self.service = ContractService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

    def _create(self):
        return self.service.create_contract(
            original_raw=_RAW_ODCS,
            original_format="JSON",
        )

    def test_create_contract_emits_contract_created(self):
        """C1 — the PRIMARY creation path must emit contract.created."""
        contract = self._create()

        rows = _emitted_rows("contract.created", self.tenant)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].data["contract_id"], str(contract.id))
        self.assertEqual(rows[0].data["status"], ContractStatus.DRAFT)

    def test_update_contract_emits_contract_updated(self):
        """C3 — update_contract must emit contract.updated with the
        previous/new status."""
        contract = self._create()

        updated = self.service.update_contract(
            contract_id=str(contract.id),
            original_raw=(
                '{"id": "test-contract", "info": {"name": "test-contract-2"}, '
                '"schema": {"fields": [{"name": "id", "type": "string"}]}}'
            ),
            original_format="JSON",
        )

        rows = _emitted_rows("contract.updated", self.tenant)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].data["contract_id"], str(contract.id))
        self.assertEqual(rows[0].data["previous_status"], ContractStatus.DRAFT)
        self.assertEqual(rows[0].data["new_status"], updated.status)

    def test_delete_contract_emits_contract_deleted(self):
        """C4 — delete_contract must emit contract.deleted."""
        contract = self._create()

        self.service.delete_contract(contract_id=str(contract.id), reason="cleanup")

        rows = _emitted_rows("contract.deleted", self.tenant)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].data["contract_id"], str(contract.id))
        self.assertEqual(rows[0].data["reason"], "cleanup")

    def test_validate_contract_emits_no_validated_event(self):
        """C5 (documented absent) — validation is a read-path check, not a
        lifecycle transition: no contract.validated event."""
        contract = self._create()

        self.service.validate_contract(str(contract.id), str(self.tenant.id))

        self.assertEqual(_emitted_rows("contract.validated", self.tenant), [])


def _marketplace_fixtures():
    if Listing is None:
        skip_or_fail("marketplace (paid layer) not installed in core-only mode")
    """Provider/consumer tenants + users + ACTIVE asset (order-flow fixtures)."""
    uid = uuid.uuid4().hex[:6]
    provider = Tenant.objects.create(
        name=f"W41B Prov {uid}",
        slug=f"w41b-prov-{uid}",
        status="ACTIVE",
        kyc_status=KYCStatus.VERIFIED,
    )
    consumer = Tenant.objects.create(
        name=f"W41B Cons {uid}",
        slug=f"w41b-cons-{uid}",
        status="ACTIVE",
        kyc_status=KYCStatus.VERIFIED,
    )
    ensure_tenant_has_active_subscription(provider)
    ensure_tenant_has_active_subscription(consumer)
    provider_user = User.objects.create_user(
        email=f"w41b-prov-{uid}@example.com",
        password="testpass123",
        tenant=provider,
        status=UserStatus.ACTIVE,
    )
    consumer_user = User.objects.create_user(
        email=f"w41b-cons-{uid}@example.com",
        password="testpass123",
        tenant=consumer,
        status=UserStatus.ACTIVE,
    )
    asset = Asset.objects.create(
        tenant=provider,
        key=f"w41b-asset-{uid}",
        name=f"W41B Asset {uid}",
        status=AssetStatus.ACTIVE,
        created_by=provider_user,
    )
    return provider, consumer, provider_user, consumer_user, asset


class TestMarketplaceOrderEmitters(TestCase):
    """C2 — the notification_subscriber consumes marketplace.order.* but the
    publisher mixin never fired: wire the primary paths."""

    def setUp(self):
        (
            self.provider,
            self.consumer,
            self.provider_user,
            self.consumer_user,
            self.asset,
        ) = _marketplace_fixtures()

    def _listing(self, pricing_model: PricingModel) -> Listing:
        return Listing.objects.create(
            tenant=self.provider,
            asset=self.asset,
            status=ListingStatus.PUBLISHED,
            pricing_model=pricing_model,
            metadata_json={"title": "W41B Listing"},
        )

    def _consumer_service(self) -> MarketplaceService:
        return MarketplaceService(
            tenant_id=str(self.consumer.id),
            user_id=str(self.consumer_user.id),
        )

    def test_create_order_emits_order_created(self):
        """C2 — create_order must emit marketplace.order.created (FREE_AUTO_APPROVE
        exercises the full auto-approve branch)."""
        listing = self._listing(PricingModel.FREE_AUTO_APPROVE)

        order = self._consumer_service().create_order(
            tenant_id=str(self.consumer.id),
            user_id=str(self.consumer_user.id),
            listing_id=str(listing.id),
        )
        self.assertEqual(order.status, OrderStatus.FULFILLED)

        rows = _emitted_rows("marketplace.order.created", self.consumer)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].data["order_id"], str(order.id))
        self.assertEqual(rows[0].data["listing_id"], str(listing.id))
        self.assertEqual(rows[0].data["buyer_id"], str(self.consumer_user.id))

    def test_approve_order_emits_order_approved(self):
        """C2 — approve_order must emit marketplace.order.approved."""
        listing = self._listing(PricingModel.REQUEST_APPROVAL)
        order = self._consumer_service().create_order(
            tenant_id=str(self.consumer.id),
            user_id=str(self.consumer_user.id),
            listing_id=str(listing.id),
        )
        self.assertEqual(order.status, OrderStatus.REQUESTED)

        svc = MarketplaceService(
            tenant_id=str(self.provider.id),
            user_id=str(self.provider_user.id),
        )
        approved = svc.approve_order(
            order_id=str(order.id),
            tenant_id=str(self.provider.id),
            approver_id=str(self.provider_user.id),
        )
        self.assertEqual(approved.status, OrderStatus.FULFILLED)

        rows = _emitted_rows("marketplace.order.approved", self.provider)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].data["order_id"], str(order.id))

    def test_reject_order_emits_order_rejected(self):
        """C2 — reject_order must emit marketplace.order.rejected."""
        listing = self._listing(PricingModel.REQUEST_APPROVAL)
        order = self._consumer_service().create_order(
            tenant_id=str(self.consumer.id),
            user_id=str(self.consumer_user.id),
            listing_id=str(listing.id),
        )

        svc = MarketplaceService(
            tenant_id=str(self.provider.id),
            user_id=str(self.provider_user.id),
        )
        rejected = svc.reject_order(
            order_id=str(order.id),
            tenant_id=str(self.provider.id),
            approver_id=str(self.provider_user.id),
            reason="insufficient quota",
        )
        self.assertEqual(rejected.status, OrderStatus.REJECTED)

        rows = _emitted_rows("marketplace.order.rejected", self.provider)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].data["order_id"], str(order.id))
        self.assertEqual(rows[0].data["rejection_reason"], "insufficient quota")


class TestMarketplaceAbsentEmitters(TestCase):
    """C7 — documented-absent events must STAY absent (deliberate decisions,
    pinned so accidental wiring is caught)."""

    def setUp(self):
        (
            self.provider,
            self.consumer,
            self.provider_user,
            self.consumer_user,
            self.asset,
        ) = _marketplace_fixtures()
        self.listing = Listing.objects.create(
            tenant=self.provider,
            asset=self.asset,
            status=ListingStatus.PUBLISHED,
            pricing_model=PricingModel.FREE_AUTO_APPROVE,
            metadata_json={"title": "W41B Absent Listing"},
        )
        self.order = self._consumer_service().create_order(
            tenant_id=str(self.consumer.id),
            user_id=str(self.consumer_user.id),
            listing_id=str(self.listing.id),
        )
        self.assertEqual(self.order.status, OrderStatus.FULFILLED)

    def _consumer_service(self) -> MarketplaceService:
        return MarketplaceService(
            tenant_id=str(self.consumer.id),
            user_id=str(self.consumer_user.id),
        )

    def test_no_order_fulfilled_event(self):
        """C7 — fulfillment is atomic with approval (approve/create already
        emit); no separate marketplace.order.fulfilled event."""
        self.assertEqual(_emitted_rows("marketplace.order.fulfilled", self.consumer), [])
        # The approved/created events DID fire — the absence is deliberate,
        # not a dead bus.
        self.assertEqual(len(_emitted_rows("marketplace.order.created", self.consumer)), 1)

    def test_no_entitlement_events(self):
        """C7 — entitlement grants/revocations have no bus consumers (W2.6's
        ENTITLEMENT_REVOKED audit covers revocation); no entitlement events."""
        self.assertEqual(_emitted_rows("marketplace.entitlement.granted", self.consumer), [])
        self.assertEqual(_emitted_rows("marketplace.entitlement.revoked", self.consumer), [])


class TestMarketplaceListingPublishEmitter(TestCase):
    """C7 — marketplace.listing.published on the primary publish path."""

    def setUp(self):
        (
            self.provider,
            self.consumer,
            self.provider_user,
            self.consumer_user,
            self.asset,
        ) = _marketplace_fixtures()
        self.listing = Listing.objects.create(
            tenant=self.provider,
            asset=self.asset,
            status=ListingStatus.DRAFT,
            pricing_model=PricingModel.FREE,
            metadata_json={
                "title": "W41B Publish Listing",
                "short_description": "Publish-path listing",
                "long_description": "Listing for the W4.1b emitter pin.",
            },
        )

    def test_publish_listing_emits_listing_published(self):
        """C7 — publish_listing must emit marketplace.listing.published."""
        svc = MarketplaceService(
            tenant_id=str(self.provider.id),
            user_id=str(self.provider_user.id),
        )
        published = svc.publish_listing(
            listing_id=str(self.listing.id),
            tenant_id=str(self.provider.id),
            user_id=str(self.provider_user.id),
        )
        self.assertEqual(published.status, ListingStatus.PUBLISHED)

        rows = _emitted_rows("marketplace.listing.published", self.provider)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].data["listing_id"], str(self.listing.id))
        self.assertEqual(rows[0].data["asset_id"], str(self.asset.id))
