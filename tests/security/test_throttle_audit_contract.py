"""
pilot-readiness 4.1 — Phase 273 throttle-audit contract.

The contract (CLAUDE.md, Phase 273):
- every 429 emits the surface's ``*_RATE_LIMIT_EXCEEDED`` audit event
  (SEARCH / SPARQL / MARKETPLACE / BAAS / API_KEY);
- on DRF 3.16 the emission MUST live in ``allow_request``'s failure
  branch (``_on_throttled``) — a ``throttled()`` override is dead code;
- throttle cache keys include tenant_id (tenant A's exhaustion never
  affects tenant B's quota);
- the emission is try/except-wrapped — an audit-DB outage never blocks
  the 429 response.

Two layers, no mocks:
1. Behavioral — drive the REAL throttle objects to exhaustion against
   a real request and assert the audit row lands.
2. Conformance — AST-walk the throttle modules: every Phase-273
   surface must implement the contract shape.

Known gaps this file pins (found RED, fixed in the same task):
- BaaSUsageThrottle had NO allow_request override at all — its 429s
  were silent (no BAAS_RATE_LIMIT_EXCEEDED row).
- BAAS_RATE_LIMIT_EXCEEDED and API_KEY_RATE_LIMIT_EXCEEDED had ZERO
  test assertions repo-wide.
- UnifiedSearchView carried a stale forwarding loop to a throttle-level
  ``throttled()`` method that no longer exists on DRF 3.16.
"""

import ast
import uuid
from pathlib import Path

import pytest
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIRequestFactory

from hub.apps.audit.models import AuditEvent
from hub.apps.auth.throttles import APIKeyThrottle
from hub.apps.baas.throttles import BaaSAPIKeyThrottle, BaaSUsageThrottle
from hub.apps.marketplace.throttles import MarketplaceUserThrottle
from hub.apps.search.throttles import SearchUserThrottle
from hub.apps.semantic.throttles import SPARQLUserThrottle
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.security

REPO_ROOT = Path(__file__).resolve().parents[2]


def _make_request(user):
    factory = APIRequestFactory()
    request = factory.get("/api/v1/search/?q=pilot")
    # The throttles read ``request.user`` directly on the WSGIRequest
    # (the marketplace throttle-audit test's pattern) — force_authenticate
    # only works on DRF Request objects.
    request.user = user
    return request


def _audit_count(action):
    return AuditEvent.objects.filter(action=action).count()


class ThrottleAuditBehavioralTests(TestCase):
    """Drive the REAL throttle objects to exhaustion — the audit row
    must land for every Phase-273 surface."""

    @classmethod
    def setUpTestData(cls):
        cls.tenant = Tenant.objects.create(
            name=f"throttle-audit-{uuid.uuid4().hex[:8]}",
            slug=f"throttle-audit-{uuid.uuid4().hex[:8]}",
            status="ACTIVE",
        )
        cls.user = User.objects.create_user(
            email=f"throttle-audit-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=cls.tenant,
            status=UserStatus.ACTIVE,
        )

    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def _exhaust(self, throttle, request):
        """Return True once the throttle starts rejecting (any() short-
        circuits on the first rejection, so the loop stops there)."""
        return any(not throttle.allow_request(request, None) for _ in range(500))

    def test_search_429_emits_search_rate_limit_exceeded(self):
        request = _make_request(self.user)
        assert self._exhaust(SearchUserThrottle(), request)
        assert _audit_count("SEARCH_RATE_LIMIT_EXCEEDED") >= 1

    def test_sparql_429_emits_sparql_rate_limit_exceeded(self):
        request = _make_request(self.user)
        assert self._exhaust(SPARQLUserThrottle(), request)
        assert _audit_count("SPARQL_RATE_LIMIT_EXCEEDED") >= 1

    def test_baas_api_key_429_emits_baas_rate_limit_exceeded(self):
        request = _make_request(self.user)
        assert self._exhaust(BaaSAPIKeyThrottle(), request)
        assert _audit_count("BAAS_RATE_LIMIT_EXCEEDED") >= 1

    def test_baas_usage_429_emits_baas_rate_limit_exceeded(self):
        request = _make_request(self.user)
        assert self._exhaust(BaaSUsageThrottle(), request)
        assert _audit_count("BAAS_RATE_LIMIT_EXCEEDED") >= 1

    def test_api_key_429_emits_api_key_rate_limit_exceeded(self):
        request = _make_request(self.user)
        assert self._exhaust(APIKeyThrottle(), request)
        assert _audit_count("API_KEY_RATE_LIMIT_EXCEEDED") >= 1

    def test_marketplace_429_emits_marketplace_rate_limit_exceeded(self):
        request = _make_request(self.user)
        assert self._exhaust(MarketplaceUserThrottle(), request)
        assert _audit_count("MARKETPLACE_RATE_LIMIT_EXCEEDED") >= 1

    def test_throttled_rows_are_tenant_scoped(self):
        """The audit row must carry the tenant — infer_tenant_from_actor
        resolves it from the throttled user."""
        request = _make_request(self.user)
        assert self._exhaust(SearchUserThrottle(), request)
        row = AuditEvent.objects.filter(action="SEARCH_RATE_LIMIT_EXCEEDED").latest("timestamp")
        assert row.tenant_id == self.tenant.id




def _class_node(module_path: Path, class_name: str):
    tree = ast.parse(module_path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return node
    raise AssertionError(f"{class_name} not found in {module_path}")


def _class_source(node: ast.ClassDef) -> str:
    return ast.unparse(node)


class ThrottleAuditConformanceTests:
    """AST conformance: every Phase-273 surface must implement the
    contract shape — no dead throttled() overrides, _on_throttled in
    the allow_request failure branch, the right event constant, and a
    tenant-scoped cache key."""

    # The Phase-273 surfaces: (module, class, event).
    @pytest.mark.parametrize(
        ("module_rel", "class_name", "event"),
        [
            ("hub/apps/search/throttles.py", "SearchUserThrottle", "SEARCH_RATE_LIMIT_EXCEEDED"),
            ("hub/apps/semantic/throttles.py", "SPARQLUserThrottle", "SPARQL_RATE_LIMIT_EXCEEDED"),
            ("hub/apps/marketplace/throttles.py", "MarketplaceUserThrottle", "MARKETPLACE_RATE_LIMIT_EXCEEDED"),
            ("hub/apps/baas/throttles.py", "BaaSAPIKeyThrottle", "BAAS_RATE_LIMIT_EXCEEDED"),
            ("hub/apps/baas/throttles.py", "BaaSUsageThrottle", "BAAS_RATE_LIMIT_EXCEEDED"),
            ("hub/apps/auth/throttles.py", "APIKeyThrottle", "API_KEY_RATE_LIMIT_EXCEEDED"),
        ],
    )
    def test_surface_conforms(self, module_rel, class_name, event):
        node = _class_node(REPO_ROOT / module_rel, class_name)
        source = _class_source(node)

        # No throttled() override — dead code on DRF 3.16.
        assert "def throttled" not in source, (
            f"{class_name} defines throttled() — dead on DRF 3.16; "
            f"audit emission must run in allow_request's failure branch"
        )

        # _on_throttled must exist and reference the surface's event.
        assert "_on_throttled" in source, f"{class_name} must define _on_throttled"
        on_throttled = next(
            stmt for stmt in node.body if isinstance(stmt, ast.FunctionDef) and stmt.name == "_on_throttled"
        )
        on_source = ast.unparse(on_throttled)
        assert event in on_source, (
            f"{class_name}._on_throttled must emit {event} (found: {on_source[:200]})"
        )

        # The audit emission must be try/except-wrapped — an audit-DB
        # outage never blocks the 429 response.
        assert "try:" in on_source, (
            f"{class_name}._on_throttled must wrap the audit emission in try/except"
        )
        assert "except" in on_source, (
            f"{class_name}._on_throttled must wrap the audit emission in try/except"
        )

        # allow_request must call _on_throttled on the failure branch.
        allow_request = next(
            (
                stmt
                for stmt in node.body
                if isinstance(stmt, ast.FunctionDef) and stmt.name == "allow_request"
            ),
            None,
        )
        assert allow_request is not None, f"{class_name} must override allow_request"
        allow_source = ast.unparse(allow_request)
        assert "_on_throttled" in allow_source, (
            f"{class_name}.allow_request must call _on_throttled in its failure branch"
        )

        # Tenant-scoped cache key.
        cache_key = next(
            (
                stmt
                for stmt in node.body
                if isinstance(stmt, ast.FunctionDef) and stmt.name == "get_cache_key"
            ),
            None,
        )
        assert cache_key is not None, f"{class_name} must define get_cache_key"
        key_source = ast.unparse(cache_key)
        assert "tenant" in key_source, (
            f"{class_name}.get_cache_key must be tenant-scoped "
            f"(f\"throttle_{{name}}_{{tenant_id}}\"): {key_source[:200]}"
        )
        assert "throttle" in key_source, (
            f"{class_name}.get_cache_key must be tenant-scoped "
            f"(f\"throttle_{{name}}_{{tenant_id}}\"): {key_source[:200]}"
        )

    def test_no_view_has_throttle_forwarding_loop(self):
        """UnifiedSearchView carried a stale forwarding loop to a
        throttle-level throttled() that no longer exists on DRF 3.16
        (pilot-readiness 4.1 cleanup)."""
        views = (REPO_ROOT / "hub/apps/search/views.py").read_text()
        assert 'getattr(throttle, "throttled", None)' not in views
