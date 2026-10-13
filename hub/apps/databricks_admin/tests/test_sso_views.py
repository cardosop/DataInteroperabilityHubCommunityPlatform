"""TDD pins for the Databricks SSO API surface (task 0b.12).

No mocks: real Postgres (tenant/workspace/SSO config/flag columns), the
REAL sso_state lifecycle (signed, single-use), the REAL provider
(exchange drives a real local HTTP server), the REAL binding + vault +
JWT issuance. The pins cover:

- GET /api/v1/databricks/sso/workspaces/ — the chooser: tenant's ACTIVE
  non-GCP workspaces; gated by the 0b.10 SSO flag/kill switch (403).
- GET /api/v1/databricks/sso/login-url/ — authorize URL with PKCE
  (S256) + signed state; GCP → 400 DATABRICKS_SSO_UNAVAILABLE; missing
  client_id config → 400.
- POST /api/v1/databricks/sso/callback/ — state consumed BEFORE the
  exchange, id_token claims provision the Hub user + binding, tokens
  stored in the vault, a Hub JWT is issued.
- GET /api/v1/databricks/sso/session/ — the countdown state + hub
  re-auth deadline (authenticated).
"""

import json
import uuid

import pytest
from rest_framework.test import APIClient

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
    config.sso_config = sso  # plaintext dict — encrypted by save()
    config.save()
    return tenant


def _workspace(tenant, **overrides):
    from hub.apps.databricks_admin.models import DatabricksCloud, DatabricksWorkspace

    return DatabricksWorkspace.objects.create(
        tenant=tenant,
        name=overrides.pop("name", f"ws-{uuid.uuid4().hex[:8]}"),
        host=REAL_HOST,
        cloud=overrides.pop("cloud", DatabricksCloud.AWS),
        region="us-east-1",
        status=overrides.pop("status", "ACTIVE"),
        **overrides,
    )


class TestSSOWorkspacesChooser:
    def test_chooser_lists_active_non_gcp_workspaces(self):
        tenant = _tenant_with_sso_config()
        tenant.databricks_sso_enabled = True
        tenant.save(update_fields=["databricks_sso_enabled"])
        _workspace(tenant)
        _workspace(tenant, status="REGISTERED")
        from hub.apps.databricks_admin.models import DatabricksCloud

        _workspace(tenant, cloud=DatabricksCloud.GCP)

        response = APIClient().get(f"{SSO_URL}/workspaces/?tenant_id={tenant.id}")
        assert response.status_code == 200, response.content
        items = response.json()["workspaces"]
        assert len(items) == 1

    def test_chooser_403_when_sso_flag_off(self):
        tenant = _tenant_with_sso_config()
        response = APIClient().get(f"{SSO_URL}/workspaces/?tenant_id={tenant.id}")
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "DATABRICKS_SSO_DISABLED"


class TestSSOLoginUrl:
    def test_login_url_has_pkce_and_signed_state(self):
        tenant = _tenant_with_sso_config()
        tenant.databricks_sso_enabled = True
        tenant.save(update_fields=["databricks_sso_enabled"])
        workspace = _workspace(tenant)

        response = APIClient().get(
            f"{SSO_URL}/login-url/?tenant_id={tenant.id}&workspace_id={workspace.id}"
        )
        assert response.status_code == 200, response.content
        body = response.json()
        from urllib.parse import parse_qs, urlparse

        params = parse_qs(urlparse(body["login_url"]).query)
        assert params["response_type"] == ["code"]
        assert params["code_challenge_method"] == ["S256"]
        assert params["client_id"] == ["client-abc"]
        assert "state" in params

    def test_gcp_workspace_returns_sso_unavailable(self):
        from hub.apps.databricks_admin.models import DatabricksCloud

        tenant = _tenant_with_sso_config()
        tenant.databricks_sso_enabled = True
        tenant.save(update_fields=["databricks_sso_enabled"])
        workspace = _workspace(tenant, cloud=DatabricksCloud.GCP)

        response = APIClient().get(
            f"{SSO_URL}/login-url/?tenant_id={tenant.id}&workspace_id={workspace.id}"
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "DATABRICKS_SSO_UNAVAILABLE"


class TestSSOCallback:
    def test_callback_issues_hub_jwt_and_stores_vault_row(self, monkeypatch, local_http_server):
        from hub.apps.databricks_admin import sso_views

        tenant = _tenant_with_sso_config()
        tenant.databricks_sso_enabled = True
        tenant.save(update_fields=["databricks_sso_enabled"])
        workspace = _workspace(tenant)

        client = APIClient()
        login_resp = client.get(
            f"{SSO_URL}/login-url/?tenant_id={tenant.id}&workspace_id={workspace.id}"
        )
        login_body = login_resp.json()
        from urllib.parse import parse_qs, urlparse

        state = parse_qs(urlparse(login_body["login_url"]).query)["state"][0]

        # The exchange drives the REAL provider against a real local server.
        RecordingHandler.script = [200]
        email = f"dbx-user-{uuid.uuid4().hex[:8]}@databricks.com"
        RecordingHandler.json_script = [
            json.dumps(
                {
                    "access_token": "u2m-at",
                    "refresh_token": "u2m-rt",
                    "id_token": _id_token_for(email),
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
        body = response.json()
        assert body["token_type"] == "Bearer"
        assert body["user"]["email"] == email

        # The binding + vault row exist for the workspace.
        from hub.apps.databricks_admin.models import (
            DatabricksOBOToken,
            DatabricksUserBinding,
        )
        from hub.apps.users.models import User

        user = User.objects.get(email=email, tenant=tenant)
        binding = DatabricksUserBinding.objects.get(user=user, workspace=workspace)
        assert DatabricksOBOToken.objects.filter(binding=binding).exists()


def _id_token_for(email: str, sub: str | None = None) -> str:
    """A REAL signed HS256 JWT — the callback decodes it unverified (the
    repo's OIDC claim-extraction convention)."""
    import base64 as _b64
    import hashlib
    import hmac as _hmac

    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": sub or f"sub-{uuid.uuid4().hex[:8]}",
        "email": email,
        "exp": 9999999999,
    }

    def enc(o) -> str:
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


class TestSSOSession:
    def test_session_returns_countdown_state_and_hub_deadline(self):
        from hub.apps.databricks_admin.models import (
            DatabricksCloud,
            DatabricksOBOToken,
            DatabricksUserBinding,
            DatabricksWorkspace,
        )

        tenant = _tenant_with_sso_config()
        admin = _make_user(tenant, f"sess-{uuid.uuid4().hex[:8]}@test.com")
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
            user=admin,
            workspace=workspace,
            databricks_sub="sub-sess",
            databricks_email=admin.email,
        )
        token = DatabricksOBOToken.objects.create(tenant=tenant, binding=binding)
        token.set_refresh_token("r1")
        token.save()

        client = APIClient()
        client.force_authenticate(user=admin)
        response = client.get(f"{SSO_URL}/session/")
        assert response.status_code == 200, response.content
        body = response.json()
        assert "countdown" in body
        assert "hub_reauth_deadline" in body


class TestPeekState:
    def test_peek_returns_tenant_without_consuming(self):
        from hub.apps.auth import sso_state

        tenant = _tenant_with_sso_config()
        state = sso_state.issue_state(str(tenant.id), "public")
        assert sso_state.peek_state(state) == str(tenant.id)
        # Not consumed — the exchange can still consume it.
        assert sso_state.consume_state(state, "public") == str(tenant.id)

    def test_peek_rejects_tampered_state(self):
        from hub.apps.auth import sso_state
        from hub.apps.auth.sso_state import SSOStateError

        with pytest.raises(SSOStateError):
            sso_state.peek_state("tampered")


class TestSessionDeadlineDerivation:
    """0b.12 review — the hub deadline must derive from the session token's
    iat (0b.7 contract), NOT the poll time (which would drift forward on
    every banner poll and never approach)."""

    def test_hub_deadline_derives_from_token_iat(self):
        from datetime import UTC, datetime, timedelta

        from rest_framework.request import Request
        from rest_framework.test import APIRequestFactory

        from hub.apps.databricks_admin.session_policy import (
            DEFAULT_HUB_SESSION_LIFETIME_SECONDS,
        )
        from hub.apps.databricks_admin.sso_views import DatabricksSSOViewSet

        tenant = _tenant_with_sso_config()
        admin = _make_user(tenant, f"sess-iat-{uuid.uuid4().hex[:8]}@test.com")

        drf_request = Request(APIRequestFactory().get(f"{SSO_URL}/session/"))
        drf_request.user = admin
        issued = datetime.now(UTC) - timedelta(hours=1)
        # The seam the JWT authentication class fills: the decoded payload.
        drf_request.token_payload = {"iat": int(issued.timestamp())}

        response = DatabricksSSOViewSet().session(drf_request)
        body = response.data
        deadline = datetime.fromisoformat(body["hub_reauth_deadline"])
        expected = issued + timedelta(seconds=DEFAULT_HUB_SESSION_LIFETIME_SECONDS)
        assert abs(deadline - expected) < timedelta(seconds=5), (
            "the deadline must derive from the session's issued-at (token iat), not the poll time"
        )


class TestCallbackBindingConflict:
    """0b.12 review — a principal already bound to a DIFFERENT Hub user
    must surface as a clean 409, never a raw 500."""

    def test_callback_binding_conflict_is_a_clean_409(self, monkeypatch, local_http_server):
        from hub.apps.databricks_admin import sso_views
        from hub.apps.databricks_admin.models import DatabricksUserBinding
        from hub.apps.databricks_admin.oidc_provider import DatabricksOIDCProvider

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

        # The principal is ALREADY bound to a different Hub user.
        other = _make_user(tenant, f"owner-{uuid.uuid4().hex[:8]}@test.com")
        DatabricksUserBinding.objects.create(
            tenant=tenant,
            user=other,
            workspace=workspace,
            databricks_sub="sub-conflict",
            databricks_email="owner@example.com",
        )

        RecordingHandler.script = [200]
        email = f"dbx-conflict-{uuid.uuid4().hex[:8]}@databricks.com"
        RecordingHandler.json_script = [
            json.dumps(
                {
                    "access_token": "u2m-at",
                    "refresh_token": "u2m-rt",
                    "id_token": _id_token_for(email, sub="sub-conflict"),
                    "expires_in": 300,
                }
            )
        ]

        def fake_factory(*_args, **_kwargs):
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
            },
            format="json",
        )
        assert response.status_code == 409, response.content
        assert response.json()["code"] == "DATABRICKS_PRINCIPAL_ALREADY_BOUND"


class TestOfflineAccessMissing:
    """UC-DB-003 error table: a token response WITHOUT ``offline_access``
    (no refresh_token) still completes the login — but NO refresh token is
    persisted, so OBO persistence is absent."""

    def test_callback_without_refresh_token_completes_without_persistence(
        self, monkeypatch, local_http_server
    ):
        from rest_framework.test import APIClient

        from hub.apps.databricks_admin import sso_views
        from hub.apps.databricks_admin.models import (
            DatabricksOBOToken,
            DatabricksUserBinding,
        )
        from hub.apps.databricks_admin.obo_tokens import get_refresh_token
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

        email = f"nooffline-{uuid.uuid4().hex[:8]}@databricks.com"
        RecordingHandler.script = [200]
        RecordingHandler.json_script = [
            json.dumps(
                {
                    "access_token": "u2m-at",
                    "id_token": _id_token_for(email),
                    "expires_in": 300,
                    # NO refresh_token — offline_access was not granted.
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
        assert DatabricksOBOToken.objects.filter(binding=binding).exists(), (
            "the vault row exists (access-token bookkeeping)"
        )
        assert get_refresh_token(binding=binding) == "", (
            "no refresh token may be persisted without offline_access"
        )
