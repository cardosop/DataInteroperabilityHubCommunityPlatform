"""
Unit tests for DadosGovBrAPIClient.

Tests Swagger API client for dados.gov.br with JWT Bearer token authentication.
Follows TDD approach - tests written before implementation.
"""
import pytest
import httpx
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any

from hub.apps.integrations.connectors.dados_gov_br_client import DadosGovBrAPIClient


class TestDadosGovBrAPIClient:
    """Test suite for DadosGovBrAPIClient."""

    def test_init_with_base_url_and_token(self):
        """Test client initialization with base URL and JWT token."""
        client = DadosGovBrAPIClient(
            base_url="https://dados.gov.br",
            jwt_token="test-token-123"
        )
        assert client.base_url == "https://dados.gov.br"
        assert client.jwt_token == "test-token-123"
        assert client._swagger_spec is None  # Not loaded yet

    def test_load_swagger_spec_success(self):
        """Test loading Swagger specification successfully."""
        mock_spec = {
            "openapi": "3.0.0",
            "info": {"title": "dados.gov.br API", "version": "1.0.0"},
            "paths": {
                "/api/3/action/package_search": {
                    "get": {
                        "operationId": "package_search",
                        "summary": "Search packages"
                    }
                }
            }
        }

        client = DadosGovBrAPIClient(
            base_url="https://dados.gov.br",
            jwt_token="test-token"
        )

        with patch('httpx.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.headers = {'content-type': 'application/json'}
            mock_response.json.return_value = mock_spec
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            spec = client.load_swagger_spec("https://dados.gov.br/v3/api-docs")

            assert spec == mock_spec
            assert client._swagger_spec == mock_spec

    def test_load_swagger_spec_failure_returns_none(self):
        """Test that loading Swagger spec returns None on failure."""
        client = DadosGovBrAPIClient(
            base_url="https://dados.gov.br",
            jwt_token="test-token"
        )

        with patch('httpx.get') as mock_get:
            mock_get.side_effect = httpx.RequestError("Connection failed")

            spec = client.load_swagger_spec("https://dados.gov.br/v3/api-docs")

            assert spec is None

    def test_get_endpoint_path_from_swagger_spec(self):
        """Test resolving endpoint path from Swagger spec."""
        mock_spec = {
            "paths": {
                "/api/3/action/package_search": {
                    "get": {
                        "operationId": "package_search"
                    }
                }
            }
        }

        client = DadosGovBrAPIClient(
            base_url="https://dados.gov.br",
            jwt_token="test-token"
        )
        client._swagger_spec = mock_spec

        path = client.get_endpoint_path("package_search")
        assert path == "/api/3/action/package_search"

    def test_get_endpoint_path_fallback_when_no_spec(self):
        """Test endpoint path fallback when Swagger spec not available."""
        client = DadosGovBrAPIClient(
            base_url="https://dados.gov.br",
            jwt_token="test-token"
        )

        # No spec loaded - should use dados.gov.br endpoints
        path = client.get_endpoint_path("package_search")
        assert path == "/dados/api/publico/conjuntos-dados"  # dados.gov.br Swagger endpoint

    def test_request_includes_bearer_token(self):
        """Test that API requests include JWT token in chave-api-dados-abertos header."""
        with patch('httpx.Client') as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client

            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.headers = {'content-type': 'application/json'}
            mock_response.json.return_value = []
            mock_response.raise_for_status = Mock()
            mock_client.request.return_value = mock_response

            # Create client to use mocked httpx.Client
            client = DadosGovBrAPIClient(
                base_url="https://dados.gov.br",
                jwt_token="test-jwt-token-123"
            )

            result = client._request("GET", "/dados/api/publico/conjuntos-dados")

            # Verify chave-api-dados-abertos header was set (dados.gov.br uses this header, not Authorization)
            call_args = mock_client.request.call_args
            assert call_args is not None
            headers = call_args.kwargs.get('headers', {})
            assert headers.get('chave-api-dados-abertos') == "test-jwt-token-123"
            # Verify Authorization header is NOT used
            assert 'Authorization' not in headers or headers.get('Authorization') is None

    def test_search_datasets_with_filters(self):
        """Test searching datasets with filters."""
        client = DadosGovBrAPIClient(
            base_url="https://dados.gov.br",
            jwt_token="test-token"
        )

        mock_response_data = {
            "success": True,
            "result": {
                "count": 2,
                "results": [
                    {"id": "dataset-1", "name": "Dataset 1"},
                    {"id": "dataset-2", "name": "Dataset 2"}
                ]
            }
        }

        with patch.object(client, '_request') as mock_request:
            mock_request.return_value = mock_response_data

            result = client.search_datasets(
                query="test",
                filters={"idOrganizacao": "test-org"},
                page=1
            )

            assert result == mock_response_data
            mock_request.assert_called_once()
            call_args = mock_request.call_args
            assert call_args[0][0] == "GET"
            # Should use dados.gov.br endpoint
            assert call_args[0][1] == "/dados/api/publico/conjuntos-dados"

    def test_get_dataset_by_id(self):
        """Test getting dataset by ID."""
        client = DadosGovBrAPIClient(
            base_url="https://dados.gov.br",
            jwt_token="test-token"
        )

        mock_response_data = {
            "success": True,
            "result": {
                "id": "test-dataset",
                "name": "Test Dataset",
                "title": "Test Dataset Title"
            }
        }

        with patch.object(client, '_request') as mock_request:
            mock_request.return_value = mock_response_data

            result = client.get_dataset("test-dataset")

            assert result == mock_response_data
            mock_request.assert_called_once()
            call_args = mock_request.call_args
            # Should use dados.gov.br endpoint with ID in path
            assert call_args[0][1] == "/dados/api/publico/conjuntos-dados/test-dataset"

    def test_get_resource_by_id(self):
        """Test getting resource by ID."""
        client = DadosGovBrAPIClient(
            base_url="https://dados.gov.br",
            jwt_token="test-token"
        )

        mock_response_data = {
            "success": True,
            "result": {
                "id": "test-resource",
                "name": "Test Resource",
                "url": "https://example.com/resource.csv"
            }
        }

        with patch.object(client, '_request') as mock_request:
            mock_request.return_value = mock_response_data

            result = client.get_resource("test-resource")

            assert result == mock_response_data
            mock_request.assert_called_once()

    def test_request_handles_401_unauthorized(self):
        """Test that 401 Unauthorized errors are handled properly."""
        client = DadosGovBrAPIClient(
            base_url="https://dados.gov.br",
            jwt_token="test-token"
        )

        with patch('httpx.Client') as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client

            mock_response = Mock()
            mock_response.status_code = 401
            mock_response.text = "Unauthorized"
            mock_response.headers = {'content-type': 'application/json'}
            mock_response.json.return_value = {"error": "Unauthorized"}

            # Create HTTPStatusError properly
            http_error = httpx.HTTPStatusError(
                "Unauthorized",
                request=Mock(),
                response=mock_response
            )
            mock_response.raise_for_status.side_effect = http_error
            mock_client.request.return_value = mock_response

            client = DadosGovBrAPIClient(
                base_url="https://dados.gov.br",
                jwt_token="test-token"
            )

            # The code raises HTTPStatusError directly (not wrapped)
            with pytest.raises(httpx.HTTPStatusError):
                client._request("GET", "/api/3/action/package_search")

    def test_request_handles_network_errors(self):
        """Test that network errors are handled properly."""
        client = DadosGovBrAPIClient(
            base_url="https://dados.gov.br",
            jwt_token="test-token"
        )

        with patch('httpx.Client') as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client
            mock_client.request.side_effect = httpx.RequestError("Network error")

            client = DadosGovBrAPIClient(
                base_url="https://dados.gov.br",
                jwt_token="test-token"
            )

            with pytest.raises(httpx.RequestError):
                client._request("GET", "/api/3/action/package_search")

    def test_parse_html_error(self):
        """Test HTML error parsing."""
        client = DadosGovBrAPIClient(
            base_url="https://dados.gov.br",
            jwt_token="test-token"
        )

        html_content = """
        <html>
        <head><title>Error 404 - Not Found</title></head>
        <body>
            <h1>404 Error</h1>
            <p class="error">The requested resource was not found.</p>
            <p>Please check the URL and try again.</p>
        </body>
        </html>
        """

        error_info = client._parse_html_error(html_content)
        assert error_info['error_message'] is not None
        assert '404' in error_info['error_message'] or 'Not Found' in error_info['error_message']
        assert len(error_info['details']) > 0

    def test_request_handles_html_error_response(self):
        """Test that HTML error responses are parsed and raise ValueError."""
        client = DadosGovBrAPIClient(
            base_url="https://dados.gov.br",
            jwt_token="test-token"
        )

        with patch('httpx.Client') as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client

            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.headers = {'content-type': 'text/html'}
            mock_response.text = '<html><head><title>Error</title></head><body><h1>Error</h1></body></html>'
            mock_response.raise_for_status = Mock()

            mock_client.request.return_value = mock_response

            client = DadosGovBrAPIClient(
                base_url="https://dados.gov.br",
                jwt_token="test-token"
            )

            with pytest.raises(ValueError) as exc_info:
                client._request("GET", "/dados/api/publico/conjuntos-dados")
            assert "HTML error" in str(exc_info.value)

    def test_new_api_methods_exist(self):
        """Test that new API methods exist."""
        client = DadosGovBrAPIClient(
            base_url="https://dados.gov.br",
            jwt_token="test-token"
        )

        # Check that new methods exist
        assert hasattr(client, 'get_dataset_tags')
        assert hasattr(client, 'get_themes')
        assert hasattr(client, 'get_tags')
        assert hasattr(client, 'list_organizations')
        assert hasattr(client, 'get_organization')

    def test_get_dataset_tags(self):
        """Test getting dataset tags."""
        client = DadosGovBrAPIClient(
            base_url="https://dados.gov.br",
            jwt_token="test-token"
        )

        mock_response_data = {"tags": ["tag1", "tag2"]}

        with patch.object(client, '_request') as mock_request:
            mock_request.return_value = mock_response_data

            result = client.get_dataset_tags("test-dataset")
            assert result == mock_response_data
            mock_request.assert_called_once_with('GET', '/dados/api/publico/conjuntos-dados/test-dataset/tag')

    def test_get_themes(self):
        """Test getting themes."""
        client = DadosGovBrAPIClient(
            base_url="https://dados.gov.br",
            jwt_token="test-token"
        )

        mock_response_data = {"themes": ["theme1", "theme2"]}

        with patch.object(client, '_request') as mock_request:
            mock_request.return_value = mock_response_data

            result = client.get_themes()
            assert result == mock_response_data
            mock_request.assert_called_once_with('GET', '/dados/api/temas')

    def test_get_tags(self):
        """Test getting tags."""
        client = DadosGovBrAPIClient(
            base_url="https://dados.gov.br",
            jwt_token="test-token"
        )

        mock_response_data = [{"id": "tag1", "name": "tag1"}, {"id": "tag2", "name": "tag2"}]

        with patch.object(client, '_request') as mock_request:
            mock_request.return_value = mock_response_data

            result = client.get_tags(nome="test")
            assert result == mock_response_data
            mock_request.assert_called_once_with('GET', '/dados/api/tags', params={'nome': 'test'})

    def test_list_organizations(self):
        """Test listing organizations."""
        client = DadosGovBrAPIClient(
            base_url="https://dados.gov.br",
            jwt_token="test-token"
        )

        mock_response_data = [{"id": "org1", "name": "Org 1"}]

        with patch.object(client, '_request') as mock_request:
            mock_request.return_value = mock_response_data

            result = client.list_organizations(page=1)
            assert result == mock_response_data
            mock_request.assert_called_once_with('GET', '/dados/api/publico/organizacao', params={'pagina': 1})

    def test_get_organization(self):
        """Test getting organization by ID."""
        client = DadosGovBrAPIClient(
            base_url="https://dados.gov.br",
            jwt_token="test-token"
        )

        mock_response_data = {"id": "org1", "name": "Org 1"}

        with patch.object(client, '_request') as mock_request:
            mock_request.return_value = mock_response_data

            result = client.get_organization("org1")
            assert result == mock_response_data
            mock_request.assert_called_once_with('GET', '/dados/api/publico/organizacao/org1')

