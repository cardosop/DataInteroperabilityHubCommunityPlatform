"""
Seed two ODCS contracts with a real cross-contract lineage relationship so the
contract Lineage tab in the UI has a populated example to render.

Why this exists
---------------
Audit on 2026-04-25 over all 142 contracts on staging found ZERO with a
populated `hub_contract_json.lineage` block. The visualization endpoint
therefore returns only the structural tree (contract -> model -> fields with
"contains" links) for every contract, never an actual cross-contract edge.
The E2E lineage spec at frontend/e2e/features/lineage.spec.ts accepts an empty
state outcome, so it doesn't surface the gap.

This command writes two contracts:

    Source  : info.name="Lineage Demo - Orders",            info.domain="lineage-demo"
    Derived : info.name="Lineage Demo - Order Aggregations", info.domain="lineage-demo"
              hub_contract_json.lineage.contracts = [
                  {"namespace": "lineage-demo", "name": "Lineage Demo - Orders"}
              ]

`LineageReference.resolve_contract` (hub/apps/contracts/lineage.py:99-105)
matches lineage[].namespace against `info.domain` OR `extensions.namespace`,
and lineage[].name against `info.name` (case-sensitive). Both contracts must
live in the same tenant for resolution to succeed (tenant scoping is enforced
in `LineageTraverser.traverse_bottom_up` at lineage_service.py:600-605).

Usage
-----
    python hub/manage.py seed_contract_lineage --dry-run
    python hub/manage.py seed_contract_lineage
    python hub/manage.py seed_contract_lineage --cleanup
    python hub/manage.py seed_contract_lineage --force-recreate

    # Override defaults:
    python hub/manage.py seed_contract_lineage \
        --tenant-slug some-other-tenant \
        --owner-email a-tenant-resident@example.com \
        --namespace alt-namespace

Idempotency
-----------
Re-runs without --force-recreate are a no-op. The command keys lookups on
(tenant, hub_contract_json.info.name) so it identifies its own seeded rows
deterministically.

Direct ORM, not the API
-----------------------
This command writes via Contract.objects.create() rather than going through
ContractService.create_contract(). The API path requires constructing valid
ODCS YAML with extensions and trusts the normalization engine to preserve
the lineage.contracts shape; for a seed whose entire purpose is to land
specific JSON, direct ORM is more reliable. Matches the migrate_contracts.py
pattern. The trade-off is that we set normalization_status / validation_status
manually rather than running the full pipeline, so the seeded rows look
"normalized + valid" without invoking the engine.

Cache invalidation
------------------
Lineage cache is NOT auto-invalidated on Contract post_save (verified: no
caller of `invalidate_lineage_cache` exists in the codebase). Without the
explicit invalidation below, the visualization endpoint can return cached
empty graphs for up to CACHE_TTL_LINEAGE seconds (10 min default per
hub/apps/contracts/caching.py:18).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from hub.apps.contracts.caching import invalidate_lineage_cache
from hub.apps.contracts.models import (
    Contract,
    ContractStatus,
    NormalizationStatus,
    OriginalFormat,
    OriginalSpecType,
    ValidationStatus,
)
from hub.apps.contracts.versioning import CURRENT_HUBCONTRACT_VERSION_STRING
from hub.apps.tenants.models import Tenant

logger = logging.getLogger(__name__)
User = get_user_model()

# Stable seed identifiers. The names double as idempotency keys —
# changing either of these constants in a future revision should be paired
# with a one-shot `--cleanup` of the prior names.
SOURCE_NAME = "Lineage Demo - Orders"
DERIVED_NAME = "Lineage Demo - Order Aggregations"
DEFAULT_NAMESPACE = "lineage-demo"
DEFAULT_TENANT_SLUG = "default"
DEFAULT_OWNER_EMAIL = "e2e_admin@example.com"


def _build_source_hub_contract_json(namespace: str) -> Dict[str, Any]:
    """Construct a fully-formed hub_contract_json for the upstream contract.

    The shape satisfies `validate_hub_contract_dict` (typed_models.py:515) —
    `hub_contract_version`, `id`, `info.name`, and a non-empty `schema.fields`
    are all required. `info.domain` carries the lineage `namespace` so the
    LineageReference matcher resolves references back to this row.
    """
    return {
        "hub_contract_version": CURRENT_HUBCONTRACT_VERSION_STRING,
        "id": "lineage-demo-source",
        "info": {
            "name": SOURCE_NAME,
            "domain": namespace,
            "version": "1.0.0",
            "description": (
                "Demo source contract — represents an upstream Orders dataset. "
                "Seeded by `seed_contract_lineage` so the Lineage tab has a "
                "real cross-contract edge to render."
            ),
        },
        "schema": {
            "fields": [
                {"name": "order_id", "type": "string", "nullable": False},
                {"name": "customer_id", "type": "string", "nullable": False},
                {"name": "amount", "type": "number", "nullable": True},
                {"name": "placed_at", "type": "string", "format": "date-time"},
            ],
        },
        "models": [
            {
                "name": "Orders",
                "description": "Order facts table.",
                "fields": [
                    {"name": "order_id", "type": "string", "nullable": False},
                    {"name": "customer_id", "type": "string", "nullable": False},
                    {"name": "amount", "type": "number", "nullable": True},
                    {"name": "placed_at", "type": "string", "format": "date-time"},
                ],
            },
        ],
    }


def _build_derived_hub_contract_json(namespace: str) -> Dict[str, Any]:
    """Derived contract — declares lineage dependency on the Source.

    The `lineage.contracts[]` shape (NOT bare `lineage[]`) is the canonical
    one — see references at lineage.py:735 and the LineageSection /
    ContractLineageReference types at typed_models.py:370-399.
    """
    return {
        "hub_contract_version": CURRENT_HUBCONTRACT_VERSION_STRING,
        "id": "lineage-demo-derived",
        "info": {
            "name": DERIVED_NAME,
            "domain": namespace,
            "version": "1.0.0",
            "description": (
                "Demo derived contract — depends on the Orders source. "
                "Aggregates per-customer order counts and totals."
            ),
        },
        "schema": {
            "fields": [
                {"name": "customer_id", "type": "string", "nullable": False},
                {"name": "total_orders", "type": "integer", "nullable": False},
                {"name": "total_amount", "type": "number", "nullable": False},
            ],
        },
        "models": [
            {
                "name": "OrderAggregations",
                "description": "Per-customer order aggregates derived from Orders.",
                "fields": [
                    {"name": "customer_id", "type": "string", "nullable": False},
                    {"name": "total_orders", "type": "integer", "nullable": False},
                    {"name": "total_amount", "type": "number", "nullable": False},
                ],
            },
        ],
        "lineage": {
            "contracts": [
                {
                    "namespace": namespace,
                    "name": SOURCE_NAME,
                    "version": "1.0.0",
                    "description": "Upstream Orders source.",
                },
            ],
        },
    }


def _find_existing(tenant: Tenant, contract_name: str) -> Optional[Contract]:
    """Idempotency lookup: tenant + hub_contract_json.info.name.

    Contract has no `name` column; the canonical contract identifier in this
    repo is the JSONField path `hub_contract_json.info.name`. We scope by
    tenant first to avoid cross-tenant collisions.
    """
    return (
        Contract.objects.filter(tenant=tenant, hub_contract_json__info__name=contract_name)
        .order_by("created_at")
        .first()
    )


class Command(BaseCommand):
    help = (
        "Seed two ODCS contracts with a real cross-contract lineage relationship "
        "(Orders -> OrderAggregations) for visualization in the contract Lineage tab."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--tenant-slug",
            type=str,
            default=DEFAULT_TENANT_SLUG,
            help=f"Slug of the tenant to seed into (default: {DEFAULT_TENANT_SLUG}).",
        )
        parser.add_argument(
            "--owner-email",
            type=str,
            default=DEFAULT_OWNER_EMAIL,
            help=(
                "Email of the user to record as `created_by`. Should be a "
                "tenant-resident user with TENANT_ADMIN or DATA_PROVIDER role "
                f"(default: {DEFAULT_OWNER_EMAIL})."
            ),
        )
        parser.add_argument(
            "--namespace",
            type=str,
            default=DEFAULT_NAMESPACE,
            help=(
                "Lineage namespace — written to both contracts' info.domain "
                "and the derived contract's lineage.contracts[].namespace "
                f"(default: {DEFAULT_NAMESPACE})."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Log planned actions without writing to the database.",
        )
        parser.add_argument(
            "--cleanup",
            action="store_true",
            help="Delete the two seeded contracts (matched by name) and exit.",
        )
        parser.add_argument(
            "--force-recreate",
            action="store_true",
            help="Delete the two seeded contracts (if any) and recreate fresh.",
        )

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]
        cleanup: bool = options["cleanup"]
        force_recreate: bool = options["force_recreate"]
        tenant_slug: str = options["tenant_slug"]
        owner_email: str = options["owner_email"]
        namespace: str = options["namespace"]

        if cleanup and force_recreate:
            raise CommandError("--cleanup and --force-recreate are mutually exclusive.")
        if cleanup and dry_run:
            # Honor dry-run for cleanup too — print the plan without deleting.
            pass

        tenant = self._lookup_tenant(tenant_slug)
        owner = self._lookup_owner(owner_email)

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY-RUN: no database writes will be made."))

        if cleanup:
            self._cleanup(tenant, dry_run=dry_run)
            return

        if force_recreate:
            self._cleanup(tenant, dry_run=dry_run)

        self._seed(tenant, owner, namespace, dry_run=dry_run)

    # --------------------------------------------------------------- helpers

    def _lookup_tenant(self, slug: str) -> Tenant:
        try:
            return Tenant.objects.get(slug=slug)
        except Tenant.DoesNotExist as exc:
            raise CommandError(
                f"Tenant slug={slug!r} not found. Run `python manage.py "
                f"ensure_e2e_user_roles` first, or pick a different "
                f"--tenant-slug."
            ) from exc

    def _lookup_owner(self, email: str):
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist as exc:
            raise CommandError(
                f"User email={email!r} not found. Run `python manage.py "
                f"ensure_e2e_user_roles` first, or pick a different "
                f"--owner-email. The owner is recorded as `created_by` on "
                f"the seeded contracts and should have TENANT_ADMIN or "
                f"DATA_PROVIDER role for parity with API-created contracts."
            ) from exc
        return user

    def _seed(self, tenant: Tenant, owner, namespace: str, *, dry_run: bool) -> None:
        source_payload = _build_source_hub_contract_json(namespace)
        derived_payload = _build_derived_hub_contract_json(namespace)

        existing_source = _find_existing(tenant, SOURCE_NAME)
        existing_derived = _find_existing(tenant, DERIVED_NAME)

        if existing_source and existing_derived:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Both seed contracts already exist in tenant={tenant.slug!r}. "
                    f"Source={existing_source.id} Derived={existing_derived.id}. "
                    f"Re-run with --force-recreate to reset."
                )
            )
            return

        if dry_run:
            for label, existing, payload in (
                ("source", existing_source, source_payload),
                ("derived", existing_derived, derived_payload),
            ):
                if existing:
                    self.stdout.write(
                        self.style.NOTICE(
                            f"DRY-RUN: would skip {label} (already exists, id={existing.id})"
                        )
                    )
                else:
                    info_name = (payload.get("info") or {}).get("name", "?")
                    self.stdout.write(
                        self.style.NOTICE(
                            f"DRY-RUN: would create {label} contract "
                            f"name={info_name!r} in tenant={tenant.slug!r}"
                        )
                    )
            return

        with transaction.atomic():
            source = existing_source or self._create_contract(
                tenant=tenant,
                owner=owner,
                hub_contract_json=source_payload,
            )
            if existing_source is None:
                self.stdout.write(
                    self.style.SUCCESS(f"Created source contract id={source.id}")
                )

            derived = existing_derived or self._create_contract(
                tenant=tenant,
                owner=owner,
                hub_contract_json=derived_payload,
            )
            if existing_derived is None:
                self.stdout.write(
                    self.style.SUCCESS(f"Created derived contract id={derived.id}")
                )

        # Cache invalidation runs OUTSIDE the transaction so a Redis hiccup
        # doesn't roll back the DB writes — the worst case is a 10-minute
        # stale-graph window, not a half-seeded state.
        for contract in (source, derived):
            try:
                invalidate_lineage_cache(str(contract.id))
            except Exception:
                # Best-effort: log and move on. The TTL backstop will refresh.
                logger.warning(
                    "seed_contract_lineage: invalidate_lineage_cache failed "
                    "for contract %s; relying on TTL.",
                    contract.id,
                    exc_info=True,
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded lineage demo. View in UI: "
                f"/contracts/{derived.id}  (Lineage tab)  "
                f"or /contracts/{source.id}  (Lineage tab — upstream view)."
            )
        )

    def _create_contract(
        self,
        *,
        tenant: Tenant,
        owner,
        hub_contract_json: Dict[str, Any],
    ) -> Contract:
        """Direct ORM create.

        Skips ContractService.create_contract / clean() / full_clean() so the
        precise hub_contract_json shape lands without normalization-engine
        rewrites. Sets validation_status=VALID + normalization_status=
        NORMALIZED_OK so the row presents as a fully-realized contract in
        the UI (those fields gate `Contract.clean()`'s ACTIVE-status checks
        but we're not invoking clean explicitly).
        """
        return Contract.objects.create(
            tenant=tenant,
            asset=None,  # Contract-only — no parent asset linkage for the demo.
            status=ContractStatus.ACTIVE,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw="{}",  # Verbatim source-of-truth — empty for ORM-seeded rows.
            hub_contract_version=CURRENT_HUBCONTRACT_VERSION_STRING,
            hub_contract_json=hub_contract_json,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            validation_status=ValidationStatus.VALID,
            created_by=owner,
        )

    def _cleanup(self, tenant: Tenant, *, dry_run: bool) -> None:
        targets = []
        for name in (DERIVED_NAME, SOURCE_NAME):  # delete derived first (FK politeness)
            existing = _find_existing(tenant, name)
            if existing:
                targets.append(existing)

        if not targets:
            self.stdout.write(
                self.style.NOTICE(
                    f"Cleanup: no seeded contracts found in tenant={tenant.slug!r}."
                )
            )
            return

        if dry_run:
            for c in targets:
                info_name = ((c.hub_contract_json or {}).get("info") or {}).get("name", "?")
                self.stdout.write(
                    self.style.NOTICE(
                        f"DRY-RUN: would delete contract id={c.id} name={info_name!r}"
                    )
                )
            return

        with transaction.atomic():
            for c in targets:
                info_name = ((c.hub_contract_json or {}).get("info") or {}).get("name", "?")
                c.delete()
                self.stdout.write(
                    self.style.SUCCESS(f"Deleted contract id={c.id} name={info_name!r}")
                )

        for c in targets:
            try:
                invalidate_lineage_cache(str(c.id))
            except Exception:
                logger.warning(
                    "seed_contract_lineage: invalidate_lineage_cache failed "
                    "for contract %s during cleanup; relying on TTL.",
                    c.id,
                    exc_info=True,
                )
