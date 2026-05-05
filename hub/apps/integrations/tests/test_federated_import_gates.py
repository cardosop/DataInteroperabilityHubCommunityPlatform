"""
Phase 250.5.A — TDD pin for federated-import gating + tombstone cascade
+ cross-region consent + cross-tenant 404 protection.

Per D250.3, federated import is opt-in via ``Tenant.federated_import_enabled``
(default FALSE on existing tenants — additive-only field, non-breaking
for current callers). Per D250.16, source-tenant deletion tombstones
consumer-side federated copies via
``ExternalResourceReference.source_tenant_deleted_at`` with a 90-day
grace window before consumer-side delete. Per I2-3, cross-region
federated import is refused unless an explicit consent flag is set on
the call.

Tests use real Django ORM rows + real audit-event helper — NO mocks of
business logic. The DiscoveryService entry point is invoked directly
with a synthesised ``MarketplaceAssetMapping``; downstream resource
downloads are skipped via ``data_strategy="METADATA_ONLY"`` so the
test doesn't need an S3 boundary mock.
"""
from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from hub.apps.assets.models import (
    Asset,
    AssetSourceType,
    ExternalResourceReference,
)
from hub.apps.audit import event_types as audit_event_types
from hub.apps.audit.models import AuditEvent
from hub.apps.tenants.models import Tenant, TenantStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import UserStatus


pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


def _seed_tenant(*, slug_prefix: str = "tenant", region: str | None = None,
                 federated_import_enabled: bool = False):
    uid = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"{slug_prefix} {uid}",
        slug=f"{slug_prefix}-{uid}",
        status=TenantStatus.ACTIVE,
        kyc_status="UNVERIFIED",
        data_residency_region=region,
        federated_import_enabled=federated_import_enabled,
    )
    ensure_tenant_has_active_subscription(tenant)
    user = User.objects.create_user(
        email=f"u-{uid}@example.com",
        password="testpass123",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )
    return tenant, user


def _seed_marketplace_connection(tenant, user):
    """Build a minimal MarketplaceConnection row so the discovery
    service has a connection FK to attach external resources to."""
    from hub.apps.integrations.base import MarketplaceType
    from hub.apps.integrations.models import MarketplaceConnection

    return MarketplaceConnection.objects.create(
        tenant=tenant,
        name=f"Conn {uuid.uuid4().hex[:6]}",
        marketplace_type=MarketplaceType.CKAN_INSTANCE.value,
        config={"endpoint_url": "https://ckan.example/api"},
        is_active=True,
    )


def _build_asset_mapping(*, key: str, name: str, marketplace_type: str = "CKAN"):
    """Synthesise a ``MarketplaceAssetMapping`` carrying a single
    metadata-only resource so the discovery service has something to
    persist without needing a real CKAN HTTP fetch."""
    from hub.apps.integrations.base import (
        MarketplaceAssetMapping,
        MarketplaceResource,
    )

    return MarketplaceAssetMapping(
        asset_data={
            "key": key,
            "name": name,
            "description": "Test federated asset",
            "domain": "test",
        },
        source_metadata={
            "marketplace_type": marketplace_type,
            "marketplace_id": "external-id-123",
            "listing_id": "listing-456",
        },
        resources=[
            MarketplaceResource(
                resource_id=f"r-{uuid.uuid4().hex[:6]}",
                resource_type="data",
                name="resource-a",
                description="meta-only resource",
                url="https://ckan.example/r/a.csv",
                format="CSV",
                size_bytes=None,
            ),
        ],
    )


# ---------------------------------------------------------------------------
# 250.5.A.2 — Tenant.federated_import_enabled defaults FALSE on existing rows
# ---------------------------------------------------------------------------


class TenantFederatedImportFlagDefaultTest(TestCase):
    """Per D250.3, the new flag MUST default to FALSE on every tenant
    so the deploy doesn't accidentally enable federated import for
    customers who never asked for it."""

    def test_new_tenant_defaults_to_disabled(self):
        tenant = Tenant.objects.create(
            name=f"T {uuid.uuid4().hex[:6]}",
            slug=f"t-{uuid.uuid4().hex[:6]}",
            status=TenantStatus.ACTIVE,
            kyc_status="UNVERIFIED",
        )
        assert tenant.federated_import_enabled is False


# ---------------------------------------------------------------------------
# 250.5.A.3 — sync gate: tenant flag DISABLED ⇒ refuse + audit
# ---------------------------------------------------------------------------


class FederatedImportGateOnTenantFlagTest(TestCase):
    """When ``Tenant.federated_import_enabled=False``, the discovery
    service refuses to create the FEDERATED asset, raises a typed
    ``FederatedImportRejected`` exception, AND emits the
    ``FEDERATED_IMPORT_REJECTED`` audit row carrying the reason +
    tenant id + connection id."""

    def test_disabled_tenant_blocks_federated_import_with_audit(self):
        from hub.apps.integrations.services import MarketplaceIntegrationService as IntegrationService
        from hub.apps.integrations.exceptions import FederatedImportRejected

        tenant, user = _seed_tenant(federated_import_enabled=False)
        connection = _seed_marketplace_connection(tenant, user)
        mapping = _build_asset_mapping(
            key=f"fed-{uuid.uuid4().hex[:6]}",
            name="Federated A",
        )
        service = IntegrationService(
            tenant_id=str(tenant.id),
            user_id=str(user.id),
        )

        before = AuditEvent.objects.filter(
            action=audit_event_types.FEDERATED_IMPORT_REJECTED,
            tenant=tenant,
        ).count()

        with pytest.raises(FederatedImportRejected) as ei:
            service.create_federated_asset_with_contracts(
                asset_mapping=mapping,
                connection=connection,
                tenant_id=str(tenant.id),
                user_id=str(user.id),
                data_strategy="METADATA_ONLY",
            )

        # The exception carries the structured rejection code.
        assert ei.value.code == "FEDERATED_IMPORT_DISABLED"
        # No Asset row landed (the rejection fires BEFORE persistence).
        assert not Asset.objects.filter(
            tenant=tenant, source_type=AssetSourceType.FEDERATED,
        ).exists()
        # Audit row emitted with the rejection reason.
        after = AuditEvent.objects.filter(
            action=audit_event_types.FEDERATED_IMPORT_REJECTED,
            tenant=tenant,
        ).order_by("-created_at")
        assert after.count() - before == 1
        ev = after.first()
        assert ev.details_json["code"] == "FEDERATED_IMPORT_DISABLED"
        assert ev.details_json["connection_id"] == str(connection.id)


# ---------------------------------------------------------------------------
# 250.5.A.6 — cross-region refusal without explicit consent
# ---------------------------------------------------------------------------


class CrossRegionFederatedImportConsentTest(TestCase):
    """Per I2-3, a federated import where the source tenant's
    ``data_residency_region`` differs from the consumer tenant's MUST
    be refused unless the call carries explicit consent
    (``cross_region_consent=True`` kwarg). The refusal emits the
    ``FEDERATED_IMPORT_CROSS_REGION_BLOCKED`` audit row.
    """

    def test_different_region_without_consent_is_blocked(self):
        from hub.apps.integrations.services import MarketplaceIntegrationService as IntegrationService
        from hub.apps.integrations.exceptions import FederatedImportRejected

        consumer_tenant, user = _seed_tenant(
            slug_prefix="consumer",
            region="eu-west-1",
            federated_import_enabled=True,
        )
        source_tenant, _src_user = _seed_tenant(
            slug_prefix="source",
            region="us-east-1",
            federated_import_enabled=True,
        )
        connection = _seed_marketplace_connection(consumer_tenant, user)
        mapping = _build_asset_mapping(
            key=f"x-{uuid.uuid4().hex[:6]}",
            name="Cross-region",
        )
        # Tag the mapping's source_metadata so the gate can resolve
        # which Hub tenant produced this asset.
        mapping.source_metadata["source_tenant_id"] = str(source_tenant.id)

        service = IntegrationService(
            tenant_id=str(consumer_tenant.id),
            user_id=str(user.id),
        )
        before = AuditEvent.objects.filter(
            action=audit_event_types.FEDERATED_IMPORT_CROSS_REGION_BLOCKED,
            tenant=consumer_tenant,
        ).count()

        with pytest.raises(FederatedImportRejected) as ei:
            service.create_federated_asset_with_contracts(
                asset_mapping=mapping,
                connection=connection,
                tenant_id=str(consumer_tenant.id),
                user_id=str(user.id),
                data_strategy="METADATA_ONLY",
                cross_region_consent=False,
            )

        assert ei.value.code == "CROSS_REGION_CONSENT_REQUIRED"
        after = AuditEvent.objects.filter(
            action=audit_event_types.FEDERATED_IMPORT_CROSS_REGION_BLOCKED,
            tenant=consumer_tenant,
        ).count()
        assert after - before == 1

    def test_different_region_with_explicit_consent_proceeds(self):
        from hub.apps.integrations.services import MarketplaceIntegrationService as IntegrationService

        consumer_tenant, user = _seed_tenant(
            slug_prefix="consumer",
            region="eu-west-1",
            federated_import_enabled=True,
        )
        source_tenant, _src_user = _seed_tenant(
            slug_prefix="source",
            region="us-east-1",
            federated_import_enabled=True,
        )
        from hub.apps.integrations.exceptions import FederatedImportRejected

        connection = _seed_marketplace_connection(consumer_tenant, user)
        mapping = _build_asset_mapping(
            key=f"x-{uuid.uuid4().hex[:6]}",
            name="Cross-region OK",
        )
        mapping.source_metadata["source_tenant_id"] = str(source_tenant.id)

        service = IntegrationService(
            tenant_id=str(consumer_tenant.id),
            user_id=str(user.id),
        )
        # Audit-pass scope: this test pins the GATE-PASSAGE contract,
        # not the full federated-asset persistence pipeline (which
        # exercises ODPS/ODCS contract creation, semantic-layer
        # mapping via Fuseki RPC, etc. — orthogonal infra that's
        # covered by ``test_federated_asset_creation.py``). The
        # contract being pinned here is: cross_region_consent=True
        # MUST NOT raise FederatedImportRejected. Any other exception
        # (semantic infra, contract templates, etc.) is acceptable
        # because it confirms the gate let the call PROCEED past the
        # refusal point. The gate-rejection event would have been
        # ``FEDERATED_IMPORT_REJECTED`` with code
        # ``CROSS_REGION_CONSENT_REQUIRED``; we assert that no such
        # audit row exists.
        before = AuditEvent.objects.filter(
            action=audit_event_types.FEDERATED_IMPORT_CROSS_REGION_BLOCKED,
            tenant=consumer_tenant,
        ).count()
        try:
            asset = service.create_federated_asset_with_contracts(
                asset_mapping=mapping,
                connection=connection,
                tenant_id=str(consumer_tenant.id),
                user_id=str(user.id),
                data_strategy="METADATA_ONLY",
                cross_region_consent=True,
            )
            # If the full pipeline ran successfully, double-check the
            # asset shape too.
            assert asset is not None
            assert asset.source_type == AssetSourceType.FEDERATED
        except FederatedImportRejected as exc:  # pragma: no cover
            pytest.fail(
                f"Cross-region gate falsely refused with consent=True: {exc.code}"
            )
        # Cross-region gate did NOT fire — no rejection audit row.
        after = AuditEvent.objects.filter(
            action=audit_event_types.FEDERATED_IMPORT_CROSS_REGION_BLOCKED,
            tenant=consumer_tenant,
        ).count()
        assert after == before


# ---------------------------------------------------------------------------
# 250.5.A.5 — source-tenant deletion tombstones consumer-side resources
# ---------------------------------------------------------------------------


class SourceTenantDeletionTombstoneTest(TestCase):
    """Per D250.16, when a source tenant is soft-deleted, every
    ExternalResourceReference row carrying ``source_tenant_id == tenant.id``
    has its ``source_tenant_deleted_at`` populated to NOW. Consumer-side
    deletion happens after a 90-day grace window — the row remains
    queryable in the meantime so the consumer can export.
    """

    def test_soft_delete_populates_tombstone_on_consumer_resources(self):
        consumer_tenant, c_user = _seed_tenant(
            slug_prefix="consumer", federated_import_enabled=True,
        )
        source_tenant, _s_user = _seed_tenant(
            slug_prefix="source", federated_import_enabled=True,
        )
        # Stand up a federated asset on the consumer side.
        consumer_asset = Asset.objects.create(
            tenant=consumer_tenant,
            key=f"fed-{uuid.uuid4().hex[:6]}",
            name="Federated copy",
            status="DRAFT",
            source_type=AssetSourceType.FEDERATED,
            source_metadata={"source_tenant_id": str(source_tenant.id)},
            created_by=c_user,
        )
        # Stand up an ExternalResourceReference linking back to source.
        connection = _seed_marketplace_connection(consumer_tenant, c_user)
        ref = ExternalResourceReference.objects.create(
            asset=consumer_asset,
            resource_id="r-1",
            name="r1",
            url="https://ext/r1",
            format="CSV",
            connection_id=connection.id,
            marketplace_type="CKAN",
            source_tenant_id=source_tenant.id,
        )
        assert ref.source_tenant_deleted_at is None

        # Soft-delete the source tenant.
        source_tenant.soft_delete()

        # Tombstone is populated synchronously via the post-save signal.
        ref.refresh_from_db()
        assert ref.source_tenant_deleted_at is not None
        # The consumer-side row is STILL queryable (within grace).
        assert ExternalResourceReference.objects.filter(id=ref.id).exists()
        # Audit row emitted.
        assert AuditEvent.objects.filter(
            action=audit_event_types.FEDERATED_SOURCE_TENANT_DELETED,
        ).count() >= 1

    def test_grace_period_property(self):
        """The ``is_within_tombstone_grace`` property returns True for
        the first 90 days after ``source_tenant_deleted_at`` is set;
        False after."""
        consumer_tenant, c_user = _seed_tenant(slug_prefix="c")
        connection = _seed_marketplace_connection(consumer_tenant, c_user)
        asset = Asset.objects.create(
            tenant=consumer_tenant, key=f"k-{uuid.uuid4().hex[:6]}",
            name="X", source_type=AssetSourceType.FEDERATED,
        )
        ref = ExternalResourceReference.objects.create(
            asset=asset,
            resource_id="r1",
            name="r1",
            url="https://ext/r1",
            format="CSV",
            connection_id=connection.id,
            marketplace_type="CKAN",
        )
        # Before tombstone: in grace by definition.
        assert ref.is_within_tombstone_grace is True

        # Just-tombstoned: in grace.
        ref.source_tenant_deleted_at = timezone.now()
        ref.save(update_fields=["source_tenant_deleted_at"])
        assert ref.is_within_tombstone_grace is True

        # 91 days ago: out of grace.
        ref.source_tenant_deleted_at = timezone.now() - timedelta(days=91)
        ref.save(update_fields=["source_tenant_deleted_at"])
        assert ref.is_within_tombstone_grace is False


# ---------------------------------------------------------------------------
# 250.5.A.4 — cross-tenant 404 protection on FEDERATED assets
# ---------------------------------------------------------------------------


class CrossTenantFederatedAssetReadProtectionTest(TestCase):
    """A user from tenant B trying to GET a FEDERATED asset that
    belongs to tenant A receives 404 (not 403, not 200, not the asset
    body) — to prevent existence-leak per the spec."""

    def test_cross_tenant_get_returns_404(self):
        from rest_framework.test import APIClient

        tenant_a, user_a = _seed_tenant(slug_prefix="a")
        tenant_b, user_b = _seed_tenant(slug_prefix="b")
        # Promote so user_b at least has a role; the 404 must fire
        # even for users with broad scopes.
        user_b.roles = ["TENANT_ADMIN", "DATA_PROVIDER"]
        user_b.save(update_fields=["roles"])

        federated_asset = Asset.objects.create(
            tenant=tenant_a,
            key=f"fed-{uuid.uuid4().hex[:6]}",
            name="A federated",
            status="DRAFT",
            source_type=AssetSourceType.FEDERATED,
        )
        client = APIClient()
        client.force_authenticate(user=user_b)
        resp = client.get(f"/api/v1/assets/{federated_asset.id}/")
        # Cross-tenant read MUST be 404. 200 leaks tenant-A data, 403
        # leaks existence (the row is there, you just don't have
        # permission). Only 404 preserves zero-knowledge per spec.
        assert resp.status_code == 404, resp.content


class AuditorReadAccessTest(TestCase):
    """An AUDITOR user in the SAME tenant CAN read federated assets
    (read-only access is part of the role's responsibility for
    compliance)."""

    def test_auditor_can_read_federated_in_own_tenant(self):
        from rest_framework.test import APIClient

        tenant, user = _seed_tenant(slug_prefix="t")
        user.roles = ["AUDITOR"]
        user.save(update_fields=["roles"])

        federated_asset = Asset.objects.create(
            tenant=tenant,
            key=f"fed-{uuid.uuid4().hex[:6]}",
            name="In-tenant federated",
            status="DRAFT",
            source_type=AssetSourceType.FEDERATED,
        )
        client = APIClient()
        client.force_authenticate(user=user)
        resp = client.get(f"/api/v1/assets/{federated_asset.id}/")
        assert resp.status_code == 200, resp.content
        body = resp.json()
        assert body["source_type"] == "FEDERATED"

    def test_auditor_cannot_patch_federated(self):
        from rest_framework.test import APIClient

        tenant, user = _seed_tenant(slug_prefix="t")
        user.roles = ["AUDITOR"]
        user.save(update_fields=["roles"])

        federated_asset = Asset.objects.create(
            tenant=tenant,
            key=f"fed-{uuid.uuid4().hex[:6]}",
            name="In-tenant federated",
            status="DRAFT",
            source_type=AssetSourceType.FEDERATED,
        )
        client = APIClient()
        client.force_authenticate(user=user)
        resp = client.patch(
            f"/api/v1/assets/{federated_asset.id}/",
            data={"name": "auditor cant", "version": federated_asset.version},
            format="json",
        )
        # AUDITOR is read-only; a 403/405/401 (depending on the perm
        # framework's surface) is acceptable. NOT 200.
        assert resp.status_code in (401, 403, 405), resp.content
