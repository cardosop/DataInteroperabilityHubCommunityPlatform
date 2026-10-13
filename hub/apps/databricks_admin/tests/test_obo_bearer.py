"""TDD pins for OBO bearer resolution (openspec add-databricks-control-plane
task 0b.5).

No mocks: the Databricks API + the OAuth token endpoint are a REAL local
HTTP server whose status/body sequences are scripted per request; the
vault + cache use the REAL Postgres row and REAL Redis (host-side
p313-redis); assertions cover the EXACT Authorization headers sent.

Contracts pinned:
- per-request identity: the bearer on the API call IS the OBO access
  token (never a service credential);
- cold cache → one refresh-token exchange → API call proceeds;
- 401 → refresh ONCE → retry (exactly one token-endpoint call, two API
  calls with different bearers);
- repeated failure (401 again after refresh) → ``DatabricksOBOError``
  code ``DATABRICKS_OBO_REFRESH_FAILED``, no retry storm;
- refresh-endpoint failure → same classified code;
- fail-closed: no bound token → error raised BEFORE any API call, and
  the client NEVER falls back to a service credential on the interactive
  path.
"""

import uuid

import pytest

from hub.apps.databricks_admin.tests._fixtures import REAL_HOST, require_dns
from hub.apps.databricks_admin.tests._http import RecordingHandler
from hub.apps.databricks_admin.tests.test_views import (
    _activate_billing,
    _make_user,
)
from tests.factories import TenantFactory

pytestmark = pytest.mark.django_db(transaction=True)


def _setup():
    require_dns()
    from hub.apps.databricks_admin.models import (
        DatabricksCloud,
        DatabricksUserBinding,
        DatabricksWorkspace,
    )

    tenant = TenantFactory.create_tenant()
    _activate_billing(tenant)
    user = _make_user(tenant, f"bearer-{uuid.uuid4().hex[:8]}@test.com")
    workspace = DatabricksWorkspace.objects.create(
        tenant=tenant,
        name=f"ws-{uuid.uuid4().hex[:8]}",
        host=REAL_HOST,
        cloud=DatabricksCloud.AWS,
        region="us-east-1",
        status="ACTIVE",
    )
    binding = DatabricksUserBinding.objects.create(
        tenant=tenant,
        user=user,
        workspace=workspace,
        databricks_sub=f"sub-{uuid.uuid4().hex[:8]}",
        databricks_email=user.email,
    )
    return tenant, binding


def _provider(binding, oidc_base_url, redis_13):
    from hub.apps.databricks_admin.obo_tokens import (
        OBOAccessTokenCache,
        OBOTokenProvider,
    )

    return OBOTokenProvider(
        binding=binding,
        oidc_client_id="client-abc",
        oidc_base_url=oidc_base_url,
        access_cache=OBOAccessTokenCache(redis_client=redis_13),
    )


def _seed_vault(binding, refresh_token="r1"):
    from hub.apps.databricks_admin.models import DatabricksOBOToken

    token = DatabricksOBOToken.objects.create(tenant=binding.tenant, binding=binding)
    token.set_refresh_token(refresh_token)
    token.save()
    return token


class TestProviderResolution:
    def test_cold_cache_refreshes_via_token_endpoint(self, local_http_server, redis_13):
        from hub.apps.databricks_admin.obo_tokens import get_refresh_token

        _tenant, binding = _setup()
        _seed_vault(binding, refresh_token="r1")
        RecordingHandler.script = [200]
        RecordingHandler.json_script = [
            '{"access_token": "new-at", "refresh_token": "new-rt", "expires_in": 300}'
        ]
        provider = _provider(binding, f"http://127.0.0.1:{local_http_server}", redis_13)

        assert provider.get_bearer() == "new-at"
        assert len(RecordingHandler.requests) == 1
        req = RecordingHandler.requests[0]
        assert req["path"] == "/oidc/v1/token"
        assert "grant_type=refresh_token" in req["body"]
        assert "r1" in req["body"]
        # The vault rotated to the replacement refresh token.
        assert get_refresh_token(binding=binding) == "new-rt"

    def test_warm_cache_skips_the_token_endpoint(self, local_http_server, redis_13):
        _tenant, binding = _setup()
        provider = _provider(binding, f"http://127.0.0.1:{local_http_server}", redis_13)
        provider.access_cache.set(binding.id, "warm-at", 300)

        assert provider.get_bearer() == "warm-at"
        assert RecordingHandler.requests == [], "a warm cache must not hit the token endpoint"

    def test_no_bound_token_fails_closed_before_any_network(self, local_http_server, redis_13):
        from hub.apps.databricks_admin.client import DatabricksOBOError

        _tenant, binding = _setup()
        # NO vault row at all.
        provider = _provider(binding, f"http://127.0.0.1:{local_http_server}", redis_13)
        with pytest.raises(DatabricksOBOError) as excinfo:
            provider.get_bearer()
        assert excinfo.value.code == "DATABRICKS_OBO_REFRESH_FAILED"
        assert RecordingHandler.requests == []


class TestClientOBOFlow:
    def _client(self, provider, oidc_base_url):
        from hub.apps.databricks_admin.client import DatabricksApiClient

        return DatabricksApiClient(
            base_url=oidc_base_url,
            tenant_id="t",
            obo_provider=provider,
            max_retries=1,
        )

    def test_api_call_carries_the_obo_bearer(self, local_http_server, redis_13):
        _tenant, binding = _setup()
        provider = _provider(binding, f"http://127.0.0.1:{local_http_server}", redis_13)
        provider.access_cache.set(binding.id, "warm-at", 300)
        RecordingHandler.script = [200]
        RecordingHandler.json_script = ["{}"]

        client = self._client(provider, f"http://127.0.0.1:{local_http_server}")
        response = client.request("GET", "workspace.list")
        assert response.status_code == 200
        assert RecordingHandler.requests[0]["headers"]["Authorization"] == "Bearer warm-at"

    def test_401_refreshes_once_and_retries(self, local_http_server, redis_13):
        _tenant, binding = _setup()
        _seed_vault(binding, refresh_token="r1")
        provider = _provider(binding, f"http://127.0.0.1:{local_http_server}", redis_13)
        provider.access_cache.set(binding.id, "at-old", 300)
        # API 401 → token 200 → API 200.
        RecordingHandler.script = [401, 200, 200]
        RecordingHandler.json_script = [
            '{"error": "unauthorized"}',
            '{"access_token": "refreshed-at", "refresh_token": "r2", "expires_in": 300}',
            "{}",
        ]

        client = self._client(provider, f"http://127.0.0.1:{local_http_server}")
        response = client.request("GET", "workspace.list")
        assert response.status_code == 200

        requests = RecordingHandler.requests
        assert [r["path"] for r in requests] == [
            "/api/2.0/workspace/list",
            "/oidc/v1/token",
            "/api/2.0/workspace/list",
        ]
        assert requests[0]["headers"]["Authorization"] == "Bearer at-old"
        assert requests[2]["headers"]["Authorization"] == "Bearer refreshed-at"

    def test_repeated_401_after_refresh_raises_classified_code(self, local_http_server, redis_13):
        from hub.apps.databricks_admin.client import DatabricksOBOError

        _tenant, binding = _setup()
        _seed_vault(binding, refresh_token="r1")
        provider = _provider(binding, f"http://127.0.0.1:{local_http_server}", redis_13)
        provider.access_cache.set(binding.id, "at-old", 300)
        # API 401 → token 200 → API 401 (the new token is ALSO rejected).
        RecordingHandler.script = [401, 200, 401]
        RecordingHandler.json_script = [
            '{"error": "unauthorized"}',
            '{"access_token": "refreshed-at", "refresh_token": "r2", "expires_in": 300}',
            '{"error": "unauthorized"}',
        ]

        client = self._client(provider, f"http://127.0.0.1:{local_http_server}")
        with pytest.raises(DatabricksOBOError) as excinfo:
            client.request("GET", "workspace.list")
        assert excinfo.value.code == "DATABRICKS_OBO_REFRESH_FAILED"
        # Exactly ONE token-endpoint call — no retry storm.
        token_calls = [r for r in RecordingHandler.requests if r["path"] == "/oidc/v1/token"]
        assert len(token_calls) == 1

    def test_refresh_endpoint_failure_raises_classified_code(self, local_http_server, redis_13):
        from hub.apps.databricks_admin.client import DatabricksOBOError

        _tenant, binding = _setup()
        _seed_vault(binding, refresh_token="r1")
        provider = _provider(binding, f"http://127.0.0.1:{local_http_server}", redis_13)
        provider.access_cache.set(binding.id, "at-old", 300)
        # API 401 → token 500.
        RecordingHandler.script = [401, 500]
        RecordingHandler.json_script = [
            '{"error": "unauthorized"}',
            '{"error": "server_error"}',
        ]

        client = self._client(provider, f"http://127.0.0.1:{local_http_server}")
        with pytest.raises(DatabricksOBOError) as excinfo:
            client.request("GET", "workspace.list")
        assert excinfo.value.code == "DATABRICKS_OBO_REFRESH_FAILED"


class TestConnectorOBO:
    def test_resolve_access_token_prefers_obo_and_never_falls_back(
        self, local_http_server, redis_13
    ):
        from hub.apps.databricks_admin.obo_tokens import get_refresh_token
        from hub.apps.warehouses.connectors.databricks import resolve_access_token

        _tenant, binding = _setup()
        _seed_vault(binding, refresh_token="r1")
        RecordingHandler.script = [200]
        RecordingHandler.json_script = [
            '{"access_token": "obo-token", "refresh_token": "r2", "expires_in": 300}'
        ]
        provider = _provider(binding, f"http://127.0.0.1:{local_http_server}", redis_13)

        # The config carries a PAT — the INTERACTIVE path must ignore it.
        config = {"host": REAL_HOST, "pat_token": "dapi-service-credential"}
        token = resolve_access_token(config, obo_provider=provider)
        assert token == "obo-token"
        assert get_refresh_token(binding=binding) == "r2"


class TestRefreshBodyRobustness:
    """0b.5 review — the COLD-cache path (get_bearer → refresh) must
    classify malformed/non-object token bodies: a raw JSONDecodeError /
    AttributeError would leak through _bearer() outside any
    DatabricksOBOError wrapper."""

    def test_malformed_token_body_raises_classified_error(self, redis_13, local_http_server):
        from hub.apps.databricks_admin.client import DatabricksOBOError
        from hub.apps.databricks_admin.tests._http import RecordingHandler

        _tenant, binding = _setup()
        _seed_vault(binding, refresh_token="r1")
        RecordingHandler.json_script = ["not-json{{{"]
        provider = _provider(
            binding,
            f"http://127.0.0.1:{local_http_server}",
            redis_13,
        )

        with pytest.raises(DatabricksOBOError) as excinfo:
            provider.get_bearer()
        assert "JSON" in str(excinfo.value)

    def test_non_object_token_body_raises_classified_error(self, redis_13, local_http_server):
        from hub.apps.databricks_admin.client import DatabricksOBOError
        from hub.apps.databricks_admin.tests._http import RecordingHandler

        _tenant, binding = _setup()
        _seed_vault(binding, refresh_token="r1")
        RecordingHandler.json_script = ["[1, 2, 3]"]
        provider = _provider(
            binding,
            f"http://127.0.0.1:{local_http_server}",
            redis_13,
        )

        with pytest.raises(DatabricksOBOError) as excinfo:
            provider.get_bearer()
        assert excinfo.value.code == "DATABRICKS_OBO_REFRESH_FAILED"


class TestOBORefreshAudit:
    """0b.11 — every successful OBO refresh emits DATABRICKS_OBO_TOKEN_REFRESHED."""

    def test_refresh_emits_audit_row(self, local_http_server, redis_13):
        from hub.apps.audit.models import AuditEvent

        _tenant, binding = _setup()
        _seed_vault(binding, refresh_token="r1")
        RecordingHandler.script = [200]
        RecordingHandler.json_script = [
            '{"access_token": "new-at", "refresh_token": "r2", "expires_in": 300}'
        ]
        provider = _provider(binding, f"http://127.0.0.1:{local_http_server}", redis_13)
        provider.refresh()

        event = AuditEvent.objects.filter(action="REFRESHED").order_by("-timestamp").first()
        assert event is not None, "a successful OBO refresh must emit a real audit row"
        assert event.resource_type == "DATABRICKS_OBO_TOKEN"


class TestCrossWorkspaceTokenIsolation:
    """JOURNEY-DB-003 success criterion: cross-workspace token reuse never
    happens — a W1 refresh must never leak into W2's cache or bearer."""

    def test_w1_refresh_never_reaches_w2(self, local_http_server, redis_13):
        from hub.apps.databricks_admin.models import DatabricksCloud, DatabricksWorkspace

        _tenant, binding_w1 = _setup()
        from hub.apps.databricks_admin.models import DatabricksUserBinding

        workspace_w2 = DatabricksWorkspace.objects.create(
            tenant=binding_w1.tenant,
            name=f"ws2-{uuid.uuid4().hex[:8]}",
            host=REAL_HOST,
            cloud=DatabricksCloud.AWS,
            region="us-east-1",
            status="ACTIVE",
        )
        binding_w2 = DatabricksUserBinding.objects.create(
            tenant=binding_w1.tenant,
            user=binding_w1.user,
            workspace=workspace_w2,
            databricks_sub="sub-w2",
            databricks_email=binding_w1.user.email,
        )
        _seed_vault(binding_w1, refresh_token="r1-w1")
        _seed_vault(binding_w2, refresh_token="r1-w2")

        cache = type(_provider(binding_w1, "", redis_13).access_cache)(redis_client=redis_13)
        provider_w1 = _provider(binding_w1, f"http://127.0.0.1:{local_http_server}", redis_13)
        provider_w2 = _provider(binding_w2, f"http://127.0.0.1:{local_http_server}", redis_13)

        # Refresh W1 only.
        RecordingHandler.script = [200]
        RecordingHandler.json_script = [
            '{"access_token": "w1-new-at", "refresh_token": "w1-new-rt", "expires_in": 300}'
        ]
        assert provider_w1.refresh() == "w1-new-at"

        # W2's cache and vault are untouched by W1's rotation.
        assert provider_w2.access_cache.get(binding_w2.id) is None
        from hub.apps.databricks_admin.obo_tokens import get_refresh_token

        assert get_refresh_token(binding=binding_w2) == "r1-w2"
        assert cache.get(binding_w1.id) == "w1-new-at"
