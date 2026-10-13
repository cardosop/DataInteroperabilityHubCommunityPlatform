"""Phase 5 (openspec add-delta-sharing-server task 5.9) — the fixture
share battery: canned Parquet fixtures + the P9 oracle validation.

- CANNED FIXTURES (checked in under ``tests/fixtures/delta_sharing/``):
  a REAL pyarrow-generated parquet object (3 rows), the matching
  Delta-protocol log entry, and the REAL endpoint envelopes captured
  from the shipped views (``oracle_wire/``) — all integrity-pinned (the
  3.10 fixture convention).
- THE ACCEPTANCE round-trip: a fixture share served end-to-end —
  profile → shares → schemas → tables → metadata → version → presigned
  download → pyarrow reads the SAME fixture rows back from REAL MinIO.
- PRESIGNED EXPIRY: the X-Amz-Expires stamp + a REAL replay after
  expiry against the real MinIO (403 AccessDenied).
- SNAPSHOT IDEMPOTENCY driven by the fixture source (the sanctioned
  ``source_reader`` seam).
- P9: the REAL ``delta_sharing`` REST client (the dev-only oracle, 5.6)
  parses the canned envelopes through a REAL local HTTP server; a
  shape-drift guard ties the canned envelopes to the LIVE endpoints.

No mocks: real Postgres rows, real MinIO objects, real presigned
round-trips, the real oracle client's parsers, the real DRF views; the
sanctioned seams are the connector factory (the 5.3 convention) and the
snapshot reader (the 5.4 convention).
"""

import http.server
import json
import threading
import urllib.error
import urllib.request
import uuid
from datetime import timedelta
from io import BytesIO
from pathlib import Path
from typing import ClassVar

import pytest
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from hub.apps.databricks_admin.tests._fixtures import require_dns
from hub.apps.databricks_admin.tests.test_delta_sharing_endpoints import (
    PROTOCOL_BASE,
    _mk_asset,
    _mk_connection,
    _mk_recipient,
    _mk_token,
    _RecordingConnector,
)
from hub.apps.databricks_admin.tests.test_uc_browse import _setup_tenant

pytestmark = pytest.mark.django_db(transaction=True)

FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "delta_sharing"
PARQUET_FIXTURE = FIXTURE_ROOT / "share_parquet" / "part-00000.snappy.parquet"
LOG_FIXTURE = FIXTURE_ROOT / "share_delta_log" / "00000000000000000001.json"
WIRE_ROOT = FIXTURE_ROOT / "oracle_wire"


def _upload_fixture_parquet(storage, *, share, schema, table, version=1):
    """Upload the fixture parquet to the canonical storage key and
    return the files manifest (the 5.3 contract shape)."""
    payload = PARQUET_FIXTURE.read_bytes()
    key = (
        f"delta-share-snapshots/{share}/{schema}/{table}/v{version:020d}/part-00000.snappy.parquet"
    )
    storage.upload_file(key, payload)
    return [{"id": "part-00000", "path": key, "size": len(payload), "partition_values": {}}]


class _FixtureSourceReader:
    """The sanctioned snapshot-reader seam: the canned source — the
    REAL fixture parquet's version + rows (the 5.4 ``source_reader``
    contract, a plain callable)."""

    def __call__(self, _connection, _table_ref, _tenant_id):
        import pyarrow.parquet as pq

        from hub.apps.databricks_admin.delta_sharing_snapshot import _SourceVersion

        table = pq.read_table(PARQUET_FIXTURE)
        columns = table.column_names
        rows = [[record[column] for column in columns] for record in table.to_pylist()]
        return _SourceVersion(version=1, columns=columns, rows=rows)


class OracleWireHandler(http.server.BaseHTTPRequestHandler):
    """A REAL path-routed HTTP server serving the canned endpoint
    envelopes (the RecordingHandler convention, extended with the
    protocol's response header on the /metadata + /version paths)."""

    routes: ClassVar[dict[str, bytes]] = {}
    requests: ClassVar[list[dict]] = []

    def _handle(self):
        type(self).requests.append({"method": self.command, "path": self.path})
        body = b"{}"
        for suffix, payload in type(self).routes.items():
            if self.path.endswith(suffix):
                body = payload
                break
        status = 200 if body != b"{}" or not type(self).routes else 404
        self.send_response(status)
        if self.path.endswith("/metadata") or self.path.endswith("/version"):
            self.send_header("delta-table-version", "1")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._handle()

    def do_POST(self):
        self._handle()

    def log_message(self, *_args):
        pass


@pytest.fixture
def oracle_server():
    """A real local HTTP server serving the oracle-wire fixtures."""
    OracleWireHandler.routes = {}
    OracleWireHandler.requests = []
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), OracleWireHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    try:
        yield port
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


class TestFixtureIntegrity:
    """The canned fixtures are what the battery claims them to be."""

    def test_the_parquet_fixture_carries_the_canned_share_dataset(self):
        import pyarrow.parquet as pq

        table = pq.read_table(PARQUET_FIXTURE)
        assert table.column_names == ["id", "name", "region"]
        assert table.to_pylist() == [
            {"id": 1, "name": "alpha", "region": "eu"},
            {"id": 2, "name": "beta", "region": "us"},
            {"id": 3, "name": "gamma", "region": "eu"},
        ]

    def test_the_delta_log_fixture_matches_the_protocol_shape(self):
        entry = json.loads(LOG_FIXTURE.read_text())
        assert entry["commitInfo"]["operation"] == "WRITE"
        assert len(entry["metaData"]["id"]) == 32
        assert entry["metaData"]["format"]["provider"] == "parquet"
        assert entry["add"]["path"].endswith("part-00000.snappy.parquet")
        assert entry["add"]["size"] == PARQUET_FIXTURE.stat().st_size
        schema = json.loads(entry["metaData"]["schemaString"])
        assert [f["name"] for f in schema["fields"]] == ["id", "name", "region"]

    def test_the_wire_fixtures_parse(self):
        for name in ("shares", "share", "schemas", "tables", "table", "profile"):
            json.loads((WIRE_ROOT / f"{name}.json").read_text())
        for name in ("metadata", "version"):
            lines = [
                json.loads(line) for line in (WIRE_ROOT / f"{name}.ndjson").read_text().splitlines()
            ]
            assert lines[0] == {"protocol": {"minReaderVersion": 1}}
            assert "metaData" in lines[1]


class TestFixtureShareEndToEnd(TestCase):
    """The acceptance: the fixture share served end-to-end over the REAL
    protocol surface, rows read back from REAL MinIO."""

    def setUp(self):
        require_dns()
        self.tenant, self.admin = _setup_tenant()
        self.connection = _mk_connection(self.tenant)
        self.asset = _mk_asset(self.tenant, self.connection, table_ref="catalog.schema.orders")
        self.recipient = _mk_recipient(self.tenant, self.admin)
        self.token, self.plaintext = _mk_token(self.recipient)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.plaintext}")
        _RecordingConnector.calls = []

    def _stamp_fixture_snapshot(self):
        from hub.apps.databricks_admin.models import DeltaShareSnapshot
        from hub.apps.files.storage import S3StorageClient

        storage = S3StorageClient()
        files = _upload_fixture_parquet(
            storage,
            share="meshant",
            schema=self.asset.id.hex,
            table="catalog.schema.orders",
        )
        return DeltaShareSnapshot.objects.create(
            tenant=self.tenant,
            share_name="meshant",
            schema_name=self.asset.id.hex,
            table_name="catalog.schema.orders",
            version=1,
            files=files,
            expires_at=timezone.now() + timedelta(hours=1),
        )

    def test_the_fixture_share_round_trips_profile_to_parquet_rows(self):
        self._stamp_fixture_snapshot()

        # The catalog walk.
        profile = self.client.get(f"{PROTOCOL_BASE}/profile")
        assert profile.status_code == 200
        assert profile.json()["shareCredentialsVersion"] == 1
        assert profile.json()["endpoint"].endswith(PROTOCOL_BASE)

        shares = self.client.get(f"{PROTOCOL_BASE}/shares")
        assert shares.json() == {"items": [{"name": "meshant"}]}
        schemas = self.client.get(f"{PROTOCOL_BASE}/shares/meshant/schemas")
        assert schemas.json() == {"items": [{"name": self.asset.id.hex, "share": "meshant"}]}
        tables = self.client.get(
            f"{PROTOCOL_BASE}/shares/meshant/schemas/{self.asset.id.hex}/tables"
        )
        assert tables.json()["items"][0]["name"] == "catalog.schema.orders"
        metadata = self.client.get(
            f"{PROTOCOL_BASE}/shares/meshant/schemas/{self.asset.id.hex}"
            "/tables/catalog.schema.orders/metadata"
        )
        assert metadata.headers["delta-table-version"] == "1"

        # The data mode: presign → REAL download → the fixture rows.
        version = self.client.get(
            f"{PROTOCOL_BASE}/shares/meshant/schemas/{self.asset.id.hex}"
            "/tables/catalog.schema.orders/version"
        )
        assert version.headers["delta-table-version"] == "1"
        file_action = [json.loads(line) for line in version.content.decode().splitlines()][2][
            "file"
        ]
        with urllib.request.urlopen(file_action["url"]) as response:
            payload = response.read()

        import pyarrow.parquet as pq

        downloaded = pq.read_table(BytesIO(payload))
        assert downloaded.to_pylist() == [
            {"id": 1, "name": "alpha", "region": "eu"},
            {"id": 2, "name": "beta", "region": "us"},
            {"id": 3, "name": "gamma", "region": "eu"},
        ]

    def test_json_query_mode_serves_the_fixture_rows(self):
        from unittest import mock

        with mock.patch(
            "hub.apps.databricks_admin.delta_sharing_service.get_connector_for_connection",
            return_value=_RecordingConnector,
        ):
            resp = self.client.post(
                f"{PROTOCOL_BASE}/shares/meshant/schemas/{self.asset.id.hex}"
                "/tables/catalog.schema.orders/query",
                data=json.dumps({"limitHint": 100}),
                content_type="application/json",
            )
        assert resp.status_code == 200
        lines = [json.loads(line) for line in resp.content.decode().splitlines()]
        assert lines[2]["query"]["count"] == 2
        assert lines[2]["query"]["rows"] == [[1, "alpha"], [2, "beta"]]

    def test_an_invalid_token_is_401_on_the_fixture_share(self):
        bad = APIClient()
        bad.credentials(HTTP_AUTHORIZATION=f"Bearer bogus-{uuid.uuid4().hex}")
        resp = bad.get(f"{PROTOCOL_BASE}/shares")
        assert resp.status_code == 401

    def test_an_opted_out_asset_is_404_on_the_fixture_share(self):
        opted_out = _mk_asset(self.tenant, self.connection, optout=True)
        resp = self.client.get(f"{PROTOCOL_BASE}/shares/meshant/schemas/{opted_out.id.hex}/tables")
        assert resp.status_code == 404


class TestPresignedExpiry(TestCase):
    """The presigned URL expires — pinned on the real MinIO."""

    def setUp(self):
        require_dns()
        self.tenant, self.admin = _setup_tenant()
        self.connection = _mk_connection(self.tenant)
        self.asset = _mk_asset(self.tenant, self.connection, table_ref="catalog.schema.orders")
        self.recipient = _mk_recipient(self.tenant, self.admin)
        self.token, self.plaintext = _mk_token(self.recipient)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.plaintext}")

    def _version_url(self):
        from hub.apps.databricks_admin.models import DeltaShareSnapshot
        from hub.apps.files.storage import S3StorageClient

        storage = S3StorageClient()
        files = _upload_fixture_parquet(
            storage, share="meshant", schema=self.asset.id.hex, table="catalog.schema.orders"
        )
        DeltaShareSnapshot.objects.create(
            tenant=self.tenant,
            share_name="meshant",
            schema_name=self.asset.id.hex,
            table_name="catalog.schema.orders",
            version=1,
            files=files,
            expires_at=timezone.now() + timedelta(hours=1),
        )
        resp = self.client.get(
            f"{PROTOCOL_BASE}/shares/meshant/schemas/{self.asset.id.hex}"
            "/tables/catalog.schema.orders/version"
        )
        lines = [json.loads(line) for line in resp.content.decode().splitlines()]
        return lines[2]["file"]["url"]

    def test_the_presigned_url_carries_the_documented_expiry(self):
        from urllib.parse import parse_qs, urlparse

        url = self._version_url()
        assert parse_qs(urlparse(url).query)["X-Amz-Expires"] == ["3600"]

    def test_a_replayed_url_after_expiry_is_refused(self):
        import time

        from hub.apps.files.storage import S3StorageClient

        key = f"delta-share-snapshots/expiry-probe-{uuid.uuid4().hex[:8]}.bin"
        storage = S3StorageClient()
        storage.upload_file(key, b"probe")
        short_lived = storage.generate_presigned_download_url(key=key, expires_in=1)
        time.sleep(1.5)
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(short_lived)
        assert exc_info.value.code == 403, "an expired presigned URL must be refused"


class TestSnapshotIdempotencyWithFixtureSource(TestCase):
    """The snapshot job driven by the canned source: two runs, one row,
    one object set — S3 never rewritten."""

    def setUp(self):
        require_dns()
        self.tenant, self.admin = _setup_tenant()
        self.connection = _mk_connection(self.tenant)
        self.asset = _mk_asset(self.tenant, self.connection, table_ref="catalog.schema.orders")

    def test_two_runs_over_the_fixture_source_stamp_one_row_and_rewrite_nothing(self):
        from hub.apps.databricks_admin.delta_sharing_snapshot import run_snapshot_job
        from hub.apps.databricks_admin.models import DeltaShareSnapshot
        from hub.apps.files.storage import S3StorageClient
        from hub.apps.jobs.models import JobStatus

        first = run_snapshot_job(
            asset=self.asset,
            source_reader=_FixtureSourceReader(),
            actor_user=self.admin,
        )
        assert first.status == JobStatus.COMPLETED
        assert first.result_json["reused_existing"] is False

        second = run_snapshot_job(
            asset=self.asset,
            source_reader=_FixtureSourceReader(),
            actor_user=self.admin,
        )
        assert second.status == JobStatus.COMPLETED
        assert second.result_json["reused_existing"] is True, (
            "the same source version must reuse the existing row"
        )

        rows = DeltaShareSnapshot.objects.filter(
            tenant=self.tenant,
            share_name="meshant",
            schema_name=self.asset.id.hex,
            table_name="catalog.schema.orders",
        )
        assert rows.count() == 1
        assert rows.first().version == 1

        # The S3 objects at the manifest path carry the FIXTURE's rows —
        # a re-run never rewrote them.
        storage = S3StorageClient()
        manifest_path = rows.first().files[0]["path"]
        downloaded = storage.download_file(manifest_path)
        import pyarrow.parquet as pq

        table = pq.read_table(BytesIO(downloaded))
        assert table.to_pylist() == [
            {"id": 1, "name": "alpha", "region": "eu"},
            {"id": 2, "name": "beta", "region": "us"},
            {"id": 3, "name": "gamma", "region": "eu"},
        ]
        base = manifest_path.rsplit("/", 1)[0] + "/"
        assert storage.file_exists(f"{base}_delta_log/00000000000000000001.json")


class TestP9OracleClient:
    """The REAL delta-sharing REST client (the dev-only oracle) parses
    the canned envelopes — the wire-shape proof the P9 phase promises."""

    def _oracle_client(self, port):
        from delta_sharing.protocol import DeltaSharingProfile  # type: ignore[import-untyped]
        from delta_sharing.rest_client import DataSharingRestClient  # type: ignore[import-untyped]

        profile = DeltaSharingProfile(
            share_credentials_version=1,
            endpoint=f"http://127.0.0.1:{port}",
            bearer_token="oracle-token",
        )
        return DataSharingRestClient(profile)

    def _serve(self, routes):
        OracleWireHandler.routes = {
            suffix: (WIRE_ROOT / name).read_bytes() for suffix, name in routes.items()
        }
        OracleWireHandler.requests = []

    def test_the_oracle_parses_the_catalog_envelopes(self, oracle_server):
        from envpolicy import skip_or_fail

        try:
            client = self._oracle_client(oracle_server)
        except ImportError:  # the dev-only oracle (5.6) — W16 decides
            skip_or_fail("delta-sharing oracle not installed")
            return

        self._serve(
            routes={
                "/shares": "shares.json",
                "/shares/meshant": "share.json",
                "/shares/meshant/schemas": "schemas.json",
                "/tables": "tables.json",
                "/metadata": "metadata.ndjson",
                "/version": "version.ndjson",
            }
        )

        shares = client.list_shares()
        assert [share.name for share in shares.shares] == ["meshant"]
        schemas = client.list_schemas(shares.shares[0])
        assert len(schemas.schemas) == 1
        assert len(schemas.schemas[0].name) == 32, "the canned schema is the asset hex"
        tables = client.list_tables(schemas.schemas[0])
        assert [table.name for table in tables.tables] == ["catalog.schema.orders"]

    def test_the_oracle_parses_the_metadata_and_version_envelopes(self, oracle_server):
        from delta_sharing.protocol import Table

        from envpolicy import skip_or_fail

        try:
            client = self._oracle_client(oracle_server)
        except ImportError:  # the dev-only oracle (5.6) — W16 decides
            skip_or_fail("delta-sharing oracle not installed")
            return

        self._serve(
            routes={
                "/metadata": "metadata.ndjson",
                "/version": "version.ndjson",
            }
        )

        table = Table(name="catalog.schema.orders", share="meshant", schema="{schema}")
        metadata = client.query_table_metadata(table)
        assert metadata.protocol.min_reader_version == 1
        assert metadata.metadata.name == "catalog.schema.orders"

        version = client.query_table_version(table)
        assert version.delta_table_version == 1

    def test_the_canned_envelopes_match_the_live_endpoints(self):
        """The drift guard: the LIVE endpoints still produce the canned
        envelope SHAPES (key paths) — a wire change without a fixture
        update fails here."""
        require_dns()
        tenant, admin = _setup_tenant()
        connection = _mk_connection(tenant)
        _mk_asset(tenant, connection, table_ref="catalog.schema.orders")
        recipient = _mk_recipient(tenant, admin)
        _token, plaintext = _mk_token(recipient)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {plaintext}")

        def paths_of(obj, prefix=""):
            if isinstance(obj, dict):
                out = set()
                for key, value in obj.items():
                    out |= paths_of(value, f"{prefix}.{key}")
                return out
            if isinstance(obj, list):
                out = set()
                for item in obj:
                    out |= paths_of(item, prefix)
                return out
            return {prefix}

        checks = [
            ("shares.json", client.get(f"{PROTOCOL_BASE}/shares").json()),
            ("share.json", client.get(f"{PROTOCOL_BASE}/shares/meshant").json()),
            (
                "schemas.json",
                client.get(f"{PROTOCOL_BASE}/shares/meshant/schemas").json(),
            ),
        ]
        for name, live in checks:
            canned = json.loads((WIRE_ROOT / name).read_text())
            assert paths_of(live) == paths_of(canned), f"{name} drifted from the canned envelope"
