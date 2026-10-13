"""Phase 5 (openspec add-delta-sharing-server task 5.3) — the native
Delta Sharing 1.0 protocol endpoints: profile, shares, schemas, tables,
metadata, query (JSON mode), data (Parquet snapshot / presigned-URL).

Wire shapes are pinned against the dev-only protocol oracle (the
``delta_sharing`` package's client parsers — shares/schemas/tables list
envelopes with ``items``, the ndjson line protocol with the
``delta-table-version`` header, the v1 profile fields, the ``file``
action shape). The ONE sanctioned patch point is the warehouse-connector
FACTORY symbol in the service module (the 4.4 outbound-boundary
convention): the query pins patch it with a RECORDING connector (a real
``WarehouseConnector`` subclass that captures the SQL and returns real
``QueryResult`` rows) — the warehouse SDKs' transports are the one
boundary no repo component can script against a local server, exactly
the class of seam the 4.4 lineage/webhook recorders cover. Everything
else is REAL: DRF views over real HTTP, real bearer-token auth (hash
lookup), the real throttle over the real cache, real RLS, real audit
rows, real Postgres snapshot rows, and REAL presigned URLs from the
production ``S3StorageClient``.
"""

import json
import uuid
from datetime import timedelta
from typing import ClassVar

import pytest
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from hub.apps.databricks_admin.tests._fixtures import require_dns
from hub.apps.databricks_admin.tests.test_uc_browse import _setup_tenant
from hub.apps.warehouses.base import WarehouseConnector

pytestmark = pytest.mark.django_db(transaction=True)

PROTOCOL_BASE = "/api/v1/databricks/delta-sharing"


def _mk_recipient(tenant, admin=None):
    from hub.apps.databricks_admin.models import DeltaShareRecipient

    return DeltaShareRecipient.objects.create(
        tenant=tenant,
        name=f"recipient-{uuid.uuid4().hex[:8]}",
        created_by=admin,
    )


def _mk_token(recipient, *, share="meshant", schema=None, table=None):
    from hub.apps.databricks_admin.models import DeltaShareToken

    return DeltaShareToken.issue(
        recipient=recipient,
        share_name=share,
        schema_name=schema,
        table_name=table,
    )


def _mk_connection(tenant, **overrides):
    from hub.apps.warehouses.models import WarehouseConnection, WarehouseType

    kwargs = {
        "tenant": tenant,
        "name": f"conn-{uuid.uuid4().hex[:8]}",
        "warehouse_type": WarehouseType.DATABRICKS,
        "config": {
            "host": "adb-123.azuredatabricks.net",
            "http_path": "/sql/1.0/warehouses/wh-1",
            "pat_token": "dapi-own-token",
        },
    }
    kwargs.update(overrides)
    return WarehouseConnection.objects.create(**kwargs)


def _mk_asset(tenant, connection=None, *, table_ref=None, optout=False, **overrides):
    from hub.apps.assets.models import Asset, DataStrategy

    kwargs = {
        "tenant": tenant,
        "key": f"asset-{uuid.uuid4().hex[:8]}",
        "name": f"asset-{uuid.uuid4().hex[:8]}",
        "data_strategy": DataStrategy.LIVE_QUERY,
        "warehouse_connection": connection,
        "semantic_federate_optout": optout,
        "metadata_json": {
            "external_table_ref": table_ref or f"catalog.schema.t-{uuid.uuid4().hex[:6]}"
        },
    }
    kwargs.update(overrides)
    return Asset.objects.create(**kwargs)


def _auth(client, plaintext):
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {plaintext}")


class TestDeltaShareTokenAuthentication(TestCase):
    """The bearer-token auth class: resolve, expiry, stamping, 401s."""

    def setUp(self):
        require_dns()
        self.tenant, self.admin = _setup_tenant()
        self.recipient = _mk_recipient(self.tenant, self.admin)
        self.token, self.plaintext = _mk_token(self.recipient)

    def _request(self, plaintext):
        from rest_framework.test import APIRequestFactory

        return APIRequestFactory().get(
            f"{PROTOCOL_BASE}/shares",
            HTTP_AUTHORIZATION=f"Bearer {plaintext}",
        )

    def test_a_valid_token_authenticates_and_stamps_last_used(self):
        from django.contrib.auth.models import AnonymousUser

        from hub.apps.databricks_admin.delta_sharing_auth import (
            DeltaShareTokenAuthentication,
        )

        request = self._request(self.plaintext)
        result = DeltaShareTokenAuthentication().authenticate(request)
        assert result is not None
        user, token = result
        assert isinstance(user, AnonymousUser), "request.user must stay user-shaped"
        assert token.id == self.token.id, "the token rides request.auth"
        self.token.refresh_from_db()
        assert self.token.last_used_at is not None, "auth must stamp last_used_at"

    def test_an_unknown_token_returns_none(self):
        from hub.apps.databricks_admin.delta_sharing_auth import (
            DeltaShareTokenAuthentication,
        )

        request = self._request(f"bogus-{uuid.uuid4().hex}")
        assert DeltaShareTokenAuthentication().authenticate(request) is None

    def test_a_missing_header_returns_none(self):
        from rest_framework.test import APIRequestFactory

        from hub.apps.databricks_admin.delta_sharing_auth import (
            DeltaShareTokenAuthentication,
        )

        request = APIRequestFactory().get(f"{PROTOCOL_BASE}/shares")
        assert DeltaShareTokenAuthentication().authenticate(request) is None

    def test_an_expired_token_returns_none_and_never_stamps(self):
        from hub.apps.databricks_admin.delta_sharing_auth import (
            DeltaShareTokenAuthentication,
        )
        from hub.apps.databricks_admin.models import DeltaShareToken

        expired, expired_plaintext = DeltaShareToken.issue(
            recipient=self.recipient,
            share_name="meshant",
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        assert (
            DeltaShareTokenAuthentication().authenticate(self._request(expired_plaintext)) is None
        )
        expired.refresh_from_db()
        assert expired.last_used_at is None

    def test_the_protocol_responds_401_without_a_token(self):
        from hub.apps.audit.models import AuditEvent

        before = set(AuditEvent.objects.values_list("id", flat=True))
        client = APIClient()
        resp = client.get(f"{PROTOCOL_BASE}/shares")
        assert resp.status_code == 401
        assert resp.headers.get("WWW-Authenticate", "").lower().startswith("bearer")
        # The 401 emits WAREHOUSE_SHARE_AUTH_FAILED (best-effort, the
        # unresolvable token has no tenant — the row carries no tenant).
        # The before-set delta scopes the pin to THIS request (the 4.4
        # row-set convention — immune to the shared DB's leaked rows).
        failed = AuditEvent.objects.filter(action="WAREHOUSE_SHARE_AUTH_FAILED").exclude(
            id__in=before
        )
        assert failed.count() == 1
        assert failed.first().tenant_id is None


class TestDeltaShareCatalog(TestCase):
    """The (share, schema, table) catalog mapping — deterministic and
    opt-out-aware."""

    def setUp(self):
        require_dns()
        self.tenant, self.admin = _setup_tenant()
        self.connection = _mk_connection(self.tenant)
        self.asset = _mk_asset(self.tenant, self.connection, table_ref="catalog.schema.orders")

    def test_share_name_is_the_tenant_share_and_schema_is_the_asset_hex(self):
        from hub.apps.databricks_admin.delta_sharing_service import (
            schema_name_for,
            share_name_for,
        )

        assert share_name_for(self.tenant) == "meshant"
        assert schema_name_for(self.asset) == self.asset.id.hex

    def test_table_name_comes_from_the_external_table_ref(self):
        from hub.apps.databricks_admin.delta_sharing_service import table_name_for

        assert table_name_for(self.asset) == "catalog.schema.orders"

    def test_shareable_assets_include_only_live_query_connected_opted_in(self):
        from hub.apps.databricks_admin.delta_sharing_service import shareable_assets

        _mk_asset(self.tenant, self.connection, optout=True)
        _mk_asset(self.tenant, None)  # no warehouse connection
        ids = {a.id for a in shareable_assets(self.tenant.id)}
        assert self.asset.id in ids
        assert len(ids) == 1, "opt-out and connection-less assets must never surface"

    def test_resolve_share_table_finds_the_asset(self):
        from hub.apps.databricks_admin.delta_sharing_service import resolve_share_table

        found = resolve_share_table(
            self.tenant.id,
            share="meshant",
            schema=self.asset.id.hex,
            table="catalog.schema.orders",
        )
        assert found is not None
        assert found.id == self.asset.id

    def test_resolve_share_table_misses_wrong_scope_parts(self):
        from hub.apps.databricks_admin.delta_sharing_service import resolve_share_table

        assert (
            resolve_share_table(
                self.tenant.id,
                share="other-share",
                schema=self.asset.id.hex,
                table="catalog.schema.orders",
            )
            is None
        )
        assert (
            resolve_share_table(
                self.tenant.id, share="meshant", schema="0" * 32, table="catalog.schema.orders"
            )
            is None
        )
        assert (
            resolve_share_table(
                self.tenant.id, share="meshant", schema=self.asset.id.hex, table="other.table"
            )
            is None
        )


class TestDeltaShareSnapshotModel(TestCase):
    """The snapshot row the data endpoints serve (5.4's job populates)."""

    def setUp(self):
        require_dns()
        self.tenant, self.admin = _setup_tenant()

    def _mk(self, **overrides):
        from hub.apps.databricks_admin.models import DeltaShareSnapshot

        kwargs = {
            "tenant": self.tenant,
            "share_name": "meshant",
            "schema_name": "0" * 32,
            "table_name": f"t-{uuid.uuid4().hex[:6]}",
            "version": 3,
            "files": [
                {
                    "id": "part-00000",
                    "path": "delta-sharing/part-00000-3.parquet",
                    "size": 1024,
                    "partition_values": {},
                }
            ],
            "expires_at": timezone.now() + timedelta(hours=1),
        }
        kwargs.update(overrides)
        return DeltaShareSnapshot.objects.create(**kwargs)

    def test_latest_snapshot_serves_the_highest_version_not_expired(self):
        from hub.apps.databricks_admin.delta_sharing_service import latest_snapshot

        self._mk(version=2, expires_at=timezone.now() - timedelta(minutes=1))
        current = self._mk(version=3)
        latest = latest_snapshot(
            self.tenant.id, share="meshant", schema="0" * 32, table=current.table_name
        )
        assert latest is not None
        assert latest.version == 3

    def test_an_expired_snapshot_is_never_served(self):
        from hub.apps.databricks_admin.delta_sharing_service import latest_snapshot

        expired = self._mk(version=1, expires_at=timezone.now() - timedelta(minutes=1))
        assert (
            latest_snapshot(
                self.tenant.id, share="meshant", schema="0" * 32, table=expired.table_name
            )
            is None
        )

    def test_a_snapshot_without_a_ttl_fails_closed(self):
        from hub.apps.databricks_admin.delta_sharing_service import latest_snapshot

        ttl_less = self._mk(version=1, expires_at=None)
        assert (
            latest_snapshot(
                self.tenant.id, share="meshant", schema="0" * 32, table=ttl_less.table_name
            )
            is None
        ), "a snapshot without a TTL stamp must never be served (fail-closed)"

    def test_negative_version_is_refused(self):
        from django.core.exceptions import ValidationError

        from hub.apps.databricks_admin.models import DeltaShareSnapshot

        snapshot = DeltaShareSnapshot(
            tenant=self.tenant,
            share_name="meshant",
            schema_name="0" * 32,
            table_name="t",
            version=-1,
            files=[],
        )
        with pytest.raises(ValidationError):
            snapshot.full_clean()

    def test_blank_share_or_schema_is_refused(self):
        from django.core.exceptions import ValidationError

        from hub.apps.databricks_admin.models import DeltaShareSnapshot

        snapshot = DeltaShareSnapshot(
            tenant=self.tenant, share_name="  ", schema_name="0" * 32, table_name="t", version=1
        )
        with pytest.raises(ValidationError):
            snapshot.full_clean()


class _RecordingConnector(WarehouseConnector):
    """The sanctioned test double for the outbound warehouse boundary —
    a real ``WarehouseConnector`` subclass that records the executed SQL
    and returns real ``QueryResult`` rows (the 4.4 recorder convention)."""

    warehouse_type = "recording"
    calls: ClassVar[list[dict]] = []
    result = None

    def __init__(self, connection_config=None, timeout_ms=30000, **kwargs):
        self._connected = False

    def connect(self):
        self._connected = True

    def close(self):
        self._connected = False

    def reflect_schema(self, _table_name):
        return []

    def execute_query(self, sql, params=None, limit=100):
        from hub.apps.warehouses.base import QueryResult

        type(self).calls.append({"sql": sql, "params": params, "limit": limit})
        if self.result is not None:
            return self.result
        return QueryResult(columns=["id", "name"], rows=[[1, "alpha"], [2, "beta"]], row_count=2)


class TestDeltaShareProtocolEndpoints(TestCase):
    """The real protocol surface over real HTTP: envelopes, scope
    filtering, opt-out, throttle mount, audit rows."""

    def setUp(self):
        require_dns()
        self.tenant, self.admin = _setup_tenant()
        self.connection = _mk_connection(self.tenant)
        self.asset = _mk_asset(self.tenant, self.connection, table_ref="catalog.schema.orders")
        self.recipient = _mk_recipient(self.tenant, self.admin)
        self.token, self.plaintext = _mk_token(self.recipient)
        self.client = APIClient()
        _auth(self.client, self.plaintext)

    def test_profile_returns_the_v1_client_profile(self):
        resp = self.client.get(f"{PROTOCOL_BASE}/profile")
        assert resp.status_code == 200
        body = resp.json()
        assert body["shareCredentialsVersion"] == 1
        assert body["endpoint"].endswith(PROTOCOL_BASE)
        assert body["bearerToken"] == self.plaintext

    def test_shares_listing_follows_the_oracle_envelope(self):
        resp = self.client.get(f"{PROTOCOL_BASE}/shares")
        assert resp.status_code == 200
        assert resp.json() == {"items": [{"name": "meshant"}]}

    def test_share_detail(self):
        resp = self.client.get(f"{PROTOCOL_BASE}/shares/meshant")
        assert resp.status_code == 200
        assert resp.json() == {"share": {"name": "meshant"}}

    def test_unknown_share_is_404(self):
        resp = self.client.get(f"{PROTOCOL_BASE}/shares/other")
        assert resp.status_code == 404

    def test_schemas_listing(self):
        resp = self.client.get(f"{PROTOCOL_BASE}/shares/meshant/schemas")
        assert resp.status_code == 200
        assert resp.json() == {"items": [{"name": self.asset.id.hex, "share": "meshant"}]}

    def test_tables_listing(self):
        resp = self.client.get(f"{PROTOCOL_BASE}/shares/meshant/schemas/{self.asset.id.hex}/tables")
        assert resp.status_code == 200
        assert resp.json() == {
            "items": [
                {
                    "name": "catalog.schema.orders",
                    "share": "meshant",
                    "schema": self.asset.id.hex,
                }
            ]
        }

    def test_table_detail(self):
        resp = self.client.get(
            f"{PROTOCOL_BASE}/shares/meshant/schemas/{self.asset.id.hex}/tables/catalog.schema.orders"
        )
        assert resp.status_code == 200
        assert resp.json() == {
            "table": {
                "name": "catalog.schema.orders",
                "share": "meshant",
                "schema": self.asset.id.hex,
            }
        }

    def test_metadata_endpoint_returns_the_ndjson_envelope_with_header(self):
        resp = self.client.get(
            f"{PROTOCOL_BASE}/shares/meshant/schemas/{self.asset.id.hex}"
            "/tables/catalog.schema.orders/metadata"
        )
        assert resp.status_code == 200
        assert resp.headers["delta-table-version"] == "0"
        lines = [json.loads(line) for line in resp.content.decode().splitlines()]
        assert lines[0] == {"protocol": {"minReaderVersion": 1}}
        assert lines[1]["metaData"]["name"] == "catalog.schema.orders"
        assert lines[1]["metaData"]["format"] == {"provider": "parquet"}

    def test_an_opted_out_asset_never_surfaces(self):
        _mk_asset(self.tenant, self.connection, optout=True)
        resp = self.client.get(f"{PROTOCOL_BASE}/shares/meshant/schemas")
        assert resp.status_code == 200
        assert resp.json() == {"items": [{"name": self.asset.id.hex, "share": "meshant"}]}
        opted_out = _mk_asset(self.tenant, self.connection, optout=True)
        direct = self.client.get(
            f"{PROTOCOL_BASE}/shares/meshant/schemas/{opted_out.id.hex}/tables"
        )
        assert direct.status_code == 404

    def test_the_token_scope_filters_everything_outside_it(self):
        _scoped, scoped_plaintext = _mk_token(
            self.recipient, schema=self.asset.id.hex, table="catalog.schema.orders"
        )
        client = APIClient()
        _auth(client, scoped_plaintext)
        other = _mk_asset(self.tenant, self.connection, table_ref="catalog.schema.events")
        resp = client.get(f"{PROTOCOL_BASE}/shares/meshant/schemas/{other.id.hex}/tables")
        assert resp.status_code == 404
        resp = client.get(f"{PROTOCOL_BASE}/shares/meshant/schemas")
        assert resp.json() == {"items": [{"name": self.asset.id.hex, "share": "meshant"}]}

    def test_every_access_emits_warehouse_share_accessed_with_ip_and_ua(self):
        from hub.apps.audit.models import AuditEvent

        before = set(AuditEvent.objects.values_list("id", flat=True))
        self.client.get(
            f"{PROTOCOL_BASE}/shares/meshant/schemas/{self.asset.id.hex}/tables",
            HTTP_USER_AGENT="delta-sharing-test/1.0",
        )
        rows = AuditEvent.objects.filter(action="WAREHOUSE_SHARE_ACCESSED").exclude(id__in=before)
        assert rows.count() == 1
        assert "delta-sharing-test/1.0" in str(rows.first().details_json.get("user_agent"))

    def test_the_protocol_views_mount_the_per_token_throttle(self):
        from hub.apps.databricks_admin.delta_sharing_views import (
            DeltaSharingProtocolViewSet,
        )
        from hub.apps.databricks_admin.throttles import DeltaShareTokenRateThrottle

        assert DeltaShareTokenRateThrottle in DeltaSharingProtocolViewSet.throttle_classes


class TestDeltaShareQueryJsonMode(TestCase):
    """query (JSON mode): the SELECT rides the production connector
    factory; the envelope is the ndjson protocol with a query line."""

    def setUp(self):
        require_dns()
        self.tenant, self.admin = _setup_tenant()
        self.connection = _mk_connection(self.tenant)
        self.asset = _mk_asset(self.tenant, self.connection, table_ref="catalog.schema.orders")
        self.recipient = _mk_recipient(self.tenant, self.admin)
        self.token, self.plaintext = _mk_token(self.recipient)
        self.client = APIClient()
        _auth(self.client, self.plaintext)
        _RecordingConnector.calls = []

    def _factory(self, result=None):
        _RecordingConnector.result = result

        def factory(warehouse_type):
            assert warehouse_type == self.connection.warehouse_type
            return _RecordingConnector

        return factory

    def test_query_returns_rows_in_the_ndjson_envelope(self):
        from unittest import mock

        with mock.patch(
            "hub.apps.databricks_admin.delta_sharing_service.get_connector_for_connection",
            self._factory(),
        ):
            resp = self.client.post(
                f"{PROTOCOL_BASE}/shares/meshant/schemas/{self.asset.id.hex}"
                "/tables/catalog.schema.orders/query",
                data=json.dumps({"limitHint": 50}),
                content_type="application/json",
            )
            assert resp.status_code == 200
            assert resp.headers["delta-table-version"] == "0"
            lines = [json.loads(line) for line in resp.content.decode().splitlines()]
            assert lines[0] == {"protocol": {"minReaderVersion": 1}}
            assert lines[1]["metaData"]["name"] == "catalog.schema.orders"
            assert lines[2]["query"]["count"] == 2
            assert lines[2]["query"]["rows"] == [[1, "alpha"], [2, "beta"]]

    def test_the_select_is_bound_to_the_exact_table_and_limit(self):
        from unittest import mock

        with mock.patch(
            "hub.apps.databricks_admin.delta_sharing_service.get_connector_for_connection",
            self._factory(),
        ):
            self.client.post(
                f"{PROTOCOL_BASE}/shares/meshant/schemas/{self.asset.id.hex}"
                "/tables/catalog.schema.orders/query",
                data=json.dumps({"limitHint": 25}),
                content_type="application/json",
            )
            assert len(_RecordingConnector.calls) == 1
            call = _RecordingConnector.calls[0]
            assert call["sql"] == "SELECT * FROM catalog.schema.orders LIMIT 25"
            assert call["limit"] == 25

    def test_a_connectionless_asset_fails_closed(self):
        # A connectionless asset never enters the share catalog — its
        # 404 IS the fail-closed contract (the 400 query-unavailable
        # branch covers a connection deleted after listing).
        asset = _mk_asset(self.tenant, None, table_ref="catalog.schema.orphan")
        resp = self.client.post(
            f"{PROTOCOL_BASE}/shares/meshant/schemas/{asset.id.hex}/tables/catalog.schema.orphan/query",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert resp.status_code == 404

    def test_an_invalid_table_ref_is_refused_before_any_query(self):
        from unittest import mock

        with mock.patch(
            "hub.apps.databricks_admin.delta_sharing_service.get_connector_for_connection",
            self._factory(),
        ):
            evil = _mk_asset(self.tenant, self.connection, table_ref="orders; DROP TABLE x")
            resp = self.client.post(
                f"{PROTOCOL_BASE}/shares/meshant/schemas/{evil.id.hex}/tables/orders%3B%20DROP%20TABLE%20x/query",
                data=json.dumps({}),
                content_type="application/json",
            )
            assert resp.status_code == 400
            assert _RecordingConnector.calls == [], (
                "an unsafe table ref must never reach the connector"
            )


class TestDeltaShareVersionEndpoint(TestCase):
    """data (Parquet snapshot mode): the version endpoint serves
    presigned file actions from the snapshot row."""

    def setUp(self):
        require_dns()
        self.tenant, self.admin = _setup_tenant()
        self.connection = _mk_connection(self.tenant)
        self.asset = _mk_asset(self.tenant, self.connection, table_ref="catalog.schema.orders")
        self.recipient = _mk_recipient(self.tenant, self.admin)
        self.token, self.plaintext = _mk_token(self.recipient)
        self.client = APIClient()
        _auth(self.client, self.plaintext)

    def _snapshot(self, **overrides):
        from hub.apps.databricks_admin.models import DeltaShareSnapshot

        kwargs = {
            "tenant": self.tenant,
            "share_name": "meshant",
            "schema_name": self.asset.id.hex,
            "table_name": "catalog.schema.orders",
            "version": 5,
            "files": [
                {
                    "id": "part-00000",
                    "path": "delta-sharing/tenant/orders/part-00000-5.parquet",
                    "size": 4096,
                    "partition_values": {"region": "eu"},
                }
            ],
            "expires_at": timezone.now() + timedelta(hours=1),
        }
        kwargs.update(overrides)
        return DeltaShareSnapshot.objects.create(**kwargs)

    def test_version_endpoint_serves_presigned_file_actions(self):
        self._snapshot()
        resp = self.client.get(
            f"{PROTOCOL_BASE}/shares/meshant/schemas/{self.asset.id.hex}"
            "/tables/catalog.schema.orders/version"
        )
        assert resp.status_code == 200
        assert resp.headers["delta-table-version"] == "5"
        lines = [json.loads(line) for line in resp.content.decode().splitlines()]
        assert lines[0] == {"protocol": {"minReaderVersion": 1}}
        assert lines[1]["metaData"]["name"] == "catalog.schema.orders"
        file_action = lines[2]["file"]
        assert file_action["id"] == "part-00000"
        assert file_action["size"] == 4096
        assert file_action["partitionValues"] == {"region": "eu"}
        # A REAL presigned URL from the production storage client:
        # the signed query carries the expiry, never the credentials.
        assert "X-Amz-Expires" in file_action["url"]
        assert "X-Amz-Signature" in file_action["url"]
        assert "part-00000-5.parquet" in file_action["url"]

    def test_version_without_a_snapshot_is_404(self):
        resp = self.client.get(
            f"{PROTOCOL_BASE}/shares/meshant/schemas/{self.asset.id.hex}"
            "/tables/catalog.schema.orders/version"
        )
        assert resp.status_code == 404

    def test_version_serves_nothing_from_an_expired_snapshot(self):
        self._snapshot(expires_at=timezone.now() - timedelta(minutes=1))
        resp = self.client.get(
            f"{PROTOCOL_BASE}/shares/meshant/schemas/{self.asset.id.hex}"
            "/tables/catalog.schema.orders/version"
        )
        assert resp.status_code == 404


class TestDeltaShareSnapshotRLS(TestCase):
    """The snapshot table's direct-FK policy filters at runtime."""

    def setUp(self):
        require_dns()
        self.tenant, self.admin = _setup_tenant()
        from hub.apps.tenants.models import Tenant

        self.other = Tenant.objects.create(
            name=f"other-{uuid.uuid4().hex[:8]}",
            slug=f"other-{uuid.uuid4().hex[:8]}",
            status="ACTIVE",
        )
        from hub.apps.databricks_admin.models import DeltaShareSnapshot

        DeltaShareSnapshot.objects.create(
            tenant=self.tenant,
            share_name="meshant",
            schema_name="0" * 32,
            table_name=f"t-{uuid.uuid4().hex[:6]}",
            version=1,
            files=[],
            expires_at=timezone.now() + timedelta(hours=1),
        )

    def _probe_role(self):
        from hub.apps.databricks_admin.tests.test_uc_rls_isolation import (
            _connection_bypasses_rls,
            _ensure_rls_probe_role,
        )

        if _connection_bypasses_rls():
            _ensure_rls_probe_role()
            return "hub_rls_probe"
        return None

    def test_foreign_tenants_see_zero_snapshot_rows(self):
        from django.db import connection

        from hub.apps.databricks_admin.tests.test_uc_rls_isolation import _visible_count_as

        probe = self._probe_role()
        assert _visible_count_as(probe, self.tenant.id, "databricks_delta_share_snapshots") == 1
        assert _visible_count_as(probe, self.other.id, "databricks_delta_share_snapshots") == 0

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT policyname FROM pg_policies WHERE tablename = %s",
                ["databricks_delta_share_snapshots"],
            )
            names = {row[0] for row in cursor.fetchall()}
        assert "databricks_delta_share_snapshots_tenant_isolation" in names
