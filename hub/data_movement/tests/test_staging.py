"""TDD pins for the managed-volume staging default (openspec
wire-databricks-dlt-movement task 6.4) — the staging resolution + the
once-per-tenant volume ensure + the S3 external-location opt-in gate.

No mocks: REAL Postgres tenant rows (the staging fields + the flag),
REAL Redis (the once-per-tenant sentinel on the shared cache pool, db 13
per the runbook), and the REAL P2 `UCChangeExecutor` over the
PRODUCTION `DatabricksApiClient` against a REAL threaded local HTTP
server (the pinned uc.volumes.create wire asserted). The sanctioned
seams are the injected client/cache (the caller-owned-client contract)
and the settings TTL override — never the unit under test.
"""

import http.server
import json
import threading
import uuid

import pytest
from django.test import override_settings

from hub.apps.databricks_admin.tests._http import RecordingHandler
from tests.factories import TenantFactory

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def staging_tenant():
    return TenantFactory.create_tenant()


@pytest.fixture(autouse=True)
def redis_13(test_redis_endpoint):
    """The shared test cache on db 13 (the runbook convention; flushed
    per fixture — autouse so every test starts with a clean sentinel
    namespace).  The endpoint follows the environment: the compose
    stack's ``redis-cache-test`` in-container, the host-side
    ``p313-redis`` mapping on host runs — see ``test_redis_endpoint``."""
    import redis

    host, port = test_redis_endpoint
    client = redis.Redis(host=host, port=port, db=13)
    client.flushdb()
    yield client
    client.flushdb()


@pytest.fixture
def local_http_server():
    RecordingHandler.script = []
    RecordingHandler.requests = []
    RecordingHandler.json_script = []
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), RecordingHandler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield port
    server.shutdown()
    server.server_close()


def _api_client(port, tenant_id):
    from hub.apps.databricks_admin.client import DatabricksApiClient

    return DatabricksApiClient(
        base_url=f"http://127.0.0.1:{port}",
        tenant_id=str(tenant_id),
        credential_config={"token": "dapi-staging"},
        timeout_ms=5000,
        max_retries=1,
        retry_base_delay=0.05,
        retry_max_delay=0.1,
        use_breaker=False,
    )


class TestStagingVolumeNameResolution:
    def test_blank_volume_name_resolves_to_the_auto_default(self, staging_tenant):
        from hub.data_movement.staging import staging_volume_name_for

        assert staging_volume_name_for(staging_tenant) == "_dlt_staging_load_volume"

    def test_a_whitespace_override_is_the_default(self, staging_tenant):
        from hub.data_movement.staging import staging_volume_name_for

        staging_tenant.databricks_staging_volume_name = "   "
        assert staging_volume_name_for(staging_tenant) == "_dlt_staging_load_volume"

    def test_a_tenant_override_is_respected(self, staging_tenant):
        from hub.data_movement.staging import staging_volume_name_for

        staging_tenant.databricks_staging_volume_name = "staging_vol"
        assert staging_volume_name_for(staging_tenant) == "staging_vol"

    def test_an_invalid_volume_name_is_refused(self, staging_tenant):
        from hub.data_movement.staging import DatabricksStagingRefused, staging_volume_name_for

        staging_tenant.databricks_staging_volume_name = "bad name!"
        with pytest.raises(DatabricksStagingRefused):
            staging_volume_name_for(staging_tenant)


class TestS3ExternalLocationGate:
    def test_a_requested_external_location_with_the_flag_off_is_refused(self, staging_tenant):
        from hub.data_movement.staging import DatabricksStagingRefused, resolve_staging

        with pytest.raises(DatabricksStagingRefused):
            resolve_staging(staging_tenant, requested_location="s3://bucket/staging/path")

    def test_with_the_flag_on_the_location_is_honored(self, staging_tenant):
        from hub.data_movement.staging import resolve_staging

        staging_tenant.databricks_s3_external_location_enabled = True
        spec = resolve_staging(staging_tenant, requested_location="s3://bucket/staging/path")
        assert spec.kind == "EXTERNAL_LOCATION"
        assert spec.location == "s3://bucket/staging/path"
        assert spec.volume_name is None

    def test_a_non_s3_location_is_refused_even_with_the_flag_on(self, staging_tenant):
        from hub.data_movement.staging import DatabricksStagingRefused, resolve_staging

        staging_tenant.databricks_s3_external_location_enabled = True
        with pytest.raises(DatabricksStagingRefused):
            resolve_staging(staging_tenant, requested_location="gs://bucket/staging/path")

    def test_no_request_yields_the_managed_volume_spec(self, staging_tenant):
        from hub.data_movement.staging import resolve_staging

        spec = resolve_staging(staging_tenant)
        assert spec.kind == "MANAGED_VOLUME"
        assert spec.volume_name == "_dlt_staging_load_volume"
        assert spec.location is None


class TestEnsureStagingVolume:
    def _ensure(self, tenant, port, **kwargs):
        from hub.data_movement.staging import ensure_staging_volume

        return ensure_staging_volume(
            tenant=tenant,
            catalog="meshant",
            schema="staging",
            client=_api_client(port, tenant.id),
            **kwargs,
        )

    def test_the_first_call_creates_the_volume_through_the_p2_executor(
        self, staging_tenant, local_http_server
    ):
        RecordingHandler.json_script = [json.dumps({})] * 4

        name = self._ensure(staging_tenant, local_http_server)

        assert name == "_dlt_staging_load_volume"
        posts = [
            r
            for r in RecordingHandler.requests
            if r["method"] == "POST" and "/volumes" in r["path"]
        ]
        assert len(posts) == 1, "exactly ONE create for the first call"
        body = json.loads(posts[0]["body"])
        assert body["name"] == "_dlt_staging_load_volume"
        assert body["catalog_name"] == "meshant"
        assert body["schema_name"] == "staging"
        assert body["volume_type"] == "MANAGED"

    def test_the_second_call_skips_the_create_via_the_sentinel(
        self, staging_tenant, local_http_server
    ):
        RecordingHandler.json_script = [json.dumps({})] * 6
        self._ensure(staging_tenant, local_http_server)
        creates = [
            r
            for r in RecordingHandler.requests
            if r["method"] == "POST" and "/volumes" in r["path"]
        ]
        assert len(creates) == 1

        self._ensure(staging_tenant, local_http_server)
        creates = [
            r
            for r in RecordingHandler.requests
            if r["method"] == "POST" and "/volumes" in r["path"]
        ]
        assert len(creates) == 1, "the sentinel skips the create — never per run"

    def test_a_sentinel_expiry_re_runs_the_create(self, staging_tenant, local_http_server):
        RecordingHandler.json_script = [json.dumps({})] * 8
        with override_settings(DLT_STAGING_VOLUME_CACHE_TTL_SECONDS=0):
            self._ensure(staging_tenant, local_http_server)
            self._ensure(staging_tenant, local_http_server)
        creates = [
            r
            for r in RecordingHandler.requests
            if r["method"] == "POST" and "/volumes" in r["path"]
        ]
        assert len(creates) == 2, "an expired sentinel re-runs the create"

    def test_a_create_failure_never_poisons_the_sentinel(self, staging_tenant, local_http_server):
        from hub.apps.databricks_admin.client import DatabricksApiError

        RecordingHandler.json_script = [json.dumps({})] * 3
        RecordingHandler.script = [500] * 6
        with pytest.raises(DatabricksApiError):
            self._ensure(staging_tenant, local_http_server)

        # The failed create set NO sentinel — a healthy retry creates.
        RecordingHandler.script = []
        RecordingHandler.json_script = [json.dumps({})] * 6
        self._ensure(staging_tenant, local_http_server)
        creates = [
            r
            for r in RecordingHandler.requests
            if r["method"] == "POST" and "/volumes" in r["path"]
        ]
        assert len(creates) == 1

    def test_the_sentinel_is_tenant_scoped(self, local_http_server):
        tenant_a = TenantFactory.create_tenant()
        tenant_b = TenantFactory.create_tenant()
        RecordingHandler.json_script = [json.dumps({})] * 8

        self._ensure(tenant_a, local_http_server)
        self._ensure(tenant_b, local_http_server)

        creates = [
            r
            for r in RecordingHandler.requests
            if r["method"] == "POST" and "/volumes" in r["path"]
        ]
        assert len(creates) == 2, "tenant A's sentinel never suppresses tenant B's create"


class TestStagingFlagRegistration:
    def test_the_s3_opt_in_flag_ships_in_the_registry_default_off(self):
        from hub.apps.tenants.feature_flag_registry import REGISTRY

        flag = next(f for f in REGISTRY if f.name == "databricks_s3_external_location_enabled")
        assert flag.stage == "DRAFT"
        assert flag.default_new_tenants is False
        assert flag.default_existing_tenants is False

    def test_the_flag_persists_and_flips_through_the_feature_flags_endpoint(self, staging_tenant):
        from rest_framework.test import APIClient

        from hub.apps.audit.models import AuditEvent
        from hub.apps.databricks_admin.tests.test_views import _activate_billing, _make_user

        _activate_billing(staging_tenant)
        admin = _make_user(
            staging_tenant, f"staging-{uuid.uuid4().hex[:8]}@test.com", "TENANT_ADMIN"
        )
        client = APIClient()
        client.force_authenticate(user=admin)

        resp = client.patch(
            "/api/v1/tenants/me/feature-flags/",
            {"databricks_s3_external_location_enabled": True},
            format="json",
        )
        assert resp.status_code == 200, resp.content
        staging_tenant.refresh_from_db()
        assert staging_tenant.databricks_s3_external_location_enabled is True
        event = (
            AuditEvent.objects.filter(action="TENANT_FEATURE_FLAG_UPDATED")
            .order_by("-timestamp")
            .first()
        )
        assert event is not None, "a flag flip must emit a real audit row"
        assert (event.details_json or {}).get(
            "flag_name"
        ) == "databricks_s3_external_location_enabled"


class TestStagingSettings:
    def test_the_sentinel_ttl_ships_with_the_documented_default(self):
        from django.conf import settings

        assert settings.DLT_STAGING_VOLUME_CACHE_TTL_SECONDS == 86400
