"""TDD pins for the P12 acceptance contract (openspec
add-databricks-ml-assets task 12.8) — the phase's acceptance line,
closed without duplication.

The coverage audit (before any pin): the title's four elements map to
the phase's suites — "MLflow client mocks" is SUPERSEDED by the
STRONGER real-transport pins (the 12.2 suite's version-log pins + the
12.6 views suite + the 12.7 journey pin, all on the PRODUCTION client
over a REAL local HTTP server — the 12.1 decision, the P3
statement-executor convention, never a live workspace); "alias CRUD"'s
create/delete/read legs are pinned by the 12.2 suite (set/remove +
the row's aliases list) and the READ leg of the acceptance round-trip
(register → version-log → alias-set with the three audit rows) is the
12.7 journey pin's (`TestJOURNEYDB019RegisterUCModel`); "tag
convention" is the 12.3 suite (9 pins); "boundary lint" is the 12.5
suite (5 pins). The genuinely UNPINNED legs this file closes:

- The CRUD's UPDATE leg: setting the SAME alias to a new version
  REPLACES the entry (exactly one entry carrying the new version) —
  never an append (the double-entry defect class).
- The alias round-trip's THEN clause at the reconcile end: the P1
  sync's models branch captures the payload's aliases (absent/malformed
  → [], the never-invent discipline) and the `_FIELD_MAPS` entry
  carries the alias key — the mirror reconciles on the next sync.

No mocks: the REAL service over a REAL threaded local HTTP server (the
wire paths/bodies asserted), real Postgres rows, the REAL sync
`_normalize`/`_FIELD_MAPS`.
"""

from __future__ import annotations

import json
import uuid

import pytest
from django.test import TestCase

from hub.apps.databricks_admin.tests._fixtures import require_dns
from hub.apps.databricks_admin.tests._http import RecordingHandler
from hub.apps.databricks_admin.tests.test_ml_assets_versions import _client, _server
from hub.apps.databricks_admin.tests.test_uc_sync import _make_workspace
from tests.factories import TenantFactory

pytestmark = pytest.mark.django_db(transaction=True)


class TestAliasRePoint(TestCase):
    """The CRUD's Update leg: the same alias re-pointed REPLACES the
    entry — exactly one entry carrying the new version, never an
    append."""

    def setUp(self):
        require_dns()
        self.tenant = TenantFactory.create_tenant()
        self.workspace = _make_workspace(self.tenant, name=f"ws-repoint-{uuid.uuid4().hex[:8]}")
        from hub.apps.databricks_admin.models import UCCatalog, UCModel, UCSchema

        catalog = UCCatalog.objects.create(workspace=self.workspace, name="ml_catalog")
        schema = UCSchema.objects.create(catalog=catalog, name="ml_schema")
        self.model = UCModel.objects.create(schema=schema, name="churn_model")

    def test_setting_the_same_alias_to_a_new_version_replaces_the_entry(self):
        from hub.apps.databricks_admin.ml_assets import set_model_alias

        server, port = _server()
        self.addCleanup(server.shutdown)
        RecordingHandler.script = [200, 200]
        RecordingHandler.json_script = [
            json.dumps({"alias": "prod", "version_num": 1}),
            json.dumps({"alias": "prod", "version_num": 2}),
        ]

        client = _client(port, str(self.tenant.id))
        set_model_alias(client, model=self.model, alias="prod", version=1)
        set_model_alias(client, model=self.model, alias="prod", version=2)

        self.model.refresh_from_db()
        assert self.model.aliases == [{"alias_name": "prod", "version_num": 2}], (
            "the re-point replaces the entry — exactly one, the NEW version"
        )
        assert [r["method"] for r in RecordingHandler.requests] == ["PUT", "PUT"]
        assert json.loads(RecordingHandler.requests[1]["body"]) == {"version_num": 2}


class TestAliasSyncReconcile:
    """The alias round-trip's THEN clause at the reconcile end: the P1
    sync's models branch captures the payload's aliases and the field
    map carries the key — the mirror reconciles on the next sync."""

    def test_the_sync_models_branch_captures_aliases_and_never_invents(self):
        from hub.apps.databricks_admin.uc_sync import _normalize

        assert _normalize(
            "models",
            {"name": "m", "aliases": [{"alias_name": "champion", "version_num": 2}]},
        )["aliases"] == [{"alias_name": "champion", "version_num": 2}]
        assert _normalize("models", {"name": "no_aliases"})["aliases"] == []
        assert _normalize("models", {"name": "junk", "aliases": "bogus"})["aliases"] == []

    def test_the_field_maps_carry_the_aliases_field(self):
        from hub.apps.databricks_admin.models import UCModel
        from hub.apps.databricks_admin.uc_sync import _FIELD_MAPS, _NATURAL_KEY

        assert _NATURAL_KEY[UCModel] == "name"
        assert UCModel in _FIELD_MAPS
        assert _FIELD_MAPS[UCModel][1]["aliases"] == ("aliases", [])
