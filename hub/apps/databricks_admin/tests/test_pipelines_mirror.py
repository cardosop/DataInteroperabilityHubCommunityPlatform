"""TDD pins for the DLT pipeline mirror sync (openspec
add-databricks-dlt-pipelines task 10.3) — the delta-diff refresh into
the 10.2 mirror models, the 4.2 jobs_mirror pattern.

The mirror is a READ cache of the Databricks-owned state: the sync lists
the workspace's pipelines (``pipelines.list``, 2.0 — the ``statuses``
array), fetches each pipeline's spec (``pipelines.get`` — the settings +
channel live there, the list's statuses do not carry them), then lists
each pipeline's updates (``pipelines.updates.list``, page_token chains)
and delta-diffs the 10.2 rows — created/updated/unchanged/deleted per
surface, the freshness stamp touched ONLY on change. The Hub NEVER
invents a state: unknown reported states/channels are SKIPPED with a
warning; junk rows and missing identities are skipped; malformed bodies
are classified (the 0.7 discipline); a pipeline deleted between list
and get (a 404) skips the row WITHOUT sweeping an existing one; a
transient 404 on a pipeline's updates list keeps that pipeline's
existing update rows untouched (never a destructive wipe on an error).

No mocks: real Postgres rows (the 313full contract) + the PRODUCTION
client against a REAL threaded local HTTP server with scripted
pipelines envelopes (the 0.5/3.2 convention).
"""

import json
import uuid

import pytest
from django.test import TestCase

from hub.apps.databricks_admin.tests._fixtures import require_dns
from hub.apps.databricks_admin.tests._http import RecordingHandler
from hub.apps.databricks_admin.tests.test_uc_sync import _make_workspace
from hub.apps.databricks_admin.tests.test_views import _activate_billing
from tests.factories import TenantFactory

pytestmark = pytest.mark.django_db(transaction=True)


def _mirror_client(port):
    from hub.apps.databricks_admin.client import DatabricksApiClient

    return DatabricksApiClient(
        base_url=f"http://127.0.0.1:{port}",
        tenant_id="t1",
        credential_config={"token": "dapi-mirror"},
        timeout_ms=5000,
        max_retries=1,
        retry_base_delay=0.05,
        retry_max_delay=0.1,
    )


def _status(pipeline_id="p-1", state="IDLE", name="nightly-dlt"):
    return {"pipeline_id": pipeline_id, "state": state, "name": name}


def _get_payload(pipeline_id="p-1", state="IDLE", name="nightly-dlt", channel="CURRENT"):
    return {
        "pipeline_id": pipeline_id,
        "state": state,
        "name": name,
        "spec": {
            "name": name,
            "edition": "CORE",
            "channel": channel,
            "continuous": False,
            "clusters": [{"label": "default", "num_workers": 0}],
        },
    }


def _update(update_id="u-1", state="COMPLETED", full_refresh=True):
    return {
        "update_id": update_id,
        "state": state,
        "full_refresh": full_refresh,
        "refresh_selection": {"tables": ["bronze_customers"]},
    }


class TestPipelinesMirror(TestCase):
    def setUp(self):
        require_dns()
        self.tenant = TenantFactory.create_tenant()
        _activate_billing(self.tenant)
        self.workspace = _make_workspace(self.tenant, name=f"ws-dlt-{uuid.uuid4().hex[:8]}")
        import http.server
        import threading

        RecordingHandler.script = []
        RecordingHandler.requests = []
        RecordingHandler.json_script = []
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), RecordingHandler)
        self.server = server
        self.port = server.server_address[1]
        self.thread = threading.Thread(target=server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def _sync(self):
        from hub.apps.databricks_admin.pipelines_mirror import refresh_dlt_mirror

        return refresh_dlt_mirror(self.workspace, client=_mirror_client(self.port))

    def test_sync_creates_pipeline_rows_from_reported_statuses(self):
        RecordingHandler.json_script.append(
            json.dumps(
                {"statuses": [_status("p-1"), _status("p-2", state="ACTIVE", name="hourly-dlt")]}
            )
        )
        RecordingHandler.json_script.append(json.dumps(_get_payload("p-1")))
        RecordingHandler.json_script.append(
            json.dumps(_get_payload("p-2", state="ACTIVE", name="hourly-dlt"))
        )
        RecordingHandler.json_script.append(json.dumps({"updates": []}))
        RecordingHandler.json_script.append(json.dumps({"updates": []}))

        counters = self._sync()

        from hub.apps.databricks_admin.models import DatabricksDltPipeline

        assert counters["pipelines"] == {"created": 2, "updated": 0, "unchanged": 0, "deleted": 0}
        rows = list(DatabricksDltPipeline.objects.filter(workspace=self.workspace))
        assert len(rows) == 2
        p1 = next(r for r in rows if r.pipeline_id == "p-1")
        assert p1.name == "nightly-dlt"
        assert p1.state == "IDLE"
        assert p1.channel == "CURRENT"
        assert p1.settings["edition"] == "CORE"

    def test_sync_updates_and_sweeps(self):
        # Run 1: one pipeline.
        RecordingHandler.json_script.append(json.dumps({"statuses": [_status("p-1")]}))
        RecordingHandler.json_script.append(json.dumps(_get_payload("p-1")))
        RecordingHandler.json_script.append(json.dumps({"updates": []}))
        self._sync()
        # Run 2: the name changed; p-1 gone, p-2 arrived.
        RecordingHandler.json_script.append(
            json.dumps({"statuses": [_status("p-2", name="renamed")]})
        )
        RecordingHandler.json_script.append(json.dumps(_get_payload("p-2", name="renamed")))
        RecordingHandler.json_script.append(json.dumps({"updates": []}))
        counters = self._sync()

        from hub.apps.databricks_admin.models import DatabricksDltPipeline

        assert counters["pipelines"] == {"created": 1, "updated": 0, "unchanged": 0, "deleted": 1}
        assert not DatabricksDltPipeline.objects.filter(
            workspace=self.workspace, pipeline_id="p-1"
        ).exists(), (
            "absent-on-the-workspace pipelines leave the mirror — derived, never compensated"
        )
        assert DatabricksDltPipeline.objects.filter(
            workspace=self.workspace, pipeline_id="p-2"
        ).exists()

    def test_unchanged_rows_keep_their_freshness_stamp(self):
        RecordingHandler.json_script.append(json.dumps({"statuses": [_status("p-1")]}))
        RecordingHandler.json_script.append(json.dumps(_get_payload("p-1")))
        RecordingHandler.json_script.append(json.dumps({"updates": []}))
        self._sync()
        from hub.apps.databricks_admin.models import DatabricksDltPipeline

        first = DatabricksDltPipeline.objects.get(workspace=self.workspace, pipeline_id="p-1")
        stamp = first.synced_at

        RecordingHandler.json_script.append(json.dumps({"statuses": [_status("p-1")]}))
        RecordingHandler.json_script.append(json.dumps(_get_payload("p-1")))
        RecordingHandler.json_script.append(json.dumps({"updates": []}))
        counters = self._sync()

        assert counters["pipelines"]["unchanged"] == 1
        first.refresh_from_db()
        assert first.synced_at == stamp, "the freshness stamp is touched ONLY on change"

    def test_an_unknown_reported_state_is_skipped_with_a_warning(self):
        RecordingHandler.json_script.append(
            json.dumps({"statuses": [_status("p-1", state="WARPING")]})
        )
        RecordingHandler.json_script.append(json.dumps(_get_payload("p-1", state="WARPING")))
        RecordingHandler.json_script.append(json.dumps({"updates": []}))

        with self.assertLogs(
            "hub.apps.databricks_admin.pipelines_mirror", level="WARNING"
        ) as captured:
            counters = self._sync()

        from hub.apps.databricks_admin.models import DatabricksDltPipeline

        assert not DatabricksDltPipeline.objects.filter(workspace=self.workspace).exists(), (
            "a state the vocabulary does not know is NEVER invented into a row"
        )
        assert counters["pipelines"]["created"] == 0
        assert any(getattr(record, "state", None) == "WARPING" for record in captured.records), (
            "the skip warning must carry the offending state (the extra-attrs convention)"
        )

    def test_a_pipeline_deleted_between_list_and_get_never_sweeps_an_existing_row(self):
        # Run 1: p-1 mirrored.
        RecordingHandler.json_script.append(json.dumps({"statuses": [_status("p-1")]}))
        RecordingHandler.json_script.append(json.dumps(_get_payload("p-1")))
        RecordingHandler.json_script.append(json.dumps({"updates": []}))
        self._sync()
        # Run 2: still listed (the list body is scripted again — the
        # status script and the body script are separate queues), but the
        # GET 404s (deleted in flight).
        RecordingHandler.json_script.append(json.dumps({"statuses": [_status("p-1")]}))
        RecordingHandler.script.append(200)  # list
        RecordingHandler.script.append(404)  # get
        counters = self._sync()

        from hub.apps.databricks_admin.models import DatabricksDltPipeline

        assert counters["pipelines"]["deleted"] == 0
        assert DatabricksDltPipeline.objects.filter(
            workspace=self.workspace, pipeline_id="p-1"
        ).exists(), "a 404 between list and get skips the row WITHOUT sweeping the existing one"

    def test_update_rows_are_mirrored_per_pipeline(self):
        RecordingHandler.json_script.append(json.dumps({"statuses": [_status("p-1")]}))
        RecordingHandler.json_script.append(json.dumps(_get_payload("p-1")))
        RecordingHandler.json_script.append(
            json.dumps(
                {
                    "updates": [
                        _update("u-1", "COMPLETED"),
                        _update("u-2", "FAILED", full_refresh=False),
                    ]
                }
            )
        )
        counters = self._sync()

        from hub.apps.databricks_admin.models import (
            DatabricksDltPipeline,
            DatabricksDltPipelineUpdate,
        )

        pipeline = DatabricksDltPipeline.objects.get(workspace=self.workspace, pipeline_id="p-1")
        rows = list(DatabricksDltPipelineUpdate.objects.filter(pipeline=pipeline))
        assert counters["updates"] == {"created": 2, "updated": 0, "unchanged": 0, "deleted": 0}
        assert len(rows) == 2
        u1 = next(r for r in rows if r.update_id == "u-1")
        assert u1.state == "COMPLETED"
        assert u1.full_refresh is True
        assert u1.refresh_selection == {"tables": ["bronze_customers"]}
        u2 = next(r for r in rows if r.update_id == "u-2")
        assert u2.state == "FAILED"
        assert u2.full_refresh is False

    def test_updates_pagination_follows_page_tokens(self):
        RecordingHandler.json_script.append(json.dumps({"statuses": [_status("p-1")]}))
        RecordingHandler.json_script.append(json.dumps(_get_payload("p-1")))
        RecordingHandler.json_script.append(
            json.dumps({"updates": [_update("u-1")], "next_page_token": "tok-9"})
        )
        RecordingHandler.json_script.append(json.dumps({"updates": [_update("u-2")]}))
        self._sync()

        from hub.apps.databricks_admin.models import (
            DatabricksDltPipeline,
            DatabricksDltPipelineUpdate,
        )

        pipeline = DatabricksDltPipeline.objects.get(workspace=self.workspace, pipeline_id="p-1")
        ids = set(
            DatabricksDltPipelineUpdate.objects.filter(pipeline=pipeline).values_list(
                "update_id", flat=True
            )
        )
        assert ids == {"u-1", "u-2"}
        assert "page_token=tok-9" in RecordingHandler.requests[-1]["path"], (
            "the second page request carries the reported token"
        )

    def test_a_transient_updates_404_keeps_existing_update_rows(self):
        RecordingHandler.json_script.append(json.dumps({"statuses": [_status("p-1")]}))
        RecordingHandler.json_script.append(json.dumps(_get_payload("p-1")))
        RecordingHandler.json_script.append(json.dumps({"updates": [_update("u-1")]}))
        self._sync()
        # Run 2: the updates list 404s (pipeline mid-deletion) — the
        # status script queues the 404 on the THIRD request (list, get
        # are 200; updates is the 404).
        RecordingHandler.json_script.append(json.dumps({"statuses": [_status("p-1")]}))
        RecordingHandler.json_script.append(json.dumps(_get_payload("p-1")))
        RecordingHandler.script.append(200)  # list
        RecordingHandler.script.append(200)  # get
        RecordingHandler.script.append(404)  # updates list
        counters = self._sync()

        from hub.apps.databricks_admin.models import (
            DatabricksDltPipeline,
            DatabricksDltPipelineUpdate,
        )

        pipeline = DatabricksDltPipeline.objects.get(workspace=self.workspace, pipeline_id="p-1")
        assert DatabricksDltPipelineUpdate.objects.filter(pipeline=pipeline).count() == 1, (
            "a transient 404 must never wipe the updates — the sweep is skipped on errors"
        )
        assert counters["updates"]["deleted"] == 0

    def test_junk_statuses_are_skipped(self):
        RecordingHandler.json_script.append(
            json.dumps({"statuses": ["junk", {"state": "IDLE", "name": "no-id"}, _status("p-1")]})
        )
        RecordingHandler.json_script.append(json.dumps(_get_payload("p-1")))
        RecordingHandler.json_script.append(json.dumps({"updates": []}))

        with self.assertLogs(
            "hub.apps.databricks_admin.pipelines_mirror", level="WARNING"
        ) as captured:
            counters = self._sync()

        assert counters["pipelines"]["created"] == 1, "only the well-formed status mirrors"
        assert any("junk" in message for message in captured.output)

    def test_malformed_list_payloads_are_classified(self):
        RecordingHandler.json_script.append(json.dumps({"statuses": "bogus"}))
        from hub.apps.databricks_admin.client import DatabricksApiError

        with pytest.raises(DatabricksApiError):
            self._sync()
