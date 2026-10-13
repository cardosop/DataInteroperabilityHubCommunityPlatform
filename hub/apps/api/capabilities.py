"""
Phase 228 (REQ-LIN-006, 228.0.18) — capability-flag registry.

Capability flags are a backend-driven feature-discovery surface so the
frontend can branch its UI on what the deployed backend supports
without a separate config file or environment-variable shadow. The
endpoint lives at ``GET /api/v1/capabilities/`` and returns a flat
mapping of ``capability_name -> bool``.

Phase 228 ships five lineage capability flags:

* ``lineage.cross_tenant_marketplace`` — cross-tenant marketplace
  lineage browsing (Phase 228 F1).
* ``lineage.field_level_mapping`` — field-level lineage mapping editor
  (Phase 228 F2).
* ``lineage.change_notifications`` — lineage change-notification
  emails + in-app inbox (Phase 228 F3).
* ``lineage.openlineage_export`` — OpenLineage event-export adapter
  (Phase 228 F4).
* ``lineage.snapshots`` — lineage snapshot UI (Phase 228 F5).

Each flag defaults to ``False`` in production / staging. In the
``test`` environment ALL flags default to ``True`` so test fixtures
exercise the full feature surface without per-test setup. The
default policy is encoded in :func:`get_capabilities` so future
flags inherit the same shape.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import DatabaseError, InterfaceError

# Phase 228 lineage capability flag names. The shared registry is the
# single source of truth for the five names — frontend
# ``useCapability('lineage.<flag>')`` keys against the same identifier.
LINEAGE_CAPABILITY_FLAGS: tuple[str, ...] = (
    "lineage.cross_tenant_marketplace",
    "lineage.field_level_mapping",
    "lineage.change_notifications",
    "lineage.openlineage_export",
    "lineage.snapshots",
)


def _is_test_environment() -> bool:
    """Test mode auto-enables every flag so fixtures exercise the full
    surface. Recognises ``ENVIRONMENT=test`` (canonical), ``DJANGO_ENV=test``
    (legacy), or pytest's own ``PYTEST_CURRENT_TEST`` env var (so any
    test-runner invocation defaults to ON regardless of how the env is set)."""
    import os

    if getattr(settings, "ENVIRONMENT", "").lower() == "test":
        return True
    if os.environ.get("DJANGO_ENV", "").lower() == "test":
        return True
    return bool(os.environ.get("PYTEST_CURRENT_TEST"))


def get_capabilities() -> dict[str, bool]:
    """Return the flat capability map for the current environment.

    Default policy (REQ-LIN-006):

    * Production / staging: all flags ``False``.
    * Test: all flags ``True``.

    Per-flag overrides can be supplied via Django settings under the
    ``CAPABILITY_FLAGS`` dict (keyed by flag name). An override of
    ``True`` or ``False`` wins over the environment-driven default —
    that's the escape hatch ops uses to flip a flag on for a single
    customer or to roll-out gradually.
    """
    overrides: dict[str, bool] = getattr(settings, "CAPABILITY_FLAGS", {}) or {}
    test_default = _is_test_environment()
    out: dict[str, bool] = {}
    for name in LINEAGE_CAPABILITY_FLAGS:
        if name in overrides:
            out[name] = bool(overrides[name])
        else:
            out[name] = test_default
    return out


def is_capability_enabled(name: str) -> bool:
    """Check a single capability flag. Unknown names return ``False``."""
    return get_capabilities().get(name, False)


def is_capability_enabled_for_tenant(name: str, tenant_id: str | None) -> bool:
    """Phase 228 F5 (228.F5.DoD.6) — per-tenant rollout knob.

    Returns True iff EITHER the global flag is ON OR the tenant is in
    the per-flag allow-list. Lets ops phase a rollout 5 → 50% → 100%
    without code changes:

      - Phase 1 (canary, 5 internal tenants): set
        ``CAPABILITY_FLAGS_ROLLOUT_TENANTS = {"<flag>": ["<uuid>", ...]}``
        and keep the global flag OFF.
      - Phase 2 (50%): expand the allow-list.
      - Phase 3 (100% GA): set the global flag ON in
        ``CAPABILITY_FLAGS = {"<flag>": True}``; the per-tenant
        allow-list becomes redundant (still honored, no-op).

    Falls back to the global flag check when ``tenant_id`` is None,
    so existing call-sites that don't carry tenant context keep the
    same semantics.
    """
    if is_capability_enabled(name):
        return True
    if tenant_id is None:
        return False
    overrides = getattr(settings, "CAPABILITY_FLAGS_ROLLOUT_TENANTS", {}) or {}
    allow_list = overrides.get(name, ())
    if not allow_list:
        return False
    # Compare both as strings — settings may carry UUID-as-str.
    return str(tenant_id) in {str(x) for x in allow_list}


def _compute_asset_creation_blocked_reason(tenant) -> str | None:
    """Phase 250.6.D.2 — discriminate WHY ``asset_creation_enabled`` is False.

    Returns one of:

    * ``None`` — when the gate is OPEN (``asset_creation_enabled=True``).
      The SPA reads this and renders the normal create flow.
    * ``"ONBOARDING_INCOMPLETE"`` — gate closed AND
      ``onboarding_completed_at IS None``. New tenant whose admin /
      KYC / billing signals haven't all fired yet. SPA renders the
      "Complete onboarding" CTA (the picker variant from 250.6.D.3).
    * ``"DISABLED_BY_OPS"`` — gate closed AND
      ``onboarding_completed_at IS NOT None``. Fully-onboarded tenant
      that ops manually flipped (compliance hold, billing dispute).
      SPA redirects to the existing generic "disabled" page.

    Defensive defaults:

    * Returns ``None`` when ``tenant`` is None (no tenant context →
      anonymous / unresolved → "no block reason").
    * Returns ``None`` when ``asset_creation_enabled`` is True
      (regardless of onboarding state — an explicit True means ops
      has affirmatively unlocked the tenant).
    * For pre-migration rows where ``onboarding_completed_at``
      doesn't yet exist as an attribute, we treat it as None →
      ONBOARDING_INCOMPLETE. This is the conservative answer
      (suggest CTA rather than redirect to ops disabled), and
      the data migration backfills existing tenants so this
      pre-migration branch is short-lived.
    """
    if tenant is None:
        return None
    enabled = bool(getattr(tenant, "asset_creation_enabled", True))
    if enabled:
        return None
    completed_at = getattr(tenant, "onboarding_completed_at", None)
    if completed_at is None:
        return "ONBOARDING_INCOMPLETE"
    return "DISABLED_BY_OPS"


def get_capabilities_for_request(request) -> dict[str, Any]:
    """Phase 240.4.B.4 — per-request capability map.

    Extends :func:`get_capabilities` with PER-TENANT capability values
    resolved from the authenticated user's tenant.  The SPA reads this
    response to render menus correctly without a separate
    "tenant features" endpoint round-trip.

    Currently exposes:

    * ``data_quality`` — mirror of ``Tenant.data_quality_enabled``
      (default True per D240.18).
    * ``data_quality_advanced`` — conjunctive
      ``Tenant.data_quality_enabled AND
      Tenant.data_quality_advanced_enabled``.  Conjunctive on the wire
      so the SPA never advertises a sub-feature whose parent is
      disabled — matches the backend gate semantics in
      ``check_data_quality_advanced_enabled``.

    Falls back to the global static map (``get_capabilities()``) when
    the request has no resolved tenant — anonymous + unauthenticated
    requests see only the lineage flags.
    """
    # Widen to ``Dict[str, Any]`` so the per-tenant enrichment can
    # carry non-bool values (250.6.D.2 ``asset_creation_blocked_reason``
    # is ``str | None``). The wire shape is documented in the
    # capability response schema; SPA consumers must accept mixed
    # value types per-key.
    base: dict[str, Any] = dict(get_capabilities())

    tenant = None
    try:
        from hub.apps.tenants.request_tenant import get_request_tenant

        _tid, tenant = get_request_tenant(request)
    except (DatabaseError, InterfaceError, ValidationError):
        # If tenant resolution itself blows up (DB outage or a malformed
        # tenant UUID on the request), degrade gracefully — anonymous
        # capability response is correct for an unauthenticated request.
        tenant = None

    dq_base = bool(getattr(tenant, "data_quality_enabled", True)) if tenant else False
    dq_advanced_flag = (
        bool(getattr(tenant, "data_quality_advanced_enabled", False)) if tenant else False
    )
    base["data_quality"] = dq_base
    # Conjunctive on the wire so the SPA never sees
    # ``data_quality=False, data_quality_advanced=True`` — that would
    # mislead the menu-rendering code.
    base["data_quality_advanced"] = dq_base and dq_advanced_flag

    # Phase 250.6.A.4 (D250.17) — per-tenant asset-creation kill switch.
    # Mirrors ``Tenant.asset_creation_enabled`` so the SPA can render
    # the create button / form vs the disabled-capability page upstream
    # of any form-submit. The backend gate at
    # ``hub.apps.assets.views._check_asset_creation_kill_switch``
    # returns 403 + ``code="ASSET_CREATION_DISABLED"`` regardless, so
    # this capability is purely UX-grade (preferable UX path: SPA
    # never lets the user fill out a form that's guaranteed to 403).
    #
    # Default True for an UNRESOLVED tenant context (anonymous /
    # unauthenticated requests see the "feature exists" answer; the
    # backend gate handles the actual block). Default True for a
    # tenant without the attribute too (defensive: pre-migration
    # rows that haven't yet had the field added shouldn't suddenly
    # report disabled).
    base["asset_creation"] = (
        bool(getattr(tenant, "asset_creation_enabled", True)) if tenant else True
    )

    # Phase 250.6.D.2 — discriminator field so the SPA can render
    # different UI for "incomplete onboarding" (CTA back to onboarding
    # flow) vs. "ops killed it" (generic disabled page). The plain
    # boolean ``asset_creation`` above stays for backward-compat with
    # 250.6.A's CapabilityRoute gate; the reason field is purely
    # additive enrichment.
    base["asset_creation_blocked_reason"] = _compute_asset_creation_blocked_reason(tenant)

    # Phase 285.13 — per-tenant datasets/files kill switch capabilities
    if tenant:
        base["datasets"] = bool(getattr(tenant, "datasets_enabled", True))
        base["files"] = bool(getattr(tenant, "files_enabled", True))
        base["transformation_pipelines"] = bool(getattr(tenant, "transformation_enabled", False))
    else:
        base["datasets"] = True
        base["files"] = True
        base["transformation_pipelines"] = False

    # 313.H.4 review — per-tenant compliance capability flags. The SPA's
    # compliance route gates (dpia / breach / processor agreements /
    # retention dashboard / consent / ropa / dsar queue) read these keys
    # from this response; before this block the keys were never sent, so
    # every tenant — flags on or off — was silently redirected to
    # /unavailable for ALL of those surfaces. Wire keys mirror the
    # frontend's reads (no ``_enabled`` suffix); unset fields default
    # False (explicit opt-in, per the Phase 232.x tenant flag docs).
    _COMPLIANCE_CAPABILITY_FIELDS: tuple[tuple[str, str], ...] = (
        ("compliance_consent", "compliance_consent_enabled"),
        ("compliance_dsar", "compliance_dsar_enabled"),
        ("compliance_breach", "compliance_breach_enabled"),
        ("compliance_ropa", "compliance_ropa_enabled"),
        ("compliance_dpia", "compliance_dpia_enabled"),
        ("compliance_processor_agreements", "compliance_processor_agreements_enabled"),
        ("compliance_retention_enforcer", "compliance_retention_enforcer_enabled"),
    )
    for wire_key, tenant_field in _COMPLIANCE_CAPABILITY_FIELDS:
        base[wire_key] = bool(getattr(tenant, tenant_field, False)) if tenant else False

    # openspec add-databricks-control-plane P0 — the SPA's /databricks
    # route gates on ``<CapabilityRoute capability="databricks">``.
    # Before this block the key was NEVER sent, so every tenant was
    # silently redirected to /unavailable for the whole control-plane
    # surface (JOURNEY-DB-001 E2E timed out waiting for the management
    # heading). Explicit opt-in: ``databricks_control_plane_enabled``
    # must be True AND the P0 emergency kill switch must be open. The
    # server-side endpoint gates enforce the same flags regardless, so
    # this is UX-grade like ``asset_creation``.
    base["databricks"] = (
        bool(getattr(tenant, "databricks_control_plane_enabled", False))
        and not bool(getattr(tenant, "databricks_workspaces_kill_switch", False))
        if tenant
        else False
    )

    # close-test-coverage-gaps 3.2 — UX v2 staged rollout (278.R.6). The
    # SPA's ProductTourGate reads this key from the runtime snapshot.
    # Tenant flag is default-ON for new tenants
    # (Tenant._default_ux_v2_enabled); anonymous → False (pinned in
    # test_capabilities.py). Mirrors the compliance-flag emission shape.
    base["ux_v2"] = bool(getattr(tenant, "ux_v2_enabled", False)) if tenant else False

    return base


__all__ = [
    "LINEAGE_CAPABILITY_FLAGS",
    "get_capabilities",
    "get_capabilities_for_request",
    "is_capability_enabled",
    "is_capability_enabled_for_tenant",
]


# ---------------------------------------------------------------------------
# Path-derived capability manifest (Phase 273.x hardening — E2E root cause R1)
#
# The SPA derives ~35 "feature present" capabilities by fetching the FULL
# drf-spectacular OpenAPI schema (~19.7 MB in the E2E stack) on every fresh
# mount and testing path presence client-side. Under batch load that fetch
# takes minutes or fails outright, which produces the whole failure family:
# gate spinners that never resolve, auth-fallback capability maps that answer
# False for live features, and /unavailable bounces that aren't real.
#
# Fix: the server computes the SAME availability map once per process
# (cached schema, ~2 KB JSON) and the SPA fetches
# GET /api/v1/capabilities/manifest/ instead. The frontend keeps the
# OpenAPI fetch only as a fallback for old backends (404 on this route).
#
# PARITY CONTRACT: ``PATH_CAPABILITY_DEFINITIONS`` mirrors
# ``CAPABILITY_DEFINITIONS`` in
# frontend/src/features/capabilities/services/capabilitiesService.ts
# key-for-key, predicate-for-predicate (same path strings, same regex
# semantics). Any change to one list MUST land in the other in the same
# change — drift here silently disables/gates features in the SPA.
# ---------------------------------------------------------------------------

import functools
import re as _re


def _has_path(paths: dict, exact: str) -> bool:
    return exact in paths


def _any_path(paths: dict, pred) -> bool:
    return any(pred(p) for p in paths)


def _path_regex(patterns: tuple[str, ...]) -> object:
    return _re.compile("|".join(patterns))


# (key, name, endpoint, predicate) — predicate takes the schema ``paths`` dict.
PATH_CAPABILITY_DEFINITIONS: tuple[tuple[str, str, str, Any], ...] = (
    (
        "auth.register",
        "User Registration",
        "/api/v1/auth/register/",
        lambda p: (
            _has_path(p, "/api/v1/auth/register/")
            or _any_path(p, lambda x: "auth/register" in x and x.endswith("auth/register/"))
        ),
    ),
    (
        "auth.password-reset",
        "Password Reset Request",
        "/api/v1/auth/password-reset/",
        lambda p: (
            _has_path(p, "/api/v1/auth/password-reset/")
            or _any_path(p, lambda x: "auth/password-reset" in x and "confirm" not in x)
        ),
    ),
    (
        "auth.password-reset-confirm",
        "Password Reset Confirmation",
        "/api/v1/auth/password-reset/confirm/",
        lambda p: (
            _has_path(p, "/api/v1/auth/password-reset/confirm/")
            or _any_path(p, lambda x: "auth/password-reset" in x and "confirm" in x)
        ),
    ),
    (
        "ai.natural-language-search",
        "AI Natural Language Search",
        "/api/v1/ai/natural-language-search/",
        lambda p: _has_path(p, "/api/v1/ai/natural-language-search/"),
    ),
    (
        "ai.schema-matching",
        "AI Schema Matching",
        "/api/v1/ai/schema-matching/",
        lambda p: _has_path(p, "/api/v1/ai/schema-matching/"),
    ),
    (
        "search.full-text",
        "Full-Text Search",
        "/api/search/",
        lambda p: _has_path(p, "/api/search/"),
    ),
    (
        "semantic.sparql",
        "Semantic SPARQL",
        "/api/v1/semantic/sparql",
        lambda p: (
            _has_path(p, "/api/v1/semantic/sparql")
            or _any_path(p, lambda x: "semantic/sparql" in x)
        ),
    ),
    (
        "ai.classification",
        "AI Classification",
        "/api/v1/ai/classification/",
        lambda p: _has_path(p, "/api/v1/ai/classification/"),
    ),
    (
        "ai.recommendations",
        "AI Recommendations",
        "/api/v1/ai/recommendations/",
        lambda p: _has_path(p, "/api/v1/ai/recommendations/"),
    ),
    (
        "ai.anomaly-detection",
        "AI Anomaly Detection",
        "/api/v1/ai/anomaly-detection/",
        lambda p: _has_path(p, "/api/v1/ai/anomaly-detection/"),
    ),
    (
        "lineage.cross_tenant_marketplace",
        "Cross-Tenant Marketplace Lineage",
        "/api/v1/marketplace/listings/{id}/lineage/",
        lambda p: _any_path(
            p, lambda x: bool(_re.search(r"/marketplace/listings/\{[^}]+\}/lineage/?$", x))
        ),
    ),
    (
        "contracts.lineage_field_editor",
        "Field-Level Lineage Editor",
        "/api/v1/contracts/{id}/lineage/",
        lambda p: _any_path(
            p,
            lambda x: (
                bool(_re.search(r"/contracts/\{[^}]+\}/lineage/?$", x))
                and isinstance(p.get(x), dict)
                and "patch" in p.get(x, {})
            ),
        ),
    ),
    (
        "social.ratings",
        "Social Ratings",
        "/api/v1/social/ratings/",
        lambda p: _has_path(p, "/api/v1/social/ratings/"),
    ),
    (
        "social.reviews",
        "Social Reviews",
        "/api/v1/social/reviews/",
        lambda p: _has_path(p, "/api/v1/social/reviews/"),
    ),
    (
        "social.comments",
        "Social Comments",
        "/api/v1/social/comments/",
        lambda p: _has_path(p, "/api/v1/social/comments/"),
    ),
    (
        "social.communities",
        "Social Communities",
        "/api/v1/social/communities/",
        lambda p: _has_path(p, "/api/v1/social/communities/"),
    ),
    (
        "social.activity-feeds",
        "Social Activity Feeds",
        "/api/v1/social/activity-feeds/",
        # The route is /api/v1/social/activity-feeds/ (hyphenated "feeds") —
        # a "/feed" substring can never match it, which kept this capability
        # permanently false (b6 skip root cause).
        lambda p: (
            _has_path(p, "/api/v1/social/activity-feeds/")
            or _any_path(p, lambda x: "social/activity-feeds" in x)
        ),
    ),
    (
        "developer.plugins",
        "Developer Plugins",
        "/api/v1/developer/plugins/",
        lambda p: _has_path(p, "/api/v1/developer/plugins/"),
    ),
    (
        "developer.sdk",
        "Developer SDK Documentation",
        "/api/v1/developer/sdk/",
        lambda p: _has_path(p, "/api/v1/developer/sdk/"),
    ),
    (
        "baas.api-keys",
        "BaaS API Keys",
        "/api/v1/baas/api-keys/",
        lambda p: _has_path(p, "/api/v1/baas/api-keys/"),
    ),
    (
        "baas.usage",
        "BaaS Usage Tracking",
        "/api/v1/baas/usage/",
        lambda p: _has_path(p, "/api/v1/baas/usage/"),
    ),
    ("ml.models", "ML Models", "/api/v1/ml/models/", lambda p: _has_path(p, "/api/v1/ml/models/")),
    (
        "ml.training",
        "ML Training Jobs",
        "/api/v1/ml/training/jobs/",
        lambda p: _has_path(p, "/api/v1/ml/training/jobs/"),
    ),
    (
        "ml.inference",
        "ML Inference Deployments",
        "/api/v1/ml/inference/deployments/",
        lambda p: _has_path(p, "/api/v1/ml/inference/deployments/"),
    ),
    (
        "transformation",
        "Transformation",
        "/api/v1/transformation/pipelines/",
        lambda p: (
            _has_path(p, "/api/v1/transformation/pipelines/")
            or _any_path(
                p, lambda x: "transformation/pipelines" in x or "transformation.pipelines" in x
            )
        ),
    ),
    (
        "transformation.pipelines",
        "Transformation Pipelines",
        "/api/v1/transformation/pipelines/",
        lambda p: (
            _has_path(p, "/api/v1/transformation/pipelines/")
            or _any_path(
                p, lambda x: "transformation/pipelines" in x or "transformation.pipelines" in x
            )
        ),
    ),
    (
        "mesh.domains",
        "Data Mesh Domains",
        "/api/v1/mesh/domains/",
        lambda p: (
            _has_path(p, "/api/v1/mesh/domains/") or _any_path(p, lambda x: "/mesh/domains" in x)
        ),
    ),
    (
        "virtualization.datasets",
        "Virtualization Datasets",
        "/api/v1/virtualization/datasets/",
        lambda p: (
            _has_path(p, "/api/v1/virtualization/datasets/")
            or _any_path(p, lambda x: "/virtualization/datasets" in x)
        ),
    ),
    (
        "integrations.marketplace",
        "Marketplace Integrations",
        "/api/v1/integrations/marketplace/connections/",
        lambda p: (
            _has_path(p, "/api/v1/integrations/marketplace/connections/")
            or _any_path(p, lambda x: "/integrations/" in x and "marketplace" in x)
        ),
    ),
    (
        "compliance_retention_enforcer",
        "Retention auto-enforcement",
        "/api/v1/governance/retention-policies/dashboard/",
        lambda p: _any_path(
            p, lambda x: "/governance/retention-policies" in x and "dashboard" in x
        ),
    ),
    (
        "datasets",
        "Datasets",
        "/api/v1/datasets/",
        lambda p: (
            _has_path(p, "/api/v1/datasets/")
            or _any_path(
                p,
                lambda x: (
                    bool(_re.search(r"/api/v1/datasets/", x))
                    and "/virtualization/" not in x.lower()
                ),
            )
        ),
    ),
    (
        "files",
        "Files",
        "/api/v1/files/",
        lambda p: (
            _has_path(p, "/api/v1/files/")
            or _any_path(p, lambda x: bool(_re.search(r"/api/v1/files/", x)))
        ),
    ),
    (
        "marketplace",
        "Marketplace",
        "/api/v1/marketplace/listings/",
        lambda p: _any_path(p, lambda x: "/api/v1/marketplace/" in x),
    ),
    (
        "billing",
        "Billing",
        "/api/v1/billing/subscription/",
        lambda p: _any_path(p, lambda x: x.startswith("/api/v1/billing/") and "/connect/" not in x),
    ),
    (
        "billing.stripe_connect",
        "Stripe Connect",
        "/api/v1/billing/connect/status/",
        lambda p: _any_path(p, lambda x: "/api/v1/billing/connect/" in x),
    ),
)


@functools.lru_cache(maxsize=1)
def _cached_schema_paths() -> dict:
    """drf-spectacular schema paths, built once per process.

    This is the same input the SPA's OpenAPI derivation uses — caching it
    server-side is the whole point of the manifest (the schema build +
    serialization costs ~2s and ~19.7 MB of JSON per uncached generation).

    Parity mechanism: we go through ``OpenAPISchemaView._get_schema_response``
    — the SAME view the browser hits at GET /api/v1/openapi.json — with a
    minimal request stand-in carrying the attributes drf-spectacular's
    ``build_mock_request`` reads (version, method, path, user, auth,
    query_params). Replicating the generator directly instead (urlconf +
    api_version) DOES NOT match: version resolution and postprocessing
    hooks run inside the view, and the generator alone yields a different
    path set (50 vs ~690). Using the view guarantees the manifest answers
    exactly what the SPA's OpenAPI derivation would compute.
    """
    from django.contrib.auth.models import AnonymousUser

    from hub.apps.api.views import OpenAPISchemaView

    class _SchemaRequestStandin:
        version = "v1"
        method = "GET"
        path = "/api/v1/openapi.json"

        def __init__(self):
            self.user = AnonymousUser()
            self.auth = None
            self.GET = {}
            self.query_params = {}
            self.META = {"HTTP_ACCEPT": "application/json"}

    response = OpenAPISchemaView()._get_schema_response(_SchemaRequestStandin())
    data = response.data if hasattr(response, "data") else response
    return data.get("paths", {}) or {}


def get_path_capability_manifest() -> dict[str, bool]:
    """Path-derived capability availability map (parity with the SPA)."""
    paths = _cached_schema_paths()
    out: dict[str, bool] = {}
    for key, _name, _endpoint, predicate in PATH_CAPABILITY_DEFINITIONS:
        try:
            out[key] = bool(predicate(paths))
        except Exception:
            out[key] = False
    return out


from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@api_view(["GET"])
@permission_classes([AllowAny])
def capabilities_manifest_view(_request):
    """``GET /api/v1/capabilities/manifest/`` — lightweight path-derived
    capability map. The SPA fetches this instead of the 19.7 MB OpenAPI
    schema on the capability-gate critical path (see module docstring)."""
    return Response({"capabilities": get_path_capability_manifest(), "source": "urlpatterns"})
