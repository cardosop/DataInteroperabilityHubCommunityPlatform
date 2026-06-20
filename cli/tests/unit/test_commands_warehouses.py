"""
Unit tests for Warehouses CLI commands.

Tests: connections (list, get, create, update, delete, test), schemas, queries, acl.
"""

from datahub_cli.main import cli


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
    """Test warehouse schemas command"""

    def test_list_schemas(self, runner, mock_api_client):
        """Test listing schemas"""
        mock_api_client.get.return_value = {"schemas": ["public", "analytics", "staging"]}

        result = runner.invoke(cli, ["warehouses", "schemas", "list", "--connection-id", "wh-1"])

        assert result.exit_code == 0
        assert "public" in result.output

    def test_refresh_schema(self, runner, mock_api_client):
        """Test refreshing schema cache"""
        mock_api_client.post.return_value = {"status": "refreshed", "tables_found": 42}

        result = runner.invoke(cli, ["warehouses", "schemas", "refresh", "--connection-id", "wh-1"])

        assert result.exit_code == 0
        assert "42" in result.output


class TestWarehouseQueries:
    """Test warehouse live queries command"""

    def test_run_query(self, runner, mock_api_client):
        """Test running a live query"""
        mock_api_client.post.return_value = {
            "columns": ["id", "name"],
            "rows": [["1", "test"]],
            "row_count": 1,
        }

        result = runner.invoke(
            cli, ["warehouses", "queries", "run", "--connection-id", "wh-1", "--sql", "SELECT 1"]
        )

        assert result.exit_code == 0
        assert "test" in result.output


class TestWarehouseACL:
    """Test warehouse ACL commands"""

    def test_list_acl(self, runner, mock_api_client):
        """Test listing ACL entries"""
        mock_api_client.get.return_value = {
            "results": [{"id": "acl-1", "principal": "user@example.com", "role": "reader"}]
        }

        result = runner.invoke(cli, ["warehouses", "acl", "list", "--connection-id", "wh-1"])

        assert result.exit_code == 0
        assert "reader" in result.output
