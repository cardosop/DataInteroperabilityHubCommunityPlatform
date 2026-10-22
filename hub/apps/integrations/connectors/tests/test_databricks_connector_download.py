"""
Unit tests for Databricks connector download operations.

Tests download_resource and helper methods.
"""

from unittest.mock import Mock, patch

from django.test import TestCase

from hub.apps.core.services.base import NotFoundError
from hub.apps.integrations.connectors.databricks_connector import DatabricksConnector



# P3-2b: the DATABRICKS_MARKETPLACE connector TYPE registration lives in
# the databricks_admin estate (its apps.py ready()) — absent from the
# core-only public tree, the factory lookup returns None. Excluded from
# the core CI's test set; the private full suite runs them.
pytestmark = [pytest.mark.requires_estate]

class TestDatabricksConnectorDownloadResource(TestCase):
    """Test download_resource method."""

    def setUp(self):
        """Set up test fixtures."""
        from hub.apps.core.resilience.circuit_breaker import reset_circuit_breaker_by_name

        reset_circuit_breaker_by_name("databricks-connector")
        self.connector = DatabricksConnector(
            host="https://test-workspace.cloud.databricks.com", token="test-token"
        )

    @patch.object(DatabricksConnector, "_consume_share")
    @patch.object(DatabricksConnector, "_create_catalog_from_share")
    @patch.object(DatabricksConnector, "_request_with_retry")
    @patch.object(DatabricksConnector, "_download_table")
    def test_download_resource_share_name(
        self, mock_download_table, mock_request, mock_create_catalog, mock_consume
    ):
        """Test download_resource with share name."""
        # Mock consume share
        mock_consume.return_value = {"name": "test_share_recipient", "status": "active"}

        # Mock create catalog
        mock_create_catalog.return_value = "test_share_catalog"

        # Mock schemas response
        mock_schemas_response = Mock()
        mock_schemas_response.json.return_value = {
            "schemas": [
                {"full_name": "test_share_catalog.schema1"},
                {"full_name": "test_share_catalog.schema2"},
            ]
        }
        mock_schemas_response.status_code = 200

        # Mock tables response
        mock_tables_response = Mock()
        mock_tables_response.json.return_value = {
            "tables": [
                {"full_name": "test_share_catalog.schema1.table1"},
                {"full_name": "test_share_catalog.schema2.table2"},
            ]
        }
        mock_tables_response.status_code = 200

        # Mock request_with_retry to return different responses
        def request_side_effect(method, path, **kwargs):
            if "schemas" in path:
                return mock_schemas_response
            elif "tables" in path:
                return mock_tables_response
            return Mock(status_code=200, json=dict)

        mock_request.side_effect = request_side_effect

        # Mock _download_table to raise NotImplementedError (expected behavior)
        mock_download_table.side_effect = NotImplementedError("SQL execution requires setup")

        # _download_table raises NotImplementedError as SQL execution requires setup.
        # This propagates through download_resource so callers know the feature
        # is genuinely unimplemented rather than masking it as ConnectionError.
        with self.assertRaises(NotImplementedError) as context:
            self.connector.download_resource("test_share", "/tmp/test.csv")
        # Verify the error message indicates SQL execution requires setup
        assert "SQL execution" in str(context.exception)

        # Verify helper methods were called
        mock_consume.assert_called_once_with("test_share")
        mock_create_catalog.assert_called_once_with("test_share")

    @patch.object(DatabricksConnector, "_consume_share")
    def test_download_resource_share_not_found(self, mock_consume):
        """Test download_resource when share is not found."""
        mock_consume.side_effect = NotFoundError("Share not found")

        with self.assertRaises(NotFoundError):
            self.connector.download_resource("nonexistent_share", "/tmp/test.csv")

    @patch.object(DatabricksConnector, "_consume_share")
    @patch.object(DatabricksConnector, "_create_catalog_from_share")
    def test_download_resource_permission_denied(self, mock_create_catalog, mock_consume):
        """Test download_resource when permission is denied."""
        mock_consume.return_value = {"name": "test_share_recipient"}
        mock_create_catalog.side_effect = PermissionError("Permission denied")

        with self.assertRaises(PermissionError):
            self.connector.download_resource("test_share", "/tmp/test.csv")

    def test_download_resource_invalid_resource_id(self):
        """Test download_resource with invalid resource_id format."""
        with self.assertRaises(ValueError):
            self.connector.download_resource("invalid.format", "/tmp/test.csv")


class TestDatabricksConnectorConsumeShare(TestCase):
    """Test _consume_share helper method."""

    def setUp(self):
        """Set up test fixtures."""
        from hub.apps.core.resilience.circuit_breaker import reset_circuit_breaker_by_name

        reset_circuit_breaker_by_name("databricks-connector")
        self.connector = DatabricksConnector(
            host="https://test-workspace.cloud.databricks.com", token="test-token"
        )

    @patch.object(DatabricksConnector, "_get_share_details")
    @patch.object(DatabricksConnector, "_request_with_retry")
    def test_consume_share_success(self, mock_request, mock_get_details):
        """Test _consume_share when share exists."""
        mock_get_details.return_value = {"name": "test_share"}

        # Mock recipients response
        mock_response = Mock()
        mock_response.json.return_value = {
            "recipients": [{"name": "test_share_recipient", "share_name": "test_share"}]
        }
        mock_request.return_value = mock_response

        result = self.connector._consume_share("test_share")

        assert result is not None
        assert "name" in result

    @patch.object(DatabricksConnector, "_get_share_details")
    def test_consume_share_not_found(self, mock_get_details):
        """Test _consume_share when share is not found."""
        mock_get_details.side_effect = NotFoundError("Share not found")

        with self.assertRaises(NotFoundError):
            self.connector._consume_share("nonexistent_share")


class TestDatabricksConnectorCreateCatalog(TestCase):
    """Test _create_catalog_from_share helper method."""

    def setUp(self):
        """Set up test fixtures."""
        from hub.apps.core.resilience.circuit_breaker import reset_circuit_breaker_by_name

        reset_circuit_breaker_by_name("databricks-connector")
        self.connector = DatabricksConnector(
            host="https://test-workspace.cloud.databricks.com", token="test-token"
        )

    @patch.object(DatabricksConnector, "_request_with_retry")
    def test_create_catalog_from_share_exists(self, mock_request):
        """Test _create_catalog_from_share when catalog already exists."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_request.return_value = mock_response

        result = self.connector._create_catalog_from_share("test_share")

        assert result == "test_share_catalog"

    @patch.object(DatabricksConnector, "_request_with_retry")
    def test_create_catalog_from_share_new(self, mock_request):
        """Test _create_catalog_from_share when catalog doesn't exist."""
        # First call (check existence) returns 404, second call (create) succeeds
        mock_response_404 = Mock()
        mock_response_404.status_code = 404

        mock_request.side_effect = [mock_response_404]

        result = self.connector._create_catalog_from_share("test_share")

        assert result == "test_share_catalog"


class TestDatabricksConnectorExtractSchema(TestCase):
    """Test _extract_schema_from_table helper method."""

    def setUp(self):
        """Set up test fixtures."""
        from hub.apps.core.resilience.circuit_breaker import reset_circuit_breaker_by_name

        reset_circuit_breaker_by_name("databricks-connector")
        self.connector = DatabricksConnector(
            host="https://test-workspace.cloud.databricks.com", token="test-token"
        )

    @patch.object(DatabricksConnector, "_request_with_retry")
    def test_extract_schema_from_table_success(self, mock_request):
        """Test _extract_schema_from_table with valid table."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "columns": [
                {"name": "col1", "type_name": "STRING", "comment": "Column 1", "nullable": True},
                {"name": "col2", "type_name": "INT", "comment": "Column 2", "nullable": False},
            ]
        }
        mock_request.return_value = mock_response

        result = self.connector._extract_schema_from_table("catalog.schema.table")

        assert "schema" in result
        assert "fields" in result["schema"]
        assert len(result["schema"]["fields"]) == 2
        assert result["schema"]["fields"][0]["name"] == "col1"
        assert result["schema"]["fields"][0]["type"] == "string"
        assert result["schema"]["fields"][1]["type"] == "number"

    @patch.object(DatabricksConnector, "_request_with_retry")
    def test_extract_schema_from_table_not_found(self, mock_request):
        """Test _extract_schema_from_table when table is not found."""
        import httpx

        mock_response = Mock()
        mock_response.status_code = 404
        mock_error = httpx.HTTPStatusError("Not found", request=Mock(), response=mock_response)
        mock_request.side_effect = mock_error

        with self.assertRaises(NotFoundError) as context:
            self.connector._extract_schema_from_table("catalog.schema.nonexistent")

        assert "not found" in str(context.exception).lower()

    def test_extract_schema_from_table_invalid_format(self):
        """Test _extract_schema_from_table with invalid table name format."""
        # ValueError is caught and re-raised as ConnectionError
        with self.assertRaises(ConnectionError) as context:
            self.connector._extract_schema_from_table("invalid")
        assert "Invalid table name format" in str(context.exception)


class TestDatabricksConnectorMapType(TestCase):
    """Test _map_databricks_type helper method."""

    def setUp(self):
        from hub.apps.core.resilience.circuit_breaker import reset_circuit_breaker_by_name

        reset_circuit_breaker_by_name("databricks-connector")
        """Set up test fixtures."""
        self.connector = DatabricksConnector(
            host="https://test-workspace.cloud.databricks.com", token="test-token"
        )

    def test_map_databricks_type_string(self):
        """Test mapping string types."""
        assert self.connector._map_databricks_type("STRING") == "string"
        assert self.connector._map_databricks_type("VARCHAR") == "string"
        assert self.connector._map_databricks_type("BINARY") == "string"

    def test_map_databricks_type_number(self):
        """Test mapping number types."""
        assert self.connector._map_databricks_type("INT") == "number"
        assert self.connector._map_databricks_type("BIGINT") == "number"
        assert self.connector._map_databricks_type("FLOAT") == "number"
        assert self.connector._map_databricks_type("DOUBLE") == "number"
        assert self.connector._map_databricks_type("DECIMAL") == "number"

    def test_map_databricks_type_boolean(self):
        """Test mapping boolean type."""
        assert self.connector._map_databricks_type("BOOLEAN") == "boolean"

    def test_map_databricks_type_datetime(self):
        """Test mapping datetime types."""
        assert self.connector._map_databricks_type("TIMESTAMP") == "datetime"
        assert self.connector._map_databricks_type("DATE") == "datetime"

    def test_map_databricks_type_array(self):
        """Test mapping array type."""
        assert self.connector._map_databricks_type("ARRAY<STRING>") == "array"

    def test_map_databricks_type_object(self):
        """Test mapping object types."""
        assert self.connector._map_databricks_type("STRUCT") == "object"
        assert self.connector._map_databricks_type("MAP") == "object"

    def test_map_databricks_type_unknown(self):
        """Test mapping unknown type defaults to string."""
        assert self.connector._map_databricks_type("UNKNOWN_TYPE") == "string"
