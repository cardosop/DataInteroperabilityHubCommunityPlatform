#!/usr/bin/env python3
"""
Provision smoke-test fixtures for Phase 231 (CRITICAL listing) and
Phase 250 (federated import source listing).

Creates ephemeral Assets, Listings, and ComplianceRuns in the given
database so that the corresponding smoke tests can exercise their
full contract without pre-seeded staging data.

Usage:
    python scripts/provision_smoke_fixtures.py [--db DB_NAME]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid

# Ensure the project root is on sys.path so ``hub`` is importable.
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hub.settings")
import django

django.setup()

from django.db import transaction
from django.utils import timezone

from hub.apps.assets.models import Asset
from hub.apps.compliance.models import ComplianceRun
from hub.apps.marketplace.models import Listing, ListingStatus
from hub.apps.tenants.models import Tenant


def _pick_or_create_fixture_tenant() -> Tenant:
    """Return a dedicated tenant for smoke fixtures.

    Creates one if it doesn't exist, with KYC and feature flags already
    enabled so the compliance gate and marketplace publish checks pass.
    """
    t = Tenant.objects.filter(slug="smoke-fixture-tenant").first()
    if t is None:
        t = Tenant.objects.create(
            name="Smoke Fixture Tenant",
            slug="smoke-fixture-tenant",
            kyc_status="VERIFIED",
            compliance_intake_gate_enabled=True,
            marketplace_publish_compliance_gate_enabled=True,
            federated_import_enabled=True,
        )
        # Ensure a TenantConfig row exists so the compliance gate can
        # read ``compliance_risk_threshold`` (business_rules.py:2019).
        from hub.apps.tenants.models import TenantConfig

        TenantConfig.objects.get_or_create(
            tenant=t,
            defaults={"compliance_risk_threshold": "HIGH"},
        )
    return t


def _delete_by_key_prefix(tenant: Tenant, prefix: str) -> None:
    """Best-effort cleanup of any previously created fixtures."""
    Asset.objects.filter(tenant=tenant, key__startswith=prefix).delete()


def provision_critical_listing(tenant: Tenant) -> str:
    """Create a CRITICAL ComplianceRun fixture.

    Returns the Listing ID (UUID string).  The caller should export it as
    ``SMOKE_PHASE231_CRITICAL_LISTING_ID``.
    """
    key = f"smoke-critical-fixture-{uuid.uuid4().hex[:8]}"
    asset = Asset.objects.create(
        tenant=tenant,
        key=key,
        name=f"Smoke CRITICAL fixture ({key})",
        description="Auto-provisioned smoke fixture. Safe to delete.",
        status="ACTIVE",
    )
    listing = Listing.objects.create(
        tenant=tenant,
        asset=asset,
        metadata_json={
            "title": f"Smoke CRITICAL Listing {key[:8]}",
            "short_description": "Auto-provisioned smoke fixture — CRITICAL risk level.",
        },
        status=ListingStatus.DRAFT,
    )
    ComplianceRun.objects.create(
        tenant=tenant,
        asset=asset,
        status="SUCCEEDED",
        risk_level="CRITICAL",
        overall_status="PASS",
        allowed_to_store=True,
        completed_at=timezone.now(),
    )
    print(f"export SMOKE_PHASE231_CRITICAL_LISTING_ID={listing.id}")
    return str(listing.id)


def provision_federated_source(tenant: Tenant) -> str:
    """Create a source tenant + listing for federated import.

    Returns the source Listing ID (UUID string).  The caller should
    export it as ``SMOKE_PHASE250_FEDERATED_SOURCE_LISTING_ID``.
    """
    suffix = uuid.uuid4().hex[:8]
    source = Tenant.objects.create(
        name=f"Smoke Federated Source {suffix}",
        slug=f"smoke-fed-source-{suffix}",
        kyc_status="VERIFIED",
    )
    key = f"smoke-fed-source-asset-{suffix}"
    asset = Asset.objects.create(
        tenant=source,
        key=key,
        name="Smoke Federated Source Asset",
        description="Source asset for federated import smoke test.",
        status="ACTIVE",
    )
    # Use a raw INSERT + UPDATE to avoid Django model signals (the
    # marketplace cache-invalidation signal references a stale import:
    # invalidate_marketplace_caches_for_asset which doesn't exist).
    listing_id = uuid.uuid4()
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO listings (id, tenant_id, asset_id, status, "
            "pricing_model, metadata_json, created_at, updated_at, "
            "published_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            [
                listing_id,
                source.id,
                asset.id,
                "PUBLISHED",
                "FREE",
                json.dumps(
                    {
                        "title": f"Smoke Federated Listing {suffix[:8]}",
                        "short_description": ("Auto-provisioned federated import smoke fixture."),
                    }
                ),
                timezone.now(),
                timezone.now(),
                timezone.now(),
            ],
        )
    print(f"export SMOKE_PHASE250_FEDERATED_SOURCE_LISTING_ID={listing_id}")
    return str(listing_id)


def main() -> None:
    parser = argparse.ArgumentParser(description="Provision smoke-test fixtures")
    parser.add_argument(
        "--tenant-id",
        default=None,
        help="Tenant UUID to own the fixtures. If not provided, uses the dedicated smoke-fixture-tenant.",
    )
    parser.add_argument(
        "--critical-only",
        action="store_true",
        help="Only provision the CRITICAL listing fixture.",
    )
    parser.add_argument(
        "--federated-only",
        action="store_true",
        help="Only provision the federated import source fixture.",
    )
    args = parser.parse_args()

    do_critical = not args.federated_only
    do_federated = not args.critical_only

    if args.tenant_id:
        tenant = Tenant.objects.get(pk=args.tenant_id)
    else:
        tenant = _pick_or_create_fixture_tenant()

    if do_critical:
        _delete_by_key_prefix(tenant, "smoke-critical-fixture-")
        with transaction.atomic():
            provision_critical_listing(tenant)

    if do_federated:
        _delete_by_key_prefix(tenant, "smoke-fed-source-asset-")
        with transaction.atomic():
            provision_federated_source(tenant)


if __name__ == "__main__":
    main()
