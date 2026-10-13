"""TDD pins for DatabricksOIDCProvider (openspec add-databricks-control-plane
task 0b.1) — the U2M auth-code flow with PKCE (S256) + signed-state validation.

No mocks:
- the token exchange drives a REAL local HTTP server (RecordingHandler)
  and asserts the EXACT form body the Databricks token endpoint receives;
- PKCE state is REAL: verifier persistence uses the real Django cache
  (Redis in test env) and state lifecycle uses the REAL
  hub.apps.auth.sso_state issue/consume path (signed, single-use,
  ip-class-bound, 300s TTL);
- the S256 challenge is VERIFIED end-to-end: the challenge embedded in the
  authorize URL must equal base64url(SHA256(verifier)) of the verifier
  the provider later POSTs.

Security-order contract: ``consume_state`` MUST run BEFORE the token POST —
a replayed / expired / ip-mismatched / tenant-mismatched state produces
ZERO requests against the token endpoint.
"""

import base64
import hashlib
import time
import uuid

import pytest
from django.core.cache import cache

from hub.apps.auth import sso_state
from hub.apps.auth.sso_state import SSOStateError
from hub.apps.databricks_admin.tests._fixtures import REAL_HOST, require_dns
from hub.apps.databricks_admin.tests._http import RecordingHandler
from tests.factories import TenantFactory

pytestmark = pytest.mark.django_db(transaction=True)


def _provider(tenant_id, **config_overrides):
    from hub.apps.databricks_admin.oidc_provider import DatabricksOIDCProvider

    config = {
        "host": "dbc-111.cloud.databricks.com",
        "client_id": "client-abc",
        "redirect_uri": "https://hub.example.com/auth/databricks/callback",
        **config_overrides,
    }
    return DatabricksOIDCProvider(str(tenant_id), config)


def _tenant():
    from hub.apps.databricks_admin.tests.test_views import _activate_billing

    tenant = TenantFactory.create_tenant()
    _activate_billing(tenant)
    return tenant


def _s256(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


class TestAuthorizeUrl:
    def test_url_shape_pkce_s256_and_state(self):
        tenant = _tenant()
        state = sso_state.issue_state(str(tenant.id), "public")
        provider = _provider(tenant.id)

        result = provider.build_authorize_url(state=state)
        from urllib.parse import parse_qs, urlparse

        url = result["login_url"]
        parsed = urlparse(url)
        assert parsed.scheme == "https"
        assert parsed.netloc == "dbc-111.cloud.databricks.com"
        assert parsed.path == "/oidc/v1/authorize"

        params = parse_qs(parsed.query)
        assert params["response_type"] == ["code"]
        assert params["client_id"] == ["client-abc"]
        assert params["redirect_uri"] == ["https://hub.example.com/auth/databricks/callback"]
        assert params["state"] == [state]
        assert params["code_challenge_method"] == ["S256"]
        challenge = params["code_challenge"][0]
        # 43-char unpadded base64url — the SHA-256 digest shape.
        assert len(challenge) == 43

    def test_verifier_is_cached_keyed_to_state(self):
        tenant = _tenant()
        state = sso_state.issue_state(str(tenant.id), "public")
        provider = _provider(tenant.id)

        provider.build_authorize_url(state=state)

        from hub.apps.databricks_admin.oidc_provider import _verifier_cache_key

        key = _verifier_cache_key(state)
        cached = cache.get(key)
        assert cached, "the PKCE verifier must be persisted server-side"
        assert isinstance(cached, str)
        assert len(cached) >= 43


class TestExchangeAuthCode:
    def test_success_posts_authorization_code_with_verifier(self, local_http_server):
        tenant = _tenant()
        state = sso_state.issue_state(str(tenant.id), "public")
        RecordingHandler.script = [200]
        RecordingHandler.json_script = [
            '{"access_token": "u2m-at", "id_token": "u2m-id", "token_type": "Bearer"}'
        ]
        provider = _provider(tenant.id, oidc_base_url=f"http://127.0.0.1:{local_http_server}")
        authorize = provider.build_authorize_url(state=state)
        from urllib.parse import parse_qs, urlparse

        challenge = parse_qs(urlparse(authorize["login_url"]).query)["code_challenge"][0]

        tokens = provider.exchange_auth_code(code="auth-code-1", state=state, ip_class="public")
        assert tokens["access_token"] == "u2m-at"

        # The REAL token-endpoint request carried the full OIDC form body
        # (application/x-www-form-urlencoded — decode before asserting).
        from urllib.parse import unquote_plus

        assert len(RecordingHandler.requests) == 1
        req = RecordingHandler.requests[0]
        assert req["path"] == "/oidc/v1/token"
        body = {
            unquote_plus(k): unquote_plus(v)
            for part in req.get("body", "").split("&")
            if "=" in part
            for k, v in [part.split("=", 1)]
        }
        assert body["grant_type"] == "authorization_code"
        assert body["code"] == "auth-code-1"
        assert body["redirect_uri"] == "https://hub.example.com/auth/databricks/callback"
        # The S256 contract holds end-to-end: the posted verifier hashes to
        # the challenge that went into the authorize URL.
        assert _s256(body["code_verifier"]) == challenge

    def test_reused_state_fails_before_any_token_post(self, local_http_server):
        tenant = _tenant()
        state = sso_state.issue_state(str(tenant.id), "public")
        provider = _provider(tenant.id, oidc_base_url=f"http://127.0.0.1:{local_http_server}")
        provider.build_authorize_url(state=state)

        # First consumption succeeds (mock-adjacent: consume via the real path).
        sso_state.consume_state(state, "public")

        with pytest.raises(SSOStateError) as excinfo:
            provider.exchange_auth_code(code="c", state=state, ip_class="public")
        assert excinfo.value.code == "SSO_STATE_REUSED"
        assert RecordingHandler.requests == [], (
            "a replayed state must never reach the token endpoint"
        )

    def test_ip_class_mismatch_fails_before_any_token_post(self, local_http_server):
        tenant = _tenant()
        state = sso_state.issue_state(str(tenant.id), "public")
        provider = _provider(tenant.id, oidc_base_url=f"http://127.0.0.1:{local_http_server}")
        provider.build_authorize_url(state=state)

        with pytest.raises(SSOStateError) as excinfo:
            provider.exchange_auth_code(code="c", state=state, ip_class="private")
        assert excinfo.value.code == "SSO_STATE_IP_MISMATCH"
        assert RecordingHandler.requests == []

    def test_tenant_mismatch_fails_before_any_token_post(self, local_http_server):
        tenant = _tenant()
        other = _tenant()
        state = sso_state.issue_state(str(other.id), "public")
        provider = _provider(tenant.id, oidc_base_url=f"http://127.0.0.1:{local_http_server}")
        provider.build_authorize_url(state=state)

        with pytest.raises(SSOStateError) as excinfo:
            provider.exchange_auth_code(code="c", state=state, ip_class="public")
        assert excinfo.value.code == "SSO_STATE_TENANT_MISMATCH"
        assert RecordingHandler.requests == []

    def test_expired_state_fails_before_any_token_post(self, local_http_server):
        tenant = _tenant()
        # Forge a REAL signed state with an issued-timestamp in the past
        # (signature produced by the same helper — verification is the
        # production code path, not a mock).
        nonce = uuid.uuid4().hex
        issued_ts = str(int(time.time()) - 301)
        sig = sso_state._state_sig(str(tenant.id), nonce, issued_ts, "public")
        payload = f"{tenant.id}|{nonce}|{issued_ts}|public|{sig}".encode()
        state = base64.urlsafe_b64encode(payload).decode().rstrip("=")
        cache.set(f"consume:state:{nonce}", "issued", timeout=300)

        provider = _provider(tenant.id, oidc_base_url=f"http://127.0.0.1:{local_http_server}")
        provider.build_authorize_url(state=state)

        with pytest.raises(SSOStateError) as excinfo:
            provider.exchange_auth_code(code="c", state=state, ip_class="public")
        assert excinfo.value.code == "SSO_STATE_EXPIRED"
        assert RecordingHandler.requests == []

    def test_verifier_cache_miss_fails_before_any_token_post(self, local_http_server):
        tenant = _tenant()
        state = sso_state.issue_state(str(tenant.id), "public")
        # NO build_authorize_url call — the state is valid but the provider
        # never minted a verifier for it.
        provider = _provider(tenant.id, oidc_base_url=f"http://127.0.0.1:{local_http_server}")

        with pytest.raises(SSOStateError) as excinfo:
            provider.exchange_auth_code(code="c", state=state, ip_class="public")
        assert excinfo.value.code == "SSO_STATE_INVALID"
        assert RecordingHandler.requests == []

    def test_token_endpoint_error_is_classified(self, local_http_server):
        from hub.apps.databricks_admin.oidc_provider import DatabricksOIDCTokenError

        tenant = _tenant()
        state = sso_state.issue_state(str(tenant.id), "public")
        RecordingHandler.script = [400]
        RecordingHandler.json_script = [
            '{"error": "invalid_grant", "error_description": "Code expired"}'
        ]
        provider = _provider(tenant.id, oidc_base_url=f"http://127.0.0.1:{local_http_server}")
        provider.build_authorize_url(state=state)

        with pytest.raises(DatabricksOIDCTokenError) as excinfo:
            provider.exchange_auth_code(code="c", state=state, ip_class="public")
        assert excinfo.value.code == "invalid_grant"
        assert "Code expired" in str(excinfo.value)


class TestScopesContract:
    """0b.2 — the authorize URL requests ``sql all-apis offline_access``
    by default; the identity scopes (``openid email profile``) are OPTIONAL
    and appended only when the tenant config enables them."""

    def test_default_scopes_are_sql_all_apis_offline_access(self):
        from urllib.parse import parse_qs, urlparse

        tenant = _tenant()
        state = sso_state.issue_state(str(tenant.id), "public")
        provider = _provider(tenant.id)

        url = provider.build_authorize_url(state=state)["login_url"]
        scopes = parse_qs(urlparse(url).query)["scope"][0].split()
        assert scopes == ["sql", "all-apis", "offline_access"]

    def test_optional_identity_scopes_appended_when_enabled(self):
        from urllib.parse import parse_qs, urlparse

        tenant = _tenant()
        state = sso_state.issue_state(str(tenant.id), "public")
        provider = _provider(tenant.id, include_openid_scopes=True)

        url = provider.build_authorize_url(state=state)["login_url"]
        scopes = parse_qs(urlparse(url).query)["scope"][0].split()
        assert scopes == ["sql", "all-apis", "offline_access", "openid", "email", "profile"]

    def test_explicit_scopes_override_still_wins(self):
        from urllib.parse import parse_qs, urlparse

        tenant = _tenant()
        state = sso_state.issue_state(str(tenant.id), "public")
        provider = _provider(tenant.id, scopes="sql offline_access")

        url = provider.build_authorize_url(state=state)["login_url"]
        scopes = parse_qs(urlparse(url).query)["scope"][0].split()
        assert scopes == ["sql", "offline_access"]


class TestConsentExplainer:
    """0b.2 — the canonical consent-screen content contract (U6). The copy
    lives in the BACKEND so the frontend consent screen (0b.12) renders
    auditable, versionable content instead of scattered copy."""

    def test_explains_the_requested_scopes_in_plain_language(self):
        from hub.apps.databricks_admin.oidc_provider import SSO_CONSENT_EXPLAINER

        scopes = SSO_CONSENT_EXPLAINER["scopes"]
        assert set(scopes) == {"sql", "all-apis", "offline_access"}
        for name, description in scopes.items():
            assert isinstance(description, str), f"scope {name} lacks a plain-language description"
            assert len(description) > 20, f"scope {name} description too short"

    def test_states_what_the_hub_does_on_the_users_behalf(self):
        from hub.apps.databricks_admin.oidc_provider import SSO_CONSENT_EXPLAINER

        joined = " ".join(
            [SSO_CONSENT_EXPLAINER["title"]]
            + list(SSO_CONSENT_EXPLAINER["scopes"].values())
            + SSO_CONSENT_EXPLAINER["statements"]
        ).lower()
        assert "on your behalf" in joined

    def test_states_tokens_are_encrypted_and_revocable(self):
        from hub.apps.databricks_admin.oidc_provider import SSO_CONSENT_EXPLAINER

        joined = " ".join(SSO_CONSENT_EXPLAINER["statements"]).lower()
        assert "encrypted" in joined
        assert "revok" in joined  # revoke/revocable


class TestOIDCRobustnessAndConfig:
    """0b.1 review — token-body robustness, OAuth-correct missing-code
    classification, and fail-loud construction."""

    def test_malformed_token_body_is_classified(self, local_http_server):
        from hub.apps.databricks_admin.oidc_provider import DatabricksOIDCTokenError

        tenant = _tenant()
        state = sso_state.issue_state(str(tenant.id), "public")
        RecordingHandler.script = [200]
        RecordingHandler.json_script = ["not-json{{{"]
        provider = _provider(tenant.id, oidc_base_url=f"http://127.0.0.1:{local_http_server}")
        provider.build_authorize_url(state=state)

        with pytest.raises(DatabricksOIDCTokenError) as excinfo:
            provider.exchange_auth_code(code="c", state=state, ip_class="public")
        assert excinfo.value.code == "invalid_response"

    def test_non_object_token_body_is_classified(self, local_http_server):
        from hub.apps.databricks_admin.oidc_provider import DatabricksOIDCTokenError

        tenant = _tenant()
        state = sso_state.issue_state(str(tenant.id), "public")
        RecordingHandler.script = [200]
        RecordingHandler.json_script = ["[1, 2, 3]"]
        provider = _provider(tenant.id, oidc_base_url=f"http://127.0.0.1:{local_http_server}")
        provider.build_authorize_url(state=state)

        with pytest.raises(DatabricksOIDCTokenError) as excinfo:
            provider.exchange_auth_code(code="c", state=state, ip_class="public")
        assert excinfo.value.code == "invalid_response"

    def test_missing_code_raises_oauth_invalid_request(self, local_http_server):
        # A missing authorization CODE is an OAuth request problem, not a
        # STATE problem — the callback error surface (0b.2) must be able to
        # tell them apart. Still zero network calls.
        from hub.apps.databricks_admin.oidc_provider import DatabricksOIDCTokenError

        tenant = _tenant()
        state = sso_state.issue_state(str(tenant.id), "public")
        provider = _provider(tenant.id, oidc_base_url=f"http://127.0.0.1:{local_http_server}")
        provider.build_authorize_url(state=state)

        with pytest.raises(DatabricksOIDCTokenError) as excinfo:
            provider.exchange_auth_code(code="", state=state, ip_class="public")
        assert excinfo.value.code == "invalid_request"
        assert RecordingHandler.requests == []

    def test_missing_config_raises_at_construction(self):
        from hub.apps.databricks_admin.oidc_provider import DatabricksOIDCProvider

        tenant = _tenant()
        with pytest.raises(ValueError, match="host"):
            DatabricksOIDCProvider(
                str(tenant.id),
                {"client_id": "client-abc", "redirect_uri": "https://hub.example.com/cb"},
            )
        with pytest.raises(ValueError, match="client_id"):
            DatabricksOIDCProvider(
                str(tenant.id),
                {
                    "host": "dbc-111.cloud.databricks.com",
                    "redirect_uri": "https://hub.example.com/cb",
                },
            )
        with pytest.raises(ValueError, match="redirect_uri"):
            DatabricksOIDCProvider(
                str(tenant.id),
                {"host": "dbc-111.cloud.databricks.com", "client_id": "client-abc"},
            )


class TestSSOSupportGuard:
    """0b.8 — SSO attempts on GCP workspaces surface
    ``DATABRICKS_SSO_UNAVAILABLE`` (UC-DB-003 error table)."""

    def _workspace(self, cloud):
        from hub.apps.databricks_admin.models import DatabricksCloud, DatabricksWorkspace

        # Unsaved instance — the guard reads only the cloud field.
        return DatabricksWorkspace(
            name="gcp-check",
            host="dbc-111.gcp.databricks.com" if cloud == DatabricksCloud.GCP else REAL_HOST,
            cloud=cloud,
            region="us-central1" if cloud == DatabricksCloud.GCP else "us-east-1",
        )

    def test_gcp_raises_sso_unavailable(self):
        from hub.apps.databricks_admin.models import DatabricksCloud
        from hub.apps.databricks_admin.oidc_provider import (
            DatabricksSSOUnavailableError,
            ensure_sso_supported,
        )

        ws = self._workspace(DatabricksCloud.GCP)
        with pytest.raises(DatabricksSSOUnavailableError) as excinfo:
            ensure_sso_supported(ws)
        assert excinfo.value.code == "DATABRICKS_SSO_UNAVAILABLE"

    def test_aws_and_azure_pass(self):
        from hub.apps.databricks_admin.models import DatabricksCloud
        from hub.apps.databricks_admin.oidc_provider import ensure_sso_supported

        ensure_sso_supported(self._workspace(DatabricksCloud.AWS))
        ensure_sso_supported(self._workspace(DatabricksCloud.AZURE))


class TestSSOLoginAudit:
    """0b.11 — every SSO token exchange emits DATABRICKS_SSO_LOGIN_SUCCESS
    (or FAILED for token-endpoint rejections); state-validation failures
    are NOT login failures (masked state codes, per DB-003)."""

    def test_success_exchange_emits_login_success(self, local_http_server):
        from hub.apps.audit.models import AuditEvent

        tenant = _tenant()
        state = sso_state.issue_state(str(tenant.id), "public")
        RecordingHandler.script = [200]
        RecordingHandler.json_script = [
            '{"access_token": "u2m-at", "refresh_token": "u2m-rt", "expires_in": 300}'
        ]
        provider = _provider(tenant.id, oidc_base_url=f"http://127.0.0.1:{local_http_server}")
        provider.build_authorize_url(state=state)
        provider.exchange_auth_code(code="c", state=state, ip_class="public")

        event = AuditEvent.objects.filter(action="LOGIN_SUCCESS").order_by("-timestamp").first()
        assert event is not None, "a successful exchange must emit a real audit row"
        assert event.resource_type == "DATABRICKS_SSO"

    def test_token_rejection_emits_login_failed(self, local_http_server):
        from hub.apps.audit.models import AuditEvent
        from hub.apps.databricks_admin.oidc_provider import DatabricksOIDCTokenError

        tenant = _tenant()
        state = sso_state.issue_state(str(tenant.id), "public")
        RecordingHandler.script = [400]
        RecordingHandler.json_script = ['{"error": "invalid_grant"}']
        provider = _provider(tenant.id, oidc_base_url=f"http://127.0.0.1:{local_http_server}")
        provider.build_authorize_url(state=state)
        with pytest.raises(DatabricksOIDCTokenError):
            provider.exchange_auth_code(code="c", state=state, ip_class="public")

        event = AuditEvent.objects.filter(action="LOGIN_FAILED").order_by("-timestamp").first()
        assert event is not None, "a rejected exchange must emit a real audit row"
        assert event.resource_type == "DATABRICKS_SSO"

    def test_transport_failure_emits_login_failed(self):
        # A login attempt whose token endpoint is UNREACHABLE is still a
        # failed login — abuse/brute-force detection needs every failure
        # mode audited, not only non-2xx rejections.
        from hub.apps.audit.models import AuditEvent
        from hub.apps.databricks_admin.oidc_provider import DatabricksOIDCTokenError

        tenant = _tenant()
        state = sso_state.issue_state(str(tenant.id), "public")
        provider = _provider(
            tenant.id,
            oidc_base_url="http://127.0.0.1:1",  # unreachable
        )
        provider.build_authorize_url(state=state)
        with pytest.raises(DatabricksOIDCTokenError):
            provider.exchange_auth_code(code="c", state=state, ip_class="public")

        event = (
            AuditEvent.objects.filter(action="LOGIN_FAILED", tenant=tenant)
            .order_by("-timestamp")
            .first()
        )
        assert event is not None, "a transport failure must emit a real audit row"
        assert event.resource_type == "DATABRICKS_SSO"

    def test_malformed_body_emits_login_failed(self, local_http_server):
        from hub.apps.audit.models import AuditEvent
        from hub.apps.databricks_admin.oidc_provider import DatabricksOIDCTokenError

        tenant = _tenant()
        state = sso_state.issue_state(str(tenant.id), "public")
        RecordingHandler.json_script = ["not-json{{{"]
        provider = _provider(tenant.id, oidc_base_url=f"http://127.0.0.1:{local_http_server}")
        provider.build_authorize_url(state=state)
        with pytest.raises(DatabricksOIDCTokenError):
            provider.exchange_auth_code(code="c", state=state, ip_class="public")

        event = (
            AuditEvent.objects.filter(action="LOGIN_FAILED", tenant=tenant)
            .order_by("-timestamp")
            .first()
        )
        assert event is not None, "a malformed exchange body must emit a real audit row"
        assert event.resource_type == "DATABRICKS_SSO"

    def test_state_failure_emits_no_login_event(self, local_http_server):
        from hub.apps.audit.models import AuditEvent

        tenant = _tenant()
        state = sso_state.issue_state(str(tenant.id), "public")
        provider = _provider(tenant.id, oidc_base_url=f"http://127.0.0.1:{local_http_server}")
        provider.build_authorize_url(state=state)
        sso_state.consume_state(state, "public")  # replay setup
        with pytest.raises(SSOStateError):
            provider.exchange_auth_code(code="c", state=state, ip_class="public")

        assert not AuditEvent.objects.filter(action="LOGIN_FAILED", tenant=tenant).exists(), (
            "state-validation failures are masked state codes, not login failures"
        )
        assert not AuditEvent.objects.filter(action="LOGIN_SUCCESS", tenant=tenant).exists()

    def test_classify_sso_state_error_maps_to_api_code(self):
        from hub.apps.databricks_admin.oidc_provider import classify_sso_state_error

        assert (
            classify_sso_state_error(SSOStateError("SSO_STATE_REUSED"))
            == "DATABRICKS_SSO_STATE_MISMATCH"
        )


class TestLiveDatabricksSSO:
    """0b.14 — W16-gated live-Databricks SSO branch (the task's
    "envpolicy on live-Databricks SSO branches" line): the authorize URL
    resolves and the workspace's OIDC authorize endpoint ANSWERS over
    TLS. No credentials, deterministic — a bogus client_id is never
    answered with a 5xx/transport error (the observed live behavior is a
    303 See Other redirect to the workspace's error surface).
    The full live U2M round-trip (consent + callback) is deferred to the
    P9 sandbox per the acceptance line; this pin proves the transport
    precondition — DNS, TLS, host reachability — that the round-trip
    depends on, following the 0.5 live-401 contract-test pattern."""

    def test_live_authorize_endpoint_rejects_bogus_client(self):
        require_dns()
        import httpx

        from hub.apps.databricks_admin.oidc_provider import DatabricksOIDCProvider

        provider = DatabricksOIDCProvider(
            "t1",
            {
                "host": REAL_HOST,
                "client_id": "bogus-client-for-e2e",
                "redirect_uri": "https://hub.example.com/auth/databricks/callback",
            },
        )
        url = provider.build_authorize_url(state="live-smoke-state")["login_url"]
        response = httpx.get(url, timeout=15, follow_redirects=False)
        assert response.status_code < 500, (
            "the live OIDC authorize endpoint must answer a bogus client_id "
            f"with a 3xx/4xx — got {response.status_code}"
        )
        # 3xx redirects legitimately carry an EMPTY body (the observed live
        # behavior is 303 See Other) — RFC 7231 makes the Location target
        # the deterministic contract for a redirect; an error page must
        # carry a body.
        if response.is_redirect:
            assert response.headers.get("location"), (
                "a redirect from the live authorize endpoint must carry "
                "a Location target (RFC 7231)"
            )
        else:
            assert response.content, "a non-redirect must carry a body"
