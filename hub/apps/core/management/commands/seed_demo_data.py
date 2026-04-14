"""
Seed persistent demo data for staging QA (Phase 219 / openspec preprod01).

Creates ~250 records across all services so every UI page has meaningful
content: assets, contracts (ODCS + ODPS), datasets, marketplace listings,
orders, entitlements, DQ runs, compliance runs, webhooks, and
governance retention policies.

Idempotent: uses get_or_create with `demo-` prefixed keys. Safe to re-run
on every deploy. The E2E orphan reaper only sweeps `e2e-` prefix, so
`demo-` data persists.

Usage:
    python hub/manage.py seed_demo_data --verbosity=2
"""

import json
import logging
import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db.models import F
from django.utils import timezone

logger = logging.getLogger(__name__)
User = get_user_model()

# ---------------------------------------------------------------------------
# Domain templates — 6 domains × 5 nouns = 30 assets
# ---------------------------------------------------------------------------

DOMAINS = [
    {
        "name": "finance",
        "nouns": ["transactions", "payments", "accounts", "invoices", "risk-scores"],
        "model_a": "Transaction",
        "model_b": "Customer",
        "fields_a": [
            {"name": "transaction_id", "type": "string"},
            {"name": "customer_id", "type": "string"},
            {"name": "amount", "type": "number"},
            {"name": "currency", "type": "string"},
            {"name": "timestamp", "type": "string"},
        ],
        "fields_b": [
            {"name": "customer_id", "type": "string"},
            {"name": "name", "type": "string"},
            {"name": "email", "type": "string"},
            {"name": "segment", "type": "string"},
        ],
    },
    {
        "name": "healthcare",
        "nouns": ["patient-records", "lab-results", "prescriptions", "appointments", "claims"],
        "model_a": "Patient",
        "model_b": "Diagnosis",
        "fields_a": [
            {"name": "patient_id", "type": "string"},
            {"name": "name", "type": "string"},
            {"name": "dob", "type": "string"},
            {"name": "blood_type", "type": "string"},
        ],
        "fields_b": [
            {"name": "diagnosis_id", "type": "string"},
            {"name": "patient_id", "type": "string"},
            {"name": "icd_code", "type": "string"},
            {"name": "diagnosed_at", "type": "string"},
            {"name": "severity", "type": "string"},
        ],
    },
    {
        "name": "retail",
        "nouns": ["inventory", "orders", "products", "customers", "returns"],
        "model_a": "Product",
        "model_b": "Warehouse",
        "fields_a": [
            {"name": "sku", "type": "string"},
            {"name": "name", "type": "string"},
            {"name": "price", "type": "number"},
            {"name": "category", "type": "string"},
            {"name": "warehouse_id", "type": "string"},
        ],
        "fields_b": [
            {"name": "warehouse_id", "type": "string"},
            {"name": "location", "type": "string"},
            {"name": "capacity", "type": "number"},
        ],
    },
    {
        "name": "logistics",
        "nouns": ["shipments", "warehouses", "routes", "carriers", "tracking"],
        "model_a": "Shipment",
        "model_b": "Carrier",
        "fields_a": [
            {"name": "shipment_id", "type": "string"},
            {"name": "carrier_id", "type": "string"},
            {"name": "origin", "type": "string"},
            {"name": "destination", "type": "string"},
            {"name": "weight_kg", "type": "number"},
            {"name": "shipped_at", "type": "string"},
        ],
        "fields_b": [
            {"name": "carrier_id", "type": "string"},
            {"name": "name", "type": "string"},
            {"name": "rating", "type": "number"},
        ],
    },
    {
        "name": "energy",
        "nouns": ["consumption", "grid-metrics", "solar-output", "billing", "outages"],
        "model_a": "Meter",
        "model_b": "Reading",
        "fields_a": [
            {"name": "meter_id", "type": "string"},
            {"name": "location", "type": "string"},
            {"name": "meter_type", "type": "string"},
            {"name": "installed_at", "type": "string"},
        ],
        "fields_b": [
            {"name": "reading_id", "type": "string"},
            {"name": "meter_id", "type": "string"},
            {"name": "value_kwh", "type": "number"},
            {"name": "recorded_at", "type": "string"},
        ],
    },
    {
        "name": "marketing",
        "nouns": ["campaigns", "impressions", "conversions", "audiences", "attribution"],
        "model_a": "Campaign",
        "model_b": "Audience",
        "fields_a": [
            {"name": "campaign_id", "type": "string"},
            {"name": "audience_id", "type": "string"},
            {"name": "channel", "type": "string"},
            {"name": "budget", "type": "number"},
            {"name": "start_date", "type": "string"},
            {"name": "end_date", "type": "string"},
        ],
        "fields_b": [
            {"name": "audience_id", "type": "string"},
            {"name": "name", "type": "string"},
            {"name": "size", "type": "number"},
            {"name": "segment_criteria", "type": "string"},
        ],
    },
]

ODCS_VERSIONS = ["v3.0.0", "v3.0.2", "v3.1.0"]
DATASET_FORMATS = ["CSV", "CSV", "CSV", "JSON", "JSON", "PARQUET"]
FILE_SIZES = [1024, 5120, 25600, 102400, 512000, 1048576, 5242880, 10485760, 26214400, 52428800]


def _build_odcs(domain, noun, index):
    """Build a minimal ODCS v3 contract JSON with models for lineage."""
    version = ODCS_VERSIONS[index % len(ODCS_VERSIONS)]
    fk_field = domain["fields_b"][0]["name"]
    return json.dumps({
        "apiVersion": f"odcs.io/{version}",
        "kind": "DataContract",
        "id": f"demo-{domain['name']}-{noun}",
        "name": f"{domain['name'].title()} {noun.replace('-', ' ').title()} Contract",
        "version": "1.0.0",
        "schema": {
            "fields": [{"name": f["name"], "type": f["type"]} for f in domain["fields_a"]],
        },
        "models": [
            {
                "name": domain["model_a"],
                "fields": [
                    {**f, "isPrimaryKey": i == 0, **(
                        {"references": f"{domain['model_b']}.{fk_field}"}
                        if f["name"] == fk_field else {}
                    )}
                    for i, f in enumerate(domain["fields_a"])
                ],
            },
            {
                "name": domain["model_b"],
                "fields": [
                    {**f, "isPrimaryKey": i == 0}
                    for i, f in enumerate(domain["fields_b"])
                ],
            },
        ],
        "servicelevels": {"availability": {"percentage": str(99.0 + index * 0.1)}},
        "terms": {"usage": f"Internal {domain['name']} analytics"},
    })


def _build_odps(domain, noun):
    """Build a minimal ODPS v4.1 wrapper around an embedded ODCS contract."""
    return json.dumps({
        "schema": "https://opendataproducts.org/schema/v4.1",
        "version": "4.1",
        "product": {
            "details": {
                "en": {
                    "productID": f"demo-{domain['name']}-{noun}-product",
                    "name": f"{domain['name'].title()} {noun.replace('-', ' ').title()} Product",
                    "description": f"ODPS product wrapping the {noun} contract.",
                    "productVersion": "1.0.0",
                }
            }
        },
    })


def _build_schema(domain, noun):
    """Build a dataset schema JSON."""
    return {
        "fields": [
            {"name": f["name"], "type": f["type"], "nullable": i > 0}
            for i, f in enumerate(domain["fields_a"] + domain["fields_b"][:2])
        ]
    }


class Command(BaseCommand):
    help = "Seed persistent demo data for staging QA (~250 records)"

    def handle(self, *args, **options):
        from hub.apps.assets.models import Asset, AssetStatus
        from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus
        from hub.apps.contracts.models import Contract, ContractStatus, ValidationStatus, NormalizationStatus
        from hub.apps.contracts.services import ContractService
        from hub.apps.datasets.models import Dataset
        from hub.apps.dq.models import DQRun, DQRunStatus, DQEngine
        from hub.apps.files.models import File
        from hub.apps.jobs.models import Job, JobType, JobStatus
        from hub.apps.marketplace.models import Listing, Order, Entitlement
        from hub.apps.webhooks.models import Webhook

        # ── Resolve users ────────────────────────────────────────────
        try:
            dpo_user = User.objects.get(email="e2e_test@example.com")
        except User.DoesNotExist:
            self.stderr.write("e2e_test@example.com not found — run ensure_e2e_user_roles first")
            return
        dpo_tenant = dpo_user.tenant
        try:
            consumer_user = User.objects.get(email="e2e_consumer@example.com")
        except User.DoesNotExist:
            self.stderr.write("e2e_consumer@example.com not found — run ensure_e2e_user_roles first")
            return
        consumer_tenant = consumer_user.tenant

        svc = ContractService(tenant_id=str(dpo_tenant.id), user_id=str(dpo_user.id))
        stats = {"assets": 0, "contracts": 0, "datasets": 0, "listings": 0, "orders": 0}

        # ── Phase 1: Assets + ODCS Contracts ─────────────────────────
        created_assets = []
        for domain in DOMAINS:
            for i, noun in enumerate(domain["nouns"]):
                key = f"demo-{domain['name']}-{noun}"
                is_draft = i >= 3  # last 2 per domain stay DRAFT

                asset, new = Asset.objects.get_or_create(
                    key=key, tenant=dpo_tenant,
                    defaults=dict(
                        name=f"{domain['name'].title()} {noun.replace('-', ' ').title()}",
                        description=f"Demo {domain['name']} asset: {noun.replace('-', ' ')}.",
                        domain=domain["name"],
                        visibility="PUBLIC" if i % 3 == 0 else "INTERNAL",
                        status=AssetStatus.DRAFT,
                        created_by=dpo_user,
                    ),
                )
                if new:
                    stats["assets"] += 1
                    self.stdout.write(f"  Asset: {key}")
                created_assets.append((asset, is_draft, domain, noun, i))

                # ODCS contract
                if not Contract.objects.filter(asset=asset, tenant=dpo_tenant).exists():
                    try:
                        contract = svc.create_contract(
                            original_raw=_build_odcs(domain, noun, i),
                            original_format="JSON",
                            asset_id=str(asset.id),
                        )
                        contract.validation_status = ValidationStatus.VALID
                        contract.status = ContractStatus.ACTIVE
                        contract.save(update_fields=["validation_status", "status"])
                        stats["contracts"] += 1
                        self.stdout.write(f"  Contract: {key}")
                    except Exception as e:
                        self.stderr.write(f"  Contract failed {key}: {e}")

        # ── Phase 2: ODPS Contracts (10) ─────────────────────────────
        for domain in DOMAINS[:5]:
            for noun in domain["nouns"][:2]:
                key = f"demo-{domain['name']}-{noun}"
                asset = Asset.objects.filter(key=key, tenant=dpo_tenant).first()
                if not asset:
                    continue
                if Contract.objects.filter(asset=asset, original_spec_type="ODPS", tenant=dpo_tenant).exists():
                    continue
                try:
                    odps = svc.create_contract(
                        original_raw=_build_odps(domain, noun),
                        original_format="JSON",
                        original_spec_type="ODPS",
                        asset_id=str(asset.id),
                    )
                    odps.validation_status = ValidationStatus.VALID
                    odps.status = ContractStatus.ACTIVE
                    odps.save(update_fields=["validation_status", "status"])
                    stats["contracts"] += 1
                except Exception as e:
                    self.stderr.write(f"  ODPS failed {key}: {e}")

        # ── Phase 3: Files + Datasets (20) ───────────────────────────
        active_candidates = [(a, d, n) for a, draft, d, n, _ in created_assets if not draft]
        for idx, (asset, domain, noun) in enumerate(active_candidates[:20]):
            if Dataset.objects.filter(asset=asset, tenant=dpo_tenant).exists():
                continue
            fmt = DATASET_FORMATS[idx % len(DATASET_FORMATS)]
            ext = {"CSV": "csv", "JSON": "json", "PARQUET": "parquet"}[fmt]
            file_obj, _ = File.objects.get_or_create(
                tenant=dpo_tenant,
                name=f"demo-{domain['name']}-{noun}.{ext}",
                defaults=dict(
                    content_type={"CSV": "text/csv", "JSON": "application/json", "PARQUET": "application/octet-stream"}[fmt],
                    size=FILE_SIZES[idx % len(FILE_SIZES)],
                    storage_path=f"demo/{dpo_tenant.id}/{asset.id}/data.{ext}",
                    status="ACTIVE",
                    created_by=dpo_user,
                ),
            )
            Dataset.objects.get_or_create(
                asset=asset, tenant=dpo_tenant,
                defaults=dict(
                    file=file_obj,
                    format=fmt,
                    schema_json=_build_schema(domain, noun),
                    row_count=(idx + 1) * 1000,
                ),
            )
            asset.dq_status = "PASS"
            asset.compliance_status = "PASS"
            asset.save(update_fields=["dq_status", "compliance_status"])
            stats["datasets"] += 1

        # ── Phase 4: Activate 30 assets ──────────────────────────────
        activated = 0
        for asset, is_draft, _, _, _ in created_assets:
            if is_draft:
                continue
            asset.refresh_from_db()
            if asset.status != AssetStatus.DRAFT:
                continue
            can, blockers = asset.can_activate()
            if can:
                Asset.objects.filter(pk=asset.pk, version=asset.version).update(
                    status=AssetStatus.ACTIVE, version=F("version") + 1
                )
                activated += 1
            else:
                self.stderr.write(f"  Cannot activate {asset.key}: {blockers}")
        self.stdout.write(f"  Activated {activated} assets")

        # ── Phase 5: Marketplace Listings (20) ───────────────────────
        active_assets = list(
            Asset.objects.filter(key__startswith="demo-", tenant=dpo_tenant, status=AssetStatus.ACTIVE)
            .order_by("key")[:20]
        )
        pricing_cycle = ["FREE_AUTO_APPROVE", "REQUEST_APPROVAL"]
        for i, asset in enumerate(active_assets):
            if Listing.objects.filter(asset=asset, tenant=dpo_tenant).exists():
                continue
            pricing = pricing_cycle[i % 2]
            publish = i < 15
            Listing.objects.create(
                asset=asset,
                tenant=dpo_tenant,
                pricing_model=pricing,
                metadata_json={
                    "title": asset.name,
                    "short_description": asset.description or "",
                    "domain": asset.domain or "",
                    "tags": ["demo", asset.domain or "general"],
                },
                status="PUBLISHED" if publish else "DRAFT",
                published_at=timezone.now() if publish else None,
            )
            stats["listings"] += 1

        # ── Phase 6: Consumer Orders + Entitlements (10) ─────────────
        free_published = Listing.objects.filter(
            tenant=dpo_tenant, status="PUBLISHED",
            pricing_model="FREE_AUTO_APPROVE", asset__key__startswith="demo-",
        ).order_by("created_at")[:10]
        for listing in free_published:
            if Order.objects.filter(listing=listing, tenant=consumer_tenant).exists():
                continue
            order = Order.objects.create(
                listing=listing,
                tenant=consumer_tenant,
                status="APPROVED",
                created_by=consumer_user,
                approved_at=timezone.now(),
            )
            Entitlement.objects.get_or_create(
                order=order, tenant=consumer_tenant, listing=listing,
                defaults=dict(
                    asset=listing.asset,
                    status="ACTIVE",
                ),
            )
            stats["orders"] += 1

        # ── Phase 7: DQ Runs (10) ───────────────────────────────────
        dq_assets = list(Asset.objects.filter(
            key__startswith="demo-", tenant=dpo_tenant, datasets__isnull=False,
        ).distinct()[:10])
        for idx, asset in enumerate(dq_assets):
            if DQRun.objects.filter(asset=asset, tenant=dpo_tenant).exists():
                continue
            job = Job.objects.create(
                tenant=dpo_tenant, type=JobType.DQ_RUN,
                status=JobStatus.COMPLETED, created_by=dpo_user,
                resource_type="ASSET", resource_id=str(asset.id),
            )
            DQRun.objects.create(
                tenant=dpo_tenant, asset=asset, job=job,
                profile_key="intake_basic_gx",
                engine=DQEngine.GREAT_EXPECTATIONS,
                status=DQRunStatus.SUCCEEDED if idx < 5 else DQRunStatus.FAILED,
                overall_status="PASS" if idx < 5 else "FAIL",
                quality_score=95.0 if idx < 5 else 45.0,
                started_at=timezone.now() - timedelta(hours=idx),
                completed_at=timezone.now() - timedelta(hours=idx, minutes=-5),
            )

        # ── Phase 8: Compliance Runs (10) ────────────────────────────
        for idx, asset in enumerate(dq_assets):
            if ComplianceRun.objects.filter(asset=asset, tenant=dpo_tenant).exists():
                continue
            job = Job.objects.create(
                tenant=dpo_tenant, type=JobType.COMPLIANCE_RUN,
                status=JobStatus.COMPLETED, created_by=dpo_user,
                resource_type="ASSET", resource_id=str(asset.id),
            )
            ComplianceRun.objects.create(
                tenant=dpo_tenant, asset=asset, job=job,
                status=ComplianceRunStatus.SUCCEEDED if idx < 5 else ComplianceRunStatus.FAILED,
                allowed_to_store=idx < 5,
                started_at=timezone.now() - timedelta(hours=idx),
                completed_at=timezone.now() - timedelta(hours=idx, minutes=-10),
            )

        # ── Phase 9: Webhooks (5) ────────────────────────────────────
        # Webhook model validates event_types in save() → full_clean().
        # Use filter + create pattern to avoid get_or_create validation issues.
        event_configs = [
            ("Demo Asset Events", ["asset.created", "asset.updated"]),
            ("Demo Contract Events", ["contract.created", "contract.updated"]),
            ("Demo Marketplace Events", ["marketplace.listing.published", "marketplace.order.created"]),
            ("Demo DQ Events", ["dq.run.succeeded", "dq.run.failed"]),
            ("Demo Compliance Events", ["compliance.run.succeeded"]),
        ]
        for wh_name, events in event_configs:
            if Webhook.objects.filter(name=wh_name, tenant=dpo_tenant).exists():
                continue
            try:
                Webhook.objects.create(
                    name=wh_name, tenant=dpo_tenant,
                    url=f"https://webhook.site/{uuid.uuid4().hex[:12]}",
                    secret=uuid.uuid4().hex,
                    event_types=events,
                    status="ACTIVE",
                    max_retries=3,
                    retry_intervals=[1, 5, 30],
                    created_by=dpo_user,
                )
            except Exception as e:
                self.stderr.write(f"  Webhook '{wh_name}' failed: {e}")

        # ── Summary ──────────────────────────────────────────────────
        total_assets = Asset.objects.filter(key__startswith="demo-", tenant=dpo_tenant).count()
        total_contracts = Contract.objects.filter(asset__key__startswith="demo-", tenant=dpo_tenant).count()
        total_listings = Listing.objects.filter(asset__key__startswith="demo-", tenant=dpo_tenant).count()
        total_orders = Order.objects.filter(listing__asset__key__startswith="demo-", tenant=consumer_tenant).count()
        self.stdout.write(self.style.SUCCESS(
            f"\nSeeded: {total_assets} assets, {total_contracts} contracts, "
            f"{stats['datasets']} datasets, {total_listings} listings, "
            f"{total_orders} orders, 5 webhooks"
        ))
