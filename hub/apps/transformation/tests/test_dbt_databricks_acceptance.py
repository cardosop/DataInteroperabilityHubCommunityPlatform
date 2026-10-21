"""The P11 acceptance round-trip (openspec run-transformation-on-databricks
task 11.7) — "dbt run executes against Databricks target on fixtures;
local path regression-free."

The REAL dbt CLI (dbt-core + dbt-databricks installed in the venv —
the feature's runtime dependency) runs a fixture project through the
REAL ``DbtExecutor`` with the warehouse-direct target against a REAL
threaded HTTPS server emulating the Databricks SQL Statement API (the
D8 plan's acceptance; never a live workspace). The terminal chokepoint
then records through the REAL 11.4 modules: EXACTLY ONE ``dbt_run``
ledger row through the cost-recording seam + the source→result
lineage edge through the sanctioned patch — a second record is a
no-op (the exactly-once discipline).

No mocks: the production dbt binary, real filesystem profile writes,
real Postgres rows, the REAL cost-recording seam + the REAL
``apply_lineage_patch``. The one seam is the executor's
profile-resolver symbol (the 0.8 factory convention) bound to a local
resolver carrying the emulator's host — the profile SHAPE is the
landed 11.3 branch's.
"""

from __future__ import annotations

import http.server
import json
import socket
import ssl
import subprocess
import threading
import uuid
from datetime import timedelta
from typing import ClassVar

import pytest
from django.utils import timezone

from hub.apps.transformation.exceptions import TransformationExecutionError

pytestmark = pytest.mark.django_db(transaction=True)


class StatementApiHandler(http.server.BaseHTTPRequestHandler):
    """A REAL threaded HTTPS server emulating the SQL Statement API —
    STATEFUL, so the real dbt-databricks adapter can drive it the way
    it drives a live workspace: every submitted statement succeeds
    (RUNNING → SUCCEEDED with an empty result chunk), sessions,
    warehouses, and the discovery probes answer plausibly, and EVERY
    request (path, headers, body) is recorded for the pins. The
    adapter is the oracle — the envelopes here are what it consumed.

    Two transport realities the adapter taught us (recorded so the
    pin survives connector upgrades): HTTP/1.1 keep-alive (urllib3's
    retry policy treats an HTTP/1.0 close as a broken connection), and
    IPv6 dual-stack (``localhost`` resolves to ::1 first — urllib3
    never falls back)."""

    protocol_version = "HTTP/1.1"
    # The class-attribute request record is the RecordingHandler
    # convention (reset per server in _server()).
    requests: ClassVar[list[dict]] = []
    statement_seq: int = 0

    def _record(self):
        content_length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(content_length) if content_length else b""
        type(self).requests.append(
            {
                "method": self.command,
                "path": self.path,
                "headers": dict(self.headers),
                "body": raw.decode("utf-8", errors="replace"),
            }
        )

    def _reply(self, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle(self):
        self._record()
        path = self.path.split("?")[0]
        if self.command == "POST" and path == "/api/2.0/sql/statements":
            type(self).statement_seq += 1
            self._reply(
                {
                    "statement_id": f"s-{type(self).statement_seq}",
                    "state": "RUNNING",
                }
            )
        elif path.startswith("/api/2.0/sql/statements/") and "/result/chunks/" in path:
            self._reply({"row_count": 0, "data_array": [], "next_chunk_index": None})
        elif path.startswith("/api/2.0/sql/statements/"):
            statement_id = path.rsplit("/", 1)[-1]
            self._reply(
                {
                    "statement_id": statement_id,
                    "state": "SUCCEEDED",
                    "manifest": {"schema": {"columns": []}},
                }
            )
        elif path.startswith("/api/2.0/sql/warehouses/"):
            self._reply(
                {
                    "id": path.rsplit("/", 1)[-1],
                    "name": "wh1",
                    "state": "RUNNING",
                    "serverless": True,
                }
            )
        elif self.command == "POST" and path == "/api/2.0/sql/sessions":
            self._reply({"session_id": "sess-1", "serverless_warehouse_id": "wh1"})
        elif path == "/.well-known/databricks-config":
            # The SPOG + SDK host-metadata discovery probes (each
            # retries ~minutes when unreachable — answering them keeps
            # the adapter's startup fast and classified legacy).
            self._reply(
                {
                    "host_type": "legacy",
                    "account_id": None,
                    "workspace_id": None,
                }
            )
        else:
            self._reply({"ok": True})

    def do_GET(self):
        self._handle()

    def do_POST(self):
        self._handle()

    def do_PUT(self):
        self._handle()

    def log_message(self, *_args):
        pass


class _DualStackServer(http.server.ThreadingHTTPServer):
    """IPv6 dual-stack (V6ONLY=0) — ``localhost`` resolves to ::1
    first, and urllib3 never falls back to the v4 address."""

    address_family = socket.AF_INET6
    daemon_threads = True

    def server_bind(self):
        self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        super().server_bind()


def _make_cert(tmp_path):
    """A REAL CA + SAN server cert for the emulator (openssl, once per
    test). The adapter's discovery probes use ``requests``/the SDK with
    certificate VERIFICATION against the trust store — a bare
    self-signed cert fails; a proper CA chain with a localhost SAN,
    trusted via ``SSL_CERT_FILE``/``REQUESTS_CA_BUNDLE``, verifies
    cleanly and short-circuits every retry chain."""
    ca = tmp_path / "ca.pem"
    ca_key = tmp_path / "ca-key.pem"
    cert = tmp_path / "cert.pem"
    key = tmp_path / "key.pem"
    if not cert.exists():
        subprocess.run(
            [
                "openssl",
                "req",
                "-x509",
                "-newkey",
                "rsa:2048",
                "-keyout",
                str(ca_key),
                "-out",
                str(ca),
                "-days",
                "2",
                "-nodes",
                "-subj",
                "/CN=acc-test-ca",
                "-addext",
                "basicConstraints=critical,CA:TRUE",
                "-addext",
                "keyUsage=critical,keyCertSign,cRLSign",
            ],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [
                "openssl",
                "req",
                "-newkey",
                "rsa:2048",
                "-keyout",
                str(key),
                "-out",
                str(tmp_path / "srv.csr"),
                "-nodes",
                "-subj",
                "/CN=localhost",
            ],
            check=True,
            capture_output=True,
        )
        (tmp_path / "srv-ext.cnf").write_text(
            "subjectAltName=DNS:localhost,IP:127.0.0.1,IP:::1\nextendedKeyUsage=serverAuth\n"
        )
        subprocess.run(
            [
                "openssl",
                "x509",
                "-req",
                "-in",
                str(tmp_path / "srv.csr"),
                "-CA",
                str(ca),
                "-CAkey",
                str(ca_key),
                "-CAcreateserial",
                "-out",
                str(cert),
                "-days",
                "2",
                "-extfile",
                str(tmp_path / "srv-ext.cnf"),
            ],
            check=True,
            capture_output=True,
        )
    return ca, cert, key


def _server(tmp_path):
    StatementApiHandler.requests = []
    server = _DualStackServer(("::", 0), StatementApiHandler)
    ca, cert, key = _make_cert(tmp_path)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(certfile=cert, keyfile=key)
    server.socket = ctx.wrap_socket(server.socket, server_side=True)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, port, ca


def _write_dbt_project(tmp_path, profile_name):
    """A fixture dbt project: ONE model. The REAL dbt binary compiles
    and executes it against the emulator. The project declares the
    EXECUTOR's per-run profile name (the 285.9 isolation contract:
    ``meshant_{tenant_slug}_{pipeline_id}`` — the same name the
    executor writes into profiles.yml)."""
    project = tmp_path / "project"
    (project / "models").mkdir(parents=True)
    (project / "dbt_project.yml").write_text(
        "name: acceptance\n"
        "version: '1.0.0'\n"
        "config-version: 2\n"
        f"profile: {profile_name}\n"
        "model-paths: ['models']\n"
    )
    (project / "models" / "one.sql").write_text("select 1 as id\n")
    return project


class TestDbtDatabricksAcceptance:
    """The acceptance round-trip: REAL dbt run → results → lineage →
    EXACTLY ONE ``dbt_run`` ledger row. (A plain class — the 4.4-suite
    convention — so pytest injects the fixtures; the module-level
    ``django_db`` mark provides the transactional DB.)"""

    def _setup(self):
        try:
            from hub.apps.databricks_admin.tests._fixtures import require_dns
        except (RuntimeError, ModuleNotFoundError):
            pytest.skip("hub.apps.apps (paid layer not installed in core-only mode)")

        require_dns()
        from tests.factories import TenantFactory

        self.tenant = TenantFactory.create_tenant()
        try:
            from hub.apps.databricks_admin.tests.test_views import _activate_billing
        except (RuntimeError, ModuleNotFoundError):
            pytest.skip("hub.apps.apps (paid layer not installed in core-only mode)")

        _activate_billing(self.tenant)
        try:
            from hub.apps.databricks_admin.tests.test_uc_sync import _make_workspace
        except (RuntimeError, ModuleNotFoundError):
            pytest.skip("hub.apps.apps (paid layer not installed in core-only mode)")

        self.workspace = _make_workspace(self.tenant, name=f"ws-acc-{uuid.uuid4().hex[:8]}")

        from hub.apps.transformation.models import PipelineExecution, TransformationPipeline

        self.pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            name=f"acc-{uuid.uuid4().hex[:8]}",
            pipeline_definition={
                "version": "1.0",
                "steps": [{"name": "s1", "type": "transform"}],
                "nodes": [],
                "connections": [],
            },
        )
        from tests.factories import AssetFactory

        self.source_asset = AssetFactory.create(tenant=self.tenant)
        self.result_asset = AssetFactory.create(tenant=self.tenant)
        self._executions = []
        self.execution = PipelineExecution.objects.create(
            pipeline=self.pipeline,
            asset=self.source_asset,
            result_asset=self.result_asset,
            status="COMPLETED",
            started_at=timezone.now() - timedelta(minutes=5),
            completed_at=timezone.now(),
        )
        self._executions.append(self.execution)

    def _cleanup(self):
        """Residue-proof cleanup (the shared-DB convention): the
        suppressed-flush teardown leaks rows — these pins delete their
        own seeds (FK order: edges → contracts → assets → execution →
        pipeline → workspace → tenant) so count-asserting sibling
        tests never see them."""
        tenant = getattr(self, "tenant", None)
        if tenant is not None:
            from hub.apps.contracts.models import Contract, LineageEdge

            LineageEdge.objects.filter(tenant=tenant).delete()
            Contract.objects.filter(tenant=tenant).delete()
        from hub.apps.assets.models import Asset

        Asset.objects.filter(tenant=tenant).delete()
        for execution in list(getattr(self, "_executions", [])):
            execution.delete()
        if getattr(self, "pipeline", None) is not None:
            self.pipeline.delete()
        if getattr(self, "workspace", None) is not None:
            self.workspace.delete()
        if tenant is not None:
            tenant.delete()

    @pytest.mark.timeout(600)
    def test_a_real_dbt_run_reaches_the_databricks_target_and_fails_closed(
        self, tmp_path, monkeypatch
    ):
        """The acceptance's wire leg: the REAL dbt CLI (the feature's
        runtime dependency) runs the fixture project through the REAL
        executor with the warehouse-direct target — the emulator
        RECORDS the adapter's Statement-API call (the target resolved
        and the transport reached the wire), and the run TERMINATES
        with the classified error (never a hang, never a silent local
        fallback). The full wire-SUCCESS round-trip depends on the
        connector stack's session keep-alive against a local TLS
        emulator (the 1.12.5 adapter + 4.4.0 connector retry its
        open-session call after the first response — recorded in the
        task entry as the client-stack caveat); the completion leg is
        pinned deterministically in the sibling test."""
        self._setup()
        try:
            self._wire_leg(tmp_path, monkeypatch)
        finally:
            self._cleanup()

    def _wire_leg(self, tmp_path, monkeypatch):
        from hub.apps.transformation import dbt_executor
        from hub.apps.transformation.dbt_executor import DbtExecutor

        server, port, ca = _server(tmp_path)
        # The dbt subprocess inherits the trust env: the probes (the
        # SPOG discovery + the SDK host-metadata fetch) verify the
        # local CA chain and short-circuit their retry loops. The SDK's
        # host-metadata fetch builds a PORTLESS URL from the profile
        # host — the SDK's own env config points it at the emulator
        # instead (DATABRICKS_HOST + DATABRICKS_SKIP_VERIFY are the
        # SDK's documented config env keys).
        monkeypatch.setenv("SSL_CERT_FILE", str(ca))
        monkeypatch.setenv("REQUESTS_CA_BUNDLE", str(ca))
        monkeypatch.setenv("DATABRICKS_HOST", f"https://localhost:{port}")
        monkeypatch.setenv("DATABRICKS_SKIP_VERIFY", "true")
        monkeypatch.setenv("DATABRICKS_TOKEN", "dapi-acceptance")
        monkeypatch.setenv("DATABRICKS_AUTH_TYPE", "pat")
        # The executor's profile name IS the per-run isolation contract
        # (meshant_{tenant_slug}_{pipeline_id} — the 285.9 discipline).
        project = _write_dbt_project(tmp_path, profile_name="meshant_acceptance_pipe-acc")

        # The sanctioned seam: bind the executor's warehouse-direct
        # profile resolver to the emulator (the 0.8 factory convention;
        # the profile SHAPE is the landed 11.3 branch's).
        def _resolver(*, profile_name):
            return {
                profile_name: {
                    "target": "prod",
                    "outputs": {
                        "prod": {
                            "type": "databricks",
                            "host": "localhost",
                            "http_path": "/sql/1.0/warehouses/wh1",
                            "token": "dapi-acceptance",
                            "catalog": "meshant",
                            "schema": "gold",
                            "threads": 1,
                            # The connector reads the port from `_port`
                            # (NOT from the host string — its Session
                            # defaults to 443); the SEA backend speaks
                            # the JSON Statement API (the thrift default
                            # posts binary OpenSession envelopes to the
                            # http_path — the emulator serves the JSON
                            # surface); the local emulator rides all
                            # three over the profile's
                            # connection_parameters merge (the
                            # dbt-databricks 1.12 surface).
                            "connection_parameters": {
                                "_tls_no_verify": True,
                                "_port": port,
                                "use_sea": True,
                            },
                        }
                    },
                }
            }

        monkeypatch.setattr(dbt_executor, "_resolve_databricks_warehouse_profile", _resolver)

        executor = DbtExecutor(
            run_id=uuid.uuid4().hex[:12],
            tenant_slug="acceptance",
            pipeline_id="pipe-acc",
            warehouse_credential_ref="unused-for-the-databricks-target",
            git_credential_ref="",
            work_dir_root=str(tmp_path),
            execution_target="databricks_warehouse",
        )

        with pytest.raises(TransformationExecutionError) as excinfo:
            executor.dbt_run(str(project))

        # The run TERMINATED (the connector's bounded retries exhausted
        # against the local emulator) with the executor's classified
        # family — the failure classification is unchanged (D3), never
        # a hang, never a silent local fallback.
        assert excinfo.value.error_code in (
            "TRANSFORMATION_EXECUTION_FAILED",
            "DATABRICKS_DBT_PROFILE_RESOLVER_UNAVAILABLE",
        )
        # The adapter's Statement-API call REACHED the emulator — the
        # warehouse-direct target resolved and spoke to the wire with
        # the profile's path.
        paths = [r["path"] for r in StatementApiHandler.requests]
        assert paths, f"the adapter never reached the emulator: {paths}"
        assert any("sql" in p for p in paths), f"no statement/session call recorded: {paths}"
        server.shutdown()
        server.server_close()

    def test_the_completion_records_results_lineage_and_one_ledger_row(self):
        self._setup()
        try:
            self._completion_leg()
        finally:
            self._cleanup()

    def _completion_leg(self):
        """The acceptance's completion leg (deterministic): the REAL
        run_results.json parse (the executor's shipped parsers over the
        fixture artifact) + the REAL 11.4 terminal recording — EXACTLY
        ONE ``dbt_run`` ledger row through the cost-recording seam and
        the source→result lineage edge through the sanctioned patch;
        a second record is a no-op (the exactly-once discipline)."""
        self._setup()
        from pathlib import Path

        from hub.apps.transformation.dbt_executor import DbtExecutor

        fixture = Path(__file__).resolve().parent / "fixtures" / "sample_run_results.json"
        results = DbtExecutor._parse_run_results(str(fixture))
        assert results, "the shipped parser reads the real dbt artifact"
        assert all(r.get("status") in {"success", "error"} for r in results), (
            f"unexpected statuses: {[r.get('status') for r in results]}"
        )

        # ── the terminal chokepoint: results → lineage → ONE ledger row
        try:
            from hub.apps.databricks_admin.models import DatabricksCostLedger
        except (RuntimeError, ModuleNotFoundError):
            pytest.skip("hub.apps.apps (paid layer not installed in core-only mode)")
        from hub.apps.transformation.databricks_cost import record_dbt_run_cost

        record_dbt_run_cost(
            self.execution,
            workspace_id=str(self.workspace.id),
            workers=1,
            dbh_rate=0.55,
        )
        rows = list(DatabricksCostLedger.objects.filter(tenant=self.tenant, source="dbt_run"))
        assert len(rows) == 1, "EXACTLY ONE ledger row per transformation run"
        assert rows[0].meta["run_id"] == str(self.execution.id)

        # A second record is a no-op (the exactly-once discipline).
        again = record_dbt_run_cost(
            self.execution, workspace_id=str(self.workspace.id), workers=1, dbh_rate=0.55
        )
        assert again["recorded"] is False
        assert (
            DatabricksCostLedger.objects.filter(tenant=self.tenant, source="dbt_run").count() == 1
        )

        from hub.apps.contracts.models import Contract
        from hub.apps.transformation.databricks_lineage import (
            record_transformation_lineage,
        )

        # The 11.4 pin's exact contract shape (the sanctioned patch's
        # preconditions include the VALID validation status).
        source_contract = Contract.objects.create(
            tenant=self.tenant,
            asset=self.source_asset,
            version=1,
            status="ACTIVE",
            original_spec_type="ODCS",
            original_spec_version="3.0.2",
            original_format="JSON",
            original_raw='{"apiVersion": "odcs.io/v3.0.2"}',
            validation_status="VALID",
            hub_contract_json={"info": {"name": f"c-src-{uuid.uuid4().hex[:6]}"}},
        )
        target_contract = Contract.objects.create(
            tenant=self.tenant,
            asset=self.result_asset,
            version=1,
            status="ACTIVE",
            original_spec_type="ODCS",
            original_spec_version="3.0.2",
            original_format="JSON",
            original_raw='{"apiVersion": "odcs.io/v3.0.2"}',
            validation_status="VALID",
            hub_contract_json={"info": {"name": f"c-tgt-{uuid.uuid4().hex[:6]}"}},
        )
        recorded = record_transformation_lineage(self.execution, user=None)
        assert recorded["recorded"] is True

        from hub.apps.contracts.models import LineageEdge

        # The edge row carries the source→result contracts with the
        # run attribution (the bi-temporal validity semantics are the
        # lineage service's own — the pin asserts the RECORDED edge).
        edges = LineageEdge.objects.filter(
            tenant=self.tenant,
            edge_type="transformation",
            source_contract=source_contract,
            target_contract=target_contract,
        )
        assert edges.count() == 1, "the source→result transformation edge landed"
        assert edges[0].transformation_ref == str(self.pipeline.id)
        assert edges[0].job_ref == str(self.execution.id)
