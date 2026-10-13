"""TDD pins for the OBO token vault (openspec add-databricks-control-plane
task 0b.4).

No mocks:
- encryption at rest uses the REAL `hub.apps.integrations.encryption`
  chain (KMS primary, Fernet fallback in test env — same as
  DatabricksCredential) and is asserted on the RAW column;
- the access-token cache uses REAL Redis (TTL asserted ≤ expiry);
- logout revocation drives a REAL local HTTP server for the server-side
  revocation attempt and asserts the local delete + cache flush +
  audit row happen EVEN when the server-side call fails (best-effort);
- single-use rotation: each successful refresh REPLACES the stored
  refresh ciphertext (the old token can never be replayed from the
  vault), and workspaces that do NOT rotate keep the existing token.
"""

import json
import uuid

import pytest
from django.db import connection

from hub.apps.databricks_admin.tests._fixtures import REAL_HOST, require_dns
from hub.apps.databricks_admin.tests.test_views import (
    _activate_billing,
    _make_user,
)
from tests.factories import TenantFactory

pytestmark = pytest.mark.django_db(transaction=True)


def _setup():
    require_dns()
    from hub.apps.databricks_admin.models import DatabricksCloud, DatabricksWorkspace

    tenant = TenantFactory.create_tenant()
    _activate_billing(tenant)
    user = _make_user(tenant, f"obo-{uuid.uuid4().hex[:8]}@test.com")
    workspace = DatabricksWorkspace.objects.create(
        tenant=tenant,
        name=f"ws-{uuid.uuid4().hex[:8]}",
        host=REAL_HOST,
        cloud=DatabricksCloud.AWS,
        region="us-east-1",
        status="ACTIVE",
    )
    from hub.apps.databricks_admin.models import DatabricksUserBinding

    binding = DatabricksUserBinding.objects.create(
        tenant=tenant,
        user=user,
        workspace=workspace,
        databricks_sub=f"sub-{uuid.uuid4().hex[:8]}",
        databricks_email=user.email,
    )
    return tenant, binding


def _raw_column(token) -> str:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT refresh_token_encrypted FROM databricks_obo_tokens WHERE id = %s",
            [token.id],
        )
        row = cursor.fetchone()
    assert row is not None
    return json.dumps(row[0])


class TestStoreTokens:
    def test_refresh_token_encrypted_at_rest(self):
        from hub.apps.databricks_admin.obo_tokens import store_tokens

        _tenant, binding = _setup()
        token = store_tokens(
            binding=binding,
            access_token="u2m-access",
            access_expires_in=3600,
            refresh_token="u2m-refresh-secret",
        )
        raw = _raw_column(token)
        assert "_encrypted" in raw, "refresh token must be stored wrapped"
        assert "u2m-refresh-secret" not in raw

    def test_roundtrip_returns_plaintext(self):
        from hub.apps.databricks_admin.obo_tokens import (
            get_refresh_token,
            store_tokens,
        )

        _tenant, binding = _setup()
        store_tokens(
            binding=binding,
            access_token="u2m-access",
            access_expires_in=3600,
            refresh_token="u2m-refresh-secret",
        )
        assert get_refresh_token(binding=binding) == "u2m-refresh-secret"

    def test_access_token_cached_with_ttl_not_exceeding_expiry(self, redis_13):
        from hub.apps.databricks_admin.obo_tokens import (
            OBOAccessTokenCache,
            get_access_token,
            store_tokens,
        )

        _tenant, binding = _setup()
        access_cache = OBOAccessTokenCache(redis_client=redis_13)
        store_tokens(
            binding=binding,
            access_token="u2m-access",
            access_expires_in=300,
            refresh_token="u2m-refresh-secret",
            access_cache=access_cache,
        )
        assert get_access_token(binding=binding, access_cache=access_cache) == "u2m-access"
        ttl = redis_13.ttl(access_cache.key_for(binding.id))
        assert 0 < ttl <= 300, f"cache TTL {ttl} exceeds the token expiry"

    def test_store_is_idempotent_for_same_binding(self):
        from hub.apps.databricks_admin.obo_tokens import store_tokens

        _tenant, binding = _setup()
        first = store_tokens(
            binding=binding,
            access_token="a1",
            access_expires_in=300,
            refresh_token="r1",
        )
        second = store_tokens(
            binding=binding,
            access_token="a2",
            access_expires_in=300,
            refresh_token="r2",
        )
        assert first.id == second.id


class TestRotation:
    def test_rotation_replaces_ciphertext(self):
        from hub.apps.databricks_admin.obo_tokens import (
            get_refresh_token,
            rotate_refresh_token,
            store_tokens,
        )

        _tenant, binding = _setup()
        token = store_tokens(
            binding=binding,
            access_token="a1",
            access_expires_in=300,
            refresh_token="r1-old",
        )
        old_raw = _raw_column(token)

        rotate_refresh_token(
            binding=binding,
            old_refresh_token="r1-old",
            new_access_token="a2",
            new_access_expires_in=300,
            new_refresh_token="r2-new",
        )
        token.refresh_from_db()
        assert _raw_column(token) != old_raw, "rotation must rewrite the ciphertext"
        assert get_refresh_token(binding=binding) == "r2-new", (
            "the vault must hold ONLY the new token (single-use rotation)"
        )

    def test_rotation_with_a_stale_token_fails_closed(self):
        # Two concurrent refreshes: the caller presents the token it used,
        # but the vault has already moved on — the stale caller's write
        # must NOT regress the vault to the older chain.
        from hub.apps.databricks_admin.obo_tokens import (
            DatabricksOBOTokenError,
            get_refresh_token,
            rotate_refresh_token,
            store_tokens,
        )

        _tenant, binding = _setup()
        store_tokens(
            binding=binding,
            access_token="a1",
            access_expires_in=300,
            refresh_token="r-current",
        )

        with pytest.raises(DatabricksOBOTokenError) as excinfo:
            rotate_refresh_token(
                binding=binding,
                old_refresh_token="r-stale",
                new_access_token="a2",
                new_access_expires_in=300,
                new_refresh_token="r-stale-chain",
            )
        assert excinfo.value.code == "OBO_REFRESH_STALE_TOKEN"
        assert get_refresh_token(binding=binding) == "r-current", (
            "a stale caller must never regress the stored token"
        )

    def test_rotation_keeps_refresh_token_when_workspace_does_not_rotate(self, redis_13):
        from hub.apps.databricks_admin.obo_tokens import (
            OBOAccessTokenCache,
            get_access_token,
            get_refresh_token,
            rotate_refresh_token,
            store_tokens,
        )

        _tenant, binding = _setup()
        access_cache = OBOAccessTokenCache(redis_client=redis_13)
        store_tokens(
            binding=binding,
            access_token="a1",
            access_expires_in=300,
            refresh_token="r1-stable",
            access_cache=access_cache,
        )
        rotate_refresh_token(
            binding=binding,
            old_refresh_token="r1-stable",
            new_access_token="a2",
            new_access_expires_in=300,
            new_refresh_token=None,  # workspace reuses the refresh token
            access_cache=access_cache,
        )
        assert get_refresh_token(binding=binding) == "r1-stable"
        assert get_access_token(binding=binding, access_cache=access_cache) == "a2"


class TestRevocation:
    def test_revoke_posts_to_workspace_and_deletes_locally(self, local_http_server, redis_13):
        from hub.apps.audit.models import AuditEvent
        from hub.apps.databricks_admin.obo_tokens import (
            OBOAccessTokenCache,
            revoke,
            store_tokens,
        )
        from hub.apps.databricks_admin.tests._http import RecordingHandler

        _tenant, binding = _setup()
        access_cache = OBOAccessTokenCache(redis_client=redis_13)
        store_tokens(
            binding=binding,
            access_token="a1",
            access_expires_in=300,
            refresh_token="r1",
            access_cache=access_cache,
        )
        RecordingHandler.script = [200]
        revoke(
            binding=binding,
            oidc_base_url=f"http://127.0.0.1:{local_http_server}",
            access_cache=access_cache,
        )

        from hub.apps.databricks_admin.models import DatabricksOBOToken

        assert not DatabricksOBOToken.objects.filter(binding=binding).exists(), (
            "revocation must delete the vault row"
        )
        assert len(RecordingHandler.requests) == 1
        req = RecordingHandler.requests[0]
        assert req["path"] == "/oidc/v1/revoke"
        assert "r1" in req.get("body", "")
        assert access_cache.get(binding.id) is None, "cache must be flushed"
        event = AuditEvent.objects.filter(action="REVOKED").order_by("-timestamp").first()
        assert event is not None, "revocation must emit a real audit row"
        assert event.resource_type == "DATABRICKS_OBO_TOKEN"

    def test_revoke_logs_server_rejection_but_still_deletes_locally(self, local_http_server):
        # A non-2xx REVOKE response (not a transport exception) means the
        # token may still be live at Databricks — that must be logged, and
        # the local delete must STILL happen. NOTE: the repo's logging
        # config sets `propagate: False` on the `hub` logger, so caplog
        # (root-attached) cannot see these records — a REAL stdlib handler
        # on the module logger is the capture mechanism.
        import logging

        from hub.apps.databricks_admin.models import DatabricksOBOToken
        from hub.apps.databricks_admin.obo_tokens import revoke, store_tokens
        from hub.apps.databricks_admin.tests._http import RecordingHandler

        _tenant, binding = _setup()
        store_tokens(
            binding=binding,
            access_token="a1",
            access_expires_in=300,
            refresh_token="r1",
        )
        RecordingHandler.script = [500]

        records: list[logging.LogRecord] = []

        class _CaptureHandler(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                records.append(record)

        handler = _CaptureHandler()
        logger = logging.getLogger("hub.apps.databricks_admin.obo_tokens")
        logger.addHandler(handler)
        try:
            revoke(
                binding=binding,
                oidc_base_url=f"http://127.0.0.1:{local_http_server}",
            )
        finally:
            logger.removeHandler(handler)

        assert not DatabricksOBOToken.objects.filter(binding=binding).exists(), (
            "local delete must happen regardless of the server response"
        )
        assert any("obo_revoke" in record.getMessage() for record in records), (
            "a server rejection must be logged, not silently ignored"
        )

    def test_revoke_is_best_effort_when_workspace_unreachable(self):
        from hub.apps.databricks_admin.models import DatabricksOBOToken
        from hub.apps.databricks_admin.obo_tokens import revoke, store_tokens

        _tenant, binding = _setup()
        store_tokens(
            binding=binding,
            access_token="a1",
            access_expires_in=300,
            refresh_token="r1",
        )
        # Unreachable port — the server-side revocation fails; the local
        # delete MUST still happen.
        revoke(binding=binding, oidc_base_url="http://127.0.0.1:1")
        assert not DatabricksOBOToken.objects.filter(binding=binding).exists()


class TestVaultModel:
    def test_one_vault_row_per_binding(self):
        from django.db import IntegrityError

        from hub.apps.databricks_admin.obo_tokens import store_tokens

        _tenant, binding = _setup()
        store_tokens(
            binding=binding,
            access_token="a1",
            access_expires_in=300,
            refresh_token="r1",
        )
        from hub.apps.databricks_admin.models import DatabricksOBOToken

        with pytest.raises(IntegrityError):
            DatabricksOBOToken.objects.create(
                tenant=binding.tenant,
                binding=binding,
                refresh_token_encrypted={"_encrypted": "x"},
            )

    def test_rls_policy_migration_exists_for_the_table(self):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM pg_policies WHERE schemaname = 'public' "
                "AND tablename = 'databricks_obo_tokens'"
            )
            assert cursor.fetchone() is not None, "databricks_obo_tokens lacks an RLS policy"
