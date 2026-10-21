"""W11.3 (oss-release-remediation) — ASVS V4 access-control regression matrix.

One probe per tenant-scoped route key, generated from the live API
inventory and pinned by the checked-in manifest
(``docs/api-audit/idor-probe-manifest.json`` — the matrix doc is
``docs/security/adversarial-matrices/w113-access-control-matrix.md``).

Everything here is REAL: real DB rows built by
``hub.apps.testing.idor_synthesis`` (the same engine the generator
validated), real APIClient requests through the RLS-arming middleware, two
real tenants with subscriptions, feature flags ON, and role-gated viewsets
probed with a TENANT_ADMIN user so a role 403 can never mask the IDOR
outcome.  The strict contract (per probe type) is stated in the matrix
doc; the load-bearing rule is: **cross-tenant object access must be 404,
never 403** — a 403 leaks existence.

The in-suite coverage gate (``test_coverage_gate``) recomputes the LIVE
tenant-scoped inventory and fails on manifest drift in either direction,
dead allowlist entries, or coverage below the 95% task threshold — a new
tenant-scoped route without a probe fails CI until the generator runs.
"""

from __future__ import annotations

import json
import uuid
from typing import ClassVar

import pytest
from django.contrib.auth import get_user_model
from django.db.models import (
    BooleanField,
    Model,
)
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.core import idor_inventory as inv
from hub.apps.tenants.models import Tenant
from hub.apps.testing import idor_synthesis as synth
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import UserStatus, UserTenantMembership

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.security]

User = get_user_model()

_MANIFEST = json.loads(
    (inv.REPO_ROOT / "docs" / "api-audit" / "idor-probe-manifest.json").read_text(encoding="utf-8")
)
PROBE_ROUTES = [route for route in _MANIFEST["routes"] if route.get("disposition") == "probe"]

# Positive-control expectations per probe type: the response codes that
# prove the OWNER's request resolved the object (not that it succeeded).
_POSITIVE_OK = {
    "object": {
        status.HTTP_200_OK,
        status.HTTP_201_CREATED,
        status.HTTP_202_ACCEPTED,
        status.HTTP_204_NO_CONTENT,
    },
    "list": {status.HTTP_200_OK},
    "nested_list": {status.HTTP_200_OK},
    "self_route": {
        status.HTTP_200_OK,
        status.HTTP_201_CREATED,
        status.HTTP_202_ACCEPTED,
        status.HTTP_204_NO_CONTENT,
    },
}
# Mutating object methods where the generic probe may legitimately return
# a validation error once the object RESOLVED (the IDOR signal is 404).
_OBJECT_MUTATION_OK = {status.HTTP_200_OK, status.HTTP_204_NO_CONTENT, status.HTTP_400_BAD_REQUEST}


@override_settings(
    # Real signing keys for the consent grant flow (the "__default__" ring
    # shape from hub.apps.consent.signing) — the probe asserts the TENANT
    # boundary, and the HMAC itself is pinned by the consent suites.
    CONSENT_SIGNING_KEYS_JSON={"__default__": ["00" * 32]},
)
class W113AccessControlMatrix(TestCase):
    """The generated cross-tenant probe matrix — one test per route key."""

    _objects: ClassVar[dict[str, tuple[Model, Model]]] = {}
    _related_ids: ClassVar[dict[tuple[str, str], str]] = {}

    def setUp(self):
        # Each test runs in its own transaction (django_db transaction=True)
        # which is rolled back — objects synthesized by an earlier test are
        # GONE.  The lazy caches must reset per test, or a probe would
        # assert against rows that no longer exist.
        type(self)._objects = {}
        type(self)._related_ids = {}

    @classmethod
    def setUpTestData(cls):
        uid = uuid.uuid4().hex[:8]
        cls.tenant_a = Tenant.objects.create(
            name=f"W113 Tenant A {uid}", slug=f"w113-tenant-a-{uid}"
        )
        cls.tenant_b = Tenant.objects.create(
            name=f"W113 Tenant B {uid}", slug=f"w113-tenant-b-{uid}"
        )
        for tenant in (cls.tenant_a, cls.tenant_b):
            ensure_tenant_has_active_subscription(tenant)
            # The create probes synthesize MANY rows (ML models, assets,
            # jobs...) — the seeded plan's per-tenant counters (e.g.
            # max_ml_models=3) would gate unrelated probes.  Quota
            # enforcement itself is pinned by the billing suites.
            from hub.apps.billing.models import Subscription

            subscription = Subscription.objects.filter(tenant=tenant).first()
            if subscription is not None and getattr(subscription, "plan", None) is not None:
                limits = dict(getattr(subscription.plan, "limits_json", None) or {})
                limits["max_ml_models"] = 10000
                subscription.plan.limits_json = limits
                subscription.plan.save()
            # The create probes enqueue REAL jobs into the shared Redis —
            # the default max_queued_jobs (50) exhausts after a handful of
            # probes and would 400 unrelated creates.  The quota behavior
            # itself is pinned by the jobs suites; the matrix probes
            # tenancy, so the per-tenant queue ceiling is raised.
            from hub.apps.tenants.models import TenantConfig

            config, _ = TenantConfig.objects.get_or_create(
                tenant=tenant, defaults={"rate_limits": {}}
            )
            config.max_queued_jobs = 10000
            config.max_job_concurrency = 10000
            config.save()
            if hasattr(tenant, "kyc_status"):
                tenant.kyc_status = "VERIFIED"
            for field in tenant._meta.fields:
                if isinstance(field, BooleanField) and field.name.endswith("_enabled"):
                    setattr(tenant, field.name, True)
            tenant.save()

        cls.user_a = User.objects.create_user(
            email=f"w113a-{uid}@example.com",
            password="testpass123",
            tenant=cls.tenant_a,
            status=UserStatus.ACTIVE,
        )
        cls.user_b = User.objects.create_user(
            email=f"w113b-{uid}@example.com",
            password="testpass123",
            tenant=cls.tenant_b,
            status=UserStatus.ACTIVE,
        )
        for user, tenant in ((cls.user_a, cls.tenant_a), (cls.user_b, cls.tenant_b)):
            UserTenantMembership.objects.get_or_create(user=user, tenant=tenant)
        # A SECOND active user per tenant — the delegation create cannot
        # delegate to the caller themselves.
        cls.user_a_delegate = User.objects.create_user(
            email=f"w113del-a-{uid}@example.com",
            password="testpass123",
            tenant=cls.tenant_a,
            status=UserStatus.ACTIVE,
        )
        cls.user_b_delegate = User.objects.create_user(
            email=f"w113del-b-{uid}@example.com",
            password="testpass123",
            tenant=cls.tenant_b,
            status=UserStatus.ACTIVE,
        )
        for user, tenant in (
            (cls.user_a_delegate, cls.tenant_a),
            (cls.user_b_delegate, cls.tenant_b),
        ):
            UserTenantMembership.objects.get_or_create(user=user, tenant=tenant)
        # Grant every WRITE-capable tenant role to both probe users: a
        # scope/role gate (HasScope / IsTenantAdmin / HasAnyRole) must
        # never mask the IDOR outcome — the probe asserts the TENANT
        # boundary (404), the register-row-1 contract.  AUDITOR is the one
        # RESTRICTIVE role (read-only — holding it denies writes in the
        # compliance/contracts/files gates) and is deliberately NOT granted;
        # its read-only enforcement is pinned by the app suites that grant
        # it (dq/files/compliance auditor-denial tests).
        from hub.apps.auth.scopes import ROLE_SCOPE_MAP
        from hub.apps.users.models import Role, UserRole

        probe_role_names = sorted(
            (set(ROLE_SCOPE_MAP) - {"PLATFORM_ADMIN", "AUDITOR"})
            | {"DPO", "SECURITY_ADMIN", "LEGAL_ADMIN", "DATA_CONSUMER"}
        )
        for user, tenant in ((cls.user_a, cls.tenant_a), (cls.user_b, cls.tenant_b)):
            for role_name in probe_role_names:
                role, _ = Role.objects.get_or_create(tenant=tenant, name=role_name)
                UserRole.objects.get_or_create(user=user, role=role, tenant=tenant)

    @staticmethod
    def _request(client: APIClient, method: str, url: str):
        """Bodyless methods must go out with NO content-type: a synthetic
        application/octet-stream body makes DRF 415 on views that touch
        request.data (observed on the mesh remove_policy action)."""
        if method == "GET":
            return client.get(url)
        if method == "DELETE":
            return client.delete(url)
        if method == "POST":
            return client.post(url, {}, format="json")
        if method == "PATCH":
            return client.patch(url, {}, format="json")
        if method == "PUT":
            return client.put(url, {}, format="json")
        return client.generic(method, url, data={}, format="json")

    # ── helpers ─────────────────────────────────────────────────────────

    @classmethod
    def _objects_for(cls, route: dict) -> tuple[Model, Model]:
        """(tenant A's row, tenant B's row) for a route — built lazily by
        the SAME synthesis engine the generator validated (real DB).  A
        per-route object creator (manifest ``object_creator``) wins over
        the per-model strategy — e.g. the BaaS key surface requires a
        tier assignment the bare auth.APIKey row lacks."""
        return cls._objects_for_model(
            route["model"],
            creator_name=route.get("object_creator"),
            route_key=route["key"],
        )

    @classmethod
    def _objects_for_model(
        cls,
        model_label: str,
        *,
        creator_name: str | None = None,
        route_key: str | None = None,
    ) -> tuple[Model, Model]:
        cache_key = f"{model_label}:{creator_name}" if creator_name else model_label
        cached = cls._objects.get(cache_key)
        if cached is None:
            from django.apps import apps

            model = apps.get_model(model_label)
            creator = synth.route_object_creator(route_key or "") if creator_name else None
            if creator is not None:
                obj_a = creator(cls.tenant_a, cls.user_a)
                obj_b = creator(cls.tenant_b, cls.user_b)
            else:
                obj_a = synth.synthesize_instance(model, cls.tenant_a, cls.user_a)
                obj_b = synth.synthesize_instance(model, cls.tenant_b, cls.user_b)
            cls._objects[cache_key] = (obj_a, obj_b)
            cached = cls._objects[cache_key]
        return cached

    @classmethod
    def _client(cls, user: User) -> APIClient:
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    @classmethod
    def _probe_user(cls, _route: dict, side: str) -> User:
        """The probe actor.  Both users hold EVERY tenant role (granted in
        setUpTestData), so a scope/role gate can never mask the IDOR 404 —
        the assertion is the tenant boundary itself."""
        return cls.user_a if side == "a" else cls.user_b

    @classmethod
    def _url(cls, route: dict, obj: Model | None) -> str:
        """Build the concrete URL: named reverse when possible, template
        substitution otherwise (the manifest records the mode).  Nested
        params with a recorded resolver (manifest ``url_param_resolvers``)
        get their value from the resolver-built child row."""
        values: dict[str, str] = {}
        resolvers = route.get("url_param_resolvers") or {}
        for param, semantic in (route.get("path_params") or {}).items():
            if param in resolvers:
                resolver = synth.URL_PARAM_RESOLVERS.get(route["key"], {}).get(param)
                if resolver is not None and obj is not None:
                    values[param] = str(resolver(getattr(obj, "tenant", cls.tenant_a), None, obj))
                    continue
            if semantic == "tenant_id":
                # ID-based, NOT identity-based: Django's setUpTestData replay
                # hands tests deserialized copies of the fixture objects, so
                # ``obj is cls.tenant_b`` is not replay-safe.
                if obj is None:
                    values[param] = str(cls.tenant_a.id)
                else:
                    values[param] = str(getattr(obj, "tenant_id", None) or obj.id)
            else:
                values[param] = str(getattr(obj, param, obj.pk if obj is not None else ""))
        # P3-2 (sibling-red-gates, GATE-06): the reverse-mode branch was
        # DEAD CODE — no matrix route ever sets url_mode="reverse" (the
        # only two url_mode references are this check and the probe-dict
        # pass-through), so the try/except NoReverseMatch could never
        # run. Removed: URL-name bugs must surface, not be swallowed.
        template = route["path_template"]
        for param, value in values.items():
            template = template.replace(f"{{{param}}}", str(value))
        return template

    def _payload(self, route: dict, side: str) -> dict:
        """The write payload: caller-side ids for the create probe,
        OTHER-tenant ids for the payload-FK direction."""
        serializer = inv.serializer_for_route(
            inv.RouteInfo(
                key=route["key"],
                method=route["method"],
                path_template=route["path_template"],
                url_name=route.get("url_name"),
                url_mode=route.get("url_mode"),
                lookup_field=route.get("lookup_field"),
                path_params=route.get("path_params") or {},
                view_class=route.get("view_class"),
                model=route.get("model"),
                app=route.get("app"),
                shape=route.get("shape", "list"),
                disposition="probe",
                probe_role=route.get("probe_role"),
            )
        )
        override = route.get("route_payload_override") or {}
        if serializer is not None and override:
            # MERGE: the serializer-driven payload supplies the common
            # required fields; the override patches the route-specific
            # ones (odps documents, warehouse_config, idempotent ids...).
            base_payload = self._payload_without_override(route, side, serializer)
            for drop_name in route.get("payload_drop_fields") or []:
                base_payload.pop(drop_name, None)
            for name, value in override.items():
                if isinstance(value, list):
                    base_payload[name] = [
                        _expand_override_value(self, item, side) for item in value
                    ]
                else:
                    base_payload[name] = _expand_override_value(self, value, side)
            return base_payload
        if override:
            payload: dict[str, str] = {}
            for name, value in override.items():
                if isinstance(value, list):
                    payload[name] = [_expand_override_value(self, item, side) for item in value]
                else:
                    payload[name] = _expand_override_value(self, value, side)
            return payload
        if serializer is None:
            raise AssertionError(f"{route['key']}: no serializer resolvable for payload probe")
        return self._payload_without_override(route, side, serializer)

    @classmethod
    def _payload_without_override(self, route: dict, side: str, serializer) -> dict:
        """The serializer-driven payload (no route override applied).

        The CREATE probe runs AS tenant B, so the caller-side FK references
        must be B's objects (index 1); the cross-tenant direction ("other")
        carries A's ids (index 0)."""
        other = side == "other"
        ids: dict[str, str] = {}
        for fk_name in route.get("payload_fk_fields") or []:
            if other:
                target = self._objects_for(route)[0]
                field_value = getattr(target, fk_name, None)
                if field_value is None and hasattr(target, f"{fk_name}_id"):
                    field_value = getattr(target, f"{fk_name}_id")
                if field_value is not None:
                    ids[fk_name] = getattr(field_value, "pk", field_value)
                continue
            # Caller side: a FRESH row of the RELATED model — referencing
            # the probe object's OWN FKs would violate unique-together
            # constraints (asset+processor, connection+user, ...).
            from django.apps import apps as _apps

            model = _apps.get_model(route["model"])
            field = model._meta.get_field(fk_name)
            related_model = field.related_model
            fresh_related = synth.synthesize_instance(related_model, self.tenant_b, self.user_b)
            ids[fk_name] = getattr(fresh_related, "pk", fresh_related)
        for name, field in serializer().fields.items():
            from rest_framework import serializers as drf_serializers

            if isinstance(field, drf_serializers.PrimaryKeyRelatedField):
                related = getattr(getattr(field, "queryset", None), "model", None)
                # NEVER supply a tenant field — the request tenant is
                # authoritative (a client-supplied tenant is the row-1
                # attack itself, and the view's save(tenant=...) wins anyway).
                if (
                    related is not None
                    and related._meta.label != "tenants.Tenant"
                    and name not in ids
                ):
                    ids[name] = self._related_for(related._meta.label, other=not other)
        return synth.payload_for(serializer, ids_by_field=ids)

    @classmethod
    def _related_for(cls, model_label: str, other: bool) -> str:
        """An existing row id of a related model in the chosen tenant."""
        key = (model_label, "other" if other else "caller")
        cached = cls._related_ids.get(key)
        if cached is None:
            obj_a, obj_b = cls._objects_for_model(model_label)
            cached = str((obj_b if other else obj_a).pk)
            cls._related_ids[key] = cached
        return cached

    def _created_row(self, route: dict, before: set, response) -> Model | None:
        """The row the create probe just made (diffed, never trusted from
        the response body)."""
        from django.apps import apps

        model = apps.get_model(route["model"])
        after = set(model.objects.values_list("pk", flat=True))
        new = after - before
        if not new:
            return None
        return model.objects.get(pk=sorted(new)[0])

    # ── the generated probes ────────────────────────────────────────────

    def _run_probe(self, route: dict):
        """The strict cross-tenant contract for this route key."""
        probe_type = route.get("probe_type")
        dispatcher = getattr(self, f"_probe_{probe_type}")
        dispatcher(route)

    def _probe_object(self, route: dict):
        obj_a, _obj_b = self._objects_for(route)
        url = self._url(route, obj_a)
        client_b = self._client(self._probe_user(route, "b"))
        response = self._request(client_b, route["method"], url)
        accepted = set(route.get("object_probe_accepted_statuses") or (404,))
        assert response.status_code in accepted, (
            f"{route['key']}: cross-tenant {route['method']} must be one of "
            f"{sorted(accepted)} (existence leak) — got {response.status_code}"
        )
        # Positive control: the owner resolves the object (skipped only for
        # the routes the manifest marks — resolve-ness pinned by a sibling).
        if not route.get("positive_control", True):
            return
        client_a = self._client(self._probe_user(route, "a"))
        response = self._request(client_a, route["method"], url)
        if route["method"] in {"PUT", "PATCH", "DELETE"}:
            ok_codes = _OBJECT_MUTATION_OK
        elif route["method"] == "POST":
            # Custom detail actions (activate/refresh etc.): the cross-tenant
            # 404 was asserted FIRST, so a state-based 400/409 (e.g. an ACTIVE
            # asset has nothing to activate; a refresh already in flight)
            # still proves tenant-dependent resolution.
            ok_codes = _POSITIVE_OK["object"] | {
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_409_CONFLICT,
                # 422: resolved-but-unprocessable state (e.g. the governance
                # approve action without a quorum-configured approval chain).
                status.HTTP_422_UNPROCESSABLE_ENTITY,
            }
        elif route["method"] == "GET":
            # 400/410 are acceptable for custom GET actions: the cross-tenant
            # direction already asserted 404, so a 400 (query-param
            # validation) or 410 (resolved-but-purged state, e.g. the
            # datasets sample action) contrast proves tenant-dependent
            # resolution — the row resolved for its owner and for nobody else.
            ok_codes = _POSITIVE_OK["object"] | {
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_410_GONE,
                # 409/403: resolved-but-wrong-state actions (e.g. the files
                # multipart parts listing without an upload session; the
                # marketplace preview of a DRAFT listing) — the cross-tenant
                # 404 was asserted FIRST, so a state-based 403 for the OWNER
                # still proves tenant-dependent resolution.
                status.HTTP_409_CONFLICT,
                status.HTTP_403_FORBIDDEN,
            }
        else:
            ok_codes = _POSITIVE_OK["object"]
        assert response.status_code in ok_codes, (
            f"{route['key']}: own-tenant {route['method']} must resolve the object — "
            f"got {response.status_code}"
        )

    def _probe_list(self, route: dict):
        obj_a, obj_b = self._objects_for(route)
        client_b = self._client(self._probe_user(route, "b"))
        query_params = {
            name: _substitute_placeholders(
                value, obj_a=obj_a, obj_b=obj_b, resolver=self._related_for
            )
            for name, value in (route.get("list_query_params") or {}).items()
        }
        response = client_b.get(self._url(route, None), query_params)
        accepted = set(route.get("list_accepted_statuses") or (200,))
        assert response.status_code in accepted, (
            f"{route['key']}: cross-tenant list must be one of {sorted(accepted)} — "
            f"got {response.status_code}"
        )
        response_data = (
            response.data if hasattr(response, "data") else json.loads(response.content.decode())
        )
        if not route.get("list_cross_tenant_visible"):
            assert not _contains_token(response_data, str(obj_a.pk)), (
                f"{route['key']}: tenant B's list must never carry tenant A's object"
            )
        if route.get("list_own_object", True):
            assert _contains_token(response_data, str(obj_b.pk)), (
                f"{route['key']}: tenant B's list must carry B's own object"
            )
        cross_params = route.get("list_cross_tenant_query_params") or {}
        if cross_params:
            other_query = {
                name: _substitute_placeholders(
                    value, obj_a=obj_a, obj_b=obj_b, resolver=self._related_for
                )
                for name, value in cross_params.items()
            }
            response = client_b.get(self._url(route, None), other_query)
            # 404 is the STRICT outcome (get_object_or_404 on the foreign
            # tenant's resource); 200 must then carry no trace of tenant A.
            assert response.status_code in {status.HTTP_200_OK, status.HTTP_404_NOT_FOUND}, (
                f"{route['key']}: cross-tenant query-param request must 404 or 200 — "
                f"got {response.status_code}"
            )
            if response.status_code == status.HTTP_404_NOT_FOUND:
                return
            other_data = (
                response.data
                if hasattr(response, "data")
                else json.loads(response.content.decode())
            )
            assert not _contains_token(other_data, str(obj_a.pk)), (
                f"{route['key']}: tenant B querying tenant A's resource must never "
                "leak tenant A's rows"
            )

    def _probe_create(self, route: dict):
        from django.apps import apps

        model = apps.get_model(route["model"])
        client_b = self._client(self._probe_user(route, "b"))
        payload = self._payload(route, side="caller")
        if route.get("create_mutates"):
            # Snapshot AFTER the payload build — payload synthesis creates
            # its own related rows, which must not count as API mutations.
            snapshot_a = list(model.objects.filter(tenant=self.tenant_a).values())
        # Snapshot AFTER the payload is built — the payload synthesis
        # creates its own related rows, which must not be mistaken for
        # the row the API call creates.
        before = set(model.objects.values_list("pk", flat=True))
        post_kwargs = _post_kwargs(route, payload, tenant=self.tenant_b)
        response = client_b.post(self._url(route, None), **post_kwargs)
        accepted_create = set(route.get("create_accepted_statuses") or (200, 201, 202))
        assert response.status_code in accepted_create, (
            f"{route['key']}: tenant B's create must succeed with a caller-side payload — "
            f"got {response.status_code}: {response.content[:200]!r}"
        )
        if route.get("create_mutates"):
            after_a = list(model.objects.filter(tenant=self.tenant_a).values())
            assert after_a == snapshot_a, (
                f"{route['key']}: tenant B's state-changing create must never touch tenant A's rows"
            )
            return
        if response.status_code not in {200, 201, 202}:
            # A documented non-2xx (plan-limit gate) — the row-landing
            # assertion does not apply.
            return
        created = self._created_row(route, before, response)
        assert created is not None, f"{route['key']}: create returned no new row"
        assert (
            getattr(created, "tenant_id", None) == self.tenant_b.id
            or getattr(created, "tenant", None) == self.tenant_b
        ), (
            f"{route['key']}: the created row must land in the CALLER's tenant "
            f"(register row 8) — landed in tenant_id={getattr(created, 'tenant_id', None)}"
        )
        if route.get("payload_fk_fields"):
            other_payload = self._payload(route, side="other")
            response = client_b.post(
                self._url(route, None),
                **_post_kwargs(route, other_payload, tenant=self.tenant_b),
            )
            accepted = set(route.get("fk_probe_accepted_statuses") or (404,))
            assert response.status_code in accepted, (
                f"{route['key']}: create referencing tenant A's objects must be one of "
                f"{sorted(accepted)} — got {response.status_code}"
            )

    def _probe_payload_fk(self, route: dict):
        client_b = self._client(self._probe_user(route, "b"))
        payload = self._payload(route, side="other")
        response = client_b.post(
            self._url(route, None),
            **_post_kwargs(route, payload, tenant=self.tenant_b),
        )
        accepted = set(route.get("fk_probe_accepted_statuses") or (404,))
        assert response.status_code in accepted, (
            f"{route['key']}: cross-tenant payload references must be one of "
            f"{sorted(accepted)} before execution — got {response.status_code}: "
            f"{response.content[:300]!r}"
        )

    def _probe_bulk(self, route: dict):
        obj_a, _ = self._objects_for(route)
        client_b = self._client(self._probe_user(route, "b"))
        fk_fields = (
            [route.get("bulk_ids_field")]
            if route.get("bulk_ids_field")
            else (route.get("payload_fk_fields") or ["ids"])
        )
        accepted = set(route.get("bulk_accepted_statuses") or (404,))
        for field_name in fk_fields:
            payload = {field_name: [str(obj_a.pk)]}
            response = client_b.post(self._url(route, None), payload, format="json")
            assert response.status_code in accepted, (
                f"{route['key']}: bulk action over tenant A's ids must be one of "
                f"{sorted(accepted)} — got {response.status_code} for {field_name}"
            )

    def _probe_self_route(self, route: dict):
        from django.apps import apps

        model = apps.get_model(route["model"])
        snapshot = list(model.objects.filter(tenant=self.tenant_a).values())
        client_b = self._client(self._probe_user(route, "b"))
        payload = self._payload(route, side="caller")
        if route["method"] == "POST":
            response = client_b.post(
                self._url(route, None),
                payload or {},
                format="json",
                **_headers_for(route, tenant=self.tenant_b, payload=payload or {}),
            )
        else:
            response = client_b.patch(self._url(route, None), payload or {}, format="json")
        accepted_self = set(route.get("self_route_accepted_statuses") or (200, 201, 202, 204))
        assert response.status_code in accepted_self, (
            f"{route['key']}: tenant B's /me/ mutation must succeed — "
            f"got {response.status_code}: {response.content[:200]!r}"
        )
        after = list(model.objects.filter(tenant=self.tenant_a).values())
        assert after == snapshot, (
            f"{route['key']}: tenant B's /me/ mutation leaked into tenant A's row"
        )

    def _probe_nested_list(self, route: dict):
        parent_creator = synth.PARENT_CREATORS.get(route["key"])
        assert parent_creator is not None, f"{route['key']}: no parent creator recorded"
        parent_a = parent_creator(self.tenant_a, self.user_a)
        parent_b = parent_creator(self.tenant_b, self.user_b)
        client_b = self._client(self._probe_user(route, "b"))
        if route["method"] != "GET":
            # Nested create/action: the cross-tenant direction is the
            # parent resolution — B must not operate on A's parent id.
            response = client_b.post(self._url(route, parent_a), {}, format="json")
            assert response.status_code == status.HTTP_404_NOT_FOUND, (
                f"{route['key']}: tenant B mutating via tenant A's parent id must 404 — "
                f"got {response.status_code}"
            )
            return
        url_a = self._url(route, parent_a)
        url_b = self._url(route, parent_b)
        response = client_b.get(url_a)
        assert response.status_code == status.HTTP_404_NOT_FOUND, (
            f"{route['key']}: tenant B listing via tenant A's parent id must 404 — "
            f"got {response.status_code}"
        )
        response = client_b.get(url_b)
        assert response.status_code == status.HTTP_200_OK, (
            f"{route['key']}: tenant B listing via B's own parent id must 200 — "
            f"got {response.status_code}"
        )

    # ── unauthenticated sweep + the in-suite coverage gate ──────────────

    def _run_unauth(self, route: dict):
        client = APIClient()
        obj_a, _ = self._objects_for(route)
        target = obj_a if route.get("probe_type") == "object" else None
        response = client.get(self._url(route, target))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED, (
            f"{route['key']}: unauthenticated request must 401 — got {response.status_code}"
        )

    def test_coverage_gate(self):
        """Live inventory vs manifest + allowlist: drift fails, <95% fails."""
        live = inv.enumerate_routes()
        allowlist = inv.load_allowlist()
        problems, summary = inv.audit_coverage(live, _MANIFEST, allowlist)
        assert not problems, "IDOR coverage gate problems:\n" + "\n".join(problems)
        assert summary["coverage_pct"] >= inv.COVERAGE_THRESHOLD_PCT, summary


# ── Per-route test generation ────────────────────────────────────────────
#
# pytest.mark.parametrize does NOT expand unittest TestCase methods (the
# first suite run proved it: 3 collected items).  TestCase is required for
# setUpTestData + per-test transactional isolation, so the probe methods
# are generated with real names — unittest/pytest discover them by the
# ``test_`` prefix and each failure names its exact route key.


def _expand_override_value(probe, value: str, side: str) -> str:  # noqa: PLR0911
    """Expand a route-payload-override placeholder to a real value.
    (A placeholder-dispatch table is the natural shape here.)"""
    if value == "{probe}":
        return f"probe-{uuid.uuid4().hex[:8]}"
    if value == "{uuid}":
        return str(uuid.uuid4())
    if value == "{sha256}":
        import hashlib as _hashlib

        return _hashlib.sha256(uuid.uuid4().bytes).hexdigest()
    if value == "{mlmodel_b}":
        return probe._related_for("ml.MLModel", other=(side != "other"))
    if value == "{mlmodel2_b}":
        from django.apps import apps as _apps

        ml_model = _apps.get_model("ml", "MLModel")
        row = synth.synthesize_instance(ml_model, probe.tenant_b, probe.user_b)
        return str(row.pk)
    if value == "{listing_b}":
        return probe._related_for("marketplace.Listing", other=(side != "other"))
    if value == "{listing_a}":
        return probe._related_for("marketplace.Listing", other=(side == "other"))
    if value == "{connection_b}":
        return probe._related_for("integrations.MarketplaceConnection", other=(side != "other"))
    if value == "{connection_a}":
        return probe._related_for("integrations.MarketplaceConnection", other=(side == "other"))
    if value == "{user_b}":
        return str(probe.user_b.pk if side != "other" else probe.user_a.pk)
    if value == "{user_a}":
        return str(probe.user_a.pk if side != "other" else probe.user_b.pk)
    if value == "{email_b}":
        return probe.user_b_delegate.email if side != "other" else probe.user_a_delegate.email
    if value == "{email_a}":
        return probe.user_a_delegate.email if side != "other" else probe.user_b_delegate.email
    if value == "{asset_b}":
        return probe._related_for("assets.Asset", other=(side != "other"))
    if value == "{asset_a}":
        return probe._related_for("assets.Asset", other=(side == "other"))
    if value == "{purpose_b}":
        return probe._related_for("consent.ConsentPurpose", other=(side != "other"))
    if value == "{purpose_a}":
        return probe._related_for("consent.ConsentPurpose", other=(side == "other"))
    if value == "{dataset_b}":
        return probe._related_for("datasets.Dataset", other=(side != "other"))
    if value == "{dataset_a}":
        return probe._related_for("datasets.Dataset", other=(side == "other"))
    if value == "{baas_key_b}":
        creator = synth.route_object_creator("GET:/api/v1/baas/api-keys/{id}/")
        assert creator is not None, "baas key creator missing"
        return str(
            creator(
                probe.tenant_b if side != "other" else probe.tenant_a,
                probe.user_b if side != "other" else probe.user_a,
            ).pk
        )
    if value == "{file_a}":
        return probe._related_for("files.File", other=(side == "other"))
    if value == "{file_b}":
        # The CREATE probe runs AS tenant B — B's own file.
        return probe._related_for("files.File", other=(side != "other"))
    return value


def _canonical_body(payload: dict) -> str:
    """The canonical wire body the IdempotencyService hashes (sort_keys +
    compact separators — the server hashes request.body verbatim, so the
    client MUST send this exact form for the key to match)."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _post_kwargs(route: dict, payload: dict, *, tenant) -> dict:
    """POST kwargs honoring the route's header contract — idempotent
    routes send the CANONICAL body string (the server hashes request.body
    verbatim; format='json' would re-serialize with different whitespace
    and break the key match)."""
    headers = _headers_for(route, tenant=tenant, payload=payload)
    if any(template == "{idempotency}" for template in (route.get("route_headers") or {}).values()):
        return {
            "data": _canonical_body(payload),
            "content_type": "application/json",
            **headers,
        }
    return {"data": payload, "format": "json", **headers}


def _headers_for(route: dict, *, tenant, payload) -> dict[str, str]:
    """Expand the per-route header contract (Idempotency-Key etc.).

    The Idempotency-Key is COMPOSED from the caller's tenant + the
    canonical request body — the server rejects random UUIDs as malformed
    (hub.apps.core.idempotency)."""
    from hub.apps.core.idempotency import IdempotencyService

    headers: dict[str, str] = {}
    for name, template in (route.get("route_headers") or {}).items():
        if template == "{idempotency}":
            header_value = IdempotencyService.compose_key(tenant.id, _canonical_body(payload))
        elif template == "{uuid}":
            header_value = str(uuid.uuid4())
        else:
            header_value = template
        # DRF's test client only maps kwargs to environ verbatim — pass the
        # HTTP_ form so request.META.get("HTTP_IDEMPOTENCY_KEY") resolves.
        headers[f"HTTP_{name.upper().replace('-', '_')}"] = header_value
    return headers


def _substitute_placeholders(value: str, *, obj_a, obj_b, resolver) -> str:
    """Expand the query-param placeholders:
    ``{obj_a}``/``{obj_b}`` → the side's route-model pk;
    ``{obj_b.asset}`` → a dotted FK traversal off the side's object;
    ``{asset_a}``/``{asset_b}`` → a synthesized Asset row of the side."""
    text = value
    for side_obj, side_name in ((obj_a, "obj_a"), (obj_b, "obj_b")):
        text = text.replace(f"{{{side_name}}}", str(side_obj.pk))
        import re as _re

        for match in _re.finditer(r"\{" + side_name + r"\.([a-zA-Z_]+)\}", text):
            related = getattr(side_obj, match.group(1), None)
            text = text.replace(match.group(0), str(getattr(related, "pk", related) or ""))
    text = text.replace("{asset_a}", resolver("assets.Asset", other=False)).replace(
        "{asset_b}", resolver("assets.Asset", other=True)
    )
    return text


def _contains_token(payload, needle: str) -> bool:
    """Token-level containment — str(value) == needle for any scalar in the
    payload.  Substring matching would collide integer pks with ISO
    timestamps ('202' ⊂ '2026-10-16…')."""
    if isinstance(payload, dict):
        return any(_contains_token(value, needle) for value in payload.values())
    if isinstance(payload, list):
        return any(_contains_token(value, needle) for value in payload)
    return str(payload) == needle


def _slug(key: str) -> str:
    return (
        key.lower()
        .replace("/", "_")
        .replace("{", "")
        .replace("}", "")
        .replace("-", "_")
        .replace(":", "_")
        .replace(".", "_")
    )


def _make_probe_method(route: dict):
    def method(self):
        self._run_probe(route)

    method.__doc__ = f"Cross-tenant probe: {route['method']} {route['path_template']}"
    return method


def _make_unauth_method(route: dict):
    def method(self):
        self._run_unauth(route)

    method.__doc__ = f"Unauthenticated 401: {route['method']} {route['path_template']}"
    return method


for _route in PROBE_ROUTES:
    setattr(
        W113AccessControlMatrix,
        f"test_probe_{_slug(_route['key'])}",
        _make_probe_method(_route),
    )
for _route in [r for r in PROBE_ROUTES if r["method"] == "GET"]:
    setattr(
        W113AccessControlMatrix,
        f"test_unauth_{_slug(_route['key'])}",
        _make_unauth_method(_route),
    )
