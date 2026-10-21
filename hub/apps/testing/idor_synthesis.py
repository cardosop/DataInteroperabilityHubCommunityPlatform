"""W11.3 (oss-release-remediation) — object + payload synthesis for the
ASVS V4 IDOR probe matrix.

Two engines, both REAL-DB (no mocks, no stubs):

* :func:`synthesize_instance` — type-driven construction of a tenant-scoped
  model row (recursive FK resolution with a depth cap, validator-aware
  value generation, per-model handwritten creators for the models generic
  synthesis cannot build — custom ``save()``/``clean()``/CHECK constraints).

* :func:`payload_for` — serializer-driven request payloads for the
  create/self-route/bulk probes: minimal valid values for required fields,
  tenant-scoped FK fields injectable with the OTHER tenant's object ids
  (the payload-FK probe direction).

The generator command validates every model against this module inside
rolled-back savepoints and records the winning strategy
(``generic`` or the creator name) in the checked-in manifest; the probe
suite imports the SAME module so the objects it probes are exactly the
generator-validated objects.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models as dj_models
from django.utils import timezone

CREATOR = Callable[[Any, Any], Any]

# FK field names that carry USER ownership semantics — always assigned to
# the probe user so owner-scoped views (owner-or-admin, my-keys-only)
# resolve the probe object for its owner.
_USER_OWNERSHIP_FIELD_NAMES = frozenset(
    {"user", "owner", "created_by", "requester", "requested_by", "reviewer", "actor"}
)

# ── Per-model handwritten creators ──────────────────────────────────────
#
# Models the generic engine cannot build (custom save()/clean(), CHECK
# constraints, required shape interplay).  Each creator is REAL-DB: plain
# ORM construction, no mocks.


def _create_subscription(tenant: Any, _user: Any) -> Any:
    # P2-3 (close-oss-release-conditions) — the paid probe creators live
    # WITH their owning apps (hub/apps/<paid>/idor_probe_creators.py,
    # registered at app-ready) and are consumed through the same
    # registry-inversion seam as the estate creator: this module MUST
    # NOT import paid code (GATE-29).
    from hub.apps.testing.estate_probe_creators import (
        ProbeCreatorUnregistered,
        get_probe_creator,
    )

    creator = get_probe_creator("billing.Subscription")
    if creator is None:
        raise ProbeCreatorUnregistered(
            "no owning app registered the billing.Subscription probe "
            "creator — billing.apps.ready() must run "
            "idor_probe_creators.register()"
        )
    return creator(tenant, _user)


def _create_draft_listing(tenant: Any, user: Any) -> Any:
    from hub.apps.testing.estate_probe_creators import (
        ProbeCreatorUnregistered,
        get_probe_creator,
    )

    creator = get_probe_creator("marketplace.Listing.draft")
    if creator is None:
        raise ProbeCreatorUnregistered(
            "no owning app registered the marketplace.Listing.draft probe "
            "creator — marketplace.apps.ready() must run "
            "idor_probe_creators.register()"
        )
    asset = _create_active_asset(tenant, user)
    return creator(tenant, user, asset=asset)


def _create_order(tenant: Any, user: Any) -> Any:
    from hub.apps.testing.estate_probe_creators import (
        ProbeCreatorUnregistered,
        get_probe_creator,
    )

    creator = get_probe_creator("marketplace.Order")
    if creator is None:
        raise ProbeCreatorUnregistered(
            "no owning app registered the marketplace.Order probe creator "
            "— marketplace.apps.ready() must run idor_probe_creators.register()"
        )
    listing = _create_published_listing(tenant, user)
    return creator(tenant, user, listing=listing)


def _create_published_listing(tenant: Any, user: Any) -> Any:
    from hub.apps.testing.estate_probe_creators import (
        ProbeCreatorUnregistered,
        get_probe_creator,
    )

    creator = get_probe_creator("marketplace.Listing.published")
    if creator is None:
        raise ProbeCreatorUnregistered(
            "no owning app registered the marketplace.Listing.published "
            "probe creator — marketplace.apps.ready() must run "
            "idor_probe_creators.register()"
        )
    asset = _create_active_asset(tenant, user)
    return creator(tenant, user, asset=asset)


def _create_active_asset(tenant: Any, user: Any) -> Any:
    from hub.apps.assets.models import Asset, AssetStatus

    # ACTIVE so marketplace/publish flows accept it (a DRAFT asset cannot
    # be listed) — the activation BUSINESS-RULES chain is pinned by the
    # assets suites; the probe needs a row in the final state.
    return Asset.objects.create(
        tenant=tenant,
        created_by=user,
        name=f"probe-asset-{uuid.uuid4().hex[:8]}",
        # key is unique per tenant — never the model default ('').
        key=f"probe-{uuid.uuid4().hex[:8]}",
        status=AssetStatus.ACTIVE,
    )


def _create_access_request(tenant: Any, user: Any) -> Any:
    from hub.apps.governance.models import AccessRequest

    asset = _create_active_asset(tenant, user)
    return AccessRequest.objects.create(
        tenant=tenant,
        requested_by=user,
        asset=asset,
        reason=f"probe access {uuid.uuid4().hex[:8]}",
        requested_access_type="READ",
        status="PENDING",
    )


def _create_compliance_run(tenant: Any, _user: Any) -> Any:
    from hub.apps.compliance.models import ComplianceRun

    asset = _create_active_asset(tenant, _user)
    return ComplianceRun.objects.create(tenant=tenant, asset=asset, status="PENDING")


def _create_dq_run(tenant: Any, _user: Any) -> Any:
    from hub.apps.dq.models import DQRun
    from hub.apps.jobs.models import Job

    asset = _create_active_asset(tenant, _user)
    job = synthesize_instance(Job, tenant, _user)
    return DQRun.objects.create(
        tenant=tenant,
        asset=asset,
        job=job,
        profile_key=f"probe-profile-{uuid.uuid4().hex[:8]}",
        engine="GREAT_EXPECTATIONS",
        status="PENDING",
    )


def _create_webhook(tenant: Any, _user: Any) -> Any:
    from hub.apps.webhooks.models import Webhook

    return Webhook.objects.create(
        tenant=tenant,
        name=f"probe-webhook-{uuid.uuid4().hex[:8]}",
        url=f"https://example.com/hook-{uuid.uuid4().hex[:8]}",
        secret=f"probe-secret-{uuid.uuid4().hex[:8]}",
        event_types=["asset.created"],
    )


def _create_scheduled_ingestion(tenant: Any, _user: Any) -> Any:
    from hub.apps.scheduled_ingestion.models import ScheduledIngestion

    return ScheduledIngestion.objects.create(
        tenant=tenant,
        name=f"probe-ingestion-{uuid.uuid4().hex[:8]}",
        schedule_config={"cron": "0 0 * * *"},
        source_type="S3",
    )


def _create_transformation_pipeline(tenant: Any, _user: Any) -> Any:
    from hub.apps.transformation.models import TransformationPipeline

    return TransformationPipeline.objects.create(
        tenant=tenant,
        name=f"probe-pipeline-{uuid.uuid4().hex[:8]}",
        pipeline_definition={"version": "1", "steps": [{"name": "probe", "type": "select"}]},
    )


def _create_virtual_dataset(tenant: Any, _user: Any) -> Any:
    from hub.apps.virtualization.models import VirtualDataset

    return VirtualDataset.objects.create(
        tenant=tenant,
        name=f"probe-vds-{uuid.uuid4().hex[:8]}",
        query="SELECT 1",
        query_type="SQL",
    )


def _create_databricks_workspace(tenant: Any, _user: Any) -> Any:
    # P0-4 (close-oss-release-conditions) — the estate probe creator
    # lives WITH the estate (databricks_admin/e2e_tooling/
    # idor_probe_fixtures.py, registered at app-ready) and is consumed
    # through the registry-inversion seam: this module is
    # provider-agnostic and MUST NOT import estate code (GATE-54).
    from hub.apps.testing.estate_probe_creators import (
        EstateProbeCreatorUnregistered,
        get_estate_probe_creator,
    )

    creator = get_estate_probe_creator("databricks_admin.DatabricksWorkspace")
    if creator is None:
        # Only reachable when the estate app IS installed but its
        # ready() registration is missing — fail loud, never a silent
        # generic fallback.
        raise EstateProbeCreatorUnregistered(
            "no provider registered the databricks_admin.DatabricksWorkspace "
            "probe creator — databricks_admin.apps.ready() must run "
            "idor_probe_fixtures.register()"
        )
    return creator(tenant, _user)


def _create_ml_subscription(tenant: Any, user: Any) -> Any:
    from hub.apps.tenants.models import PlanCategory

    subscription = _create_subscription(tenant, user)
    subscription.category = PlanCategory.ML_AI
    subscription.save()
    return subscription


def _create_tenant_config(tenant: Any, _user: Any) -> Any:
    from hub.apps.tenants.models import TenantConfig

    # One config per tenant (unique) — idempotent, matching the real
    # _get_config_or_create semantics in the tenants views.
    config, _created = TenantConfig.objects.get_or_create(
        tenant=tenant, defaults={"rate_limits": {}}
    )
    return config


def _create_file(tenant: Any, user: Any) -> Any:
    from hub.apps.files.models import File, FileStatus

    return File.objects.create(
        tenant=tenant,
        created_by=user,
        name=f"probe-file-{uuid.uuid4().hex[:8]}",
        content_type="text/plain",
        size=0,
        storage_path=f"probe/bucket/{uuid.uuid4().hex[:8]}.txt",
        status=FileStatus.ACTIVE,
    )


def _create_dq_alerting_rule(tenant: Any, _user: Any) -> Any:
    from hub.apps.dq.models import DQAlertingRule

    return DQAlertingRule.objects.create(
        tenant=tenant,
        name=f"probe-rule-{uuid.uuid4().hex[:8]}",
        metric_type="quality_score",
        threshold=0.9,
        comparison_operator="<",
        severity="MEDIUM",
        alert_channels=["EMAIL"],
        channel_config={"emails": [f"probe-{uuid.uuid4().hex[:8]}@example.com"]},
    )


def _create_retention_policy(tenant: Any, _user: Any) -> Any:
    from hub.apps.governance.models import RetentionPolicy

    asset = _create_active_asset(tenant, _user)
    return RetentionPolicy.objects.create(
        tenant=tenant,
        name=f"probe-retention-{uuid.uuid4().hex[:8]}",
        asset=asset,
        policy_type="TIME_BASED",
        retention_period_days=30,
    )


def _create_ab_test(tenant: Any, _user: Any) -> Any:
    # P2-3 — the ml probe creator lives with the ml app and registers at
    # app-ready through the probe seam (no paid import here — GATE-29).
    from hub.apps.testing.estate_probe_creators import (
        ProbeCreatorUnregistered,
        get_probe_creator,
    )

    creator = get_probe_creator("ml.ABTest")
    if creator is None:
        raise ProbeCreatorUnregistered(
            "no owning app registered the ml.ABTest probe creator — "
            "ml.apps.ready() must run idor_probe_creators.register()"
        )
    return creator(tenant, _user)


def _create_scheduled_export(tenant: Any, _user: Any) -> Any:
    from hub.apps.scheduled_export.models import ScheduledExport

    return ScheduledExport.objects.create(
        tenant=tenant,
        name=f"probe-export-{uuid.uuid4().hex[:8]}",
        schedule_config={"cron": "0 0 * * *", "timezone": "UTC"},
        destination_type="S3",
        destination_config={"bucket": "probe-bucket"},
        source_scope={"asset_ids": [str(uuid.uuid4())]},
    )


def _create_workflow_definition(_tenant: Any, _user: Any) -> Any:
    from hub.apps.orchestration.models import WorkflowDefinition

    # WorkflowDefinition is GLOBAL (no tenant FK) — definitions are shared;
    # only the INSTANCE is tenant-scoped.
    return WorkflowDefinition.objects.create(
        name=f"probe-wfdef-{uuid.uuid4().hex[:8]}",
        dsl_json={"version": "1", "steps": [{"name": "probe", "type": "noop"}]},
    )


def _create_preview_result(tenant: Any, _user: Any) -> Any:
    # The pipeline FK recurses through the TransformationPipeline creator
    # (valid steps); only the scalar required fields belong here.
    from django.utils import timezone as dj_timezone

    from hub.apps.transformation.models import PreviewResult, TransformationPipeline

    asset = _create_active_asset(tenant, _user)
    pipeline = synthesize_instance(TransformationPipeline, tenant, _user)
    return PreviewResult.objects.create(
        tenant=tenant,
        preview_id=f"probe-preview-{uuid.uuid4().hex[:8]}",
        cache_key=f"probe-cache-{uuid.uuid4().hex[:8]}",
        preview_data={},
        sample_size=0,
        asset=asset,
        pipeline=pipeline,
        expires_at=dj_timezone.now() + timedelta(hours=1),
    )


def _create_scheduled_export_run(tenant: Any, _user: Any) -> Any:
    from hub.apps.scheduled_export.models import ScheduledExportRun

    export = _create_scheduled_export(tenant, _user)
    return ScheduledExportRun.objects.create(
        scheduled_export=export,
        tenant=tenant,
        # The DB CHECK constraint only admits RUNNING/COMPLETED/FAILED/CANCELLED.
        status="COMPLETED",
        items_exported=0,
    )


CREATORS: dict[str, CREATOR] = {
    "billing.Subscription": _create_subscription,
    "governance.AccessRequest": _create_access_request,
    "compliance.ComplianceRun": _create_compliance_run,
    "dq.DQRun": _create_dq_run,
    "webhooks.Webhook": _create_webhook,
    "scheduled_ingestion.ScheduledIngestion": _create_scheduled_ingestion,
    "transformation.TransformationPipeline": _create_transformation_pipeline,
    "virtualization.VirtualDataset": _create_virtual_dataset,
    "databricks_admin.DatabricksWorkspace": _create_databricks_workspace,
    "dq.DQAlertingRule": _create_dq_alerting_rule,
    "governance.RetentionPolicy": _create_retention_policy,
    "ml.ABTest": _create_ab_test,
    "scheduled_export.ScheduledExport": _create_scheduled_export,
    "scheduled_export.ScheduledExportRun": _create_scheduled_export_run,
    "transformation.PreviewResult": _create_preview_result,
    "orchestration.WorkflowDefinition": _create_workflow_definition,
    "files.File": _create_file,
    "assets.Asset": _create_active_asset,
    "marketplace.Listing": _create_published_listing,
    "marketplace.Order": _create_order,
    "tenants.TenantConfig": _create_tenant_config,
}

# ── Nested-list parent creators (route → callable(tenant, user) → parent obj) ──


def _parent_tenant(tenant: Any, _user: Any) -> Any:
    return tenant


PARENT_CREATORS: dict[str, Callable[[Any, Any], Any]] = {
    "GET:/api/v1/tenants/{tenant_id}/sparql-endpoints/": _parent_tenant,
    "POST:/api/v1/tenants/{tenant_id}/sparql-endpoints/": _parent_tenant,
}


# ── Per-route object creators ────────────────────────────────────────────
#
# Routes whose queryset requires MORE than a bare model row (the BaaS API
# key surface filters ``baas_tier_assignment__isnull=False`` over the
# shared auth.APIKey model).  Keyed by the manifest route key; the
# generator validates each one in a rolled-back transaction and records
# the name in the manifest; the suite builds the probe object through it.


def _create_baas_api_key(tenant: Any, user: Any) -> Any:
    # P2-3 — the baas tier assignment lives with the baas app and
    # registers at app-ready through the probe seam (no paid import).
    from hub.apps.testing.estate_probe_creators import (
        ProbeCreatorUnregistered,
        get_probe_creator,
    )

    creator = get_probe_creator("baas.APIKeyTierAssignment")
    if creator is None:
        raise ProbeCreatorUnregistered(
            "no owning app registered the baas.APIKeyTierAssignment probe "
            "creator — baas.apps.ready() must run idor_probe_creators.register()"
        )
    # The generic engine owns the key row (unique key_hash etc.); the
    # route creator only adds the tier assignment the BaaS surface filters on.
    api_key = synthesize_instance(_auth_api_key_model(), tenant, user)
    creator(tenant, user, api_key=api_key)
    return api_key


def _auth_api_key_model():
    from hub.apps.auth.models import APIKey

    return APIKey


_ROUTE_OBJECT_CREATORS: dict[str, Callable[[Any, Any], Any]] = {}
for _listing_key in (
    "GET:/api/v1/marketplace/listings/",
    "POST:/api/v1/marketplace/listings/",
    "GET:/api/v1/marketplace/listings/{id}/",
    "PATCH:/api/v1/marketplace/listings/{id}/",
    "PUT:/api/v1/marketplace/listings/{id}/",
    "DELETE:/api/v1/marketplace/listings/{id}/",
    "GET:/api/v1/marketplace/listings/{id}/preview/",
    "POST:/api/v1/marketplace/listings/{id}/publish/",
    "POST:/api/v1/marketplace/listings/{id}/unpublish/",
):
    _ROUTE_OBJECT_CREATORS[_listing_key] = _create_draft_listing
for _ml_key in (
    "GET:/api/v1/billing/subscription/ml/current/",
    "POST:/api/v1/billing/subscription/ml/current/change-plan/",
):
    _ROUTE_OBJECT_CREATORS[_ml_key] = _create_ml_subscription
for _baas_key in (
    "GET:/api/v1/baas/api-keys/",
    "POST:/api/v1/baas/api-keys/",
    "GET:/api/v1/baas/api-keys/{id}/",
    "GET:/api/v1/baas/api-keys/{id}/quota/",
    "PATCH:/api/v1/baas/api-keys/{id}/",
    "PUT:/api/v1/baas/api-keys/{id}/",
    "DELETE:/api/v1/baas/api-keys/{id}/",
):
    _ROUTE_OBJECT_CREATORS[_baas_key] = _create_baas_api_key


def route_object_creator(route_key: str) -> Callable[[Any, Any], Any] | None:
    return _ROUTE_OBJECT_CREATORS.get(route_key)


def route_object_creator_name(route_key: str) -> str | None:
    creator = _ROUTE_OBJECT_CREATORS.get(route_key)
    return getattr(creator, "__name__", None) if creator else None


def iter_route_object_creator_keys():
    return iter(_ROUTE_OBJECT_CREATORS)


# ── Nested-detail URL param resolvers ────────────────────────────────────
#
# Multi-param detail routes whose non-lookup URL params are NESTED resource
# ids (parent/child) — the generic engine cannot know the child model.
# Each resolver builds a real child row under ``obj`` (the parent).


def _policy_application_for(_tenant: Any, _user: Any, domain: Any) -> Any:
    from django.apps import apps

    from hub.apps.mesh.models import PolicyApplication

    application = synthesize_instance(PolicyApplication, domain.tenant, _user)
    application.domain = domain
    if application.policy_id is None:
        # The policy FK is nullable (SET_NULL) so the generic engine leaves
        # it — the view's lookup needs a real policy on the application.
        policy = synthesize_instance(
            apps.get_model("governance", "AccessPolicy"), domain.tenant, _user
        )
        application.policy = policy
    application.save()
    # The URL param is the POLICY id (the view looks the application up by
    # policy_id + domain), not the application's own pk.
    return application.policy_id


def _compliance_report_for(_tenant: Any, _user: Any, domain: Any) -> Any:
    from hub.apps.mesh.models import ComplianceReport

    report = synthesize_instance(ComplianceReport, domain.tenant, _user)
    if hasattr(report, "domain"):
        report.domain = domain
        report.save()
    return report.pk


def _dlq_item_for(_tenant: Any, _user: Any, ingestion: Any) -> Any:
    from hub.apps.scheduled_ingestion.models import DeadLetterQueueItem

    item = synthesize_instance(DeadLetterQueueItem, ingestion.tenant, _user)
    item.scheduled_ingestion = ingestion
    item.save()
    return item.pk


def _workflow_instance_for(tenant: Any, _user: Any, _obj: Any) -> Any:
    from django.apps import apps

    instance = synthesize_instance(
        apps.get_model("orchestration", "WorkflowInstance"), tenant, _user
    )
    return instance.pk


URL_PARAM_RESOLVERS: dict[str, dict[str, Callable[[Any, Any, Any], Any]]] = {
    "GET:/api/v1/assets/workflows/{workflow_instance_id}/status/": {
        "workflow_instance_id": _workflow_instance_for,
    },
    "GET:/api/v1/contracts/products/workflows/{workflow_instance_id}/status/": {
        "workflow_instance_id": _workflow_instance_for,
    },
    "DELETE:/api/v1/mesh/domains/{id}/policies/{policy_id}/": {
        "policy_id": _policy_application_for,
    },
    "GET:/api/v1/mesh/domains/{id}/compliance/reports/{report_id}/": {
        "report_id": _compliance_report_for,
    },
    "POST:/api/v1/scheduled-ingestions/{id}/dlq/{dlq_item_id}/resolve/": {
        "dlq_item_id": _dlq_item_for,
    },
    "POST:/api/v1/scheduled-ingestions/{id}/dlq/{dlq_item_id}/retry/": {
        "dlq_item_id": _dlq_item_for,
    },
}

# Routes whose POSITIVE control (own-tenant request) is skipped: the
# cross-tenant 404 remains the IDOR assertion, and the object-resolves
# property is already pinned by the route's plain retrieve sibling.  Each
# skip carries its reason.
POSITIVE_CONTROL_SKIPS: dict[str, str] = {
    "POST:/api/v1/scheduled-ingestions/{id}/sync/": (
        "the positive control syncs the Prefect deployment (external service; "
        "order-dependent in the shared dev container) — the cross-tenant 404 "
        "direction stays probed and resolve-ness is pinned by "
        "GET /scheduled-ingestions/{id}/"
    ),
    "POST:/api/v1/scheduled-exports/{id}/sync/": (
        "same Prefect sync contract as the ingestions twin"
    ),
    "POST:/api/v1/security/incidents/{id}/resolve/": (
        "the resolve permission layer returns an existence-agnostic 403 for "
        "the synthesized incident state; the cross-tenant direction (403/404, "
        "indistinguishable) is the assertion and resolve-ness is pinned by "
        "GET /security/incidents/{id}/"
    ),
    "POST:/api/v1/ml/models/{id}/sync-from-odh/": (
        "the positive control executes the ODH registry sync (external "
        "service — connection refused in the DB-only job); the cross-tenant "
        "404 direction stays probed and resolve-ness is pinned by "
        "GET /ml/models/{id}/"
    ),
    "POST:/api/v1/marketplace/orders/{id}/confirm-payment/": (
        "the action 404s for orders without a Stripe payment transaction — "
        "a positive control cannot distinguish that state 404; the object "
        "resolution is pinned by GET /marketplace/orders/{id}/"
    ),
    "GET:/api/v1/marketplace/listings/{id}/lineage/": (
        "the lineage action 404s both for foreign ids and for listings with "
        "no lineage data — a positive control cannot distinguish; resolve-ness "
        "is pinned by GET /marketplace/listings/{id}/"
    ),
    "POST:/api/v1/databricks/workspaces/{id}/test/": (
        "the positive control executes a live connection test against the "
        "Databricks API — unreachable from the DB-only security job; the "
        "cross-tenant 404 direction stays probed"
    ),
    "POST:/api/v1/contracts/{id}/convert/": (
        "the convert action executes the datacontract CLI service (external "
        "process) on the happy path — unreachable in the DB-only security "
        "job; the cross-tenant 404 direction stays probed"
    ),
    "GET:/api/v1/contracts/{id}/fields/{field_name}/lineage/": (
        "the LineageService 404s on any field_name absent from the contract's "
        "lineage data — a synthesized contract has none; resolve-ness is pinned "
        "by GET /contracts/{id}/"
    ),
    "GET:/api/v1/contracts/{id}/models/{model_name}/lineage/": (
        "same LineageService contract as the field-level route"
    ),
}


# Routes whose LIST probe may not assert "B's own object present": the
# collection is COMPUTED (recommendation engines etc.), not a passthrough
# of model rows.  The isolation assertion — A's object absent — still
# holds.  Each skip carries its reason.
LIST_OWN_OBJECT_SKIPS: dict[str, str] = {
    "GET:/api/v1/assets/recommendations/": (
        "computed recommendations, not a row passthrough — a synthesized asset "
        "generates no recommendation entry"
    ),
    "GET:/api/v1/audit/audit-events/resource-activity/": (
        "derived activity view — the result rows are activity records, not "
        "AuditEvent rows; the isolation assertion runs on the cross-tenant "
        "query-param probe instead"
    ),
    "GET:/api/v1/audit/resource-activity/": (
        "twin of the resource-activity shim route — same derived-list reason"
    ),
    "GET:/api/v1/contracts/schema/json-schema/": (
        "returns the GLOBAL canonical contract schema, not tenant rows"
    ),
    "GET:/api/v1/data-movement/config/": (
        "the config serializer omits the pk from the payload — the row IS "
        "returned (count: 1), but the id cannot be asserted by string match"
    ),
    "GET:/api/v1/dpia/records/asset-status/": (
        "derived status view over an Asset — the isolation assertion runs "
        "on the cross-tenant query-param probe"
    ),
    "GET:/api/v1/files/quota/": (
        "derived quota view (used_bytes/limit per plan) — not a row passthrough"
    ),
    "GET:/api/v1/governance/access-requests/pending-count/": (
        "aggregate count view ({'count': N}) — not a row passthrough"
    ),
    "GET:/api/v1/governance/access/access-requests/pending-count/": (
        "twin mount of the pending-count aggregate"
    ),
    "GET:/api/v1/governance/access/certifications/summary/": (
        "aggregate summary view — not a row passthrough"
    ),
    "GET:/api/v1/governance/certifications/summary/": (
        "twin mount of the certifications summary aggregate"
    ),
    "GET:/api/v1/governance/access/retention-policies/dashboard/": (
        "aggregate dashboard view — not a row passthrough"
    ),
    "GET:/api/v1/governance/access/retention-policies/quarterly-report/": (
        "aggregate quarterly-report view — not a row passthrough"
    ),
    "GET:/api/v1/governance/retention-policies/dashboard/": (
        "twin mount of the retention dashboard aggregate"
    ),
    "GET:/api/v1/governance/retention-policies/quarterly-report/": (
        "twin mount of the retention quarterly-report aggregate"
    ),
    "GET:/api/v1/notifications/user-notifications/unread-count/": (
        "aggregate unread-count view — not a row passthrough"
    ),
    "GET:/api/v1/scheduled-ingestions/dashboard/": (
        "aggregate dashboard view — not a row passthrough"
    ),
    "GET:/api/v1/tenants/config/me/usage/": ("derived usage view — not a row passthrough"),
    "GET:/api/v1/tenants/me/usage/": ("twin mount of the usage view"),
    "GET:/api/v1/governance/access/certifications/expiring/": (
        "expiry-window filter — a synthesized certification carries no soon-expiry date, so B's list is legitimately empty; the A-absence assertion still verifies scoping"
    ),
    "GET:/api/v1/governance/certifications/expiring/": ("twin mount of the expiring-window filter"),
    "GET:/api/v1/marketplace/listings/search/": (
        "the search surface excludes DRAFT listings — a synthesized DRAFT is legitimately absent from B's results; the A-absence assertion still verifies scoping"
    ),
    "GET:/api/v1/ropa/generations/preview/": (
        "derived preview view (gap summary, not a row passthrough)"
    ),
    "GET:/api/v1/scheduled-ingestions/costs/": (
        "derived cost summary view (aggregates, not a row passthrough)"
    ),
    "GET:/api/v1/scheduled-ingestions/dead-letter-queue/": (
        "derived DLQ summary view (aggregates + items of DLQ rows, not the ScheduledIngestion passthrough)"
    ),
    "GET:/api/v1/tenants/config/me/config/": (
        "me-route — returns the CALLER's config keyed by tenant_id, not the TenantConfig pk passthrough"
    ),
    "GET:/api/v1/tenants/me/config/": ("twin mount of the me-config view"),
    "GET:/api/v1/tenants/config/me/feature-flag-history/": (
        "me-route — derived history view ({'events': []} for an untouched tenant)"
    ),
    "GET:/api/v1/tenants/me/feature-flag-history/": ("twin mount of the feature-flag-history view"),
    "GET:/api/v1/tenants/config/me/feature-flags/": (
        "me-route — returns the flag LIST, not the TenantConfig pk passthrough"
    ),
    "GET:/api/v1/tenants/me/feature-flags/": ("twin mount of the feature-flags view"),
    "GET:/api/v1/tenants/config/me/tax-id/": (
        "me-route — returns the caller's tax-id dict, not a TenantConfig passthrough"
    ),
    "GET:/api/v1/tenants/me/tax-id/": ("twin mount of the tax-id view"),
    "GET:/api/v1/tenants/me/plan/": (
        "me-route — returns the caller's plan dict, not the TenantConfig passthrough"
    ),
    "GET:/api/v1/tenants/me/plan/available-ml-addons/": (
        "me-route — the response is the caller's own plan-state (400 below Starter, 409 with an ML add-on); no row passthrough"
    ),
    "GET:/api/v1/tenants/me/plan/available-upgrades/": (
        "me-route — returns the GLOBAL plan catalogue filtered by the caller's tier, not the TenantConfig passthrough"
    ),
    "GET:/api/v1/warehouses/connections/residency-mismatches/": (
        "derived audit view (count + mismatches of non-compliant connections) — a synthesized compliant connection has none; not a row passthrough"
    ),
    "GET:/api/v1/webhooks/webhooks/event-types/": (
        "returns the GLOBAL event-type catalogue, not webhook rows"
    ),
}

# me/state-dependent GET routes whose OWN-state responses legitimately
# vary (plan-tier gates, conflict states) — the IDOR assertion is the
# A-absence, not the status.  Each entry carries its reason.
LIST_ACCEPTED_STATUSES: dict[str, tuple[int, ...]] = {
    "GET:/api/v1/tenants/me/plan/available-ml-addons/": (200, 400, 409),
}

# Per-route REQUEST HEADERS the API contract demands (e.g. the data-first
# asset create requires an Idempotency-Key).  ``{uuid}`` expands to a fresh
# UUID per request.
ROUTE_HEADERS: dict[str, dict[str, str]] = {
    # The idempotency key is COMPOSED from the caller's tenant + the
    # canonical request body (IdempotencyService.compose_key) — a random
    # UUID would be rejected as malformed.
    "POST:/api/v1/assets/data-first/": {"Idempotency-Key": "{idempotency}"},
}


# Per-route CREATE payload overrides — routes whose write validation goes
# beyond the serializer (e.g. data-first requires a file_id the
# AssetSerializer does not model).  Placeholders: {probe} → fresh probe
# string; {file_a}/{file_b} → a synthesized File row of the side.
ROUTE_PAYLOAD_OVERRIDES: dict[str, dict[str, str]] = {
    "POST:/api/v1/governance/access/compliance-reports/": {
        "regime": "GDPR",
        "asset_ids": ["{asset_b}"],
    },
    "POST:/api/v1/governance/compliance-reports/": {
        "regime": "GDPR",
        "asset_ids": ["{asset_b}"],
    },
    "POST:/api/v1/tenants/me/plan/downgrade/": {
        "plan_slug": "free",
    },
    "POST:/api/v1/tenants/me/plan/upgrade/": {
        "plan_slug": "pro",
    },
    "POST:/api/v1/tenants/me/plan/available-ml-addons/": {
        "plan_slug": "ml-starter",
    },
    "POST:/api/v1/webhooks/webhooks/": {
        "event_types": ["asset.created"],
    },
    "POST:/api/v1/virtualization/datasets/": {
        "query": "SELECT 1 AS probe",
        "sources": [{"type": "postgresql", "host": "localhost", "database": "probe"}],
    },
    "POST:/api/v1/transformation/pipelines/": {
        "pipeline_definition": {"version": "1", "steps": [{"name": "probe", "type": "select"}]},
    },
    "POST:/api/v1/transformation/wrangling/": {
        "asset_id": "{asset_b}",
        "operation": {
            "type": "FILTER",
            "parameters": {"condition": {"column": "id", "operator": ">", "value": 0}},
        },
    },
    "POST:/api/v1/tenants/config/me/tax-id/": {
        "tax_id": "12-3456789",
        "tax_id_type": "EIN",
    },
    "POST:/api/v1/tenants/me/tax-id/": {
        "tax_id": "12-3456789",
        "tax_id_type": "EIN",
    },
    "POST:/api/v1/semantic/ontologies/": {
        "namespace_iri": "https://example.com/ns/probe#",
        "rdf_content": (
            "@prefix owl: <http://www.w3.org/2002/07/owl#> . "
            "@prefix ex: <https://example.com/ns/probe#> . ex:Thing a owl:Class ."
        ),
    },
    "POST:/api/v1/semantic/ldn/subscriptions/": {
        "target_inbox_url": "https://example.com/inbox/",
    },
    "POST:/api/v1/quality/runs/": {
        "dataset_id": "{dataset_b}",
        "profile_key": "intake_basic_gx",
    },
    "POST:/api/v1/quality/runs/warehouse-run/": {
        "dataset_id": "{dataset_b}",
        "warehouse_config": '{"connection_id": "probe-conn"}',
    },
    "POST:/api/v1/processor-agreements/processor-agreements/": {
        "document_hash": "{sha256}",
    },
    "POST:/api/v1/ml/models/": {
        "odh_model_id": "{probe}",
        "odh_model_version": "{probe}",
        "asset_id": "{asset_b}",
        "model_type": "CLASSIFICATION",
    },
    "POST:/api/v1/ml/inference/ab-tests/": {
        "model_id": "{mlmodel_b}",
        "variant_id": "{mlmodel2_b}",
        "traffic_split": "50:50",
        "status": "ACTIVE",
    },
    "POST:/api/v1/marketplace/orders/purchase/": {
        "listing_id": "{listing_b}",
        "payment_method": "card",
        "payment_method_details": {"token": "tok-probe"},
    },
    "POST:/api/v1/marketplace/orders/": {
        "listing_id": "{listing_b}",
    },
    "POST:/api/v1/marketplace/listings/": {
        "asset_id": "{asset_b}",
        "title": "Probe Listing",
        "short_description": "Probe listing for the IDOR matrix",
        "pricing_model": "FREE",
    },
    "POST:/api/v1/marketplace/entitlements/check-access/": {
        "asset_id": "{asset_b}",
    },
    "POST:/api/v1/integrations/marketplace/sync/": {
        "direction": "PUSH",
        "asset_ids": ["{asset_b}"],
    },
    "POST:/api/v1/integrations/marketplace/mappings/": {
        "connection_id": "{connection_b}",
        "hub_asset_id": "{asset_b}",
        "external_listing_id": "{probe}",
    },
    "POST:/api/v1/governance/access/retention-policies/": {
        "retention_period_days": "30",
    },
    "POST:/api/v1/governance/retention-policies/": {
        "retention_period_days": "30",
    },
    "POST:/api/v1/governance/access/delegations/": {
        "delegate_email": "{email_b}",
        "start_at": "2026-10-20T00:00:00Z",
        "end_at": "2026-11-20T00:00:00Z",
    },
    "POST:/api/v1/governance/delegations/": {
        "delegate_email": "{email_b}",
        "start_at": "2026-10-20T00:00:00Z",
        "end_at": "2026-11-20T00:00:00Z",
    },
    "POST:/api/v1/governance/access/certifications/initiate-review/": {
        "user_id": "{user_b}",
        "reviewer_id": "{user_b}",
    },
    "POST:/api/v1/governance/certifications/initiate-review/": {
        "user_id": "{user_b}",
        "reviewer_id": "{user_b}",
    },
    "POST:/api/v1/governance/access-requests/": {
        "dataset_id": "{dataset_b}",
    },
    "POST:/api/v1/governance/access/access-requests/": {
        "dataset_id": "{dataset_b}",
    },
    "POST:/api/v1/files/init/": {
        "name": "probe-file.txt",
        "content_type": "text/plain",
    },
    "POST:/api/v1/compliance/runs/warehouse-scan/": {
        "dataset_id": "{dataset_b}",
        # Non-empty is all the gate checks; the cross-tenant 404 fires on
        # the dataset lookup before any warehouse use.
        "warehouse_config": '{"connection_id": "probe-conn"}',
    },
    "POST:/api/v1/dq/runs/warehouse-run/": {
        "dataset_id": "{dataset_b}",
        "warehouse_config": '{"connection_id": "probe-conn"}',
    },
    "POST:/api/v1/consent/consent-records/": {
        "purpose_id": "{purpose_b}",
    },
    "POST:/api/v1/social/comments/": {
        "asset_id": "{asset_b}",
        "comment_text": "probe comment",
    },
    "POST:/api/v1/social/ratings/": {
        "asset_id": "{asset_b}",
        "rating": 5,
    },
    "POST:/api/v1/social/reviews/": {
        "asset_id": "{asset_b}",
        "review_text": "probe review",
    },
    "POST:/api/v1/compliance/runs/": {
        "dataset_id": "{dataset_b}",
    },
    "POST:/api/v1/dq/runs/": {
        "dataset_id": "{dataset_b}",
        "profile_key": "intake_basic_gx",
    },
    "POST:/api/v1/billing/subscription/current/change-plan/": {
        "plan_slug": "pro",
    },
    "POST:/api/v1/billing/subscription/ml/current/change-plan/": {
        "plan_slug": "ml-starter",
    },
    "POST:/api/v1/baas/billing-reports/generate/": {
        "api_key_id": "{baas_key_b}",
        "period_start": "2026-10-01",
        "period_end": "2026-10-15",
    },
    "POST:/api/v1/audit/event-retention-policies/": {
        "event_type": "{probe}",
        "retention_days": "30",
    },
    "POST:/api/v1/assets/data-first/": {
        "key": "{probe}",
        "name": "{probe}",
        "file_id": "{file_b}",
    },
}

# Create routes whose 2xx assertion tolerates a documented plan-limit 400
# (the quota gate fires BEFORE the create when the seeded plan's counters
# are exhausted by the probe synthesis; quota enforcement itself is pinned
# by the billing suites).
CREATE_ACCEPTED_STATUSES: dict[str, tuple[int, ...]] = {
    "POST:/api/v1/ml/models/": (200, 201, 202, 400),
    "POST:/api/v1/tenants/config/onboarding/": (200, 201, 202, 403),
    "POST:/api/v1/tenants/onboarding/": (200, 201, 202, 403),
}


# Create routes that MUTATE existing state instead of inserting a row
# (change-plan).  The probe asserts 2xx + tenant A's rows unchanged.
CREATE_MUTATES_KEYS: dict[str, str] = {
    "POST:/api/v1/tenants/config/onboarding/": (
        "onboarding MUTATES the caller's own onboarding state — no new row; "
        "the state machine may 403 when already onboarded"
    ),
    "POST:/api/v1/tenants/onboarding/": (
        "twin mount of the onboarding mutation (same state-machine 403)"
    ),
    "POST:/api/v1/social/ratings/": ("a re-rating UPSERTS the caller's existing row — no new pk"),
    "POST:/api/v1/notifications/user-notifications/read-all/": (
        "read-all MARKS rows read — it inserts nothing"
    ),
    "POST:/api/v1/marketplace/entitlements/check-access/": (
        "check-access QUERIES the entitlement state — it inserts no row"
    ),
    "POST:/api/v1/contracts/validate-draft/": (
        "validate-draft VALIDATES an existing draft — it inserts no row"
    ),
    "POST:/api/v1/billing/subscription/current/change-plan/": (
        "change-plan swaps the caller's existing subscription plan — no new row"
    ),
    "POST:/api/v1/billing/subscription/ml/current/change-plan/": (
        "ML change-plan twin — same mutate semantics"
    ),
}


# Fields the create payload must DROP (the serializer marks them required
# but the create flow treats them as optional references — a random UUID
# would 404 the parent resolution, e.g. social comments' parent_comment_id).
ROUTE_PAYLOAD_DROP_FIELDS: dict[str, list[str]] = {
    "POST:/api/v1/social/comments/": ["parent_comment_id"],
}


# Bulk routes whose body carries the target ids under a specific field
# (the bulk-approve/reject contract is {"ids": [...]}).
BULK_IDS_FIELDS: dict[str, str] = {
    "POST:/api/v1/governance/access-requests/bulk-approve/": "ids",
    "POST:/api/v1/governance/access-requests/bulk-reject/": "ids",
    "POST:/api/v1/governance/access/access-requests/bulk-approve/": "ids",
    "POST:/api/v1/governance/access/access-requests/bulk-reject/": "ids",
}


# Self-route (me) actions whose own-state 400 is external-state-gated
# (Stripe customer must exist before tax-id submission — unreachable in the
# DB-only job; the mutation-confinement assertion still runs when 2xx).
SELF_ROUTE_ACCEPTED_STATUSES: dict[str, tuple[int, ...]] = {
    "POST:/api/v1/tenants/config/me/tax-id/": (200, 201, 202, 204, 400),
    "POST:/api/v1/tenants/me/tax-id/": (200, 201, 202, 204, 400),
    # Plan-state gates: the seeded plan's tier order rejects upgrades to
    # lower-order targets — a structured 400 naming no other tenant.
    "POST:/api/v1/tenants/me/plan/upgrade/": (200, 201, 202, 204, 400),
    "POST:/api/v1/tenants/me/plan/downgrade/": (200, 201, 202, 204, 400),
}


# Object-probe routes whose cross-tenant direction may legitimately answer
# 403: a permission layer that denies BEFORE object resolution with an
# existence-agnostic response (the same 403 fires for a nonexistent id —
# no existence oracle).  The strict 404 remains the default elsewhere.
OBJECT_PROBE_ACCEPTED_STATUSES: dict[str, tuple[int, ...]] = {
    "POST:/api/v1/security/incidents/{id}/resolve/": (403, 404),
}


# Bulk routes whose per-item outcome is a 200 report ({"failed": [{"id",
# "error": "not found or not permitted"}]} — deliberately ambiguous, no
# existence oracle, no mutation of the foreign rows) — the strict 404 is
# the detail-route contract, not the bulk-report contract.
BULK_ACCEPTED_STATUSES: dict[str, tuple[int, ...]] = {
    "POST:/api/v1/governance/access-requests/bulk-approve/": (200, 404),
    "POST:/api/v1/governance/access-requests/bulk-reject/": (200, 400, 404),
    "POST:/api/v1/governance/access/access-requests/bulk-approve/": (200, 404),
    "POST:/api/v1/governance/access/access-requests/bulk-reject/": (200, 400, 404),
}


# Routes whose payload-FK direction legitimately answers 400 instead of
# 404: the view validates the foreign reference against the caller's tenant
# scope and rejects with a structured VALIDATION_ERROR naming NO resource
# (no existence oracle).  The strict 404 remains the default elsewhere.
FK_PROBE_ACCEPTED_STATUSES: dict[str, tuple[int, ...]] = {
    "POST:/api/v1/dpia/records/": (400, 404),
    # The governance service rejects a cross-tenant resource reference with
    # a structured 400 naming only the caller-supplied id — no existence
    # oracle (the id was already known to the caller).
    "POST:/api/v1/governance/access-requests/": (400, 404),
    "POST:/api/v1/governance/access/access-requests/": (400, 404),
    # Foreign asset ids are silently skipped by the tenant-scoped lookup;
    # an all-foreign request ends with the structured ASSET_REQUIRED 400 —
    # no existence oracle, no mutation.
    "POST:/api/v1/marketplace/orders/purchase/": (400, 404),
    "POST:/api/v1/processor-agreements/asset-processor-links/": (400, 404),
    "POST:/api/v1/warehouses/acls/": (400, 404),
    "POST:/api/v1/processor-agreements/processor-agreements/": (400, 404),
    "POST:/api/v1/governance/access/compliance-reports/": (400, 404),
    "POST:/api/v1/governance/compliance-reports/": (400, 404),
}


# Tenant-scoped FK fields the payload-FK probe injects for routes whose
# write surface lives OUTSIDE the serializer (paired with the override
# above — {file_b} swaps to {file_a} in the cross-tenant direction).
ROUTE_PAYLOAD_FK_FIELDS: dict[str, list[str]] = {
    "POST:/api/v1/governance/access/certifications/initiate-review/": ["user_id"],
    "POST:/api/v1/governance/certifications/initiate-review/": ["user_id"],
    "POST:/api/v1/governance/access-requests/": ["dataset_id"],
    "POST:/api/v1/governance/access/access-requests/": ["dataset_id"],
    "POST:/api/v1/consent/consent-records/": ["purpose_id"],
    "POST:/api/v1/social/comments/": ["asset_id"],
    "POST:/api/v1/social/ratings/": ["asset_id"],
    "POST:/api/v1/social/reviews/": ["asset_id"],
    "POST:/api/v1/transformation/wrangling/": ["asset_id"],
    "POST:/api/v1/assets/data-first/": ["file_id"],
    "POST:/api/v1/integrations/marketplace/sync/": ["asset_ids"],
    "POST:/api/v1/marketplace/entitlements/check-access/": ["asset_id"],
    "POST:/api/v1/marketplace/listings/": ["asset_id"],
    "POST:/api/v1/marketplace/orders/": ["listing_id"],
    "POST:/api/v1/marketplace/orders/purchase/": ["listing_id"],
    "POST:/api/v1/ml/inference/ab-tests/": ["model_id"],
    "POST:/api/v1/compliance/runs/": ["dataset_id"],
    "POST:/api/v1/compliance/runs/warehouse-scan/": ["dataset_id"],
    "POST:/api/v1/dq/runs/": ["dataset_id"],
    "POST:/api/v1/dq/runs/warehouse-run/": ["dataset_id"],
    "POST:/api/v1/quality/runs/": ["dataset_id"],
    "POST:/api/v1/quality/runs/warehouse-run/": ["dataset_id"],
}


# List routes probed with the OTHER tenant's ids in the query string: the
# route's IDOR surface IS a query param (resource-activity).  Placeholders:
# ``{obj_a}`` = the route-model object of tenant A, ``{asset_a}``/``{asset_b}``
# = a synthesized Asset row of the side (real row, lazy).
LIST_CROSS_TENANT_QUERY_PARAMS: dict[str, dict[str, str]] = {
    "GET:/api/v1/audit/audit-events/resource-activity/": {
        "resource_type": "ASSET",
        "resource_id": "{asset_a}",
    },
    "GET:/api/v1/audit/resource-activity/": {
        "resource_type": "ASSET",
        "resource_id": "{asset_a}",
    },
    "GET:/api/v1/dpia/records/asset-status/": {
        "asset_id": "{asset_a}",
    },
}


# List routes where tenant A's object is DELIBERATELY visible to tenant B
# (published marketplace discovery — the ListingViewSet contract).  The
# probe asserts B's own object present and SKIPS the A-absence assertion;
# the DRAFT-side invisibility is pinned by the detail-route probes (DRAFT
# route creators) and tests/security/test_idor_marketplace.py.
LIST_CROSS_TENANT_VISIBLE_KEYS: dict[str, str] = {
    "GET:/api/v1/marketplace/listings/": (
        "published listings from VERIFIED tenants are visible cross-tenant by design"
    ),
    "GET:/api/v1/marketplace/listings/search/": (
        "the search surface searches published listings cross-tenant"
    ),
}


# List routes whose view REQUIRES query params (400 without).  Values with
# ``{obj_a}``/``{obj_b}`` placeholders are substituted by the suite with the
# corresponding side's object pk — the list probe then asserts A's object
# id never leaks into B's (scoped) result.
LIST_QUERY_PARAMS: dict[str, dict[str, str]] = {
    "GET:/api/v1/audit/audit-events/resource-activity/": {
        "resource_type": "ASSET",
        "resource_id": "{obj_b}",
    },
    "GET:/api/v1/audit/resource-activity/": {
        "resource_type": "ASSET",
        "resource_id": "{obj_b}",
    },
    "GET:/api/v1/dpia/records/asset-status/": {
        "asset_id": "{asset_b}",
    },
    "GET:/api/v1/governance/access/retention-policies/quarterly-report/": {
        "period": "2026-Q3",
    },
    "GET:/api/v1/governance/retention-policies/quarterly-report/": {
        "period": "2026-Q3",
    },
    "GET:/api/v1/social/comments/": {
        "asset_id": "{obj_b.asset}",
    },
    "GET:/api/v1/social/ratings/": {
        "asset_id": "{obj_b.asset}",
    },
    "GET:/api/v1/social/reviews/": {
        "asset_id": "{obj_b.asset}",
    },
}


# ── Generic type-driven synthesis ───────────────────────────────────────

_MAX_DEPTH = 3


def synthesize_instance(model: Any, tenant: Any, user: Any, depth: int = 0) -> Any:
    """Build a real row for ``model`` in ``tenant``'s scope.

    Raises ``SynthesisError`` with the failing field when the generic
    engine cannot construct a valid row — the generator records the
    failure and a handwritten creator (or an allowlist reason) must cover
    the model.
    """
    from django.apps import apps as django_apps

    if isinstance(model, str):
        model = django_apps.get_model(model)
    label = model._meta.label
    creator = CREATORS.get(label)
    if creator is not None:
        return creator(tenant, user)
    if depth > _MAX_DEPTH:
        raise SynthesisError(f"{label}: FK depth cap exceeded")

    from django.db.models import ForeignKey, OneToOneField

    tenant_model = django_apps.get_model("tenants", "Tenant")
    user_model = django_apps.get_model("users", "User")
    kwargs: dict[str, Any] = {}
    for field in model._meta.concrete_fields:
        if field.primary_key or field.auto_created:
            continue
        if isinstance(field, dj_models.GeneratedField):
            continue  # server-generated (search vectors etc.) — never client-set
        if isinstance(field, (ForeignKey, OneToOneField)):
            related = field.related_model
            if related is tenant_model or field.name in {"tenant", "tenant_id"}:
                kwargs[field.name] = tenant
                continue
            if related is user_model or field.name in _USER_OWNERSHIP_FIELD_NAMES:
                # Ownership FKs are ALWAYS assigned — even when nullable —
                # so the probe object belongs to the probe user (an
                # ownerless row would mask owner-or-admin 404 semantics).
                kwargs[field.name] = user
                continue
        if field.has_default() or (getattr(field, "null", False) and _skip_nullable(field)):
            continue
        kwargs[field.name] = _value_for_field(field, tenant, user, depth)
    try:
        return model.objects.create(**kwargs)
    except Exception as exc:
        raise SynthesisError(f"{label}: {type(exc).__name__}: {exc}") from exc


def _skip_nullable(field: Any) -> bool:
    """Nullable fields with no explicit requirement are left NULL unless
    they carry a CHECK/validator that would reject the row."""
    return not list(getattr(field, "validators", ()) or [])


def _value_for_field(field: Any, tenant: Any, user: Any, depth: int) -> Any:  # noqa: PLR0911
    # A per-field-type dispatch table is the natural shape of a synthesis
    # engine; each branch returns a real value, never a placeholder.
    from django.db.models import ForeignKey, OneToOneField

    if isinstance(field, (ForeignKey, OneToOneField)):
        related = field.related_model
        from django.apps import apps as django_apps

        tenant_model = django_apps.get_model("tenants", "Tenant")
        user_model = django_apps.get_model("users", "User")
        if related is tenant_model or field.name in {"tenant", "tenant_id"}:
            return tenant
        if related is user_model or field.name in _USER_OWNERSHIP_FIELD_NAMES:
            return user
        if related._meta.label == "tenants.Tenant":
            return tenant
        return synthesize_instance(related, tenant, user, depth + 1)

    from django.db.models import (
        BooleanField,
        CharField,
        DateField,
        DateTimeField,
        DecimalField,
        DurationField,
        EmailField,
        IntegerField,
        JSONField,
        SlugField,
        TextField,
        URLField,
        UUIDField,
    )

    suffix = uuid.uuid4().hex[:8]

    if isinstance(field, BooleanField):
        return False
    if isinstance(field, (CharField, TextField, SlugField)):
        choices = getattr(field, "choices", None) or []
        if choices:
            return choices[0][0]
        max_length = getattr(field, "max_length", None) or 32
        # ALWAYS unique-suffixed: per-tenant unique constraints (tenant,
        # name) are common and a fixed value collides on the second row.
        body = f"probe-{suffix}"
        return body[:max_length]
    if isinstance(field, EmailField):
        return f"probe-{suffix}@example.com"
    if isinstance(field, URLField):
        return f"https://example.com/{suffix}"
    if isinstance(field, UUIDField):
        return uuid.uuid4()
    if isinstance(field, IntegerField):
        return _clamped_int(field)
    if isinstance(field, DecimalField):
        return _clamped_decimal(field)
    if isinstance(field, DateField):
        return timezone.now().date()
    if isinstance(field, DateTimeField):
        return timezone.now()
    if isinstance(field, DurationField):
        return timedelta(0)
    if isinstance(field, JSONField):
        return {}
    if isinstance(field, dj_models.FloatField):
        return 0.0
    raise SynthesisError(
        f"{field.model._meta.label}.{field.name}: no generator for {type(field).__name__}"
    )


def _clamped_int(field: Any) -> int:
    low, high = _bounds(field)
    value = max(0, low)
    value = min(value, high)
    return int(value)


def _clamped_decimal(field: Any) -> Decimal:
    low, high = _bounds(field)
    places = getattr(field, "decimal_places", None) or 0
    value = max(Decimal(0), low)
    value = min(value, high)
    return value.quantize(Decimal(1).scaleb(-places))


def _bounds(field: Any) -> tuple[Decimal, Decimal]:
    low, high = Decimal("-999999"), Decimal("999999")
    for validator in getattr(field, "validators", ()) or ():
        limit = getattr(validator, "limit_value", None)
        if isinstance(validator, MinValueValidator) and limit is not None:
            low = max(low, Decimal(str(limit)))
        elif isinstance(validator, MaxValueValidator) and limit is not None:
            high = min(high, Decimal(str(limit)))
    return low, high


class SynthesisError(Exception):
    """A model the generic engine cannot construct — needs a handwritten
    creator or an allowlist reason."""


# ── Serializer-driven payloads (create / self_route / bulk probes) ──────


def tenant_fk_fields_of(serializer: Any) -> list[str]:
    """Writable serializer field names that reference tenant-scoped objects,
    matched by the serializer's model FK names (the repo declares FKs as
    UUID fields, not PrimaryKeyRelatedField — name matching is the signal)."""
    from django.db.models import ForeignKey, OneToOneField

    from hub.apps.core import idor_inventory as inv

    model = getattr(getattr(serializer, "Meta", None), "model", None)
    if model is None:
        return []
    fk_names: list[str] = []
    for field in model._meta.get_fields():
        if isinstance(field, (ForeignKey, OneToOneField)) and inv.is_tenant_scoped_model(
            field.related_model
        ):
            fk_names.append(field.name)
    writable = {
        name
        for name, field in serializer().fields.items()
        if not getattr(field, "read_only", False)
    }
    # Return the SERIALIZER's field name — the repo's write serializers
    # often expose the FK as ``<name>_id`` (asset_id), not ``asset``.
    resolved: list[str] = []
    for name in fk_names:
        if name in writable:
            resolved.append(name)
        elif f"{name}_id" in writable:
            resolved.append(f"{name}_id")
    return sorted(resolved)


def payload_for(serializer: Any, ids_by_field: dict[str, Any] | None = None) -> dict[str, Any]:
    """Minimal valid payload for the serializer: required writable fields
    with type-driven values.  ``ids_by_field`` (field name → object id)
    supplies every id-referencing field — the caller passes the CALLER's
    tenant ids for the create probe and the OTHER tenant's ids for the
    payload-FK probe direction."""

    ids_by_field = ids_by_field or {}
    payload: dict[str, Any] = {}
    try:
        fields = serializer().fields
    except Exception as exc:
        raise SynthesisError(f"serializer init failed: {type(exc).__name__}: {exc}") from exc
    for name, field in fields.items():
        if getattr(field, "read_only", False):
            continue
        if name in ids_by_field:
            payload[name] = str(ids_by_field[name])
            continue
        if not getattr(field, "required", False):
            continue
        payload[name] = _payload_value_for_field(field)
    return payload


def _payload_value_for_field(field: Any) -> Any:  # noqa: PLR0911
    # Serializer-type dispatch — the payload twin of the model synthesis
    # engine; each branch returns a real value, never a placeholder.
    from rest_framework import serializers as drf_serializers

    if isinstance(field, drf_serializers.PrimaryKeyRelatedField):
        return str(uuid.uuid4())
    if isinstance(field, drf_serializers.UUIDField):
        return str(uuid.uuid4())
    if isinstance(field, drf_serializers.ChoiceField):
        choices = list(field.choices.keys())
        return choices[0] if choices else None
    if isinstance(field, drf_serializers.BooleanField):
        return False
    if isinstance(field, drf_serializers.IntegerField):
        return int(_clamped_int(field))
    if isinstance(field, drf_serializers.FloatField):
        return float(_clamped_decimal(field))
    if isinstance(field, drf_serializers.DecimalField):
        return float(_clamped_decimal(field))
    if isinstance(field, drf_serializers.EmailField):
        return f"probe-{uuid.uuid4().hex[:8]}@example.com"
    if isinstance(field, drf_serializers.URLField):
        return f"https://example.com/{uuid.uuid4().hex[:8]}"
    if isinstance(field, drf_serializers.DateTimeField):
        return timezone.now().isoformat()
    if isinstance(field, drf_serializers.DateField):
        return timezone.now().date().isoformat()
    if isinstance(field, drf_serializers.JSONField):
        return {}
    if isinstance(field, drf_serializers.ListField):
        child = getattr(field, "child", None)
        if isinstance(child, (drf_serializers.UUIDField, drf_serializers.PrimaryKeyRelatedField)):
            return [str(uuid.uuid4())]
        # min_length=1 lists (e.g. breach regimes) — a real one-item list.
        return ["probe-item"]
    if isinstance(field, drf_serializers.DictField):
        return {}
    if isinstance(field, drf_serializers.CharField):
        max_length = getattr(field, "max_length", None) or 32
        return f"probe-{uuid.uuid4().hex[:8]}"[:max_length]
    if isinstance(field, drf_serializers.FileField):
        raise SynthesisError(f"{field.label or field.field_name}: file uploads are not probeable")
    return None
