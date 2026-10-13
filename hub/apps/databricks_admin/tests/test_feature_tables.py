"""TDD pins for the P12 feature-table tag convention (openspec
add-databricks-ml-assets task 12.3, design D4) — a feature table is a
UC table carrying the ``feature_store`` tag; the tag set/read rides the
UC REST entity-tag-assignments surface (the Databricks-documented
2.1 family: POST create / GET list / DELETE per tag key), and the P1
mirror's table rows annotate the tag on the next sync.

No mocks: the PRODUCTION client against a REAL threaded local HTTP
server (the wire paths/bodies asserted IN ORDER, the 12.2
convention), real Postgres rows for the mirror annotation, and the
never-invent discipline (absent/malformed tags → [], the P1 sync's).
"""

import http.server
import json
import threading
import uuid

import pytest

from hub.apps.databricks_admin.tests._fixtures import require_dns
from hub.apps.databricks_admin.tests._http import RecordingHandler
from hub.apps.databricks_admin.tests.test_uc_sync import _make_workspace
from tests.factories import TenantFactory

pytestmark = pytest.mark.django_db(transaction=True)


def _client(port, tenant_id):
    from hub.apps.databricks_admin.client import DatabricksApiClient

    return DatabricksApiClient(
        base_url=f"http://127.0.0.1:{port}",
        tenant_id=tenant_id,
        credential_config={"token": "dapi-feature"},
        timeout_ms=5000,
        max_retries=1,
        retry_base_delay=0.05,
        retry_max_delay=0.1,
        use_breaker=False,
        backoff_waiter=lambda _attempt: None,
    )


class TestFeatureTableTagPins:
    """The entity-tag-assignments operations are pinned at 2.1."""

    def test_the_tag_operations_are_pinned_and_versioned(self):
        from hub.apps.databricks_admin.api_paths import API_PATH_VERSIONS, API_PATHS

        expected = {
            "uc.tag_assignments.create": "/api/2.1/unity-catalog/entity-tag-assignments",
            "uc.tag_assignments.list": (
                "/api/2.1/unity-catalog/entity-tag-assignments/{entity_type}/{entity_name}/tags"
            ),
            "uc.tag_assignments.delete": (
                "/api/2.1/unity-catalog/entity-tag-assignments/"
                "{entity_type}/{entity_name}/tags/{tag_key}"
            ),
        }
        for operation, path in expected.items():
            assert API_PATHS.get(operation) == path, f"{operation} must pin {path}"
            assert API_PATH_VERSIONS.get(operation) == "2.1", (
                f"{operation} must document the 2.1 version"
            )


class TestMarkFeatureTable:
    """The feature_store tag creation rides the documented POST."""

    def _server(self):
        RecordingHandler.script = []
        RecordingHandler.requests = []
        RecordingHandler.json_script = []
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), RecordingHandler)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return port, server, thread

    def test_mark_posts_the_convention_exactly(self):
        port, server, thread = self._server()
        try:
            RecordingHandler.json_script = [
                json.dumps(
                    {
                        "entity_type": "tables",
                        "entity_name": "main.default.customers",
                        "tag_key": "feature_store",
                        "tag_value": "true",
                    }
                )
            ]
            from hub.apps.databricks_admin.feature_tables import mark_feature_table

            assignment = mark_feature_table(_client(port, "t1"), "main.default.customers")
            assert assignment["tag_key"] == "feature_store"
            recorded = RecordingHandler.requests[-1]
            assert recorded["method"] == "POST"
            assert recorded["path"] == "/api/2.1/unity-catalog/entity-tag-assignments"
            assert json.loads(recorded["body"]) == {
                "entity_type": "tables",
                "entity_name": "main.default.customers",
                "tag_key": "feature_store",
                "tag_value": "true",
            }
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_mark_shape_discipline_runs_before_any_call(self):
        port, server, thread = self._server()
        try:
            from hub.apps.databricks_admin.feature_tables import mark_feature_table

            with pytest.raises(ValueError, match="full_name"):
                mark_feature_table(_client(port, "t1"), "   ")
            assert RecordingHandler.requests == [], "a blank full_name refuses BEFORE any API call"
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_a_workspace_rejection_propagates_classified(self):
        port, server, thread = self._server()
        try:
            RecordingHandler.script = [403]
            RecordingHandler.json_script = [json.dumps({"error_code": "DENIED"})]
            from hub.apps.databricks_admin.client import DatabricksApiError
            from hub.apps.databricks_admin.feature_tables import mark_feature_table

            with pytest.raises(DatabricksApiError):
                mark_feature_table(_client(port, "t1"), "main.default.customers")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


class TestUnmarkFeatureTable:
    """The tag removal rides the documented DELETE; a missing tag is
    already-unmarked (idempotent, never a raise)."""

    def test_unmark_deletes_the_tag_key_exactly(self):
        RecordingHandler.script = []
        RecordingHandler.requests = []
        RecordingHandler.json_script = [""]
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), RecordingHandler)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            from hub.apps.databricks_admin.feature_tables import unmark_feature_table

            unmark_feature_table(_client(port, "t1"), "main.default.customers")
            recorded = RecordingHandler.requests[-1]
            assert recorded["method"] == "DELETE"
            assert recorded["path"] == (
                "/api/2.1/unity-catalog/entity-tag-assignments/"
                "tables/main.default.customers/tags/feature_store"
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_unmark_is_idempotent_on_a_missing_assignment(self):
        RecordingHandler.script = [404]
        RecordingHandler.requests = []
        RecordingHandler.json_script = [json.dumps({"error_code": "TAG_NOT_FOUND"})]
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), RecordingHandler)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            from hub.apps.databricks_admin.feature_tables import unmark_feature_table

            # No raise — an already-unmarked table is the goal state.
            unmark_feature_table(_client(port, "t1"), "main.default.customers")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


class TestListFeatureTableTags:
    """The tag read rides the documented list with the page chain."""

    def test_list_follows_the_page_chain_with_the_repeating_token_guard(self):
        RecordingHandler.script = []
        RecordingHandler.requests = []
        RecordingHandler.json_script = [
            json.dumps(
                {
                    "tag_assignments": [
                        {
                            "entity_type": "tables",
                            "entity_name": "main.default.customers",
                            "tag_key": "feature_store",
                            "tag_value": "true",
                        }
                    ],
                    "next_page_token": "stuck",
                }
            ),
            json.dumps({"tag_assignments": [], "next_page_token": "stuck"}),
        ]
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), RecordingHandler)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            from hub.apps.databricks_admin.client import DatabricksApiError
            from hub.apps.databricks_admin.feature_tables import table_feature_tags

            with pytest.raises(DatabricksApiError) as excinfo:
                table_feature_tags(_client(port, "t1"), "main.default.customers")
            assert "repeating" in str(excinfo.value).lower(), (
                "a repeating token fails classified, never hangs"
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


class TestMirrorAnnotation:
    """The P1 sync annotates the tag on the mirror row."""

    def test_the_sync_captures_the_tables_tags(self):
        require_dns()
        tenant = TenantFactory.create_tenant()
        workspace = _make_workspace(tenant, name=f"ws-ft-{uuid.uuid4().hex[:8]}")
        from hub.apps.databricks_admin.models import (
            UCCatalog,
            UCSchema,
            UCTable,
        )

        catalog = UCCatalog.objects.create(workspace=workspace, name="main")
        schema = UCSchema.objects.create(catalog=catalog, name="default")

        # The REAL normalize path on a table payload carrying tags.
        from hub.apps.databricks_admin.uc_sync import _normalize

        row = _normalize(
            "tables",
            {
                "name": "customers",
                "full_name": "main.default.customers",
                "catalog_name": "main",
                "schema_name": "default",
                "table_type": "MANAGED",
                "tags": [{"key": "feature_store", "value": "true"}],
            },
        )
        assert row["tags"] == [{"key": "feature_store", "value": "true"}]

        # The model carries the mirror-relevant fields only — the
        # catalog/schema names ride the FK chain, never the row.
        table = UCTable.objects.create(
            schema=schema,
            name="customers",
            full_name="main.default.customers",
            comment=row["comment"],
            table_type=row["table_type"],
            storage_location=row["storage_location"],
            columns=row["columns"],
            owner=row["owner"],
            tags=row["tags"],
        )
        from hub.apps.databricks_admin.feature_tables import is_feature_table

        assert is_feature_table(table) is True

    def test_absent_or_malformed_tags_never_invent(self):
        from hub.apps.databricks_admin.uc_sync import _normalize

        assert _normalize("tables", {"name": "no_tags"})["tags"] == []
        assert _normalize("tables", {"name": "junk", "tags": "bogus"})["tags"] == []

        require_dns()
        tenant = TenantFactory.create_tenant()
        workspace = _make_workspace(tenant, name=f"ws-ft2-{uuid.uuid4().hex[:8]}")
        from hub.apps.databricks_admin.models import UCCatalog, UCSchema, UCTable

        catalog = UCCatalog.objects.create(workspace=workspace, name="main")
        schema = UCSchema.objects.create(catalog=catalog, name="default")
        table = UCTable.objects.create(schema=schema, name="plain", tags=[])
        from hub.apps.databricks_admin.feature_tables import is_feature_table

        assert is_feature_table(table) is False
