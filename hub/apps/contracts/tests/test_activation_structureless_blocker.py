"""
Phase 227 Wave 1 (227.L4.1, L4.4) — asset activation structural blocker.

The Wave 1 directive ungates the structural-floor check at every gate:
* Service layer (L3 — `ContractService.create_contract` / `update_contract`).
* ORM layer (L4 — `Asset.clean()` for direct ORM saves).
* Activation layer (L4 — `Asset.can_activate()` returns blockers).
* Marketplace publish layer (L4 — `MarketplaceService.publish_listing`,
  pinned in `test_marketplace_publish_structural_blocker.py`).

This file pins the ORM and activation paths.

Invariants
----------
1. ``Asset.can_activate()`` returns ``(False, [...blockers...])`` when the
   currently-active contract is structureless. The blocker copy includes
   the subcode (so ops can grep audit logs) and a remediation URL (so
   the frontend can deep-link to the Schema editor).
2. ``Asset.clean()`` raises Django ``ValidationError`` on direct ORM
   saves that flip the asset to ``ACTIVE`` with a structureless
   contract — the last-line defense for callers that bypass the
   service layer.
3. **Multi-version semantics**: when an asset has multiple contract
   versions, only the currently-active one drives the gate; historic
   versions SHALL NOT be retroactively validated. This is
   load-bearing — Wave 5 / L6 will demote assets but historic
   structureless versions exist legitimately as audit trail and must
   not block activation of a fresh structural version.
4. The blocker is emitted unconditionally (no flag, no per-tenant
   override) per the 2026-04-30 ungate directive.
"""
from __future__ import annotations

import uuid

import pytest
from django.test import TestCase


def _create_tenant():
    """Build a tenant with unique name+slug so parallel test runs don't
    collide on the unique-name constraint."""
    from hub.apps.tenants.models import Tenant

    suffix = uuid.uuid4().hex[:8]
    return Tenant.objects.create(
        name=f"L4 Co {suffix}",
        slug=f"l4-co-{suffix}",
    )


def _create_asset(tenant, *, name=None):
    from hub.apps.assets.models import Asset

    return Asset.objects.create(
        tenant=tenant,
        name=name or f"orders-{uuid.uuid4().hex[:6]}",
    )


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
_HC_MODELS_WITH_NO_FIELDS = {"models": [{"name": "ghost", "fields": []}]}


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

    def test_blocker_message_includes_remediation_url(self):
        """The blocker copy MUST include the Schema-editor deep link so
        the frontend can render an actionable CTA."""
        tenant = _create_tenant()
        asset = _create_asset(tenant)
        contract = _create_contract(
            tenant, asset, hub_contract_json=_HC_STRUCTURELESS,
        )
        _can, blockers = asset.can_activate()
        # The contract id must appear in the remediation URL
        # (substituted from the {contract_id} placeholder).
        relevant = [b for b in blockers if "STRUCTURELESS" in b]
        assert relevant, f"No structural blocker found in {blockers!r}"
        joined = " ".join(relevant)
        assert str(contract.id) in joined, (
            f"Remediation URL must reference the offending contract id; "
            f"got {joined!r}"
        )

    def test_blocker_emitted_for_models_with_empty_fields(self):
        """``models=[{"fields":[]}]`` is structureless even though
        ``models`` looks populated — the floor counts a model only if
        it has at least one field. Pin the corner case here."""
        tenant = _create_tenant()
        asset = _create_asset(tenant)
        _create_contract(
            tenant, asset, hub_contract_json=_HC_MODELS_WITH_NO_FIELDS,
        )
        can, blockers = asset.can_activate()
        assert can is False
        assert any("STRUCTURELESS" in b for b in blockers), (
            f"Expected structural blocker on models-with-empty-fields; "
            f"got {blockers!r}"
        )

    def test_no_blocker_when_active_contract_is_structural(self):
        tenant = _create_tenant()
        asset = _create_asset(tenant)
        _create_contract(tenant, asset, hub_contract_json=_HC_OK)
        _can, blockers = asset.can_activate()
        # Other gates may still block (DQ/compliance for assets with
        # datasets); we only assert the structural blocker is absent.
        assert not any("STRUCTURELESS" in b for b in blockers), (
            f"Structural blocker fired on a structural contract: {blockers!r}"
        )

    def test_no_active_contract_blocks_with_existing_message_not_floor(self):
        """An asset with NO active contract must surface the existing
        ``Asset must have an ACTIVE contract`` blocker — not a misleading
        structural-floor blocker (the floor only fires when there IS an
        active contract that lacks structure)."""
        tenant = _create_tenant()
        asset = _create_asset(tenant)
        # No contract created.
        can, blockers = asset.can_activate()
        assert can is False
        assert any(
            "must have an ACTIVE contract" in b for b in blockers
        ), f"Expected the no-contract blocker; got {blockers!r}"
        # The structural-floor blocker MUST NOT fire when there's no
        # contract — that would be a misleading double-blocker.
        assert not any("STRUCTURELESS" in b for b in blockers), (
            f"Floor blocker should not fire when there's no contract; "
            f"got {blockers!r}"
        )

    def test_multi_version_only_active_version_is_checked(self):
        """An asset with a structureless RETIRED v1 + structural ACTIVE
        v2 must NOT be blocked — historic versions don't count.

        This is the load-bearing multi-version invariant from L4.1:
        Wave 5 / L6 will demote assets but historic structureless
        versions exist legitimately as audit trail and must not block
        activation of a fresh structural version.
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
        _can, blockers = asset.can_activate()
        assert not any("STRUCTURELESS" in b for b in blockers), (
            f"Historic structureless version must not block; got {blockers!r}"
        )

    def test_multi_version_blocks_when_active_is_structureless_despite_ok_history(self):
        """Symmetric to the previous test: even if a HISTORIC contract
        was structural, a fresh structureless ACTIVE contract MUST block.
        The gate evaluates *only* the active version."""
        tenant = _create_tenant()
        asset = _create_asset(tenant)
        _create_contract(
            tenant, asset, hub_contract_json=_HC_OK,
            version=1, status="RETIRED",
        )
        _create_contract(
            tenant, asset, hub_contract_json=_HC_STRUCTURELESS,
            version=2, status="ACTIVE",
        )
        can, blockers = asset.can_activate()
        assert can is False
        assert any("STRUCTURELESS" in b for b in blockers), (
            f"Fresh structureless ACTIVE version must block; "
            f"got {blockers!r}"
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
        assert "STRUCTURELESS" in str(exc.value) or "no resolvable" in str(
            exc.value
        ).lower()

    def test_clean_message_includes_subcode_for_grep(self):
        """The Django ValidationError message MUST include the structural
        subcode so ops can grep audit logs by failure cause."""
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
        # ODCS structureless → STRUCTURELESS_ODCS_NO_SCHEMA subcode.
        msg = str(exc.value)
        assert "STRUCTURELESS_ODCS_NO_SCHEMA" in msg or "STRUCTURELESS" in msg, (
            f"Expected subcode in message; got {msg!r}"
        )

    def test_clean_accepts_active_with_structural_contract(self):
        """Symmetric: a structural contract MUST allow activation via
        ``Asset.clean()`` (no false positive)."""
        tenant = _create_tenant()
        asset = _create_asset(tenant)
        _create_contract(tenant, asset, hub_contract_json=_HC_OK)
        from hub.apps.assets.models import AssetStatus

        asset.status = AssetStatus.ACTIVE
        # Should not raise. (Other validators may still run; we just
        # pin that the structural-floor branch doesn't trip.)
        try:
            asset.clean()
        except Exception as exc:  # pragma: no cover - explicit failure
            assert "STRUCTURELESS" not in str(exc) and "no resolvable" not in str(
                exc
            ).lower(), (
                f"Structural-floor blocker fired on a structural contract: "
                f"{exc!r}"
            )

    def test_clean_does_not_block_draft_status(self):
        """The floor check fires only when status flips to ACTIVE.
        DRAFT assets with structureless contracts MUST be saveable —
        otherwise the user can't even fetch the contract to fix it."""
        tenant = _create_tenant()
        asset = _create_asset(tenant)
        _create_contract(
            tenant, asset, hub_contract_json=_HC_STRUCTURELESS,
        )
        from hub.apps.assets.models import AssetStatus

        asset.status = AssetStatus.DRAFT
        # Should not raise on the structural-floor branch.
        try:
            asset.clean()
        except Exception as exc:  # pragma: no cover - explicit failure
            assert "STRUCTURELESS" not in str(exc), (
                f"Floor must not block DRAFT saves; got {exc!r}"
            )
