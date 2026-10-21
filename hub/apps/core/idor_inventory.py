"""W11.3 (oss-release-remediation) — the tenant-scoped API-route inventory.

The DB-FREE core of the ASVS V4 access-control regression matrix: route
enumeration via the live URL resolver, view→model resolution, tenant-scope
and platform-admin classification, manifest schema, allowlist parsing, and
the ≥95% coverage math.  **Nothing in this module executes a query** — the
synthesis validation (which needs the DB) lives in the generator command and
its results are recorded in the checked-in manifest.

Consumers:

  * ``generate_idor_probes`` (management command) — enumerate + classify,
    validate synthesis in rolled-back savepoints, write the manifest and
    render the matrix doc;
  * ``check_idor_coverage`` (management command) — DB-free drift check
    both directions, allowlist validation, the ≥95% gate, and the
    committed coverage report (the GATE-21 house pattern);
  * ``tests/security/test_w113_asvs_v4_access_control.py`` — the probe
    suite reads the manifest, and its in-suite gate test recomputes the
    live inventory so a new tenant-scoped route without a probe fails CI;
  * ``scripts/tests/test_w113_idor_matrix_veracity.py`` — the static
    veracity pin.

Scope rule (stated in the matrix doc and enforced here): a *tenant-scoped
route* is a runtime-resolved route whose view's model has a ``tenant`` FK
to ``tenants.Tenant`` AND whose effective permission surface is not
platform-admin-gated.  Platform admins cross tenants by design; those
routes are excluded from the denominator (pinned by
``tests/security/test_admin_user_edit_security.py`` and
``tests/security/test_privilege_escalation.py``) and listed in the matrix
doc.  Coverage = probed / (probed + allowlisted) ≥ 95%.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from django.apps import apps as django_apps
from django.urls import get_resolver
from django.urls.resolvers import RoutePattern, URLPattern, URLResolver

if TYPE_CHECKING:
    from django.db.models import Model

REPO_ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = REPO_ROOT / "docs" / "api-audit" / "idor-probe-manifest.json"
ALLOWLIST_PATH = REPO_ROOT / "lint" / "idor-coverage-allowlist.yml"
MATRIX_DOC_PATH = (
    REPO_ROOT / "docs" / "security" / "adversarial-matrices" / "w113-access-control-matrix.md"
)
COVERAGE_REPORT_PATH = REPO_ROOT / "docs" / "audits" / "w113-idor-coverage-2026-10-15.md"
STATIC_INVENTORY_PATH = REPO_ROOT / "docs" / "api-audit" / "current-api-inventory.md"

COVERAGE_THRESHOLD_PCT = 95.0

VALID_DISPOSITIONS = frozenset(
    {"probe", "allowlist", "platform_admin", "no_tenant_fk", "unresolved"}
)

# The probe-type taxonomy (stated in the matrix doc).  Every tenant-scoped
# route key gets exactly one probe type:
#
#   object      detail route — cross-tenant 404, positive control 200
#   list        collection GET — B sees own rows, never A's
#   create      collection POST — the created row lands in the CALLER's
#               tenant (scopes-as-decoration row 8); when the write
#               serializer exposes tenant-scoped FK fields, the payload-FK
#               probe (A's ids → 404) runs as well
#   payload_fk  POST/PATCH with tenant-scoped FK surface only (service-
#               triggering creates skip the create probe — the 404
#               direction fires before execution)
#   bulk        POST bulk actions — A's ids in the payload → 404
#   self_route  /me/ routes — mutation confined to the caller's tenant
#   nested_list nested-router collection — cross-tenant parent id → 404
PROBE_TYPES = frozenset(
    {"object", "list", "create", "payload_fk", "bulk", "self_route", "nested_list"}
)

_BULK_ACTION_RE = re.compile(r"/bulk-[a-z-]+/?$")
_ME_ROUTE_RE = re.compile(r"/me/|/me$")

# Routes whose platform-admin gating lives INSIDE the view body (manual
# ``request.user.is_platform_admin`` checks) — invisible to the static
# permission classifier.  Excluded from the denominator by the scope rule.
MANUAL_PLATFORM_ADMIN_ROUTE_KEYS = frozenset(
    {
        "POST:/api/v1/jobs/dlq/purge_resolved/",
    }
)

# Permission class names that mark a platform-admin-gated (cross-tenant by
# design) surface.  Class-NAME matched (not imported) so this module stays
# decoupled from auth's permission module graph.
_PLATFORM_ADMIN_PERMISSION_NAMES = (
    "IsPlatformAdmin",
    "IsPlatformAdminUser",
    "IsPlatformAdminOrReadOnly",
)

# Permission class names that gate on a TENANT role rather than mere
# authentication — the suite uses a TENANT_ADMIN user for both the
# cross-tenant probe (so a 403 role-gate cannot mask the 404 IDOR signal)
# and the positive control.
_TENANT_ROLE_PERMISSION_NAMES = (
    "IsTenantAdmin",
    "IsTenantAdminOrDPO",
    "IsTenantAdminProcessorAgreements",
    "HasAnyRole",
)

# Format-suffix twin produced by DRF routers — both the legacy
# `\.(?P<format>[a-z0-9]+)` regex form and the newer
# `{drf_format_suffix:format}` route form.  These duplicates are dropped:
# the base route is the probe target.
_FORMAT_SUFFIX_RE = re.compile(r"\\\.\(\?P<format>\[a-z0-9\]\+\)/?$")
_FORMAT_SUFFIX_ROUTE_RE = re.compile(
    r"(?:<drf_format_suffix:format>|\{drf_format_suffix:format\})/?$"
)

# Converter-normalized template param, e.g. `<uuid:pk>` → `{pk}`.
_TEMPLATE_PARAM_RE = re.compile(r"<[a-z]+:(?P<name>[^>]+)>")
_PLAIN_PARAM_RE = re.compile(r"<(?P<name>[^>]+)>")
_BRACED_PARAM_RE = re.compile(r"\{(?P<name>[a-z_]+):[^}]+\}")
# Already-normalized `{name}` forms (the RegexPattern branch emits these).
_BARE_PARAM_RE = re.compile(r"\{(?P<name>[a-zA-Z0-9_]+)\}")
# RegexPattern fallback: `(?P<name>...)` groups — the inner pattern may
# carry char classes and quantifiers (lookup_value_regex UUID typings:
# `(?P<pk>[0-9a-f]{8}-...)`).  Non-greedy up to the closing paren; the
# remainder check below rejects any richer construct left over.
_REGROUP_RE = re.compile(r"\(\?P<(?P<name>[a-zA-Z0-9_]+)>.*?\)")
# RegexPattern.describe() junk: quoted regex + `[name='...']` annotations.
_QUOTED_SEGMENT_RE = re.compile(r"'(?P<inner>[^']*)'")
_NAME_ANNOTATION_RE = re.compile(r" \[name='[^']*'\]")
# What may remain once every (?P<name>[...]) group is removed: plain path
# characters only.  Anything richer (alternation, lookaheads, \\d, bare
# quantifiers) is not describable as a probe template → pattern skipped.
_REMAINDER_OK_RE = re.compile(r"^[a-zA-Z0-9_/\-^$. ]*$")


@dataclass(frozen=True)
class RouteInfo:
    """One (method, path) route key over the resolved URL conf."""

    key: str
    method: str
    path_template: str
    url_name: str | None
    url_mode: str  # "reverse" | "template"
    lookup_field: str | None
    path_params: dict[str, str]  # param name -> semantic ("pk" | "tenant_id" | ...)
    view_class: str | None
    model: str | None  # "app_label.ModelName"
    app: str | None
    shape: str  # "detail" | "list" | "nested_list"
    disposition: str
    probe_role: str | None
    probe_type: str | None = None  # object | list | create | payload_fk | self_route | nested_list
    synthesis: str | None = None
    allowlist_reason: str | None = None
    methods_present: tuple[str, ...] = ()
    payload_fk_fields: tuple[str, ...] = ()
    parent_creator: str | None = None
    object_creator: str | None = None
    url_param_resolvers: dict[str, str] = field(default_factory=dict)
    positive_control: bool = True
    list_own_object: bool = True
    list_query_params: dict[str, str] = field(default_factory=dict)
    list_cross_tenant_query_params: dict[str, str] = field(default_factory=dict)
    list_accepted_statuses: tuple[int, ...] = (200,)
    route_headers: dict[str, str] = field(default_factory=dict)
    route_payload_override: dict[str, str] = field(default_factory=dict)
    create_mutates: bool = False
    fk_probe_accepted_statuses: tuple[int, ...] = (404,)
    bulk_ids_field: str | None = None
    bulk_accepted_statuses: tuple[int, ...] = (404,)
    list_cross_tenant_visible: bool = False
    create_accepted_statuses: tuple[int, ...] = (200, 201, 202)
    object_probe_accepted_statuses: tuple[int, ...] = (404,)
    self_route_accepted_statuses: tuple[int, ...] = (200, 201, 202, 204)
    payload_drop_fields: tuple[str, ...] = ()


def _view_class_of(pattern: URLPattern) -> Any | None:
    callback = getattr(pattern, "callback", None)
    return getattr(callback, "view_class", None) or getattr(callback, "cls", None)


def _describe(pattern: URLPattern) -> str | None:
    """The route template for a pattern, or None when the pattern is
    noise (format-suffix twin, api-root, regex junk) and must be skipped.

    RoutePattern carries the clean ``_route`` string; RegexPattern
    (re_path) is accepted only when its regex reduces to simple
    ``(?P<name>[...])`` groups — anything richer (negative lookaheads,
    alternations) is not describable as a probe template and is skipped.
    """
    inner = getattr(pattern, "pattern", None)
    if isinstance(inner, RoutePattern):
        # The clean route string — `<converter:name>` forms only.
        described = _FORMAT_SUFFIX_ROUTE_RE.sub("", inner._route)
        if not described:
            return None
        return described.strip("/") or None
    regex = getattr(inner, "describe", lambda: "")() or ""
    regex = _NAME_ANNOTATION_RE.sub("", regex)
    # Quote-wrapped regex fallback form: `'^api/...$' [name='...']`.
    if regex.startswith("'"):
        quoted = _QUOTED_SEGMENT_RE.match(regex)
        if quoted:
            regex = quoted.group("inner")
    regex = _FORMAT_SUFFIX_RE.sub("", regex)
    # Every named group removed must leave plain path characters.
    remainder = _REGROUP_RE.sub("", regex)
    if not _REMAINDER_OK_RE.match(remainder):
        return None
    described = _REGROUP_RE.sub(lambda m: f"{{{m.group('name')}}}", regex)
    described = described.strip("^$").strip("/").rstrip("?/")
    if not described or described == "/":
        return None
    return described


def _normalize_template(described: str) -> tuple[str, dict[str, str]]:
    """``assets/<uuid:pk>/`` → (``/api-relative/{pk}/``, ``{pk: pk}``)."""
    path_params: dict[str, str] = {}
    text = described
    for regex in (_TEMPLATE_PARAM_RE, _PLAIN_PARAM_RE, _BRACED_PARAM_RE, _BARE_PARAM_RE):
        for match in list(regex.finditer(text)):
            name = match.group("name")
            text = text.replace(match.group(0), f"{{{name}}}")
            path_params[name] = "tenant_id" if name == "tenant_id" else "pk"
    if text and not text.startswith("/"):
        text = "/" + text
    if len(text) > 1 and not text.endswith("/"):
        text += "/"
    return text, path_params


def _resolve_route_model(view_cls: Any) -> tuple[Model | None, str | None]:
    """Resolve the view's model: queryset attr → serializer Meta.model →
    instance-method introspection (queryset/serializer resolved with a
    dummy request — class-attr-only access raises TypeError on viewsets
    that override ``get_serializer_class``).  Returns (model, how)."""
    # 1. Class-level queryset attribute.
    queryset = getattr(view_cls, "queryset", None)
    if queryset is not None and hasattr(queryset, "model"):
        return queryset.model, "queryset"

    # 2. Class-level serializer Meta.model.
    serializer_cls = getattr(view_cls, "serializer_class", None)
    if serializer_cls is not None:
        meta = getattr(serializer_cls, "Meta", None)
        model = getattr(meta, "model", None)
        if model is not None:
            return model, "serializer"

    # 3. Instance-method introspection with a dummy request.  Views that
    # scope per-request (ListingViewSet, marketplace orders, ...) resolve
    # here; the dummy is only ever used to pick the model CLASS, never to
    # fetch data.
    try:
        view = view_cls()
        view.request = _DummyRequest()
        if hasattr(view, "get_queryset"):
            resolved = view.get_queryset()
            if resolved is not None and hasattr(resolved, "model"):
                return resolved.model, "get_queryset"
        if hasattr(view, "get_serializer_class"):
            resolved_serializer = view.get_serializer_class()
            if resolved_serializer is not None:
                meta = getattr(resolved_serializer, "Meta", None)
                model = getattr(meta, "model", None)
                if model is not None:
                    return model, "get_serializer_class"
    except Exception:  # noqa: BLE001 — resolution is best-effort by design
        pass
    return None, None


class _DummyRequest:
    """Minimal request surface for model-resolution introspection only."""

    method = "GET"

    def __init__(self) -> None:
        # An anonymous platform-non-admin user: the most restrictive path,
        # which still yields the model class from scoped querysets.
        self.user: Any = _DummyUser()
        self.query_params: dict[str, str] = {}
        self.data: dict[str, Any] = {}


class _DummyUser:
    is_authenticated = False
    is_platform_admin = False


def _tenant_model() -> Model | None:
    try:
        return django_apps.get_model("tenants", "Tenant")
    except LookupError:
        return None


def is_tenant_scoped_model(model: Model | None) -> bool:
    """A model with a ``tenant`` FK/OneToOne to tenants.Tenant (the repo
    convention — the COLUMN is tenant_id; the field NAME is ``tenant``)."""
    if model is None:
        return False
    tenant_model = _tenant_model()
    if tenant_model is None:
        return False
    from django.db.models import ForeignKey, OneToOneField

    for model_field in model._meta.get_fields():
        if isinstance(model_field, (ForeignKey, OneToOneField)):
            if model_field.related_model is tenant_model:
                return True
            if (
                model_field.name in {"tenant", "tenant_id"}
                and model_field.related_model._meta.label == "tenants.Tenant"
            ):
                return True
    return False


def effective_permission_classes(view_cls: Any) -> list[Any]:
    classes = list(getattr(view_cls, "permission_classes", None) or [])
    try:
        get_permissions = getattr(view_cls, "get_permissions", None)
        if get_permissions is not None:
            resolved = get_permissions(view_cls)  # classmethod-style on DRF viewsets
            if resolved:
                classes = [pc.__class__ if isinstance(pc, object) else pc for pc in resolved]
    except Exception:  # noqa: BLE001 — best-effort classification
        pass
    # @action-decorated methods may override permissions per action.
    for attr in dir(view_cls):
        value = getattr(view_cls, attr, None)
        perms = (
            getattr(value, "kwargs", {}).get("permission_classes") if value is not None else None
        )
        if perms:
            classes.extend(perms)
    return classes


def _permission_names(view_cls: Any) -> set[str]:
    return {
        getattr(pc, "__name__", pc.__class__.__name__ if isinstance(pc, object) else str(pc))
        for pc in effective_permission_classes(view_cls)
    }


def is_platform_admin_gated(view_cls: Any) -> bool:
    return bool(_permission_names(view_cls) & set(_PLATFORM_ADMIN_PERMISSION_NAMES))


def needs_tenant_admin_role(view_cls: Any) -> bool:
    return bool(_permission_names(view_cls) & set(_TENANT_ROLE_PERMISSION_NAMES))


def iter_api_patterns(urlconf: str | None = None):
    """Recursively yield ``(URLPattern, prefix)`` for the API tree only."""
    for pattern in get_resolver(urlconf).url_patterns:
        yield from _walk(pattern, "")


def _walk(pattern, prefix: str):
    if isinstance(pattern, URLResolver):
        segment = str(pattern.pattern).strip("^$")
        for child in pattern.url_patterns:
            yield from _walk(child, prefix + segment)
        return
    if not isinstance(pattern, URLPattern):
        return
    described = _describe(pattern)
    if not described:
        return
    full = prefix + described
    if not full.startswith("api/"):
        return
    # Test-only surface — not part of the shipped inventory.
    if full.startswith("api/v1/test/"):
        return
    yield pattern, full


def enumerate_routes() -> list[RouteInfo]:
    """Enumerate every (method, path) API route key with classification.

    DB-free: the Django app registry and URL resolver only.
    """
    routes: list[RouteInfo] = []
    seen: set[str] = set()
    for pattern, described in iter_api_patterns():
        view_cls = _view_class_of(pattern)
        path_template, path_params = _normalize_template(described)
        action_names = _action_names_of(pattern)
        if action_names & {"retrieve", "update", "partial_update", "destroy"}:
            shape = "detail"
        elif path_params and action_names & {"list", "create"}:
            # Nested router route: URL params are PARENT ids, the actions
            # are list/create of children (e.g. communities/{id}/assets/).
            shape = "nested_list"
        elif path_params:
            # Custom @action(detail=True) route — object pk in the URL.
            shape = "detail"
        else:
            shape = "list"

        if view_cls is None:
            # Function-based view (GraphQL, SSE, APIRootView, webhooks, ...).
            for method in _methods_of_pattern(pattern):
                key = f"{method}:{path_template}"
                if key in seen:
                    continue
                seen.add(key)
                routes.append(
                    RouteInfo(
                        key=key,
                        method=method,
                        path_template=path_template,
                        url_name=getattr(pattern, "name", None),
                        url_mode="template",
                        lookup_field=None,
                        path_params=path_params,
                        view_class=None,
                        model=None,
                        app=None,
                        shape=shape,
                        disposition="unresolved",
                        probe_role=None,
                        methods_present=(method,),
                    )
                )
            continue

        model, _how = _resolve_route_model(view_cls)
        model_label = model._meta.label if model is not None else None
        if model_label:
            app = model_label.split(".")[0]
        elif view_cls.__module__.startswith("hub.apps."):
            app = view_cls.__module__.split(".")[2]
        else:
            app = None

        if is_tenant_scoped_model(model):
            disposition = "platform_admin" if is_platform_admin_gated(view_cls) else "probe"
        elif model is not None:
            disposition = "no_tenant_fk"
        elif is_platform_admin_gated(view_cls):
            disposition = "platform_admin"
        else:
            disposition = "unresolved"

        lookup_field = None
        if shape == "detail" and disposition in {"probe", "platform_admin"}:
            declared = getattr(view_cls, "lookup_field", None)
            if declared and declared in path_params:
                lookup_field = declared
            else:
                # First URL param is the object lookup for flat routes; for
                # nested routes (parents first) views declare lookup_field.
                lookup_field = next(iter(path_params), None)

        methods = _methods_of_pattern(pattern, view_cls)
        probe_role = "TENANT_ADMIN" if needs_tenant_admin_role(view_cls) else None
        for method in methods:
            key = f"{method}:{path_template}"
            if key in seen:
                continue
            seen.add(key)
            route_disposition = disposition
            if key in MANUAL_PLATFORM_ADMIN_ROUTE_KEYS:
                route_disposition = "platform_admin"
            routes.append(
                RouteInfo(
                    key=key,
                    method=method,
                    path_template=path_template,
                    url_name=getattr(pattern, "name", None),
                    url_mode="reverse" if getattr(pattern, "name", None) else "template",
                    lookup_field=lookup_field,
                    path_params=path_params,
                    view_class=view_cls.__name__,
                    model=model_label,
                    app=app,
                    shape=shape,
                    disposition=route_disposition,
                    probe_role=probe_role,
                    probe_type=_probe_type_for(shape, method, path_template),
                    methods_present=tuple(methods),
                )
            )
    return sorted(routes, key=lambda r: r.key)


def _probe_type_for(shape: str, method: str, path_template: str) -> str | None:
    """The probe contract for a probe-eligible (tenant-scoped) route key."""
    if shape == "detail":
        return "object"
    if shape == "nested_list":
        return "nested_list"
    if shape != "list":
        return None
    if method == "GET":
        return "list"
    mutation_types = (("self_route", _ME_ROUTE_RE), ("bulk", _BULK_ACTION_RE))
    for probe_type, matcher in mutation_types:
        if matcher.search(path_template):
            return probe_type
    return "create"


def _actions_of(pattern: URLPattern) -> dict[str, str]:
    """DRF's per-route ``actions`` mapping (method → action name)."""
    return dict(getattr(getattr(pattern, "callback", None), "actions", None) or {})


def _action_names_of(pattern: URLPattern) -> set[str]:
    return set(_actions_of(pattern).values())


def _methods_of_pattern(pattern: URLPattern, view_cls: Any | None = None) -> list[str]:
    """The HTTP methods this pattern ACTUALLY serves — DRF viewset
    ``.actions`` intersected with the view's ``http_method_names`` (a
    viewset that excludes ``delete`` — e.g. BreachIncidentViewSet — must
    not invent a DELETE key the API would answer with 405).  For non-viewset
    views, http_method_names ∩ defined handlers, so an APIView with only
    ``get`` does not fake DELETE/PUT/... keys."""
    actions = _actions_of(pattern)
    if actions:
        methods = {m.upper() for m in actions}
        if view_cls is not None:
            allowed = getattr(view_cls, "http_method_names", None)
            if allowed:
                methods &= {m.upper() for m in allowed}
        return sorted(methods)
    if view_cls is not None:
        names = set(getattr(view_cls, "http_method_names", ()))
        names.discard("options")
        names.discard("head")
        methods = sorted(m.upper() for m in names if hasattr(view_cls, m))
        if methods:
            return methods
    return ["GET"]


def serializer_for_route(route: RouteInfo) -> Any | None:
    """Resolve the write serializer class for a route's view (best effort,
    DB-free).  Used by the generator (payload-FK analysis) and the probe
    suite (payload construction)."""
    view_cls = None
    action_name = None

    def walk(patterns):
        nonlocal view_cls, action_name
        if view_cls is not None:
            return
        for pattern in patterns:
            if isinstance(pattern, URLResolver):
                walk(pattern.url_patterns)
            elif isinstance(pattern, URLPattern):
                callback = getattr(pattern, "callback", None)
                cls = getattr(callback, "view_class", None) or getattr(callback, "cls", None)
                if cls is not None and cls.__name__ == route.view_class:
                    view_cls = cls
                    actions = getattr(callback, "actions", None) or {}
                    action_name = actions.get(route.method.lower())
                    return

    walk(get_resolver().url_patterns)
    if view_cls is None:
        return None
    try:
        # Action-aware FIRST: create/update serializers differ from the
        # list serializer (get_serializer_class branches on self.action).
        view = view_cls()
        view.request = _DummyRequest()
        view.action = action_name
        serializer = view.get_serializer_class()
        if serializer is not None:
            return serializer
    except Exception:  # noqa: BLE001 — best-effort resolution
        pass
    serializer = getattr(view_cls, "serializer_class", None)
    return serializer


def audit_coverage(
    routes: list[RouteInfo],
    manifest: dict[str, Any],
    allowlist: dict[tuple[str, str], str],
) -> tuple[list[str], dict[str, Any]]:
    """The W11.3 coverage gate: live-inventory drift both directions,
    allowlist validation, and the ≥95% threshold.  Returns
    (problems, summary).  DB-free."""
    problems: list[str] = []
    manifest_routes = manifest.get("routes") or []
    # Only the tenant-scoped dispositions participate in the drift check —
    # platform_admin/no_tenant_fk/unresolved entries are informational
    # (excluded from the denominator by the documented scope rule).
    manifest_eligible = {
        (r["method"], r["path_template"])
        for r in manifest_routes
        if r.get("disposition") in {"probe", "allowlist"}
    }
    manifest_by_key = {(r["method"], r["path_template"]): r for r in manifest_routes}

    live_tenant_scoped = {
        (r.method, r.path_template)
        for r in routes
        if r.disposition in {"probe", "allowlist"} and r.probe_type
    }
    for key in sorted(live_tenant_scoped - manifest_eligible):
        problems.append(
            f"{key[0]} {key[1]} is tenant-scoped in the LIVE urlconf but absent "
            "from the manifest — run `python manage.py generate_idor_probes`"
        )
    for key in sorted(manifest_eligible - live_tenant_scoped):
        problems.append(
            f"manifest entry {key[0]} {key[1]} no longer resolves in the live "
            "urlconf (stale probe) — run `python manage.py generate_idor_probes`"
        )

    for (method, path_template), reason in sorted(allowlist.items()):
        entry = manifest_by_key.get((method, path_template))
        if entry is None:
            problems.append(
                f"dead allowlist entry {method} {path_template} — no matching manifest route"
            )
            continue
        if not reason:
            problems.append(f"allowlist entry {method} {path_template} has no written reason")
        if entry.get("disposition") != "allowlist":
            problems.append(
                f"allowlist entry {method} {path_template} is disposition="
                f"{entry.get('disposition')!r} in the manifest, not allowlist"
            )

    probed = sum(1 for r in manifest_routes if r.get("disposition") == "probe")
    allowlisted = sum(1 for r in manifest_routes if r.get("disposition") == "allowlist")
    denominator = probed + allowlisted
    coverage = 100.0 * probed / denominator if denominator else 0.0
    if coverage < COVERAGE_THRESHOLD_PCT:
        problems.append(
            f"coverage {coverage:.2f}% is below the {COVERAGE_THRESHOLD_PCT}% threshold "
            f"(probed={probed}, allowlisted={allowlisted})"
        )
    summary = {
        "tenant_scoped_route_keys": denominator,
        "probed": probed,
        "allowlisted": allowlisted,
        "coverage_pct": round(coverage, 2),
        "coverage_threshold_pct": COVERAGE_THRESHOLD_PCT,
    }
    return problems, summary


# ── Disposition finalization (shared by generator and check command) ─────


def finalize_dispositions(
    routes: list[RouteInfo],
    allowlist: dict[tuple[str, str], str],
    synthesis_by_model: dict[str, str],
) -> tuple[list[RouteInfo], list[str]]:
    """Apply the probe/allowlist rule; return (finalized, problems).

    Rule: a tenant-scoped route key with a probe type is probed when its
    model synthesis strategy is recorded (and, for nested_list, a parent
    creator is recorded); anything else is allowlisted and MUST carry a
    written reason from the allowlist file.
    """
    finalized: list[RouteInfo] = []
    problems: list[str] = []
    for route in routes:
        if route.disposition not in {"probe", "allowlist"}:
            finalized.append(route)
            continue
        disposition = "probe"
        reason = None
        if (
            not route.probe_type
            or (route.model and not synthesis_by_model.get(route.model))
            or (route.probe_type == "nested_list" and not route.parent_creator)
        ):
            disposition = "allowlist"
        if disposition == "allowlist":
            reason = allowlist.get((route.method, route.path_template))
            if not reason:
                problems.append(
                    f"{route.key} is not probeable but has no allowlist entry — "
                    f"add {{method: {route.method}, path: {route.path_template}, reason: ...}} "
                    f"to lint/idor-coverage-allowlist.yml"
                )
        finalized.append(
            RouteInfo(
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
                probe_type=route.probe_type,
                synthesis=(synthesis_by_model.get(route.model) if disposition == "probe" else None),
                allowlist_reason=reason,
                methods_present=route.methods_present,
                payload_fk_fields=route.payload_fk_fields,
                parent_creator=route.parent_creator,
                object_creator=route.object_creator,
                url_param_resolvers=route.url_param_resolvers,
                positive_control=route.positive_control,
                list_own_object=route.list_own_object,
                list_query_params=route.list_query_params,
                list_cross_tenant_query_params=route.list_cross_tenant_query_params,
                list_accepted_statuses=route.list_accepted_statuses,
                route_headers=route.route_headers,
                route_payload_override=route.route_payload_override,
                create_mutates=route.create_mutates,
                fk_probe_accepted_statuses=route.fk_probe_accepted_statuses,
                bulk_ids_field=route.bulk_ids_field,
                bulk_accepted_statuses=route.bulk_accepted_statuses,
                list_cross_tenant_visible=route.list_cross_tenant_visible,
                create_accepted_statuses=route.create_accepted_statuses,
                object_probe_accepted_statuses=route.object_probe_accepted_statuses,
                self_route_accepted_statuses=route.self_route_accepted_statuses,
                payload_drop_fields=route.payload_drop_fields,
            )
        )
    return finalized, problems


def compute_coverage(routes: list[RouteInfo]) -> dict[str, Any]:
    probed = sum(1 for r in routes if r.disposition == "probe")
    allowlisted = sum(1 for r in routes if r.disposition == "allowlist")
    denominator = probed + allowlisted
    coverage = 100.0 * probed / denominator if denominator else 0.0
    return {
        "tenant_scoped_route_keys": denominator,
        "probed": probed,
        "allowlisted": allowlisted,
        "excluded_platform_admin": sum(1 for r in routes if r.disposition == "platform_admin"),
        "excluded_no_tenant_fk": sum(1 for r in routes if r.disposition == "no_tenant_fk"),
        "excluded_unresolved": sum(1 for r in routes if r.disposition == "unresolved"),
        "coverage_pct": round(coverage, 2),
    }


def manifest_payload(
    routes: list[RouteInfo],
    generated_at: str,
    generator: str,
    coverage: dict[str, Any],
) -> dict[str, Any]:
    return {
        "generated_at": generated_at,
        "generator": generator,
        "coverage_threshold_pct": COVERAGE_THRESHOLD_PCT,
        **coverage,
        "routes": [asdict(r) for r in sorted(routes, key=lambda r: r.key)],
    }


def load_allowlist(path: Path | None = None) -> dict[tuple[str, str], str]:
    """Parse lint/idor-coverage-allowlist.yml → {(method, path_template): reason}."""
    import yaml

    allow_path = path or ALLOWLIST_PATH
    if not allow_path.is_file():
        raise FileNotFoundError(str(allow_path))
    raw = yaml.safe_load(allow_path.read_text(encoding="utf-8")) or {}
    entries = raw.get("entries") or []
    parsed: dict[tuple[str, str], str] = {}
    for entry in entries:
        method = (entry.get("method") or "").strip().upper()
        path_template = (entry.get("path") or "").strip()
        reason = (entry.get("reason") or "").strip()
        if not method or not path_template:
            raise ValueError(f"allowlist entry missing method/path: {entry!r}")
        parsed[(method, path_template)] = reason
    return parsed


def render_matrix_doc(
    routes: list[RouteInfo],
    coverage: dict[str, Any],
    generated_at: str,
) -> str:
    """Render the W11.3 access-control regression matrix (per-route disposition table)."""
    by_disposition: dict[str, list[RouteInfo]] = {}
    for route in routes:
        by_disposition.setdefault(route.disposition, []).append(route)

    lines = [
        "# W11.3 — ASVS V4 Access-Control Regression Matrix",
        "",
        f"Generated: {generated_at} — from the live URL resolver (the runtime API",
        "inventory; reconciled against `docs/api-audit/current-api-inventory.md`, the",
        "`categorize-api-inventory.py` source, by the generator command).  The single",
        "source of truth is `docs/api-audit/idor-probe-manifest.json` — the probe suite",
        "and the coverage gate both consume it.",
        "",
        "## Scope rule",
        "",
        "A *tenant-scoped route* is a runtime-resolved route whose view's model has a",
        "`tenant` FK to `tenants.Tenant` AND whose effective permission surface is not",
        "platform-admin-gated.  Platform admins cross tenants by design; those routes",
        "are excluded from the denominator (pinned by `tests/security/test_admin_user_edit_security.py`",
        "and `tests/security/test_privilege_escalation.py`).",
        "",
        "## Coverage",
        "",
        f"- Tenant-scoped route keys: **{coverage['tenant_scoped_route_keys']}**",
        f"- Probed (strict cross-tenant contract): **{coverage['probed']}**",
        f"- Allowlisted with written reasons: **{coverage['allowlisted']}**",
        f"- Coverage: **{coverage['coverage_pct']}%** (threshold {COVERAGE_THRESHOLD_PCT}%)",
        f"- Excluded from the denominator: {coverage['excluded_platform_admin']} platform-admin,",
        f"  {coverage['excluded_no_tenant_fk']} no-tenant-FK, {coverage['excluded_unresolved']} unresolved",
        "  (function views / GraphQL / SSE — each cited to its owning suite in the dispositions below).",
        "",
        "## Strict probe contract (per probe type)",
        "",
        "- `object` — cross-tenant retrieve/update/partial_update/destroy by tenant B on tenant",
        "  A's id → **404** (never 403 — an existence leak); own-tenant positive control → 200;",
        "  unauthenticated → 401.",
        "- `list` — tenant B's list → 200 carrying B's own row, never A's.",
        "- `create` — tenant B's POST lands the row in B's tenant (row 8: scopes/roles are not",
        "  decoration); where the write serializer exposes tenant-scoped FK fields, B's POST",
        "  referencing A's ids → **404** (payload-FK probe).",
        "- `payload_fk` — the 404 direction only (service-triggering creates skip the create",
        "  probe — the 404 fires before execution).",
        "- `bulk` — B's bulk action carrying A's ids → **404**.",
        "- `self_route` — B's /me/ mutation is confined to B's tenant (A's row unchanged).",
        "- `nested_list` — B listing via A's parent id → **404**.",
        "",
        "All probes run with real auth against the real DB with RLS request-path arming —",
        "no mocks.",
        "",
        "## Dispositions",
        "",
    ]

    for disposition in ("probe", "allowlist", "platform_admin", "no_tenant_fk", "unresolved"):
        group = by_disposition.get(disposition, [])
        lines.append(f"### {disposition} ({len(group)})")
        lines.append("")
        if disposition == "probe":
            lines.append("| Method | Path | View | Model | Type | Synthesis | Role |")
            lines.append("|---|---|---|---|---|---|---|")
            for r in group:
                lines.append(
                    f"| {r.method} | `{r.path_template}` | {r.view_class or '-'} | "
                    f"{r.model or '-'} | {r.probe_type or '-'} | {r.synthesis or '-'} | "
                    f"{r.probe_role or '-'} |"
                )
        elif disposition == "allowlist":
            lines.append("| Method | Path | Reason |")
            lines.append("|---|---|---|")
            for r in group:
                lines.append(f"| {r.method} | `{r.path_template}` | {r.allowlist_reason or '-'} |")
        else:
            lines.append("| Method | Path | View | Model |")
            lines.append("|---|---|---|---|")
            for r in group:
                lines.append(
                    f"| {r.method} | `{r.path_template}` | {r.view_class or '-'} | {r.model or '-'} |"
                )
        lines.append("")
    return "\n".join(lines)
