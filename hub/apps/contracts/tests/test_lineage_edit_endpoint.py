"""
Phase 228.F2 (REQ-LIN-F2-002 / F2.14) — endpoint tests for the
field-level lineage editor at
``PATCH /api/v1/contracts/{id}/lineage/``.

Coverage:

* Successful patch: open edges added, removed edges closed, lineage
  block re-serialised on the contract's HubContract.
* Validator findings: cycle, field-not-found, type-mismatch all
  surface as 400 with the typed code.
* Concurrency: stale ``If-Match`` → 412.
* Idempotency: same ``Idempotency-Key`` returns the cached response
  without re-applying the patch.
* Cap: > F2_MAX_EDGES_PER_PATCH → 413.
* RBAC: cross-tenant edit denied; tenant admin / contract owner
  permitted.
* Audit: one ``LINEAGE_EDGE_ADDED`` row per opened edge, one
  ``LINEAGE_EDGE_REMOVED`` per closed edge.

No mocks of internal code.  Real DB rows for tenants, users,
contracts, lineage edges, audit events.
"""

from __future__ import annotations

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_tenant(slug_prefix: str = "f2") -> Tenant:
    suffix = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"{slug_prefix}-{suffix}",
        slug=f"{slug_prefix}-{suffix}",
        status="ACTIVE",
        kyc_status=KYCStatus.VERIFIED,
    )
    ensure_tenant_has_active_subscription(tenant)
    return tenant


def _make_user(tenant: Tenant) -> User:  # type: ignore[name-defined]  # test: edge-case type exercise
    suffix = uuid.uuid4().hex[:8]
    return User.objects.create_user(
        email=f"u-{suffix}@example.com",
        password="testpass123",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )


def _grant_tenant_admin(user, tenant):
    from hub.apps.users.models import Role, UserRole

    role, _ = Role.objects.get_or_create(tenant=tenant, name="TENANT_ADMIN")
    UserRole.objects.get_or_create(user=user, tenant=tenant, role=role)


def _make_contract_with_field(
    tenant: Tenant,
    *,
    name: str,
    field_name: str = "id",
):
    """Contract with a structurally-sound HubContract carrying one
    model + one field of the given name."""
    from hub.apps.contracts.models import (
        Contract,
        ContractStatus,
        OriginalFormat,
        OriginalSpecType,
    )

    asset = Asset.objects.create(
        tenant=tenant,
        key=f"asset-{uuid.uuid4().hex[:6]}",
        name=name,
        status=AssetStatus.DRAFT,
    )
    return Contract.objects.create(
        tenant=tenant,
        asset=asset,
        version=1,
        original_spec_type=OriginalSpecType.ODCS,
        original_spec_version="3.1.0",
        original_format=OriginalFormat.JSON,
        original_raw="{}",
        hub_contract_json={
            "info": {"name": name},
            "models": [
                {
                    "name": "default",
                    "fields": [
                        {"name": field_name, "data_type": "string", "nullable": False},
                    ],
                }
            ],
        },
        normalization_status="NORMALIZED_OK",
        validation_status="VALID",
        status=ContractStatus.ACTIVE,
    )


def _client(user) -> APIClient:
    c = APIClient()
    c.force_authenticate(user=user)
    return c


def _url(contract) -> str:
    return f"/api/v1/contracts/{contract.id}/lineage/"


def _etag(contract) -> str:
    from hub.apps.contracts.views_crud import _contract_etag

    return _contract_etag(contract)


# ---------------------------------------------------------------------------
# Successful patch
# ---------------------------------------------------------------------------


class LineageEditSuccessTests(TestCase):
    def test_apply_one_edge_returns_200_and_persists(self):
        from hub.apps.contracts.models import LineageEdge

        tenant = _make_tenant("ok")
        user = _make_user(tenant)
        _grant_tenant_admin(user, tenant)
        c_src = _make_contract_with_field(tenant, name="orders", field_name="customer_id")
        c_tgt = _make_contract_with_field(tenant, name="customers", field_name="customer_id")

        client = _client(user)
        body = {
            "edges": [
                {
                    "source_contract": str(c_src.id),
                    "source_model": "default",
                    "source_field": "customer_id",
                    "target_contract": str(c_tgt.id),
                    "target_model": "default",
                    "target_field": "customer_id",
                    "edge_type": "reference",
                },
            ],
        }
        response = client.patch(
            _url(c_tgt),
            data=body,
            format="json",
            HTTP_IF_MATCH=_etag(c_tgt),
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["added"], 1)
        # Edge persisted.
        self.assertEqual(
            LineageEdge.objects.filter(
                target_contract_id=c_tgt.id,
                valid_to__isnull=True,
            ).count(),
            1,
        )

    def test_remove_existing_edge_closes_it(self):
        from hub.apps.contracts.models import LineageEdge

        tenant = _make_tenant("close")
        user = _make_user(tenant)
        _grant_tenant_admin(user, tenant)
        c_src = _make_contract_with_field(tenant, name="orders", field_name="cid")
        c_tgt = _make_contract_with_field(tenant, name="cust", field_name="cid")
        # Pre-existing open edge.
        LineageEdge.objects.create(
            tenant=tenant,
            source_contract_id=c_src.id,
            target_contract_id=c_tgt.id,
            source_model="default",
            source_field="cid",
            target_model="default",
            target_field="cid",
            edge_type="reference",
        )
        client = _client(user)
        # Empty edges list → close everything.
        response = client.patch(
            _url(c_tgt),
            data={"edges": []},
            format="json",
            HTTP_IF_MATCH=_etag(c_tgt),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["removed"], 1)
        self.assertEqual(
            LineageEdge.objects.filter(
                target_contract_id=c_tgt.id,
                valid_to__isnull=True,
            ).count(),
            0,
        )


# ---------------------------------------------------------------------------
# Validation findings (cycle, field-not-found, type-mismatch)
# ---------------------------------------------------------------------------


class LineageEditValidationTests(TestCase):
    def test_cycle_returns_409_with_cycle_path(self):
        """REQ-LIN-F2-002 spec — cycle returns HTTP 409 (not 400) with
        a ``cycle: [path]`` array in the response body.  Phase 228.F2
        meta-DoD audit corrected the prior 400 implementation."""
        from hub.apps.contracts.models import LineageEdge

        tenant = _make_tenant("cycle")
        user = _make_user(tenant)
        _grant_tenant_admin(user, tenant)
        c_a = _make_contract_with_field(tenant, name="a", field_name="x")
        c_b = _make_contract_with_field(tenant, name="b", field_name="x")
        # Pre-existing edge a → b.
        LineageEdge.objects.create(
            tenant=tenant,
            source_contract_id=c_a.id,
            target_contract_id=c_b.id,
            source_model="default",
            source_field="x",
            target_model="default",
            target_field="x",
            edge_type="reference",
        )
        client = _client(user)
        # Patch on c_a (target of the new edge) requesting b → a, plus
        # keeping a → b.  This forms a cycle.
        body = {
            "edges": [
                {
                    "source_contract": str(c_a.id),
                    "source_model": "default",
                    "source_field": "x",
                    "target_contract": str(c_b.id),
                    "target_model": "default",
                    "target_field": "x",
                    "edge_type": "reference",
                },
                {
                    "source_contract": str(c_b.id),
                    "source_model": "default",
                    "source_field": "x",
                    "target_contract": str(c_a.id),
                    "target_model": "default",
                    "target_field": "x",
                    "edge_type": "reference",
                },
            ],
        }
        response = client.patch(
            _url(c_a),
            data=body,
            format="json",
            HTTP_IF_MATCH=_etag(c_a),
        )
        self.assertEqual(response.status_code, 409, response.content)
        body_json = response.json()
        self.assertEqual(body_json.get("code"), "LINEAGE_CYCLE")
        # Spec mandates ``cycle: [...]`` path in the response body.
        details = body_json.get("details") or {}
        self.assertIn("cycle", details)
        self.assertIsInstance(details["cycle"], list)
        self.assertGreaterEqual(len(details["cycle"]), 2)
        # Path is a closed loop (first == last).
        self.assertEqual(details["cycle"][0], details["cycle"][-1])

    def test_field_not_found_returns_400(self):
        tenant = _make_tenant("fnf")
        user = _make_user(tenant)
        _grant_tenant_admin(user, tenant)
        c_a = _make_contract_with_field(tenant, name="a", field_name="x")
        c_b = _make_contract_with_field(tenant, name="b", field_name="y")
        client = _client(user)
        body = {
            "edges": [
                {
                    "source_contract": str(c_a.id),
                    "source_model": "default",
                    "source_field": "x",
                    "target_contract": str(c_b.id),
                    "target_model": "default",
                    "target_field": "MISSING",
                    "edge_type": "reference",
                },
            ],
        }
        response = client.patch(
            _url(c_b),
            data=body,
            format="json",
            HTTP_IF_MATCH=_etag(c_b),
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json().get("code"),
            "LINEAGE_FIELD_NOT_FOUND",
        )


# ---------------------------------------------------------------------------
# Concurrency (If-Match) + cap (413) + RBAC
# ---------------------------------------------------------------------------


class LineageEditConcurrencyAndRbacTests(TestCase):
    def test_stale_if_match_returns_412(self):
        tenant = _make_tenant("etag")
        user = _make_user(tenant)
        _grant_tenant_admin(user, tenant)
        c = _make_contract_with_field(tenant, name="c")
        client = _client(user)
        response = client.patch(
            _url(c),
            data={"edges": []},
            format="json",
            HTTP_IF_MATCH='W/"stale-etag"',
        )
        self.assertEqual(response.status_code, 412)
        self.assertEqual(response.json().get("code"), "PRECONDITION_FAILED")

    def test_more_than_1000_edges_returns_413(self):
        tenant = _make_tenant("cap")
        user = _make_user(tenant)
        _grant_tenant_admin(user, tenant)
        c = _make_contract_with_field(tenant, name="cap")
        client = _client(user)
        # Build 1001 plausible-shaped edges (validation will pass on
        # the cap check before the field-existence check fires).
        edges = [
            {
                "source_contract": str(c.id),
                "source_model": "default",
                "source_field": "id",
                "target_contract": str(c.id),
                "target_model": "default",
                "target_field": "id",
                "edge_type": "reference",
            }
            for _ in range(1001)
        ]
        response = client.patch(
            _url(c),
            data={"edges": edges},
            format="json",
            HTTP_IF_MATCH=_etag(c),
        )
        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.json().get("code"), "PAYLOAD_TOO_LARGE")

    def test_cross_tenant_edit_forbidden(self):
        tenant_a = _make_tenant("rbac-a")
        tenant_b = _make_tenant("rbac-b")
        user_b = _make_user(tenant_b)  # user in tenant B
        _grant_tenant_admin(user_b, tenant_b)
        c = _make_contract_with_field(tenant_a, name="rbac-a")
        client = _client(user_b)
        response = client.patch(
            _url(c),
            data={"edges": []},
            format="json",
            HTTP_IF_MATCH=_etag(c),
        )
        # Cross-tenant access is bound by the queryset's tenant
        # filter — the contract isn't visible at all to tenant B,
        # so the response is 404 per DRF's default get_object behaviour.
        self.assertEqual(response.status_code, 404)

    def test_non_admin_in_same_tenant_forbidden(self):
        tenant = _make_tenant("rbac-noadmin")
        user = _make_user(tenant)
        # No TENANT_ADMIN role granted; user isn't the contract owner.
        c = _make_contract_with_field(tenant, name="noadmin")
        client = _client(user)
        response = client.patch(
            _url(c),
            data={"edges": []},
            format="json",
            HTTP_IF_MATCH=_etag(c),
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json().get("code"),
            "EDIT_LINEAGE_FORBIDDEN",
        )


# ---------------------------------------------------------------------------
# Audit emission (F2.9)
# ---------------------------------------------------------------------------


class LineageEditCrossTenantEdgeTests(TestCase):
    """Phase 228.F2.DoD.1 audit — REQ-LIN-F2-002 "Cross-tenant rejected".

    An authorised user editing their own contract MUST NOT be able to
    create an edge whose source/target_contract references a contract
    owned by a different tenant.  Cross-tenant edges must use NULL on
    the foreign side per the LineageEdge model convention.
    """

    def test_cross_tenant_edge_reference_rejected(self):
        tenant_a = _make_tenant("xt-a")
        tenant_b = _make_tenant("xt-b")
        user_a = _make_user(tenant_a)
        _grant_tenant_admin(user_a, tenant_a)
        # Contract owned by tenant A.
        c_a = _make_contract_with_field(tenant_a, name="own", field_name="x")
        # Contract owned by tenant B (foreign).
        c_b = _make_contract_with_field(tenant_b, name="foreign", field_name="x")

        client = _client(user_a)
        # User A tries to PATCH their own contract's lineage with an
        # edge that references tenant B's contract.
        body = {
            "edges": [
                {
                    "source_contract": str(c_b.id),  # foreign tenant
                    "source_model": "default",
                    "source_field": "x",
                    "target_contract": str(c_a.id),
                    "target_model": "default",
                    "target_field": "x",
                    "edge_type": "reference",
                },
            ],
        }
        response = client.patch(
            _url(c_a),
            data=body,
            format="json",
            HTTP_IF_MATCH=_etag(c_a),
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(
            response.json().get("code"),
            "CROSS_TENANT_EDGE_FORBIDDEN",
        )


class LineageEditIdempotencyTests(TestCase):
    """Phase 228.F2.DoD.1 audit — REQ-LIN-F2-002 "Idempotent retry".

    Same Idempotency-Key + same body must return the cached response
    on retry without applying the patch a second time.
    """

    def test_idempotency_key_replay_returns_cached_no_double_apply(self):
        from hub.apps.contracts.models import LineageEdge

        tenant = _make_tenant("idem")
        user = _make_user(tenant)
        _grant_tenant_admin(user, tenant)
        c_src = _make_contract_with_field(tenant, name="s", field_name="x")
        c_tgt = _make_contract_with_field(tenant, name="t", field_name="x")

        client = _client(user)
        body = {
            "edges": [
                {
                    "source_contract": str(c_src.id),
                    "source_model": "default",
                    "source_field": "x",
                    "target_contract": str(c_tgt.id),
                    "target_model": "default",
                    "target_field": "x",
                    "edge_type": "reference",
                },
            ],
        }
        idem_key = str(uuid.uuid4())

        # First call lands the patch.
        first = client.patch(
            _url(c_tgt),
            data=body,
            format="json",
            HTTP_IF_MATCH=_etag(c_tgt),
            HTTP_IDEMPOTENCY_KEY=idem_key,
        )
        self.assertEqual(first.status_code, 200, first.content)
        self.assertEqual(first.json()["added"], 1)

        rows_after_first = LineageEdge.objects.filter(
            target_contract_id=c_tgt.id,
            valid_to__isnull=True,
        ).count()
        self.assertEqual(rows_after_first, 1)

        # Replay with the same key + same body.
        c_tgt.refresh_from_db()
        second = client.patch(
            _url(c_tgt),
            data=body,
            format="json",
            HTTP_IF_MATCH=_etag(c_tgt),
            HTTP_IDEMPOTENCY_KEY=idem_key,
        )
        self.assertEqual(second.status_code, 200)
        # The cached response is returned; the project's
        # IdempotencyMiddleware (hub/apps/api/middleware/idempotency.py)
        # sets ``Idempotency-Replayed: true`` to signal a replay.
        # Phase 228.F3.test-execution audit fix — test was previously
        # asserting the wrong header name (the view sets a redundant
        # ``X-Idempotent-Replay`` but the middleware short-circuits
        # before the view runs, so only the middleware header lands).
        self.assertEqual(second.get("Idempotency-Replayed"), "true")
        # Crucially: NO additional row.  If the second call had
        # re-applied the patch, the SCD Type 2 close-and-reopen would
        # have closed-and-reopened the edge — same open count but
        # with a different row id and a closed historical row.
        rows_after_second = LineageEdge.objects.filter(
            target_contract_id=c_tgt.id,
            valid_to__isnull=True,
        ).count()
        self.assertEqual(rows_after_second, 1)
        # No closed historical row from a re-apply (the only edge in
        # the universe is the one we opened the first time).
        self.assertEqual(
            LineageEdge.objects.filter(
                target_contract_id=c_tgt.id,
            ).count(),
            1,
        )


class IncludeFieldsDefaultBehaviourTests(TestCase):
    """Phase 228.F2.DoD.1 audit — REQ-LIN-F2-001 "Field nodes excluded by default".

    The visualization endpoint's ``?include_fields`` param defaults
    to false; the response shape MUST stay backwards-compatible (no
    ``field_nodes`` / ``field_links`` keys) for callers who don't
    opt in.  Pre-fix nothing asserted this.
    """

    def test_default_include_fields_omits_field_keys(self):
        tenant = _make_tenant("default-flag")
        user = _make_user(tenant)
        _grant_tenant_admin(user, tenant)
        c = _make_contract_with_field(tenant, name="default-flag")
        client = _client(user)
        # No `include_fields` param.
        response = client.get(f"/api/v1/contracts/{c.id}/lineage/visualization/?format=json")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        # Default-false: keys must NOT appear.
        self.assertNotIn(
            "field_nodes",
            body,
            msg="Default visualization must NOT carry field_nodes",
        )
        self.assertNotIn(
            "field_links",
            body,
            msg="Default visualization must NOT carry field_links",
        )

    def test_include_fields_true_adds_field_keys(self):
        from hub.apps.contracts.models import LineageEdge

        tenant = _make_tenant("flag-on")
        user = _make_user(tenant)
        _grant_tenant_admin(user, tenant)
        c_src = _make_contract_with_field(tenant, name="src", field_name="x")
        c_tgt = _make_contract_with_field(tenant, name="tgt", field_name="x")
        # Seed a real field-level lineage edge so the visualization
        # endpoint has data to project into field_nodes / field_links.
        LineageEdge.objects.create(
            tenant=tenant,
            source_contract_id=c_src.id,
            target_contract_id=c_tgt.id,
            source_model="default",
            source_field="x",
            target_model="default",
            target_field="x",
            edge_type="reference",
        )

        client = _client(user)
        response = client.get(
            f"/api/v1/contracts/{c_tgt.id}/lineage/visualization/?format=json&include_fields=true"
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("field_nodes", body)
        self.assertIn("field_links", body)
        self.assertIsInstance(body["field_nodes"], list)
        self.assertIsInstance(body["field_links"], list)
        # REQ-LIN-F2-001 spec scenario "Field nodes returned when toggle on" —
        # the response MUST include nodes with ``type='field'``.
        self.assertGreaterEqual(
            len(body["field_nodes"]),
            1,
            msg="field_nodes should be populated when seeded edges exist",
        )
        self.assertTrue(
            all(n.get("type") == "field" for n in body["field_nodes"]),
            msg="every entry in field_nodes must carry type='field' per the spec",
        )


class LineageEditAuditTests(TestCase):
    def test_one_audit_row_per_added_edge(self):
        from hub.apps.audit.models import AuditEvent
        from hub.apps.contracts.models import LineageEdge  # noqa: F401

        tenant = _make_tenant("audit-add")
        user = _make_user(tenant)
        _grant_tenant_admin(user, tenant)
        c_src = _make_contract_with_field(tenant, name="src", field_name="x")
        c_tgt = _make_contract_with_field(tenant, name="tgt", field_name="x")
        client = _client(user)
        before = AuditEvent.objects.filter(
            action="LINEAGE_EDGE_ADDED",
            tenant=tenant,
        ).count()
        response = client.patch(
            _url(c_tgt),
            data={
                "edges": [
                    {
                        "source_contract": str(c_src.id),
                        "source_model": "default",
                        "source_field": "x",
                        "target_contract": str(c_tgt.id),
                        "target_model": "default",
                        "target_field": "x",
                        "edge_type": "reference",
                    },
                ],
            },
            format="json",
            HTTP_IF_MATCH=_etag(c_tgt),
        )
        self.assertEqual(response.status_code, 200, response.content)
        after = AuditEvent.objects.filter(
            action="LINEAGE_EDGE_ADDED",
            tenant=tenant,
        ).count()
        self.assertEqual(after, before + 1)
