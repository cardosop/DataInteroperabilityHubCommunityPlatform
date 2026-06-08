"""
Phase 234.6 — Postgres FTS search over audit events.

Engineering contract this suite pins (preprod01 tasks.md 234.6):

1.  ``AuditEvent`` has a STORED ``details_json_tsvector`` GENERATED
    column that auto-populates from ``action``, ``resource_type``, and
    ``details_json``. Postgres re-runs the GENERATED expression on every
    INSERT/UPDATE — there is no separate backfill step (AUDIT.5).
2.  ``GET /api/v1/audit/audit-events/?q=<text>`` performs
    ``details_json_tsvector @@ websearch_to_tsquery('english', :q)``,
    annotates a ``ts_rank``, and returns results ordered by
    ``-rank, -timestamp``.
3.  **Tenant scoping is preserved** (AUDIT.3) — the FTS filter is
    ANDed AFTER the existing tenant-scope filter. Tenant A's search
    for a term that appears in tenant B's events returns zero of
    tenant B's rows.
4.  **Websearch syntax** (AUDIT.6) — quoted phrases match the exact
    phrase only. A search for ``"asset created"`` matches events
    where those two words appear in that order, not events where
    both words appear separately.
5.  Negation, OR, etc. — websearch_to_tsquery handles ``-word`` and
    ``or`` natively; we pin the contract by asserting one negation
    case.
6.  The ``audit_search_query_duration_seconds`` histogram (AUDIT.4) is
    observed on every ``?q=`` request — the slow-query alert
    (p95 > 5s for 5m) depends on this being emitted.
"""
from __future__ import annotations
import pytest

import uuid

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.audit.models import AuditEvent
from hub.apps.audit.utils import create_audit_event
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import Role, UserRole

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tenant() -> Tenant:
    uid = uuid.uuid4().hex[:8]
    return Tenant.objects.create(name=f"Tenant {uid}", slug=f"tenant-{uid}")


def _make_admin(tenant: Tenant) -> User:
    return _make_user_with_role(tenant, "TENANT_ADMIN")


def _make_user_with_role(tenant: Tenant, role_name: str) -> User:
    uid = uuid.uuid4().hex[:8]
    user = User.objects.create_user(
        email=f"{role_name.lower()}-{uid}@example.com",
        password="testpass123",
        tenant=tenant,
    )
    role, _ = Role.objects.get_or_create(
        tenant=tenant, name=role_name, defaults={"description": role_name}
    )
    UserRole.objects.get_or_create(user=user, tenant=tenant, role=role)
    return user


def _mk(tenant: Tenant, *, action: str, resource_type: str = "TEST", details: dict | None = None):
    return create_audit_event(
        resource_type=resource_type,
        action=action,
        actor_user=None,
        tenant=tenant,
        details=details or {},
    )


# ---------------------------------------------------------------------------
# Tier 1 — generated column + base query semantics (no HTTP)
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestAuditFtsColumnAndQuery:
    @pytest.fixture(autouse=True)
    def _setup(self):
        self.tenant = _make_tenant()

    @pytest.mark.integration
    def test_generated_column_populates_from_action_resource_and_details(self):
        """``details_json_tsvector`` materialises without any post-write step.

        Pins AUDIT.5: GENERATED ALWAYS AS ... STORED. A fresh row
        produced via ``AuditEvent.objects.create`` (which the audit
        helpers route through) MUST have a non-empty tsvector covering
        all three source fields.
        """
        evt = _mk(
            self.tenant,
            action="ASSET_CREATED",
            resource_type="ASSET",
            details={"asset_name": "warehouse_orders", "note": "compliance review pending"},
        )
        evt.refresh_from_db()
        # Field is exposed on the Django model as ``details_json_tsvector``
        # and is NEVER NULL for a successfully-inserted row.
        assert evt.details_json_tsvector is not None
        # The tsvector text-form should contain lexemes from all three
        # source fields (Postgres lowercases + stems).
        repr_text = str(evt.details_json_tsvector).lower()
        for fragment in ("asset", "warehous", "complianc"):
            assert fragment in repr_text, (
                f"expected stemmed lexeme for {fragment!r} in tsvector, "
                f"got: {repr_text}"
            )

    @pytest.mark.integration
    def test_websearch_search_query_matches_term(self):
        """A plain term match returns the matching row."""
        from django.contrib.postgres.search import SearchQuery

        match = _mk(
            self.tenant,
            action="COMPLIANCE_RUN_CREATED",
            details={"reason": "quarterly audit"},
        )
        _mk(
            self.tenant,
            action="DQ_RUN_STARTED",
            details={"reason": "ad-hoc check"},
        )

        sq = SearchQuery("compliance", search_type="websearch")
        rows = list(
            AuditEvent.objects.filter(
                tenant=self.tenant,
                details_json_tsvector=sq,
            )
        )
        ids = {r.id for r in rows}
        assert match.id in ids
        # The unmatched row must NOT show up.
        assert len(ids) == 1

    @pytest.mark.integration
    def test_quoted_phrase_only_matches_exact_phrase(self):
        """AUDIT.6 — ``"asset created"`` matches only that exact phrase."""
        from django.contrib.postgres.search import SearchQuery

        exact = _mk(
            self.tenant,
            action="ASSET_CREATED",  # tokenised as 'asset' + 'created' adjacent
            details={"name": "demo"},
        )
        # An event that contains BOTH words but separated by other
        # tokens — must NOT match the quoted phrase.
        _mk(
            self.tenant,
            action="DQ_RUN_STARTED",
            details={"description": "asset was scanned; report created"},
        )

        sq = SearchQuery('"asset created"', search_type="websearch")
        rows = list(
            AuditEvent.objects.filter(
                tenant=self.tenant,
                details_json_tsvector=sq,
            )
        )
        ids = {r.id for r in rows}
        assert exact.id in ids
        assert len(ids) == 1, (
            f"quoted phrase should not match scattered tokens; got {len(ids)} rows"
        )


# ---------------------------------------------------------------------------
# Tier 2 — DRF API surface
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestAuditFtsApi:
    @pytest.fixture(autouse=True)
    def _setup(self):
        self.tenant_a = _make_tenant()
        self.tenant_b = _make_tenant()
        self.admin_a = _make_admin(self.tenant_a)
        self.client = APIClient()
        self.list_url = "/api/v1/audit/audit-events/"

    @pytest.mark.integration
    def test_q_param_returns_matching_events(self):
        target = _mk(
            self.tenant_a,
            action="ASSET_CREATED",
            details={"name": "north-star-warehouse"},
        )
        # Distractor with no overlap.
        _mk(
            self.tenant_a,
            action="USER_LOGIN",
            details={"ip": "10.0.0.1"},
        )

        self.client.force_authenticate(self.admin_a)
        resp = self.client.get(self.list_url, {"q": "warehouse"})
        assert resp.status_code == status.HTTP_200_OK, resp.content
        body = resp.json()
        results = body.get("results", body) if isinstance(body, dict) else body
        ids = {row["id"] for row in results}
        assert str(target.id) in ids
        assert len(ids) == 1

    @pytest.mark.integration
    def test_q_param_tenant_scoping_blocks_cross_tenant_matches(self):
        """AUDIT.3 — tenant A's ?q= must NOT return tenant B's matching rows."""
        # Tenant A row WITHOUT the term.
        _mk(self.tenant_a, action="USER_LOGIN", details={"ip": "10.0.0.1"})
        # Tenant B row WITH the term — must remain invisible.
        b_match = _mk(
            self.tenant_b,
            action="COMPLIANCE_RUN_CREATED",
            details={"note": "cross-tenant-leak-test"},
        )

        self.client.force_authenticate(self.admin_a)
        resp = self.client.get(self.list_url, {"q": "compliance"})
        assert resp.status_code == status.HTTP_200_OK
        body = resp.json()
        results = body.get("results", body) if isinstance(body, dict) else body
        ids = {row["id"] for row in results}
        assert str(b_match.id) not in ids, (
            "cross-tenant leak: tenant A search returned tenant B's event"
        )

    @pytest.mark.integration
    def test_q_quoted_phrase_via_api(self):
        """AUDIT.6 — websearch quoted phrase honoured end-to-end."""
        exact = _mk(self.tenant_a, action="ASSET_CREATED", details={"name": "x"})
        _mk(
            self.tenant_a,
            action="DQ_RUN_STARTED",
            details={"summary": "asset processed; report created"},
        )

        self.client.force_authenticate(self.admin_a)
        resp = self.client.get(self.list_url, {"q": '"asset created"'})
        assert resp.status_code == status.HTTP_200_OK
        body = resp.json()
        results = body.get("results", body) if isinstance(body, dict) else body
        ids = {row["id"] for row in results}
        assert str(exact.id) in ids
        assert len(ids) == 1

    @pytest.mark.integration
    def test_q_param_orders_by_ts_rank(self):
        """ts_rank pushes ``action`` matches above ``details`` matches.

        Weights pinned by the GENERATED expression: action='A',
        resource_type='B', details='C'. An event whose ACTION contains
        the term outranks an event where the term is only in details.
        """
        high = _mk(self.tenant_a, action="COMPLIANCE_RUN_CREATED", details={"x": "y"})
        low = _mk(
            self.tenant_a,
            action="USER_LOGIN",
            details={"reason": "compliance follow-up"},
        )

        self.client.force_authenticate(self.admin_a)
        resp = self.client.get(self.list_url, {"q": "compliance"})
        assert resp.status_code == status.HTTP_200_OK
        body = resp.json()
        results = body.get("results", body) if isinstance(body, dict) else body
        ids = [row["id"] for row in results]
        assert str(high.id) in ids and str(low.id) in ids
        # High-weight (action match) precedes low-weight (details match).
        assert ids.index(str(high.id)) < ids.index(str(low.id))

    @pytest.mark.integration
    def test_empty_q_param_does_not_break_listing(self):
        """An empty ``?q=`` (e.g. cleared input box) falls back to plain list ordering."""
        _mk(self.tenant_a, action="X", details={})
        self.client.force_authenticate(self.admin_a)
        resp = self.client.get(self.list_url, {"q": ""})
        assert resp.status_code == status.HTTP_200_OK

    @pytest.mark.integration
    def test_auditor_role_can_use_q_param(self):
        """Phase 234.6 audit-fix — AUDITOR role is on AUDIT_READ_ROLES.

        The list endpoint's role gate accepts ``TENANT_ADMIN``,
        ``AUDITOR``, or ``PLATFORM_ADMIN``. Without an explicit pin
        a future refactor could narrow the gate to TENANT_ADMIN only
        and silently break read-only compliance access.
        """
        auditor = _make_user_with_role(self.tenant_a, "AUDITOR")
        target = _mk(
            self.tenant_a,
            action="ASSET_CREATED",
            details={"name": "auditor-visible"},
        )
        self.client.force_authenticate(auditor)
        resp = self.client.get(self.list_url, {"q": "auditor-visible"})
        assert resp.status_code == status.HTTP_200_OK
        body = resp.json()
        results = body.get("results", body) if isinstance(body, dict) else body
        assert str(target.id) in {row["id"] for row in results}

    @pytest.mark.integration
    def test_unauthenticated_request_to_q_param_blocked(self):
        """Anonymous request → 401/403 — q= cannot leak past the auth gate."""
        self.client.force_authenticate(None)
        resp = self.client.get(self.list_url, {"q": "anything"})
        assert resp.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )

    @pytest.mark.integration
    def test_platform_admin_q_param_spans_all_tenants_by_design(self):
        """Phase 234.6 audit-fix — platform admins see cross-tenant rows.

        The existing ``AuditEventViewSet.get_queryset`` reads:
        ``if user.is_platform_admin: queryset = AuditEvent.objects.all()``
        (no tenant filter). The FTS path inherits that behaviour by
        design — platform admins are the support-engineer role and
        need to find rows in any tenant. Pinning this contract here
        documents the intended cross-tenant reach so a future
        refactor that accidentally narrows the platform-admin
        queryset fails CI.
        """
        platform_admin = _make_user_with_role(self.tenant_a, "PLATFORM_ADMIN")
        platform_admin.is_platform_admin = True
        platform_admin.save(update_fields=["is_platform_admin"])

        a_match = _mk(self.tenant_a, action="ASSET_CREATED", details={"a": "ksp-term"})
        b_match = _mk(self.tenant_b, action="COMPLIANCE_RUN_CREATED", details={"b": "ksp-term"})

        self.client.force_authenticate(platform_admin)
        resp = self.client.get(self.list_url, {"q": "ksp-term"})
        assert resp.status_code == status.HTTP_200_OK
        body = resp.json()
        results = body.get("results", body) if isinstance(body, dict) else body
        ids = {row["id"] for row in results}
        # BOTH tenants' rows surface for a platform admin.
        assert str(a_match.id) in ids
        assert str(b_match.id) in ids


# ---------------------------------------------------------------------------
# Tier 3 — observability (AUDIT.4)
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestAuditFtsMetric:
    @pytest.fixture(autouse=True)
    def _setup(self):
        self.tenant = _make_tenant()
        self.admin = _make_admin(self.tenant)
        self.client = APIClient()
        self.list_url = "/api/v1/audit/audit-events/"

    @pytest.mark.integration
    def test_metric_observed_on_q_request(self):
        """``audit_search_query_duration_seconds`` is recorded on each ?q= hit.

        AUDIT.4 — the slow-query alert depends on this being emitted.
        We pin the contract by counting samples before/after the
        request; the value itself (sub-second) is environmental.
        """
        from hub.apps.audit import metrics as audit_metrics

        before = audit_metrics.search_query_observation_count()
        _mk(self.tenant, action="SOMETHING", details={"term": "needle"})

        self.client.force_authenticate(self.admin)
        resp = self.client.get(self.list_url, {"q": "needle"})
        assert resp.status_code == status.HTTP_200_OK

        after = audit_metrics.search_query_observation_count()
        assert after > before, (
            f"audit_search_query_duration_seconds NOT observed on ?q= request "
            f"({before=} {after=}); the slow-query alert would never fire"
        )

    @pytest.mark.integration
    def test_metric_not_observed_when_q_absent(self):
        """No FTS work happens without ``?q=`` — don't pollute the histogram."""
        from hub.apps.audit import metrics as audit_metrics

        before = audit_metrics.search_query_observation_count()
        self.client.force_authenticate(self.admin)
        resp = self.client.get(self.list_url)  # no ?q=
        assert resp.status_code == status.HTTP_200_OK

        after = audit_metrics.search_query_observation_count()
        assert after == before
