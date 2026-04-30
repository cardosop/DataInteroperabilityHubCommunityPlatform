"""
Phase 227 Wave 1 (227.L4.1, L4.4) — asset activation structural blocker.

The Wave 1 directive ungates the structural-floor check at every gate:
* Service layer (L3 — `ContractService.create_contract` / `update_contract`)
* ORM layer (L4 — `Asset.clean()` for direct ORM saves)
* Activation layer (L4 — `Asset.can_activate()` returns blockers)
* Marketplace publish layer (L4 — `MarketplaceService.publish_listing`)

This file pins the ORM and activation paths. Multi-version semantics:
when an asset has multiple contract versions, only the currently-active
one drives the gate; historic versions SHALL NOT be retroactively
validated.
"""
from __future__ import annotations

import uuid

import pytest
from django.test import TestCase


def _create_tenant():
    from hub.apps.tenants.models import Tenant
    return Tenant.objects.create(name="L4 Co", slug=f"l4-{uuid.uuid4().hex[:6]}")


def _create_asset(tenant, *, name="orders"):
    from hub.apps.assets.models import Asset
    return Asset.objects.create(tenant=tenant, name=name)


def _create_contract(
    tenant, asset, *, hub_contract_json, status="ACTIVE",
    version=1, validation_status="VALID",
    normalization_status="NORMALIZED_OK",
):
    from hub.apps.contracts.models import Contract
    return Contract.objects.create(
        tenant=tenant,
        asset=asset,
        version=version,
        original_spec_type="ODCS",
        original_spec_version="3.1.0",
        original_format="JSON",
        original_raw="{}",
        hub_contract_json=hub_contract_json,
        normalization_status=normalization_status,
        validation_status=validation_status,
        status=status,
    )


_HC_OK = {
    "models": [
        {"name": "customers", "fields": [{"name": "id", "data_type": "string"}]}
    ],
    "schema": {"fields": [{"name": "id", "data_type": "string"}]},
}
_HC_STRUCTURELESS = {"models": [], "schema": {"fields": []}}


# ---------------------------------------------------------------------------
# Asset.can_activate — structural blocker surfaces in blockers list
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class TestAssetCanActivateStructuralBlocker(TestCase):

    def test_blocker_emitted_when_active_contract_is_structureless(self):
        tenant = _create_tenant()
        asset = _create_asset(tenant)
        _create_contract(
            tenant, asset, hub_contract_json=_HC_STRUCTURELESS,
        )
        can, blockers = asset.can_activate()
        assert can is False
        assert any(
            "STRUCTURELESS" in b or "no resolvable models" in b.lower()
            for b in blockers
        ), f"Expected structural blocker; got {blockers!r}"

    def test_no_blocker_when_active_contract_is_structural(self):
        tenant = _create_tenant()
        asset = _create_asset(tenant)
        _create_contract(tenant, asset, hub_contract_json=_HC_OK)
        can, blockers = asset.can_activate()
        # Other gates may still block (DQ/compliance for assets with
        # datasets); we only assert the structural blocker is absent.
        assert not any("STRUCTURELESS" in b for b in blockers), (
            f"Structural blocker fired on a structural contract: {blockers!r}"
        )

    def test_multi_version_only_active_version_is_checked(self):
        """An asset with a structureless RETIRED v1 + structural ACTIVE
        v2 must NOT be blocked — historic versions don't count.
        """
        tenant = _create_tenant()
        asset = _create_asset(tenant)
        _create_contract(
            tenant, asset, hub_contract_json=_HC_STRUCTURELESS,
            version=1, status="RETIRED",
        )
        _create_contract(
            tenant, asset, hub_contract_json=_HC_OK,
            version=2, status="ACTIVE",
        )
        can, blockers = asset.can_activate()
        assert not any("STRUCTURELESS" in b for b in blockers), (
            f"Historic structureless version must not block; got {blockers!r}"
        )


# ---------------------------------------------------------------------------
# Asset.clean — structural blocker raises Django ValidationError on
# direct ORM saves with status=ACTIVE
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class TestAssetCleanStructuralBlocker(TestCase):

    def test_clean_rejects_active_with_structureless_contract(self):
        from django.core.exceptions import ValidationError

        tenant = _create_tenant()
        asset = _create_asset(tenant)
        _create_contract(
            tenant, asset, hub_contract_json=_HC_STRUCTURELESS,
        )
        from hub.apps.assets.models import AssetStatus
        asset.status = AssetStatus.ACTIVE
        with pytest.raises(ValidationError) as exc:
            asset.clean()
        assert "STRUCTURELESS" in str(exc.value) or "no resolvable" in str(exc.value).lower()
