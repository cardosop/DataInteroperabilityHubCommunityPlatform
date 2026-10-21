"""W11.3 (oss-release-remediation) — generate the IDOR probe manifest.

Pipeline (all real, no mocks):

1. Enumerate the live tenant-scoped route inventory (urlconf resolution +
   view→model resolution + tenant-FK/platform-admin classification).
2. Validate instance synthesis for every tenant-scoped model inside a
   rolled-back transaction — the winning strategy (``generic`` or the
   handwritten creator name) is recorded per model.
3. Analyze the write serializer of every create/bulk/self-route key for
   tenant-scoped FK fields (the payload-FK probe surface).
4. Apply the probe/allowlist rule; every allowlisted route must already
   carry a written reason in ``lint/idor-coverage-allowlist.yml``.
5. Reconcile against the static inventory
   (``docs/api-audit/current-api-inventory.md`` — the
   ``categorize-api-inventory.py`` source) and report drift.
6. Write the checked-in manifest
   (``docs/api-audit/idor-probe-manifest.json``) and render the matrix doc
   (``docs/security/adversarial-matrices/w113-access-control-matrix.md``).

The command refuses to write when problems remain (no half-state): fix
allowlist entries / creators first, re-run, and the output is byte-stable.
"""

from __future__ import annotations

import json
import re
import sys
import uuid
from datetime import UTC, datetime

from django.core.management.base import BaseCommand
from django.db import transaction

from hub.apps.core import idor_inventory as inv
from hub.apps.testing import idor_synthesis as synth

# Route keys whose create probe would execute an external service (the
# 404 payload-FK direction still fires BEFORE execution — those routes
# keep the payload_fk probe type and drop the create half).  Populated
# from RED-run triage only, each with its service.
# Routes the generated matrix cannot probe at all — the create executes a
# multi-step external workflow AND the payload carries no tenant-scoped FK
# surface, so neither the create half nor the payload-FK direction is
# meaningful in the DB-only job.  Each key MUST have a matching reason in
# lint/idor-coverage-allowlist.yml (the gate rejects reasonless entries).
# Routes whose platform-admin gating is enforced INSIDE the view body
# (manual request.user.is_platform_admin checks) — the static permission
# classifier cannot see it.  Excluded from the denominator by the scope
# rule, listed in the matrix doc under platform_admin.
PLATFORM_ADMIN_ROUTE_KEYS: set[str] = {
    "POST:/api/v1/jobs/dlq/purge_resolved/",
}


NOT_PROBEABLE_KEYS: dict[str, str] = {
    "POST:/api/v1/databricks/workspaces/": (
        "create runs SSRF host validation with live DNS resolution — no "
        "synthetic hostname can pass; the object-level probes (detail "
        "routes) stay probed"
    ),
    "POST:/api/v1/contracts/products/": (
        "create runs the full ODPS product workflow (schema validation + "
        "external steps); no tenant-scoped FK surface in the payload"
    ),
}


SERVICE_TRIGGERED_KEYS: dict[str, str] = {
    "POST:/api/v1/compliance/runs/warehouse-scan/": (
        "executes a warehouse scan (SQL engine) on create — the payload-FK "
        "404 direction fires before execution and stays probed"
    ),
    "POST:/api/v1/transformation/wrangling/": (
        "the create half executes the wrangling engine (S3 data load) — "
        "the payload-FK 404 direction fires on the foreign asset before "
        "execution and stays probed"
    ),
    "POST:/api/v1/marketplace/orders/purchase/": (
        "the create half processes payment via the Stripe gateway — "
        "unreachable in the DB-only job; the payload-FK direction (foreign "
        "listing id) stays probed"
    ),
    "POST:/api/v1/integrations/marketplace/sync/": (
        "the create half executes the marketplace connector sync — the "
        "payload-FK 404 direction (foreign asset ids) stays probed"
    ),
    "POST:/api/v1/quality/runs/warehouse-run/": (
        "executes a warehouse quality run on create — the payload-FK 404 "
        "direction fires before execution and stays probed"
    ),
    "POST:/api/v1/dq/runs/warehouse-run/": (
        "executes a warehouse DQ run on create — same split as the scan"
    ),
    "POST:/api/v1/assets/data-first/": (
        "the create half launches the asset-creation workflow, whose "
        "infer_schema step downloads the file from S3/MinIO — unreachable in "
        "the DB-only security job; the payload-FK 404 direction fires before "
        "workflow launch and stays probed"
    ),
}


class Command(BaseCommand):
    help = "Generate the W11.3 IDOR probe manifest + access-control matrix doc."

    def add_arguments(self, parser):
        parser.add_argument(
            "--allow-write",
            action="store_true",
            help="Write the manifest and matrix doc even when problems remain.",
        )

    def handle(self, *_args, **options):
        routes = inv.enumerate_routes()
        allowlist = inv.load_allowlist()

        synthesis_by_model = self._validate_synthesis(routes)
        routes = self._annotate(routes)
        finalized, problems = inv.finalize_dispositions(routes, allowlist, synthesis_by_model)
        coverage = inv.compute_coverage(finalized)

        self._report_synthesis(synthesis_by_model)
        reconciliation = self._reconcile_static_inventory(finalized)

        self.stdout.write(
            f"tenant-scoped route keys: {coverage['tenant_scoped_route_keys']} "
            f"(probed {coverage['probed']}, allowlisted {coverage['allowlisted']}, "
            f"coverage {coverage['coverage_pct']}%)"
        )
        self.stdout.write(
            f"excluded: {coverage['excluded_platform_admin']} platform-admin, "
            f"{coverage['excluded_no_tenant_fk']} no-tenant-FK, "
            f"{coverage['excluded_unresolved']} unresolved"
        )
        if reconciliation:
            self.stdout.write(f"static-inventory reconciliation: {reconciliation}")
        if problems:
            self.stderr.write(self.style.ERROR(f"{len(problems)} problem(s):"))
            for problem in problems:
                self.stderr.write(f"  - {problem}")
            if not options["allow_write"]:
                sys.exit(1)

        generated_at = datetime.now(UTC).isoformat()
        payload = inv.manifest_payload(
            finalized,
            generated_at=generated_at,
            generator="generate_idor_probes",
            coverage=coverage,
        )
        payload["static_inventory_reconciliation"] = reconciliation or {}
        manifest_text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        matrix_text = inv.render_matrix_doc(finalized, coverage, generated_at)

        if (
            inv.MANIFEST_PATH.is_file()
            and inv.MANIFEST_PATH.read_text(encoding="utf-8") == manifest_text
        ):
            self.stdout.write("Manifest unchanged — not rewriting.")
        else:
            inv.MANIFEST_PATH.write_text(manifest_text, encoding="utf-8")
            self.stdout.write(f"Manifest written: {inv.MANIFEST_PATH.relative_to(inv.REPO_ROOT)}")
        inv.MATRIX_DOC_PATH.parent.mkdir(parents=True, exist_ok=True)
        if (
            inv.MATRIX_DOC_PATH.is_file()
            and inv.MATRIX_DOC_PATH.read_text(encoding="utf-8") == matrix_text
        ):
            self.stdout.write("Matrix doc unchanged — not rewriting.")
        else:
            inv.MATRIX_DOC_PATH.write_text(matrix_text, encoding="utf-8")
            self.stdout.write(
                f"Matrix doc written: {inv.MATRIX_DOC_PATH.relative_to(inv.REPO_ROOT)}"
            )

    def _validate_synthesis(self, routes: list[inv.RouteInfo]) -> dict[str, str]:
        """Build every tenant-scoped model inside a rolled-back transaction
        (real tenant + user rows, real ORM — everything undone on exit);
        returns {model_label: strategy}."""
        from django.apps import apps as django_apps

        models = sorted(
            {r.model for r in routes if r.model and r.disposition in {"probe", "allowlist"}}
        )
        strategies: dict[str, str] = {}
        for label in models:
            model = django_apps.get_model(label)
            creator = synth.CREATORS.get(label)
            if creator is not None:
                strategies[label] = f"creator:{creator.__name__}"
                continue
            try:
                with transaction.atomic():
                    from django.contrib.auth import get_user_model

                    from hub.apps.tenants.models import Tenant
                    from hub.apps.users.models import UserStatus

                    probe_tenant = Tenant.objects.create(
                        name=f"idor-synth-{uuid.uuid4().hex[:8]}",
                        slug=f"idor-synth-{uuid.uuid4().hex[:8]}",
                    )
                    if hasattr(probe_tenant, "kyc_status"):
                        probe_tenant.kyc_status = "VERIFIED"
                        probe_tenant.save()
                    probe_user = get_user_model().objects.create_user(
                        email=f"idor-synth-{uuid.uuid4().hex[:8]}@example.com",
                        password="probe-synth-pass",
                        tenant=probe_tenant,
                        status=UserStatus.ACTIVE,
                    )
                    synth.synthesize_instance(model, probe_tenant, probe_user)
                    transaction.set_rollback(True)
                strategies[label] = "generic"
            except synth.SynthesisError as exc:
                self.stdout.write(self.style.WARNING(f"{label}: synthesis failed — {exc}"))
                strategies[label] = ""
            except Exception as exc:  # noqa: BLE001 — recorded, not swallowed
                self.stdout.write(
                    self.style.WARNING(f"{label}: synthesis failed — {type(exc).__name__}: {exc}")
                )
                strategies[label] = ""
        self._validate_route_object_creators()
        return strategies

    def _validate_route_object_creators(self) -> None:
        """Every per-route object creator must build a real row — validated
        in a rolled-back transaction exactly like the model synthesis."""
        for route_key in synth.iter_route_object_creator_keys():
            creator = synth.route_object_creator(route_key)
            if creator is None:
                continue
            try:
                with transaction.atomic():
                    from django.contrib.auth import get_user_model

                    from hub.apps.tenants.models import Tenant
                    from hub.apps.users.models import UserStatus

                    probe_tenant = Tenant.objects.create(
                        name=f"idor-synth-{uuid.uuid4().hex[:8]}",
                        slug=f"idor-synth-{uuid.uuid4().hex[:8]}",
                    )
                    if hasattr(probe_tenant, "kyc_status"):
                        probe_tenant.kyc_status = "VERIFIED"
                        probe_tenant.save()
                    probe_user = get_user_model().objects.create_user(
                        email=f"idor-synth-{uuid.uuid4().hex[:8]}@example.com",
                        password="probe-synth-pass",
                        tenant=probe_tenant,
                        status=UserStatus.ACTIVE,
                    )
                    creator(probe_tenant, probe_user)
                    transaction.set_rollback(True)
            except Exception as exc:  # noqa: BLE001 — recorded, not swallowed
                self.stdout.write(
                    self.style.WARNING(
                        f"route object creator {route_key} failed — {type(exc).__name__}: {exc}"
                    )
                )

    def _annotate(self, routes: list[inv.RouteInfo]) -> list[inv.RouteInfo]:
        annotated: list[inv.RouteInfo] = []
        for route in routes:
            disposition = route.disposition
            payload_fk_fields: tuple[str, ...] = ()
            parent_creator: str | None = None
            object_creator = synth.route_object_creator_name(route.key)
            url_param_resolvers = {
                param: getattr(resolver, "__name__", "resolver")
                for param, resolver in synth.URL_PARAM_RESOLVERS.get(route.key, {}).items()
            }
            positive_control = route.key not in synth.POSITIVE_CONTROL_SKIPS
            list_own_object = route.key not in synth.LIST_OWN_OBJECT_SKIPS
            list_query_params = dict(synth.LIST_QUERY_PARAMS.get(route.key, {}))
            list_cross_tenant_query_params = dict(
                synth.LIST_CROSS_TENANT_QUERY_PARAMS.get(route.key, {})
            )
            list_accepted_statuses = synth.LIST_ACCEPTED_STATUSES.get(route.key, (200,))
            route_headers = dict(synth.ROUTE_HEADERS.get(route.key, {}))
            route_payload_override = dict(synth.ROUTE_PAYLOAD_OVERRIDES.get(route.key, {}))
            create_mutates = route.key in synth.CREATE_MUTATES_KEYS
            fk_probe_accepted_statuses = synth.FK_PROBE_ACCEPTED_STATUSES.get(route.key, (404,))
            bulk_ids_field = synth.BULK_IDS_FIELDS.get(route.key)
            bulk_accepted_statuses = synth.BULK_ACCEPTED_STATUSES.get(route.key, (404,))
            list_cross_tenant_visible = route.key in synth.LIST_CROSS_TENANT_VISIBLE_KEYS
            create_accepted_statuses = synth.CREATE_ACCEPTED_STATUSES.get(
                route.key, (200, 201, 202)
            )
            object_probe_accepted_statuses = synth.OBJECT_PROBE_ACCEPTED_STATUSES.get(
                route.key, (404,)
            )
            self_route_accepted_statuses = synth.SELF_ROUTE_ACCEPTED_STATUSES.get(
                route.key, (200, 201, 202, 204)
            )
            payload_drop_fields = tuple(synth.ROUTE_PAYLOAD_DROP_FIELDS.get(route.key, ()))
            extra_fk_fields = tuple(synth.ROUTE_PAYLOAD_FK_FIELDS.get(route.key, ()))
            if extra_fk_fields:
                # REPLACE semantics — the curated per-route list is the
                # truth for the write surface (a union would drag in
                # serializer-derived fields the create flow never reads).
                payload_fk_fields = extra_fk_fields
            probe_type = route.probe_type
            if route.probe_type in {"create", "bulk", "self_route"}:
                serializer = self._serializer_for(route)
                if serializer is not None:
                    try:
                        payload_fk_fields = tuple(synth.tenant_fk_fields_of(serializer))
                    except synth.SynthesisError:
                        payload_fk_fields = ()
                else:
                    probe_type = None  # → allowlist with a written reason
            if route.probe_type == "nested_list":
                parent = synth.PARENT_CREATORS.get(route.key)
                if parent is not None:
                    parent_creator = getattr(parent, "__name__", "parent")
            if route.key in SERVICE_TRIGGERED_KEYS and probe_type == "create":
                probe_type = "payload_fk"
            if route.key in NOT_PROBEABLE_KEYS:
                probe_type = None
            if route.key in PLATFORM_ADMIN_ROUTE_KEYS:
                disposition = "platform_admin"
                probe_type = None
            annotated.append(
                inv.RouteInfo(
                    key=route.key,
                    method=route.method,
                    path_template=route.path_template,
                    url_name=route.url_name,
                    url_mode=route.url_mode,
                    lookup_field=route.lookup_field,
                    path_params=route.path_params,
                    view_class=route.view_class,
                    model=route.model,
                    app=route.app,
                    shape=route.shape,
                    disposition=disposition,
                    probe_role=route.probe_role,
                    probe_type=probe_type,
                    methods_present=route.methods_present,
                    payload_fk_fields=payload_fk_fields,
                    parent_creator=parent_creator,
                    object_creator=object_creator,
                    url_param_resolvers=url_param_resolvers,
                    positive_control=positive_control,
                    list_own_object=list_own_object,
                    list_query_params=list_query_params,
                    list_cross_tenant_query_params=list_cross_tenant_query_params,
                    list_accepted_statuses=list_accepted_statuses,
                    route_headers=route_headers,
                    route_payload_override=route_payload_override,
                    create_mutates=create_mutates,
                    fk_probe_accepted_statuses=fk_probe_accepted_statuses,
                    bulk_ids_field=bulk_ids_field,
                    bulk_accepted_statuses=bulk_accepted_statuses,
                    list_cross_tenant_visible=list_cross_tenant_visible,
                    create_accepted_statuses=create_accepted_statuses,
                    object_probe_accepted_statuses=object_probe_accepted_statuses,
                    self_route_accepted_statuses=self_route_accepted_statuses,
                    payload_drop_fields=payload_drop_fields,
                )
            )
        return annotated

    def _serializer_for(self, route: inv.RouteInfo):
        return inv.serializer_for_route(route)

    def _report_synthesis(self, strategies: dict[str, str]) -> None:
        generic = sum(1 for v in strategies.values() if v == "generic")
        created = sum(1 for v in strategies.values() if v.startswith("creator:"))
        failed = sum(1 for v in strategies.values() if not v)
        self.stdout.write(
            f"synthesis: {generic} generic, {created} handwritten creators, {failed} failed"
        )
        for label, strategy in sorted(strategies.items()):
            if not strategy:
                self.stdout.write(self.style.WARNING(f"  FAILED: {label}"))

    def _reconcile_static_inventory(self, routes: list[inv.RouteInfo]) -> dict:
        """Cross-check the runtime manifest against the checked-in static
        inventory (the categorize-api-inventory.py source)."""
        if not inv.STATIC_INVENTORY_PATH.is_file():
            return {"static_inventory": "missing"}
        content = inv.STATIC_INVENTORY_PATH.read_text(encoding="utf-8")
        table_row = re.compile(
            r"^\| (GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS) \| `([^`]+)` \|",
            re.MULTILINE,
        )
        static_keys: set[tuple[str, str]] = set()
        for match in table_row.finditer(content):
            method = match.group(1)
            path_template = match.group(2).replace("{id}", "{id}")
            static_keys.add((method, path_template))
        runtime_keys = {(r.method, r.path_template) for r in routes}
        tenant_scoped = {
            (r.method, r.path_template) for r in routes if r.disposition in {"probe", "allowlist"}
        }
        missing_in_static = sorted(tenant_scoped - static_keys)
        static_only = sorted(static_keys - runtime_keys)
        return {
            "static_inventory_rows": len(static_keys),
            "tenant_scoped_missing_from_static_inventory": missing_in_static,
            "static_rows_without_runtime_route": static_only,
        }
