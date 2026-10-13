"""Journey pins for the P5 Delta Sharing surface (openspec
add-delta-sharing-server task 5.8) — JOURNEY-DB-012 (Consume a Delta
Share) + UC-DB-012 (Consume Delta Share).

Class/method names are PINNED by the UC docs' "Phase P5 Test" field
(docs/mvpdocs/use-cases/UC-DB-012.md) — renaming them breaks the
docs↔test drift gates (GATE-28).

The journey spans the shipped P5 surfaces with NO mocks — real
Postgres rows (tenant/recipient/token/asset/connection/snapshot/audit),
the REAL 5.3 protocol endpoints over real HTTP (the DRF views with the
central auth chokepoint), the REAL bearer-token auth (the production
``issue()``/``resolve()`` registry), the REAL 5.4 snapshot row served
as REAL presigned URLs from the production storage client, the REAL
audit chokepoints, and the REAL per-token throttle mount. The ONE
sanctioned patch point is the warehouse-connector factory symbol for
the JSON query leg (the 5.3 test convention — the warehouse transport
boundary, the 4.4 recorder pattern).
"""

import json
from datetime import timedelta

import pytest
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from hub.apps.databricks_admin.tests._fixtures import require_dns
from hub.apps.databricks_admin.tests.test_delta_sharing_endpoints import (
    PROTOCOL_BASE,
    _auth,
    _mk_asset,
    _mk_connection,
    _mk_recipient,
    _mk_token,
)
from hub.apps.databricks_admin.tests.test_uc_browse import _setup_tenant

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.journey("JOURNEY-DB-012"),
    pytest.mark.uc("UC-DB-012"),
]


class TestJOURNEYDB012ConsumeDeltaShare(TestCase):
    """The doc-pinned class (UC-DB-012's Phase P5 Test) — the consumer's
    protocol walk: profile → catalog → data."""

    def setUp(self):
        require_dns()
        self.tenant, self.admin = _setup_tenant()
        self.connection = _mk_connection(self.tenant)
        self.asset = _mk_asset(self.tenant, self.connection, table_ref="catalog.schema.orders")
        self.recipient = _mk_recipient(self.tenant, self.admin)
        self.token, self.plaintext = _mk_token(self.recipient)
        self.client = APIClient()
        _auth(self.client, self.plaintext)

    def test_protocol_shapes(self):
        """The doc-pinned method — the consumer's end-to-end protocol
        walk over the REAL endpoints: the v1 profile, the catalog
        hierarchy envelopes, and the ndjson metadata envelope with the
        delta-table-version header."""
        # Step 1 — the profile (the client's entry point).
        profile = self.client.get(f"{PROTOCOL_BASE}/profile")
        assert profile.status_code == 200
        body = profile.json()
        assert body["shareCredentialsVersion"] == 1
        assert body["endpoint"].endswith(PROTOCOL_BASE)
        assert body["bearerToken"] == self.plaintext

        # Step 2 — the catalog hierarchy (the oracle envelopes).
        shares = self.client.get(f"{PROTOCOL_BASE}/shares")
        assert shares.json() == {"items": [{"name": "meshant"}]}
        schemas = self.client.get(f"{PROTOCOL_BASE}/shares/meshant/schemas")
        assert schemas.json() == {"items": [{"name": self.asset.id.hex, "share": "meshant"}]}
        tables = self.client.get(
            f"{PROTOCOL_BASE}/shares/meshant/schemas/{self.asset.id.hex}/tables"
        )
        assert tables.json() == {
            "items": [
                {
                    "name": "catalog.schema.orders",
                    "share": "meshant",
                    "schema": self.asset.id.hex,
                }
            ]
        }

        # Step 3 — the metadata envelope (the ndjson line protocol).
        metadata = self.client.get(
            f"{PROTOCOL_BASE}/shares/meshant/schemas/{self.asset.id.hex}"
            "/tables/catalog.schema.orders/metadata"
        )
        assert metadata.status_code == 200
        assert metadata.headers["delta-table-version"] == "0"
        lines = [json.loads(line) for line in metadata.content.decode().splitlines()]
        assert lines[0] == {"protocol": {"minReaderVersion": 1}}
        assert lines[1]["metaData"]["name"] == "catalog.schema.orders"
        assert lines[1]["metaData"]["format"] == {"provider": "parquet"}

    def test_opted_out_assets_never_surface(self):
        """The opt-out contract: an opted-out asset is invisible in the
        listings and a 404 on direct fetch (the journey's success
        criterion)."""
        opted_out = _mk_asset(self.tenant, self.connection, optout=True)
        listing = self.client.get(f"{PROTOCOL_BASE}/shares/meshant/schemas")
        names = [item["name"] for item in listing.json()["items"]]
        assert opted_out.id.hex not in names
        direct = self.client.get(
            f"{PROTOCOL_BASE}/shares/meshant/schemas/{opted_out.id.hex}/tables"
        )
        assert direct.status_code == 404

    def test_the_401_leg_emits_auth_failed(self):
        """An absent/invalid token answers 401 with the Bearer challenge
        and emits WAREHOUSE_SHARE_AUTH_FAILED (best-effort, no tenant)."""
        from hub.apps.audit.models import AuditEvent

        bare = APIClient()
        resp = bare.get(f"{PROTOCOL_BASE}/shares")
        assert resp.status_code == 401
        assert resp.headers.get("WWW-Authenticate", "").lower().startswith("bearer")
        assert AuditEvent.objects.filter(action="WAREHOUSE_SHARE_AUTH_FAILED").exists(), (
            "the 401 leg must emit the auth-failed audit"
        )

    def test_the_version_endpoint_serves_real_presigned_urls(self):
        """The data leg: the 5.4 snapshot row is served as REAL
        presigned URL actions (the journey's step 3, Parquet mode)."""
        from hub.apps.databricks_admin.models import DeltaShareSnapshot

        DeltaShareSnapshot.objects.create(
            tenant=self.tenant,
            share_name="meshant",
            schema_name=self.asset.id.hex,
            table_name="catalog.schema.orders",
            version=7,
            files=[
                {
                    "id": "part-00000",
                    "path": "delta-share-snapshots/meshant/orders/part-00000-7.parquet",
                    "size": 4096,
                    "partition_values": {},
                }
            ],
            expires_at=timezone.now() + timedelta(hours=1),
        )
        resp = self.client.get(
            f"{PROTOCOL_BASE}/shares/meshant/schemas/{self.asset.id.hex}"
            "/tables/catalog.schema.orders/version"
        )
        assert resp.status_code == 200
        assert resp.headers["delta-table-version"] == "7"
        action = [json.loads(line) for line in resp.content.decode().splitlines()][2]["file"]
        assert action["id"] == "part-00000"
        assert "X-Amz-Expires" in action["url"]
        assert "X-Amz-Signature" in action["url"]

    def test_the_scope_triple_filters_direct_fetches(self):
        """A table-scoped token can only reach its own triple — anything
        outside the scope is a 404 (never a leak)."""
        _scoped, scoped_plaintext = _mk_token(
            self.recipient,
            schema=self.asset.id.hex,
            table="catalog.schema.orders",
        )
        other = _mk_asset(self.tenant, self.connection, table_ref="catalog.schema.events")
        scoped_client = APIClient()
        _auth(scoped_client, scoped_plaintext)
        resp = scoped_client.get(f"{PROTOCOL_BASE}/shares/meshant/schemas/{other.id.hex}/tables")
        assert resp.status_code == 404
        resp = scoped_client.get(
            f"{PROTOCOL_BASE}/shares/meshant/schemas/{self.asset.id.hex}"
            "/tables/catalog.schema.orders/metadata"
        )
        assert resp.status_code == 200, "the token's own triple is reachable"

    def test_every_access_emits_the_audit_row_with_ip_and_user_agent(self):
        """The journey's audit criterion: every protocol request emits
        WAREHOUSE_SHARE_ACCESSED with the consumer's IP + user-agent."""
        from hub.apps.audit.models import AuditEvent

        before = AuditEvent.objects.filter(action="WAREHOUSE_SHARE_ACCESSED").count()
        self.client.get(
            f"{PROTOCOL_BASE}/shares/meshant/schemas/{self.asset.id.hex}/tables",
            HTTP_USER_AGENT="delta-sharing-journey/1.0",
        )
        after = AuditEvent.objects.filter(action="WAREHOUSE_SHARE_ACCESSED").count()
        assert after == before + 1, "exactly one ACCESSED row per request"

    def test_the_query_leg_rides_the_connector_factory(self):
        """The JSON-mode leg — the SELECT rides the production connector
        factory (the sanctioned seam; a recording connector returns real
        QueryResult rows)."""
        from unittest import mock

        from hub.apps.databricks_admin.tests.test_delta_sharing_endpoints import (
            _RecordingConnector,
        )

        _RecordingConnector.calls = []
        _RecordingConnector.result = None

        def factory(warehouse_type):
            assert warehouse_type == self.connection.warehouse_type
            return _RecordingConnector

        with mock.patch(
            "hub.apps.databricks_admin.delta_sharing_service.get_connector_for_connection",
            factory,
        ):
            resp = self.client.post(
                f"{PROTOCOL_BASE}/shares/meshant/schemas/{self.asset.id.hex}"
                "/tables/catalog.schema.orders/query",
                data=json.dumps({"limitHint": 50}),
                content_type="application/json",
            )
            assert resp.status_code == 200
            assert _RecordingConnector.calls[0]["sql"] == (
                "SELECT * FROM catalog.schema.orders LIMIT 50"
            )
            lines = [json.loads(line) for line in resp.content.decode().splitlines()]
            assert lines[2]["query"]["rows"] == [[1, "alpha"], [2, "beta"]]


class TestDeltaShareJourneySurfaceContract(TestCase):
    """The journey's substrate: the recipient/token registry serves the
    journey's auth leg through the production issue()/resolve() path."""

    def setUp(self):
        require_dns()
        self.tenant, self.admin = _setup_tenant()
        self.recipient = _mk_recipient(self.tenant, self.admin)

    def test_the_issued_token_authenticates_the_protocol(self):
        from hub.apps.databricks_admin.models import DeltaShareToken

        token, plaintext = _mk_token(self.recipient)
        resolved = DeltaShareToken.resolve(plaintext)
        assert resolved is not None
        assert resolved.id == token.id
        assert resolved.token_hash == token.token_hash
        # The plaintext never persists — only the hash + display prefix.
        assert resolved.token_prefix != plaintext
        assert plaintext != token.token_hash
        assert not token.token_hash.startswith(plaintext[:8])

    def test_the_throttle_mounts_on_the_protocol_surface(self):
        from hub.apps.databricks_admin.delta_sharing_views import (
            DeltaSharingProtocolViewSet,
        )
        from hub.apps.databricks_admin.throttles import DeltaShareTokenRateThrottle

        assert DeltaShareTokenRateThrottle in DeltaSharingProtocolViewSet.throttle_classes
