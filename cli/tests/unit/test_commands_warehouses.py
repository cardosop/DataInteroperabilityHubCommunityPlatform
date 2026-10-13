"""
Unit tests for Warehouses CLI commands.

Tests: connections (list, get, create, update, delete, test), schemas, queries, acl.
"""

from datahub_cli.main import cli
from tests.fixtures.test_data import fresh_id

# Unique per test process (and per xdist worker) so a static literal
# can never collide across parallel runs — Phase 216.X.2.
ASSET_ID = fresh_id("asset")


class TestWarehouseConnectionsList:
    """Test warehouse connections list command"""

    def test_list_connections(self, runner, mock_api_client):
        """Test listing warehouse connections"""
        mock_api_client.get.return_value = {
            "results": [
                {"id": "wh-1", "name": "prod-db", "db_type": "postgresql", "status": "connected"}
            ]
        }

        result = runner.invoke(cli, ["warehouses", "connections", "list"])

        assert result.exit_code == 0
        assert "prod-db" in result.output
        mock_api_client.get.assert_called_once_with("warehouses/connections/")

    def test_list_connections_empty(self, runner, mock_api_client):
        """Test listing when no connections exist"""
        mock_api_client.get.return_value = {"results": [], "count": 0}

        result = runner.invoke(cli, ["warehouses", "connections", "list"])

        assert result.exit_code == 0
        assert "No connections" in result.output

    def test_list_connections_json(self, runner, mock_api_client):
        """Test listing in JSON format"""
        mock_api_client.get.return_value = {"results": []}

        result = runner.invoke(cli, ["warehouses", "connections", "list", "--format", "json"])

        assert result.exit_code == 0


class TestWarehouseConnectionsGet:
    """Test warehouse connections get command"""

    def test_get_connection(self, runner, mock_api_client):
        """Test getting a connection by ID"""
        mock_api_client.get.return_value = {
            "id": "wh-1",
            "name": "prod-db",
            "db_type": "postgresql",
        }

        result = runner.invoke(cli, ["warehouses", "connections", "get", "wh-1"])

        assert result.exit_code == 0
        assert "prod-db" in result.output


class TestWarehouseConnectionsTest:
    """Test warehouse connections test command"""

    def test_test_connection_success(self, runner, mock_api_client):
        """Test testing a connection"""
        mock_api_client.post.return_value = {"status": "ok", "latency_ms": 45}

        result = runner.invoke(cli, ["warehouses", "connections", "test", "wh-1"])

        assert result.exit_code == 0
        assert "ok" in result.output

    def test_test_connection_failure(self, runner, mock_api_client):
        """Test testing a failing connection"""
        mock_api_client.post.return_value = {"status": "error", "message": "Timeout"}

        result = runner.invoke(cli, ["warehouses", "connections", "test", "wh-1"])

        assert result.exit_code == 0
        assert "error" in result.output


class TestWarehouseSchemas:
    """Test warehouse schema reflection command.

    The backend exposes no ``schemas`` route: schema reflection lives at
    ``GET /api/v1/warehouses/connections/{id}/schema/?table=<name>``
    (``reflect_schema``), which the CLI surfaces as
    ``warehouses connections schema <id> --table <name>``.
    """

    def test_list_schemas(self, runner, mock_api_client):
        """Test reflecting the schema of a warehouse table"""
        mock_api_client.get.return_value = {
            "connection_id": "wh-1",
            "table": "orders",
            "warehouse_type": "SNOWFLAKE",
            "columns": [
                {"name": "public_id", "data_type": "VARCHAR", "nullable": False, "comment": None},
                {"name": "amount", "data_type": "NUMBER", "nullable": True, "comment": None},
            ],
            "reflected_at": "2026-08-27T00:00:00Z",
        }

        result = runner.invoke(
            cli, ["warehouses", "connections", "schema", "wh-1", "--table", "orders"]
        )

        assert result.exit_code == 0
        assert "public" in result.output

    def test_refresh_schema(self, runner, mock_api_client):
        """Test re-reflecting schema (reflection is live — re-invoking refreshes)"""
        mock_api_client.get.return_value = {
            "connection_id": "wh-1",
            "table": "events",
            "warehouse_type": "SNOWFLAKE",
            "columns": [
                {
                    "name": "analytics_events",
                    "data_type": "VARCHAR",
                    "nullable": True,
                    "comment": None,
                }
            ],
            "reflected_at": "2026-08-27T00:05:00Z",
        }

        result = runner.invoke(
            cli, ["warehouses", "connections", "schema", "wh-1", "--table", "events"]
        )

        assert result.exit_code == 0
        assert "analytics" in result.output
        mock_api_client.get.assert_called_once_with(
            "warehouses/connections/wh-1/schema/?table=events"
        )


class TestWarehouseQueries:
    """Test warehouse live queries command.

    The backend route is ``GET /api/v1/warehouses/query/``
    (``LiveQueryViewSet``), which queries a LIVE_QUERY asset by
    ``asset_id`` with optional ``limit``/``cursor`` — the CLI surfaces it
    as ``warehouses query --asset-id <id>``.
    """

    def test_run_query(self, runner, mock_api_client):
        """Test running a live query"""
        mock_api_client.get.return_value = {
            "rows": [["1", "test"]],
            "cursor": None,
            "row_count": 1,
            "cached": False,
        }

        result = runner.invoke(cli, ["warehouses", "query", "--asset-id", ASSET_ID])

        assert result.exit_code == 0
        assert "test" in result.output
        mock_api_client.get.assert_called_once_with(
            "warehouses/query/", params={"asset_id": ASSET_ID, "limit": 100}
        )


class TestWarehouseACL:
    """Test warehouse ACL commands"""

    def test_list_acl(self, runner, mock_api_client):
        """Test listing ACL entries"""
        mock_api_client.get.return_value = {
            "results": [{"id": "acl-1", "user": "user@example.com", "role": "VIEWER"}]
        }

        result = runner.invoke(cli, ["warehouses", "acls", "list"])

        assert result.exit_code == 0
        assert "VIEWER" in result.output


class TestFabricatedShareGroupRemoved:
    """5.5 — the `warehouses share` group targeted the removed
    SessionAuth stub; the native protocol surface is bearer-token
    only (no session CLI consumer), so the group is gone (design D6 —
    removed, not migrated)."""

    def test_share_group_is_not_registered(self, runner):
        result = runner.invoke(cli, ["warehouses", "share", "--help"])
        assert result.exit_code != 0

    def test_share_group_absent_from_help(self, runner):
        result = runner.invoke(cli, ["warehouses", "--help"])
        assert result.exit_code == 0
        assert "share" not in result.output
