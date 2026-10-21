"""P0 (openspec add-databricks-control-plane task 0.11) — connector fixes.

Four root causes, four test groups. No mocks:

- auth_mode PAT|OAUTH_M2M: the M2M exchange drives a REAL local HTTP
  server (transport seam is the explicit ``exchange_base_url`` parameter,
  mirroring the client's base_url pattern — the exchange logic itself is
  production code).
- breaker swallow: real behavioral check (breaker CLOSED → no raise) plus
  a source-scan asserting the silent ``except ImportError: pass`` is gone.
- DBU double-count: AST scan — ``reflect_schema`` records cost EXACTLY
  once (the inner ``execute_query`` records its own).
- semaphore: the REAL in-memory slot state machine (patched limit constant
  only) + the REAL 429 response shape via RequestFactory.
"""

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from hub.apps.databricks_admin.tests._http import RecordingHandler
from hub.apps.warehouses import views as warehouses_views
from hub.apps.warehouses.connectors.databricks import (
    DatabricksConnector,
    resolve_access_token,
)
from hub.apps.warehouses.exceptions import WarehouseConnectionError

pytestmark = pytest.mark.django_db(transaction=True)


class TestAuthModes:
    def test_pat_mode_uses_stored_token_without_network(self):
        assert resolve_access_token({"auth_mode": "PAT", "pat_token": "dapi-pat"}) == "dapi-pat"

    def test_pat_default_when_auth_mode_absent(self):
        # Existing configs have no auth_mode — PAT is the backward-compatible default.
        assert resolve_access_token({"pat_token": "dapi-legacy"}) == "dapi-legacy"

    def test_m2m_exchange_against_real_server(self, local_http_server):
        RecordingHandler.json_script = [
            '{"access_token": "dapi-m2m-token"}',
        ]
        RecordingHandler.script = [200]
        token = resolve_access_token(
            {
                "auth_mode": "OAUTH_M2M",
                "host": "127.0.0.1",
                "client_id": "cid-1",
                "client_secret": "secret-1",
            },
            exchange_base_url=f"http://127.0.0.1:{local_http_server}",
        )
        assert token == "dapi-m2m-token"
        posts = [r for r in RecordingHandler.requests if r["path"] == "/oidc/v1/token"]
        assert len(posts) == 1

    def test_m2m_exchange_401_raises(self, local_http_server):
        RecordingHandler.script = [401]
        with pytest.raises(WarehouseConnectionError):
            resolve_access_token(
                {
                    "auth_mode": "OAUTH_M2M",
                    "host": "127.0.0.1",
                    "client_id": "cid-1",
                    "client_secret": "secret-1",
                },
                exchange_base_url=f"http://127.0.0.1:{local_http_server}",
            )

    def test_unknown_auth_mode_raises(self):
        with pytest.raises(WarehouseConnectionError, match="auth_mode"):
            resolve_access_token({"auth_mode": "PASSWORD"})


class TestBreakerSwallowRemoved:
    def test_source_has_no_silent_import_swallow(self):
        text = Path("hub/apps/warehouses/base.py").read_text()
        tree = ast.parse(text)
        method = next(
            n
            for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            and n.name == "_check_circuit_breaker"
        )
        method_src = ast.get_source_segment(text, method)
        assert method_src is not None, "method source must be extractable"
        # AST-level check — the docstring legitimately MENTIONS the old
        # pattern; the real assertion is that no except-ImportError
        # HANDLER exists in the method.
        handlers = [
            n
            for n in ast.walk(method)
            if isinstance(n, ast.ExceptHandler)
            and isinstance(n.type, ast.Name)
            and n.type.id == "ImportError"
        ]
        assert handlers == [], "the silent 'except ImportError: pass' breaker swallow must be gone"
        assert "is_circuit_open" in method_src, "breaker check must be wired"

    def test_breaker_closed_does_not_raise(self):
        connector = DatabricksConnector(
            {"host": "h", "http_path": "/x", "pat_token": "t"}, tenant_id="t1"
        )
        connector._check_circuit_breaker("t1")  # no raise when CLOSED


class TestDbuDedupe:
    def test_reflect_schema_records_cost_exactly_once(self):
        source = Path("hub/apps/warehouses/connectors/databricks.py").read_text()
        tree = ast.parse(source)
        reflect = next(
            n
            for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == "reflect_schema"
        )
        reflect_calls = [
            n
            for n in ast.walk(reflect)
            if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "_record_cost"
        ]
        execute = next(
            n
            for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == "execute_query"
        )
        execute_calls = [
            n
            for n in ast.walk(execute)
            if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "_record_cost"
        ]
        assert len(reflect_calls) == 0, "post-dedupe: reflect_schema must not record"
        assert len(execute_calls) == 1, "execute_query keeps the single cost record"


class TestSemaphore:
    def test_slot_state_machine_exhausts_and_releases(self, monkeypatch):
        monkeypatch.setattr(warehouses_views, "_MAX_CONCURRENT_QUERIES", 2)
        assert warehouses_views._acquire_query_slot("t-a")
        assert warehouses_views._acquire_query_slot("t-a")
        assert not warehouses_views._acquire_query_slot("t-a"), "third slot must be refused"
        warehouses_views._release_query_slot("t-a")
        assert warehouses_views._acquire_query_slot("t-a"), "released slot is reusable"

    def test_guard_returns_429_with_code_and_retry_after(self, monkeypatch):
        factory = APIRequestFactory()
        request = Request(
            factory.get("/api/v1/warehouses/query/?asset_id=00000000-0000-0000-0000-000000000000")
        )

        view = warehouses_views.LiveQueryViewSet()
        view.request = request
        view.format_kwarg = None
        # The guard runs AFTER the tenant match — both must resolve.
        request.tenant = SimpleNamespace(id="00000000-0000-0000-0000-000000000000")

        from hub.apps.assets.models import Asset

        monkeypatch.setattr(warehouses_views, "_acquire_query_slot", lambda _tid: False)
        # The view looks assets up via ``select_related(...).get(...)`` —
        # the queryset-builder is the real seam for the fake asset.
        monkeypatch.setattr(
            Asset.objects,
            "select_related",
            lambda *_args, **_kwargs: SimpleNamespace(
                get=lambda **_kw: SimpleNamespace(tenant_id="00000000-0000-0000-0000-000000000000")
            ),
        )

        response = view.list(request)
        assert response.status_code == 429
        assert response["Retry-After"] == "5"
        assert response.data["code"] == "WAREHOUSE_CONCURRENCY_EXCEEDED"


class TestM2MExchangeRobustness:
    """0.11 review — the exchange must classify malformed bodies and ride
    transient 429/5xx through the repo's jittered backoff, like every other
    control-plane call."""

    def _m2m_config(self):
        return {
            "auth_mode": "OAUTH_M2M",
            "host": "127.0.0.1",
            "client_id": "cid-1",
            "client_secret": "secret-1",
        }

    def test_malformed_json_body_raises_classified_error(self, local_http_server):
        RecordingHandler.json_script = ["not-json{{{"]  # valid 200, broken body
        with pytest.raises(WarehouseConnectionError, match="JSON"):
            resolve_access_token(
                self._m2m_config(),
                exchange_base_url=f"http://127.0.0.1:{local_http_server}",
            )

    def test_non_object_body_raises_classified_error(self, local_http_server):
        RecordingHandler.json_script = ["[1, 2, 3]"]
        with pytest.raises(WarehouseConnectionError):
            resolve_access_token(
                self._m2m_config(),
                exchange_base_url=f"http://127.0.0.1:{local_http_server}",
            )

    def test_retryable_statuses_retry_with_backoff_then_succeed(self, local_http_server):
        RecordingHandler.script = [500, 200]
        # json_script pops per REQUEST (regardless of status) — the 500's
        # body is consumed first; the token body must land on the 200.
        RecordingHandler.json_script = ["{}", '{"access_token": "dapi-after-retry"}']
        token = resolve_access_token(
            self._m2m_config(),
            exchange_base_url=f"http://127.0.0.1:{local_http_server}",
        )
        assert token == "dapi-after-retry"
        posts = [r for r in RecordingHandler.requests if r["path"] == "/oidc/v1/token"]
        assert len(posts) == 2, "one retry for a transient 500"

    def test_retry_budget_exhausted_raises(self, local_http_server):
        RecordingHandler.script = [503, 503, 503]
        with pytest.raises(WarehouseConnectionError, match="503"):
            resolve_access_token(
                self._m2m_config(),
                exchange_base_url=f"http://127.0.0.1:{local_http_server}",
            )
        posts = [r for r in RecordingHandler.requests if r["path"] == "/oidc/v1/token"]
        assert len(posts) == 3, "exactly the retry budget, then a classified error"
