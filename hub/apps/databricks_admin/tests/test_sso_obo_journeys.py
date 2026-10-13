"""JOURNEY-DB-003 / JOURNEY-DB-004 backend journey tests (task 0b.13).

The class/method names are PINNED by the canonical use-case docs
(``docs/mvpdocs/use-cases/UC-DB-003.md`` / ``UC-DB-004.md`` "Phase P0b
Test" fields) — renaming them requires updating those docs in the same PR.

No mocks: real Postgres, the REAL sso_state lifecycle, the REAL OIDC
provider against a real local HTTP server, the REAL binding + vault +
JWT issuance, and the REAL client OBO 401→refresh→retry flow.
"""

import json
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

SSO_URL = "/api/v1/databricks/sso"


def _tenant_with_sso_config():
    require_dns()
    tenant = TenantFactory.create_tenant()
    _activate_billing(tenant)
    from hub.apps.tenants.models import TenantConfig

    config = TenantConfig.objects.get_or_create(tenant=tenant)[0]
    sso = config.get_sso_config()
    sso["databricks"] = {
        "host": REAL_HOST,
        "client_id": "client-abc",
        "redirect_uri": "https://hub.example.com/auth/databricks/callback",
    }
    config.sso_config = sso
    config.save()
    return tenant


def _workspace(tenant):
    from hub.apps.databricks_admin.models import DatabricksCloud, DatabricksWorkspace

    return DatabricksWorkspace.objects.create(
        tenant=tenant,
        name=f"ws-{uuid.uuid4().hex[:8]}",
        host=REAL_HOST,
        cloud=DatabricksCloud.AWS,
        region="us-east-1",
        status="ACTIVE",
    )


def _id_token_for(email: str, sub: str) -> str:
    import base64 as _b64
    import hashlib
    import hmac as _hmac

    header = {"alg": "HS256", "typ": "JWT"}
    payload = {"sub": sub, "email": email, "exp": 9999999999}

    def enc(o):
        return (
            _b64.urlsafe_b64encode(json.dumps(o, separators=(",", ":")).encode())
            .rstrip(b"=")
            .decode()
        )

    signing_input = f"{enc(header)}.{enc(payload)}"
    sig = (
        _b64.urlsafe_b64encode(
            _hmac.new(b"test-secret", signing_input.encode(), hashlib.sha256).digest()
        )
        .rstrip(b"=")
        .decode()
    )
    return f"{signing_input}.{sig}"


@pytest.mark.journey("JOURNEY-DB-003")
@pytest.mark.uc("UC-DB-003")
class TestJOURNEYDB003DatabricksSignIn:
    """Sign in with Databricks — the full U2M flow."""

    def test_token_exchange_creates_binding(self, monkeypatch, local_http_server):
        from rest_framework.test import APIClient

        from hub.apps.databricks_admin import sso_views
        from hub.apps.databricks_admin.models import DatabricksUserBinding
        from hub.apps.users.models import User

        tenant = _tenant_with_sso_config()
        tenant.databricks_sso_enabled = True
        tenant.save(update_fields=["databricks_sso_enabled"])
        workspace = _workspace(tenant)

        client = APIClient()
        login_resp = client.get(
            f"{SSO_URL}/login-url/?tenant_id={tenant.id}&workspace_id={workspace.id}"
        )
        from urllib.parse import parse_qs, urlparse

        state = parse_qs(urlparse(login_resp.json()["login_url"]).query)["state"][0]

        email = f"db003-{uuid.uuid4().hex[:8]}@databricks.com"
        sub = f"sub-{uuid.uuid4().hex[:8]}"
        RecordingHandler.script = [200]
        RecordingHandler.json_script = [
            json.dumps(
                {
                    "access_token": "u2m-at",
                    "refresh_token": "u2m-rt",
                    "id_token": _id_token_for(email, sub),
                    "expires_in": 300,
                }
            )
        ]

        def fake_factory(*_args, **_kwargs):
            from hub.apps.databricks_admin.oidc_provider import DatabricksOIDCProvider

            return DatabricksOIDCProvider(
                str(tenant.id),
                {
                    "host": REAL_HOST,
                    "client_id": "client-abc",
                    "redirect_uri": "https://hub.example.com/auth/databricks/callback",
                    "oidc_base_url": f"http://127.0.0.1:{local_http_server}",
                },
            )

        monkeypatch.setattr(sso_views, "_build_oidc_provider", fake_factory)

        response = client.post(
            f"{SSO_URL}/callback/",
            {
                "code": "auth-code-1",
                "state": state,
                "workspace_id": str(workspace.id),
                "redirect_uri": "https://hub.example.com/auth/databricks/callback",
            },
            format="json",
        )
        assert response.status_code == 200, response.content
        assert response.json()["token_type"] == "Bearer"

        user = User.objects.get(email=email, tenant=tenant)
        binding = DatabricksUserBinding.objects.get(user=user, workspace=workspace)
        assert binding.databricks_sub == sub
        assert binding.databricks_email == email


@pytest.mark.journey("JOURNEY-DB-004")
@pytest.mark.uc("UC-DB-004")
class TestJOURNEYDB004SessionRefreshExpiry:
    """Session refresh and expiry handling — the 401→refresh-once→retry
    contract end-to-end."""

    def test_401_refresh_retry_once(self, local_http_server, redis_13):
        from hub.apps.databricks_admin.client import DatabricksApiClient
        from hub.apps.databricks_admin.models import (
            DatabricksCloud,
            DatabricksOBOToken,
            DatabricksUserBinding,
            DatabricksWorkspace,
        )
        from hub.apps.databricks_admin.obo_tokens import (
            OBOAccessTokenCache,
            OBOTokenProvider,
        )

        tenant = _tenant_with_sso_config()
        user = _make_user(tenant, f"db004-{uuid.uuid4().hex[:8]}@test.com")
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
            databricks_sub="sub-db004",
            databricks_email=user.email,
        )
        vault = DatabricksOBOToken.objects.create(tenant=tenant, binding=binding)
        vault.set_refresh_token("r1")
        vault.save()

        access_cache = OBOAccessTokenCache(redis_client=redis_13)
        provider = OBOTokenProvider(
            binding=binding,
            oidc_client_id="client-abc",
            oidc_base_url=f"http://127.0.0.1:{local_http_server}",
            access_cache=access_cache,
        )
        provider.access_cache.set(binding.id, "at-old", 300)

        # API 401 → token 200 → API 200 — exactly one refresh.
        RecordingHandler.script = [401, 200, 200]
        RecordingHandler.json_script = [
            '{"error": "unauthorized"}',
            '{"access_token": "refreshed-at", "refresh_token": "r2", "expires_in": 300}',
            "{}",
        ]

        client = DatabricksApiClient(
            base_url=f"http://127.0.0.1:{local_http_server}",
            tenant_id=str(tenant.id),
            obo_provider=provider,
            max_retries=1,
        )
        response = client.request("GET", "workspace.list")
        assert response.status_code == 200

        token_calls = [r for r in RecordingHandler.requests if r["path"] == "/oidc/v1/token"]
        assert len(token_calls) == 1, "a 401 must trigger exactly ONE refresh"
