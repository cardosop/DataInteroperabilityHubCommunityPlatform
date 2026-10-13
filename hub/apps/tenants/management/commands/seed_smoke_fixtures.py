"""Seed deterministic smoke-suite fixtures into the shared test DB.

Phase 231.DoD.5 + 250.DoD.7 post-deploy smoke tests need provisioned
scenario data (a gate-enabled admin tenant, a CRITICAL-compliance listing,
a federated source listing). The staging seeder does this for production;
the TEST stack gets this idempotent command, wired into
``scripts/migrate-test-dbs.sh``'s seed step so every DB rebuild provisions
the fixtures automatically.

Deterministic UUIDs let the compose env reference the rows statically
(``SMOKE_PHASE231_CRITICAL_LISTING_ID`` etc.) — the shared DB is rebuilt
from a template on every stack migrate, so fixed IDs are collision-free.

Idempotent: every row is fetched-or-created by its deterministic ID.
"""

import uuid

from django.core.management.base import BaseCommand
from django.utils import timezone

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus
# Marketplace is the paid layer — guarded for both core-only absence
# forms (W7.1); when absent the listing-seeding sections are no-ops.
try:
    from hub.apps.marketplace.models import Listing, ListingStatus, PricingModel
except (RuntimeError, ModuleNotFoundError):
    Listing = ListingStatus = PricingModel = None  # type: ignore[assignment]
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.users.models import User, UserStatus

# Deterministic fixture IDs (UUID4-shaped) — referenced by the compose env.
CRITICAL_LISTING_ID = uuid.UUID("aaaaaaaa-1111-4111-8111-111111111111")
FEDERATED_SOURCE_LISTING_ID = uuid.UUID("bbbbbbbb-2222-4222-8222-222222222222")
CRITICAL_ASSET_ID = uuid.UUID("cccccccc-3333-4333-8333-333333333333")
SOURCE_ASSET_ID = uuid.UUID("dddddddd-4444-4444-8444-444444444444")
SOURCE_TENANT_ID = uuid.UUID("eeeeeeee-5555-4555-8555-555555555555")
SOURCE_USER_ID = uuid.UUID("ffffffff-6666-4666-8666-666666666666")

ADMIN_EMAIL = "e2e_platform@example.com"
SOURCE_EMAIL = "smoke-federated-source@example.com"


class Command(BaseCommand):
    help = (
        "Seed the deterministic smoke-suite fixtures (Phase 231/250) into the "
        "shared test DB. Idempotent."
    )

    def handle(self, *_args, **_options):
        admin = User.objects.filter(email=ADMIN_EMAIL).first()
        if not admin:
            self.stderr.write(f"{ADMIN_EMAIL} not found — run ensure_e2e_user_roles first.")
            return
        admin_tenant = admin.tenant

        # 0. The admin's tenant needs an ACTIVE subscription — the paid
        # endpoints (files init, DQ/compliance, semantic, DoD7 flows) gate
        # on it, and the tenant UUID churns on every template re-clone so
        # it must be re-ensured here, not assumed from earlier seeds.
        from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

        ensure_tenant_has_active_subscription(admin_tenant)

        # 1. Flip the admin tenant's smoke flags + KYC (gate + federated import).
        admin_tenant.compliance_intake_gate_enabled = True
        admin_tenant.federated_import_enabled = True
        # 274.1.4 canary — the publish compliance gate is a no-op unless this
        # per-tenant flag is on. The 231.DoD.5 test needs the full gate.
        admin_tenant.marketplace_publish_compliance_gate_enabled = True
        if admin_tenant.kyc_status != KYCStatus.VERIFIED:
            admin_tenant.kyc_status = KYCStatus.VERIFIED
        admin_tenant.save(
            update_fields=[
                "compliance_intake_gate_enabled",
                "federated_import_enabled",
                "marketplace_publish_compliance_gate_enabled",
                "kyc_status",
                "updated_at",
            ]
        )
        self.stdout.write(f"Admin tenant {admin_tenant.id} flags enabled.")

        # 2. CRITICAL listing fixture: ACTIVE asset + SUCCEEDED CRITICAL
        #    ComplianceRun + DRAFT listing (publish must 422).
        critical_asset, _ = Asset.objects.get_or_create(
            id=CRITICAL_ASSET_ID,
            defaults={
                "tenant": admin_tenant,
                "key": "smoke-critical-asset",
                "name": "Smoke Critical Asset",
                "domain": "smoke",
                "status": AssetStatus.ACTIVE,
                "created_by": admin,
            },
        )
        # (tenant, asset) is NOT unique for ComplianceRun — repeated smoke
        # runs accumulate rows and get_or_create raises
        # MultipleObjectsReturned. Use the newest run instead.
        run = (
            ComplianceRun.objects.filter(tenant=admin_tenant, asset=critical_asset)
            .order_by("-created_at")
            .first()
        )
        created = run is None
        if created:
            run = ComplianceRun.objects.create(
                tenant=admin_tenant,
                asset=critical_asset,
                status=ComplianceRunStatus.SUCCEEDED,
                overall_status="FAIL",
                risk_level="CRITICAL",
                completed_at=timezone.now(),
                regulations=["GDPR"],
            )
        elif run.status != ComplianceRunStatus.SUCCEEDED:
            run.status = ComplianceRunStatus.SUCCEEDED
            run.risk_level = "CRITICAL"
            run.completed_at = timezone.now()
            run.save(update_fields=["status", "risk_level", "completed_at", "updated_at"])
        if Listing is None:
            self.stderr.write("marketplace (paid layer) absent — critical listing not seeded.")
            return
        listing, _ = Listing.objects.get_or_create(
            id=CRITICAL_LISTING_ID,
            defaults={
                "tenant": admin_tenant,
                "asset": critical_asset,
                "status": ListingStatus.DRAFT,
                "pricing_model": PricingModel.FREE,
                "created_by": admin,
                "metadata_json": {
                    "title": "Smoke Critical Listing",
                    "short_description": "Seeder fixture — publish must 422",
                    "description": "Seeder fixture — publish must 422 (COMPLIANCE_THRESHOLD_EXCEEDED)",
                },
            },
        )
        # Self-heal pre-existing rows (seeded before short_description was
        # required by the publish validation) and reset a listing a prior
        # run may have PUBLISHED (the smoke test publishes repeatedly and
        # must always start from a publishable state).
        meta = listing.metadata_json or {}
        updated_fields = []
        if not meta.get("short_description"):
            meta["short_description"] = "Seeder fixture — publish must 422"
            listing.metadata_json = meta
            updated_fields.append("metadata_json")
        if listing.status != ListingStatus.DRAFT:
            # The model forbids PUBLISHED → DRAFT transitions — recreate the
            # row so the deterministic ID comes back in a publishable state.
            listing.delete()
            listing, _ = Listing.objects.get_or_create(
                id=CRITICAL_LISTING_ID,
                defaults={
                    "tenant": admin_tenant,
                    "asset": critical_asset,
                    "status": ListingStatus.DRAFT,
                    "pricing_model": PricingModel.FREE,
                    "created_by": admin,
                    "metadata_json": {
                        "title": "Smoke Critical Listing",
                        "short_description": "Seeder fixture — publish must 422",
                        "description": "Seeder fixture — publish must 422 (COMPLIANCE_THRESHOLD_EXCEEDED)",
                    },
                },
            )
            updated_fields = []
        if updated_fields:
            listing.save(update_fields=[*updated_fields, "updated_at"])
        self.stdout.write(f"Critical listing {listing.id} seeded (run {run.id}).")

        # 3. Federated source: VERIFIED source tenant + PUBLISHED listing
        #    (import target for the 250 federated test).
        source_tenant, _ = Tenant.objects.get_or_create(
            id=SOURCE_TENANT_ID,
            defaults={
                "name": "Smoke Federated Source",
                "slug": "smoke-federated-source",
                "status": "ACTIVE",
                "kyc_status": KYCStatus.VERIFIED,
            },
        )
        if source_tenant.kyc_status != KYCStatus.VERIFIED:
            source_tenant.kyc_status = KYCStatus.VERIFIED
            source_tenant.save(update_fields=["kyc_status", "updated_at"])
        source_user, _ = User.objects.get_or_create(
            id=SOURCE_USER_ID,
            defaults={
                "email": SOURCE_EMAIL,
                "tenant": source_tenant,
                "status": UserStatus.ACTIVE,
            },
        )
        source_asset, _ = Asset.objects.get_or_create(
            id=SOURCE_ASSET_ID,
            defaults={
                "tenant": source_tenant,
                "key": "smoke-federated-source-asset",
                "name": "Smoke Federated Source Asset",
                "domain": "smoke",
                "status": AssetStatus.ACTIVE,
                "created_by": source_user,
            },
        )
        if Listing is None:
            self.stderr.write("marketplace (paid layer) absent — source listing not seeded.")
            return
        source_listing, _ = Listing.objects.get_or_create(
            id=FEDERATED_SOURCE_LISTING_ID,
            defaults={
                "tenant": source_tenant,
                "asset": source_asset,
                "status": ListingStatus.PUBLISHED,
                "pricing_model": PricingModel.FREE,
                "created_by": source_user,
                "metadata_json": {
                    "title": "Smoke Federated Source Listing",
                    "short_description": "Seeder fixture — federated import source",
                    "description": "Seeder fixture — federated import source for 250.DoD.7",
                },
            },
        )
        meta = source_listing.metadata_json or {}
        if not meta.get("short_description"):
            meta["short_description"] = "Seeder fixture — federated import source"
            source_listing.metadata_json = meta
            source_listing.save(update_fields=["metadata_json", "updated_at"])
        self.stdout.write(f"Federated source listing {source_listing.id} seeded.")

        self.stdout.write(
            self.style.SUCCESS(
                "Smoke fixtures ready: "
                f"CRITICAL_LISTING_ID={CRITICAL_LISTING_ID} "
                f"FEDERATED_SOURCE_LISTING_ID={FEDERATED_SOURCE_LISTING_ID}"
            )
        )
