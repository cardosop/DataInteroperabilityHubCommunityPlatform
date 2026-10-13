"""Shared-DoD helm task — the recurring snapshot sweep command pins
(`manage.py databricks_delta_share_snapshot`, the CronJob entry for the
Delta Sharing Parquet snapshot recurring job).

The command's contract:
- ADMIN-DB discovery (BYPASSRLS): tenants that own >=1 DeltaShareRecipient
  AND >=1 shareable asset (LIVE_QUERY + connected + opted in — the exact
  ``shareable_assets`` serving-side filter, plus the recipient requirement:
  a tenant nobody can fetch from is never swept).
- Per tenant UNDER that tenant's ``tenant_context`` (the jobs + snapshots
  tables are RLS-scoped): every shareable table's freshness via the
  canonical ``latest_snapshot`` lookup — a FRESH row is skipped with zero
  work; an EXPIRED (or NULL-expiry, fail-closed) or MISSING row dispatches
  the 5.4 ``run_snapshot_job`` spine (one Hub Job row + audit per refresh).
- Per-asset failures are recorded and the sweep CONTINUES (the next tick
  retries) — a broken table never starves the other tenants' tables.

No mocks: real Postgres rows (tenants/recipients/assets/connections/
snapshots/Jobs) over the admin + default DB aliases; the command runs for
real via ``call_command``. The one sanctioned seam is the dispatch
boundary (``run_snapshot_job`` — the outbound execution boundary, the
4.4/7.8 convention); the integration pin swaps the seam for the REAL
spine over a REAL local HTTP server + REAL MinIO S3.
"""

from __future__ import annotations

import contextlib
import json
import uuid
from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from hub.apps.databricks_admin.models import DeltaShareRecipient, DeltaShareSnapshot
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

pytestmark = pytest.mark.django_db(transaction=True)

# S3 cleanup registry — every integration test tracks its written keys;
# the autouse fixture best-effort deletes them at teardown (minio
# accumulates otherwise; the table refs are uuid-suffixed so a test only
# ever deletes its OWN objects — the 5.4 spine suite's convention).
_TRACKED_BASES: list[str] = []


@pytest.fixture(autouse=True)
def _cleanup_tracked_snapshot_bases():
    yield
    from hub.apps.files.storage import S3StorageClient

    storage = S3StorageClient()
    for base in list(_TRACKED_BASES):
        with contextlib.suppress(Exception):  # cleanup is best-effort hygiene
            storage.delete_prefix(base)
        _TRACKED_BASES.remove(base)


def _mk_tenant():
    uid = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"snap-{uid}",
        slug=f"snap-{uid}",
        status=TenantStatus.ACTIVE,
        kyc_status=KYCStatus.UNVERIFIED,
    )
    ensure_tenant_has_active_subscription(tenant)
    return tenant


def _mk_recipient(tenant):
    return DeltaShareRecipient.objects.create(
        tenant=tenant,
        name=f"recipient-{uuid.uuid4().hex[:8]}",
    )


def _mk_connection(tenant):
    from hub.apps.warehouses.models import WarehouseConnection, WarehouseType

    return WarehouseConnection.objects.create(
        tenant=tenant,
        name=f"conn-{uuid.uuid4().hex[:8]}",
        warehouse_type=WarehouseType.DATABRICKS,
        config={
            "host": "adb-123.azuredatabricks.net",
            "http_path": "/sql/1.0/warehouses/wh-1",
            "pat_token": "dapi-own-token",
        },
    )


def _mk_asset(tenant, connection=None, *, table_ref=None, **overrides):
    from hub.apps.assets.models import Asset, DataStrategy

    uid = uuid.uuid4().hex[:8]
    kwargs = {
        "tenant": tenant,
        "key": f"key-{uid}",
        "name": f"asset-{uid}",
        "data_strategy": DataStrategy.LIVE_QUERY,
        "warehouse_connection": connection,
        "semantic_federate_optout": False,
        "metadata_json": {
            "external_table_ref": table_ref or f"cat.schema.t-{uuid.uuid4().hex[:6]}"
        },
    }
    kwargs.update(overrides)
    return Asset.objects.create(**kwargs)


def _triple(tenant, asset):
    from hub.apps.databricks_admin.delta_sharing_service import (
        schema_name_for,
        share_name_for,
        table_name_for,
    )

    return share_name_for(tenant), schema_name_for(asset), table_name_for(asset)


def _mk_snapshot_row(tenant, asset, *, version=1, expires_at):
    share, schema, table = _triple(tenant, asset)
    return DeltaShareSnapshot.objects.create(
        tenant=tenant,
        share_name=share,
        schema_name=schema,
        table_name=table,
        version=version,
        files=[],
        expires_at=expires_at,
    )


def _stale_tenant(*, with_recipient=True):
    """A tenant with a shareable asset whose snapshot is EXPIRED."""
    tenant = _mk_tenant()
    connection = _mk_connection(tenant)
    asset = _mk_asset(tenant, connection)
    _mk_snapshot_row(tenant, asset, expires_at=timezone.now() - timedelta(hours=1))
    if with_recipient:
        _mk_recipient(tenant)
    return tenant


class _CompletedJob:
    """The minimal terminal-shape object the command's status check reads
    (the outbound-boundary convention — the real Job row is the 5.4
    suite's + the integration pin's substrate)."""

    status = "COMPLETED"


class _RecordingDispatch:
    """The dispatch-boundary recorder (the 4.4/7.8 convention) — the pin
    asserts the command's own contract (discovery, freshness, dispatch);
    the execution spine is pinned by the 5.4 suite + the integration pin."""

    def __init__(self, *, fail_for=None):
        self.dispatched: list[str] = []  # asset ids, in order
        self.calls: list[dict] = []
        self.fail_for = fail_for or set()

    def __call__(self, *, asset, **kwargs):
        self.calls.append({"asset": asset, "kwargs": kwargs})
        if str(asset.id) in self.fail_for:
            from hub.apps.databricks_admin.delta_sharing_snapshot import (
                DeltaShareSnapshotError,
            )

            raise DeltaShareSnapshotError("scripted per-asset failure")
        self.dispatched.append(str(asset.id))
        return _CompletedJob()


class TestSnapshotSweepCommand:
    def test_the_dry_run_lists_only_tenants_with_a_recipient_and_a_stale_table(self, capsys):
        stale = _stale_tenant()  # recipient + expired snapshot → listed
        fresh = _mk_tenant()  # recipient + fresh snapshot → NOT listed
        fresh_connection = _mk_connection(fresh)
        fresh_asset = _mk_asset(fresh, fresh_connection)
        _mk_snapshot_row(fresh, fresh_asset, expires_at=timezone.now() + timedelta(hours=1))
        _mk_recipient(fresh)
        missing = _mk_tenant()  # recipient + NO snapshot → listed
        _mk_asset(missing, _mk_connection(missing))
        _mk_recipient(missing)
        no_recipient = _stale_tenant(with_recipient=False)  # stale but nobody to serve
        opted_out = _mk_tenant()  # recipient + shareable-shaped asset, opted out
        _mk_asset(
            opted_out,
            _mk_connection(opted_out),
            semantic_federate_optout=True,
        )
        _mk_recipient(opted_out)

        result = call_command("databricks_delta_share_snapshot", "--dry-run")

        assert isinstance(result, str)
        listed = result.splitlines()
        assert str(stale.id) in listed, "an expired snapshot is always swept"
        assert str(missing.id) in listed, "a table with no snapshot row is always swept"
        assert str(fresh.id) not in listed, "a fresh snapshot is never swept"
        assert str(no_recipient.id) not in listed, "a tenant nobody can fetch from is never swept"
        assert str(opted_out.id) not in listed, "an opted-out asset is never swept"
        assert "tenant(s)" in capsys.readouterr().out

    def test_the_run_refreshes_only_stale_or_missing_tables(self, capsys, monkeypatch):
        tenant = _mk_tenant()
        connection = _mk_connection(tenant)
        stale_asset = _mk_asset(tenant, connection)
        _mk_snapshot_row(tenant, stale_asset, expires_at=timezone.now() - timedelta(hours=1))
        null_expiry_asset = _mk_asset(tenant, connection)
        _mk_snapshot_row(tenant, null_expiry_asset, expires_at=None)  # fail-closed: NULL = expired
        missing_asset = _mk_asset(tenant, connection)
        fresh_asset = _mk_asset(tenant, connection)
        _mk_snapshot_row(tenant, fresh_asset, expires_at=timezone.now() + timedelta(hours=1))
        _mk_recipient(tenant)

        recorder = _RecordingDispatch()
        monkeypatch.setattr(
            "hub.apps.databricks_admin.management.commands.databricks_delta_share_snapshot"
            ".run_snapshot_job",
            recorder,
        )

        result = call_command("databricks_delta_share_snapshot")

        # The dirty test DB carries leaked fixture tenants from earlier
        # runs (the suppressed-flush convention) — the command legitimately
        # sweeps them ALL. The pins scope to THIS test's rows (leak-proof,
        # the 7.8 convention).
        for expected in (stale_asset, null_expiry_asset, missing_asset):
            assert recorder.dispatched.count(str(expected.id)) == 1, (
                "the stale/NULL-expiry/missing table is dispatched exactly once"
            )
        assert str(fresh_asset.id) not in recorder.dispatched, "fresh is zero work"
        assert "refreshed " in result or "refreshed " in capsys.readouterr().out

    def test_the_run_continues_after_a_per_asset_failure(self, capsys, monkeypatch):
        tenant = _mk_tenant()
        connection = _mk_connection(tenant)
        broken_asset = _mk_asset(tenant, connection)
        _mk_snapshot_row(tenant, broken_asset, expires_at=timezone.now() - timedelta(hours=1))
        healthy_asset = _mk_asset(tenant, connection)
        _mk_snapshot_row(tenant, healthy_asset, expires_at=timezone.now() - timedelta(hours=1))
        _mk_recipient(tenant)

        recorder = _RecordingDispatch(fail_for={str(broken_asset.id)})
        monkeypatch.setattr(
            "hub.apps.databricks_admin.management.commands.databricks_delta_share_snapshot"
            ".run_snapshot_job",
            recorder,
        )

        result = call_command("databricks_delta_share_snapshot")

        # Leak-proof pins (the dirty-DB convention — earlier runs' tenants
        # are swept too, so scope to THIS test's rows).
        assert recorder.dispatched.count(str(healthy_asset.id)) == 1, (
            "a broken table never starves the tenant's other tables"
        )
        assert str(broken_asset.id) not in recorder.dispatched
        assert [c["asset"].id for c in recorder.calls].count(broken_asset.id) == 1, (
            "the failed table was attempted (retried next tick)"
        )
        err = capsys.readouterr().err
        assert "scripted per-asset failure" in err, "the failure is reported"
        assert "failed" in result or "failed" in capsys.readouterr().out

    def test_an_asset_without_a_table_ref_is_never_dispatched(self, monkeypatch):
        tenant = _mk_tenant()
        connection = _mk_connection(tenant)
        # The empty ref must ride through the helper's `or` default — pass
        # the metadata directly (an explicit "" table ref).
        empty_ref_asset = _mk_asset(tenant, connection, metadata_json={"external_table_ref": ""})
        _mk_asset(tenant, connection)  # a real table so the tenant is discovered
        _mk_recipient(tenant)

        recorder = _RecordingDispatch()
        monkeypatch.setattr(
            "hub.apps.databricks_admin.management.commands.databricks_delta_share_snapshot"
            ".run_snapshot_job",
            recorder,
        )

        call_command("databricks_delta_share_snapshot")

        assert str(empty_ref_asset.id) not in recorder.dispatched, (
            "an asset without an external table ref can never be snapshotted"
        )
        assert recorder.dispatched, "the tenant's real table is still swept"

    def test_the_dry_run_never_dispatches(self, monkeypatch):
        tenant = _stale_tenant()
        recorder = _RecordingDispatch()
        monkeypatch.setattr(
            "hub.apps.databricks_admin.management.commands.databricks_delta_share_snapshot"
            ".run_snapshot_job",
            recorder,
        )

        result = call_command("databricks_delta_share_snapshot", "--dry-run")

        assert recorder.calls == [], "dry-run is a read-only report"
        assert str(tenant.id) in result.splitlines()


class TestSnapshotSweepCommandOnTheStack:
    """The wiring pin on the REAL stack: the command's dispatch lands on
    the REAL 5.4 spine (local HTTP statement API + real MinIO S3) — the
    Hub Job row + the stamped snapshot row land, proving the command
    passes the discovered asset through the production execution path
    under the tenant's RLS context."""

    def test_the_run_materializes_a_real_snapshot(self, monkeypatch, local_http_server):
        from hub.apps.databricks_admin.tests._fixtures import require_dns
        from hub.apps.databricks_admin.tests.test_delta_share_snapshot_jobs import (
            _statement_payload,
        )

        require_dns()

        from hub.apps.databricks_admin.client import DatabricksApiClient
        from hub.apps.databricks_admin.delta_sharing_snapshot import (
            _SourceVersion,
            run_snapshot_job,
        )
        from hub.apps.databricks_admin.sql_statements import SqlStatementExecutor

        tenant = _mk_tenant()
        connection = _mk_connection(tenant)
        asset = _mk_asset(tenant, connection)
        _mk_recipient(tenant)

        # The production source reader over a REAL threaded local HTTP
        # server (the statement API's submit answers scripted with real
        # manifests — the 5.4 spine convention, no mocks).
        from hub.apps.databricks_admin.tests._http import RecordingHandler

        RecordingHandler.json_script = [
            json.dumps(
                _statement_payload(
                    state="SUCCEEDED",
                    columns=["version"],
                    rows=[["9"]],
                    statement_id="s-ver",
                )
            ),
            json.dumps(
                _statement_payload(
                    state="SUCCEEDED",
                    columns=["id", "name"],
                    rows=[["1", "alice"]],
                    statement_id="s-data",
                )
            ),
        ]

        def reader(connection, table_ref, tenant_id):
            del connection, table_ref  # the executor owns the transport
            client = DatabricksApiClient(
                base_url=f"http://127.0.0.1:{local_http_server}",
                tenant_id=str(tenant_id),
                credential_config={"token": "dapi-snap"},
                timeout_ms=5000,
                max_retries=1,
                retry_base_delay=0.05,
                retry_max_delay=0.1,
                use_breaker=False,
            )
            executor = SqlStatementExecutor(
                client=client,
                warehouse_id="wh-snap",
                poll_interval_seconds=0.01,
                poll_timeout_seconds=2.0,
            )
            version_result = executor.execute(
                "SELECT COALESCE(MAX(version),0) FROM (DESCRIBE HISTORY cat.schema.t)"
            )
            rows_result = executor.execute("SELECT * FROM cat.schema.t")
            return _SourceVersion(
                version=int(version_result.rows[0][0]),
                columns=rows_result.columns,
                rows=rows_result.rows,
            )

        # The seam swaps to the REAL spine with the local reader — the
        # command's own logic (discovery + freshness + dispatch) is the
        # unit under test, never mocked. The scripted statement API serves
        # exactly THIS test's two submissions, so only the test's own
        # asset rides the real spine; the dirty DB's leaked tenants return
        # the completed-shaped boundary object (their refresh is not this
        # test's subject).
        own_asset = asset

        def real_dispatch(*, asset, **kwargs):
            if asset.id != own_asset.id:
                return _CompletedJob()
            return run_snapshot_job(asset=asset, source_reader=reader, **kwargs)

        monkeypatch.setattr(
            "hub.apps.databricks_admin.management.commands.databricks_delta_share_snapshot"
            ".run_snapshot_job",
            real_dispatch,
        )

        call_command("databricks_delta_share_snapshot")

        from hub.apps.databricks_admin.delta_sharing_service import latest_snapshot
        from hub.apps.jobs.models import Job, JobStatus, JobType
        from hub.apps.tenants.request_tenant import tenant_context

        share, schema, table = _triple(tenant, asset)
        with tenant_context(str(tenant.id)):
            row = latest_snapshot(tenant.id, share=share, schema=schema, table=table)
            job = Job.objects.get(tenant=tenant, type=JobType.DATABRICKS_DELTA_SHARE_SNAPSHOT)
        assert row is not None, "the sweep stamped a real snapshot row"
        assert row.version == 9
        assert row.files, "the snapshot carries its Parquet files manifest"
        assert job.status == JobStatus.COMPLETED
        assert (job.result_json or {}).get("snapshot_id") == str(row.id)

        _TRACKED_BASES.append(
            f"delta-share-snapshots/{share}/{schema}/{table}/v{row.version:020d}/"
        )
