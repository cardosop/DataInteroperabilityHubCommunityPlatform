"""
Mock contract tests for the dados.gov.br Swagger connector.

All mocked tests patch ``httpx.Client`` (unittest.mock) — no network I/O and
no live credentials. The connector and its ``DadosGovBrAPIClient`` run for
real against the mocked transport, so request shape (endpoint, query params,
``chave-api-dados-abertos`` header) and the real response schema are asserted
at the HTTP layer. Error-mapping tests use real ``httpx.Response`` objects so
``raise_for_status()`` raises genuine ``httpx.HTTPStatusError`` instances.

The live smoke test (``TestDadosGovBrConnectorLive``) is gated on
``DADOS_GOV_BR_API_KEY`` (or the deprecated ``CKAN_DADOS_GOV_BR_API_KEY``)
through the W16 environment policy: a missing key skips locally and fails the
CI run loudly.

The connector is harvest-only (PULL): it reads from the dados.gov.br Swagger
API (``/dados/api/publico/conjuntos-dados``) and never pushes.
"""

import os
from unittest import TestCase
from unittest.mock import Mock, patch

import httpx
import pytest

from envpolicy import skip_or_fail
from hub.apps.assets.models import AssetSourceType
from hub.apps.core.services.base import ConnectionError, NotFoundError
from hub.apps.integrations.base import (
    MarketplaceListing,
    MarketplaceResource,
    MarketplaceType,
    SyncDirection,
    SyncStatus,
)
from hub.apps.integrations.connectors.dados_gov_br_client import DadosGovBrAPIClient
from hub.apps.integrations.connectors.dados_gov_br_connector import DadosGovBrConnector

DEFAULT_BASE_URL = "https://dados.gov.br"
DATASETS_ENDPOINT = "/dados/api/publico/conjuntos-dados"

# Portuguese (dados.gov.br) dataset payload — every field below is one the
# connector/client actually read (derived from _swagger_dataset_to_listing,
# _swagger_resource_to_marketplace_resource and map_to_hub_asset).
DATASET_FIXTURE = {
    "identificador": "dataset-001",
    "titulo": "Despesas Públicas Federais",
    "descricao": "Dados abertos de despesas públicas.",
    "nome": "despesas-publicas-federais",
    "tags": [{"nome": "orcamento"}, {"nome": "transparencia"}],
    "organizacao": {"nome": "Ministério da Economia"},
    "dataCatalogacao": "15/01/2024 10:30:00",
    "dataUltimaAtualizacaoMetadados": "2024-03-01T08:00:00Z",
    "dataUltimaAtualizacaoArquivo": "2024-02-15T12:00:00Z",
    "visibilidade": "PUBLICA",
    "atualizado": "ATUALIZADO",
    "versao": "1.2",
    "dadosAbertos": "Sim",
    "periodicidade": "Mensal",
    "selo": "Selo de Qualidade",
    "responsavel": "Equipe de Dados Abertos",
    "emailResponsavel": "dados@org.gov.br",
    "licenca": "CC-BY",
    "licenca_id": "cc-by",
    "licenca_titulo": "Creative Commons BY",
    "coberturaTemporalInicio": "2020-01-01",
    "coberturaTemporalFim": "2023-12-31",
    "coberturaEspacial": "Nacional",
    "valorCoberturaEspacial": "Brasil",
    "granularidadeEspacial": "Municipal",
    "atualizacaoVersao": "1.2",
    "descontinuado": False,
    "reuso": True,
    "temas": ["Economia e Finanças"],
    "conjuntoDadosAssociados": [],
    "dadosRacaEtnia": False,
    "dadosGenero": False,
    "observanciaLegal": "LGPD",
    "origemCadastro": "API",
    "recursos": [
        {
            "id": "res-001",
            "titulo": "Arquivo CSV 2023",
            "descricao": "Despesas de 2023 em CSV",
            "link": "https://dados.gov.br/api/download/res-001.csv",
            "formato": "CSV",
            "tamanho": 2048,
            "tipo": "arquivo",
            "nomeArquivo": "despesas-2023.csv",
            "dataCatalogacao": "15/01/2024 10:35:00",
            "dataUltimaAtualizacaoArquivo": "2024-02-15T12:00:00Z",
            "mimetype": "text/csv",
            "quantidadeDownloads": 150,
        }
    ],
}

SECOND_DATASET_FIXTURE = {
    "identificador": "dataset-002",
    "titulo": "Segundo Conjunto de Dados",
}


def _json_response(status_code, body, url=DEFAULT_BASE_URL + DATASETS_ENDPOINT):
    """Build a real httpx.Response so raise_for_status() raises real HTTPStatusError."""
    request = httpx.Request("GET", url)
    return httpx.Response(status_code, json=body, request=request)


def _html_response(status_code, html, url=DEFAULT_BASE_URL + DATASETS_ENDPOINT):
    request = httpx.Request("GET", url)
    return httpx.Response(
        status_code,
        content=html.encode("utf-8"),
        headers={"content-type": "text/html"},
        request=request,
    )


@pytest.fixture
def mocked_http():
    """Patch httpx.Client so no test performs real network I/O."""
    with patch("httpx.Client") as mock_client_class:
        mock_http = Mock()
        mock_client_class.return_value = mock_http
        yield mock_client_class, mock_http


# Snapshot the credential at IMPORT time: a mid-session os.environ mutation
# from another test file must not flip this guard into running a real HTTP
# call (test-order determinism — see the test_ckan_env_config.py leak fix).
_DADOS_LIVE_KEY_AT_IMPORT = os.getenv("DADOS_GOV_BR_API_KEY") or os.getenv(
    "CKAN_DADOS_GOV_BR_API_KEY"
)


def _dados_live_config():
    """Resolve live-API config; missing key follows the W16 environment policy."""
    jwt_token = _DADOS_LIVE_KEY_AT_IMPORT
    if not jwt_token:
        skip_or_fail(
            "DADOS_GOV_BR_API_KEY (or CKAN_DADOS_GOV_BR_API_KEY) environment variable is required"
        )
    base_url = os.getenv("DADOS_GOV_BR_BASE_URL", DEFAULT_BASE_URL)
    return base_url, jwt_token


class TestDadosGovBrClientConstruction:
    """Client construction: JWT auth header and base URL handling."""

    def test_headers_include_chave_api_when_token_set(self, mocked_http):
        mock_client_class, _ = mocked_http
        client = DadosGovBrAPIClient(base_url=DEFAULT_BASE_URL, jwt_token="test-token")

        client_kwargs = mock_client_class.call_args.kwargs
        assert client_kwargs["base_url"] == DEFAULT_BASE_URL
        assert client_kwargs["follow_redirects"] is True
        headers = client_kwargs["headers"]
        # dados.gov.br authenticates via chave-api-dados-abertos, not Authorization.
        assert headers["chave-api-dados-abertos"] == "test-token"
        assert "Authorization" not in headers
        assert headers["Content-Type"] == "application/json"
        assert headers["Accept"] == "application/json"
        assert client.jwt_token == "test-token"

    def test_headers_omit_chave_api_without_token(self, mocked_http):
        mock_client_class, _ = mocked_http
        DadosGovBrAPIClient(base_url=DEFAULT_BASE_URL)

        headers = mock_client_class.call_args.kwargs["headers"]
        assert "chave-api-dados-abertos" not in headers

    def test_base_url_trailing_slash_stripped(self, mocked_http):
        mock_client_class, _ = mocked_http
        client = DadosGovBrAPIClient(base_url=DEFAULT_BASE_URL + "/", jwt_token="")

        assert client.base_url == DEFAULT_BASE_URL
        assert mock_client_class.call_args.kwargs["base_url"] == DEFAULT_BASE_URL


class TestDadosGovBrConnectorInit:
    """Connector construction validation and metadata properties."""

    def test_init_creates_client_with_token(self):
        connector = DadosGovBrConnector(base_url=DEFAULT_BASE_URL, jwt_token="test-token")
        assert connector.base_url == DEFAULT_BASE_URL
        assert connector.jwt_token == "test-token"
        assert connector.client is not None

    def test_init_empty_base_url_raises_value_error(self):
        with pytest.raises(ValueError, match="base_url must be a non-empty string"):
            DadosGovBrConnector(base_url="", jwt_token="test-token")

    def test_init_none_jwt_token_raises_type_error(self):
        with pytest.raises(TypeError, match="jwt_token must not be None"):
            DadosGovBrConnector(base_url=DEFAULT_BASE_URL)

    def test_init_accepts_empty_string_token(self):
        # Public endpoints may work unauthenticated; only None is rejected.
        connector = DadosGovBrConnector(base_url=DEFAULT_BASE_URL, jwt_token="")
        assert connector.jwt_token == ""

    def test_swagger_spec_url_defaults_to_v3_api_docs(self):
        connector = DadosGovBrConnector(base_url=DEFAULT_BASE_URL, jwt_token="test-token")
        assert connector.swagger_spec_url == DEFAULT_BASE_URL + "/v3/api-docs"

    def test_marketplace_type_is_ckan_instance(self):
        connector = DadosGovBrConnector(base_url=DEFAULT_BASE_URL, jwt_token="test-token")
        assert connector.marketplace_type == MarketplaceType.CKAN_INSTANCE

    def test_supported_sync_directions_pull_only(self):
        connector = DadosGovBrConnector(base_url=DEFAULT_BASE_URL, jwt_token="test-token")
        assert connector.supported_sync_directions == [SyncDirection.PULL]


class TestDadosGovBrHarvestList:
    """Harvest/list flow: request shape and response-schema parsing."""

    def test_list_listings_request_shape_and_mapping(self, mocked_http):
        _, mock_http = mocked_http
        mock_http.request.return_value = _json_response(200, [DATASET_FIXTURE])
        connector = DadosGovBrConnector(base_url=DEFAULT_BASE_URL, jwt_token="test-token")

        listings = connector.list_listings(
            filters={"q": "educacao", "idOrganizacao": "org-1", "dadosAbertos": True},
            limit=10,
            offset=0,
        )

        mock_http.request.assert_called_once()
        call = mock_http.request.call_args
        assert call is not None
        assert call.args[0] == "GET"
        assert call.args[1] == DATASETS_ENDPOINT
        assert call.kwargs["params"] == {
            "pagina": 1,
            "nomeConjuntoDados": "educacao",
            "idOrganizacao": "org-1",
            "dadosAbertos": True,
        }
        assert call.kwargs["headers"]["chave-api-dados-abertos"] == "test-token"

        assert len(listings) == 1
        assert isinstance(listings[0], MarketplaceListing)

    def test_list_listings_parses_portuguese_fields(self, mocked_http):
        _, mock_http = mocked_http
        mock_http.request.return_value = _json_response(200, [DATASET_FIXTURE])
        connector = DadosGovBrConnector(base_url=DEFAULT_BASE_URL, jwt_token="test-token")

        listing = connector.list_listings()[0]

        assert listing.marketplace_id == "dataset-001"
        assert listing.title == "Despesas Públicas Federais"
        assert listing.description == "Dados abertos de despesas públicas."
        assert listing.category == "Ministério da Economia"
        assert listing.tags == ["orcamento", "transparencia"]
        assert listing.url == DEFAULT_BASE_URL + "/dataset/dataset-001"
        # Brazilian DD/MM/YYYY timestamp and ISO timestamp are both parsed.
        assert listing.created_at is not None
        assert listing.created_at.year == 2024
        assert listing.updated_at is not None

        assert len(listing.resources) == 1
        resource = listing.resources[0]
        assert isinstance(resource, MarketplaceResource)
        assert resource.resource_id == "res-001"
        assert resource.name == "Arquivo CSV 2023"
        assert resource.url == "https://dados.gov.br/api/download/res-001.csv"
        assert resource.format == "CSV"
        assert resource.size_bytes == 2048
        assert resource.resource_type == "ARQUIVO"

    def test_list_listings_limit_applied_client_side(self, mocked_http):
        _, mock_http = mocked_http
        mock_http.request.return_value = _json_response(
            200, [DATASET_FIXTURE, SECOND_DATASET_FIXTURE]
        )
        connector = DadosGovBrConnector(base_url=DEFAULT_BASE_URL, jwt_token="test-token")

        listings = connector.list_listings(limit=1)

        assert len(listings) == 1
        assert listings[0].marketplace_id == "dataset-001"

    def test_list_listings_zero_limit_returns_empty_without_request(self, mocked_http):
        _, mock_http = mocked_http
        connector = DadosGovBrConnector(base_url=DEFAULT_BASE_URL, jwt_token="test-token")

        listings = connector.list_listings(limit=0)

        assert listings == []
        mock_http.request.assert_not_called()

    def test_list_listings_page_from_offset_and_limit(self, mocked_http):
        _, mock_http = mocked_http
        mock_http.request.return_value = _json_response(200, [DATASET_FIXTURE])
        connector = DadosGovBrConnector(base_url=DEFAULT_BASE_URL, jwt_token="test-token")

        connector.list_listings(limit=20, offset=40)

        assert mock_http.request.call_args.kwargs["params"]["pagina"] == 3

    def test_list_listings_page_from_offset_only(self, mocked_http):
        _, mock_http = mocked_http
        mock_http.request.return_value = _json_response(200, [DATASET_FIXTURE])
        connector = DadosGovBrConnector(base_url=DEFAULT_BASE_URL, jwt_token="test-token")

        connector.list_listings(offset=45)

        # Offset only assumes a default page size of 20.
        assert mock_http.request.call_args.kwargs["params"]["pagina"] == 3

    def test_list_listings_default_page_one(self, mocked_http):
        _, mock_http = mocked_http
        mock_http.request.return_value = _json_response(200, [DATASET_FIXTURE])
        connector = DadosGovBrConnector(base_url=DEFAULT_BASE_URL, jwt_token="test-token")

        connector.list_listings()

        assert mock_http.request.call_args.kwargs["params"]["pagina"] == 1

    def test_list_listings_skips_non_dict_items(self, mocked_http):
        _, mock_http = mocked_http
        mock_http.request.return_value = _json_response(200, [DATASET_FIXTURE, "junk"])
        connector = DadosGovBrConnector(base_url=DEFAULT_BASE_URL, jwt_token="test-token")

        listings = connector.list_listings()

        assert len(listings) == 1
        assert listings[0].marketplace_id == "dataset-001"


class TestDadosGovBrGetListing:
    """get_listing() response-structure handling and request path."""

    def test_get_listing_direct_object_response(self, mocked_http):
        _, mock_http = mocked_http
        mock_http.request.return_value = _json_response(200, DATASET_FIXTURE)
        connector = DadosGovBrConnector(base_url=DEFAULT_BASE_URL, jwt_token="test-token")

        listing = connector.get_listing("dataset-001")

        assert listing.marketplace_id == "dataset-001"
        assert listing.title == "Despesas Públicas Federais"

    def test_get_listing_ckan_style_response(self, mocked_http):
        _, mock_http = mocked_http
        mock_http.request.return_value = _json_response(
            200, {"success": True, "result": DATASET_FIXTURE}
        )
        connector = DadosGovBrConnector(base_url=DEFAULT_BASE_URL, jwt_token="test-token")

        listing = connector.get_listing("dataset-001")

        assert listing.marketplace_id == "dataset-001"

    def test_get_listing_request_path(self, mocked_http):
        _, mock_http = mocked_http
        mock_http.request.return_value = _json_response(200, DATASET_FIXTURE)
        connector = DadosGovBrConnector(base_url=DEFAULT_BASE_URL, jwt_token="test-token")

        connector.get_listing("dataset-001")

        mock_http.request.assert_called_once()
        assert mock_http.request.call_args.args[1] == DATASETS_ENDPOINT + "/dataset-001"


class TestDadosGovBrErrorMapping:
    """HTTP status / transport errors map to the documented error types."""

    def test_request_401_raises_http_status_error(self, mocked_http):
        _, mock_http = mocked_http
        mock_http.request.return_value = _json_response(401, {"error": "Unauthorized"})
        client = DadosGovBrAPIClient(base_url=DEFAULT_BASE_URL, jwt_token="test-token")

        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            client._request("GET", DATASETS_ENDPOINT)
        assert exc_info.value.response.status_code == 401

    def test_request_429_raises_http_status_error(self, mocked_http):
        _, mock_http = mocked_http
        mock_http.request.return_value = _json_response(429, {"error": "Rate limited"})
        client = DadosGovBrAPIClient(base_url=DEFAULT_BASE_URL, jwt_token="test-token")

        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            client._request("GET", DATASETS_ENDPOINT)
        assert exc_info.value.response.status_code == 429

    def test_request_5xx_raises_http_status_error(self, mocked_http):
        _, mock_http = mocked_http
        mock_http.request.return_value = _json_response(503, {"error": "Unavailable"})
        client = DadosGovBrAPIClient(base_url=DEFAULT_BASE_URL, jwt_token="test-token")

        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            client._request("GET", DATASETS_ENDPOINT)
        assert exc_info.value.response.status_code == 503

    def test_request_signin_redirect_raises_expired_jwt_value_error(self, mocked_http):
        _, mock_http = mocked_http
        mock_http.request.return_value = _json_response(200, [], url=DEFAULT_BASE_URL + "/signin")
        client = DadosGovBrAPIClient(base_url=DEFAULT_BASE_URL, jwt_token="expired-token")

        with pytest.raises(ValueError, match="JWT token may be expired or invalid") as exc_info:
            client._request("GET", DATASETS_ENDPOINT)
        assert "DADOS_GOV_BR_API_KEY" in str(exc_info.value)

    def test_request_error_on_login_url_raises_expired_jwt_value_error(self, mocked_http):
        _, mock_http = mocked_http
        mock_http.request.return_value = _json_response(
            401, {"error": "Unauthorized"}, url=DEFAULT_BASE_URL + "/login"
        )
        client = DadosGovBrAPIClient(base_url=DEFAULT_BASE_URL, jwt_token="expired-token")

        with pytest.raises(ValueError, match="JWT token may be expired or invalid") as exc_info:
            client._request("GET", DATASETS_ENDPOINT)
        assert "CKAN_DADOS_GOV_BR_API_KEY" in str(exc_info.value)

    def test_request_html_error_page_raises_value_error(self, mocked_http):
        _, mock_http = mocked_http
        html = (
            "<html><head><title>Error 404 - Not Found</title></head>"
            "<body><h1>404 Error</h1>"
            '<p class="error">Recurso não encontrado.</p></body></html>'
        )
        mock_http.request.return_value = _html_response(200, html)
        client = DadosGovBrAPIClient(base_url=DEFAULT_BASE_URL, jwt_token="test-token")

        with pytest.raises(ValueError, match="HTML error"):
            client._request("GET", DATASETS_ENDPOINT)

    def test_request_network_error_raises_request_error(self, mocked_http):
        _, mock_http = mocked_http
        mock_http.request.side_effect = httpx.RequestError("Network down")
        client = DadosGovBrAPIClient(base_url=DEFAULT_BASE_URL, jwt_token="test-token")

        with pytest.raises(httpx.RequestError):
            client._request("GET", DATASETS_ENDPOINT)

    def test_list_listings_401_raises_connection_error(self, mocked_http):
        _, mock_http = mocked_http
        mock_http.request.return_value = _json_response(401, {"error": "Unauthorized"})
        connector = DadosGovBrConnector(base_url=DEFAULT_BASE_URL, jwt_token="expired-token")

        with pytest.raises(ConnectionError, match="API error"):
            connector.list_listings()

    def test_list_listings_429_raises_connection_error(self, mocked_http):
        _, mock_http = mocked_http
        mock_http.request.return_value = _json_response(429, {"error": "Rate limited"})
        connector = DadosGovBrConnector(base_url=DEFAULT_BASE_URL, jwt_token="test-token")

        with pytest.raises(ConnectionError, match="API error"):
            connector.list_listings()

    def test_list_listings_5xx_raises_connection_error(self, mocked_http):
        _, mock_http = mocked_http
        mock_http.request.return_value = _json_response(500, {"error": "Internal error"})
        connector = DadosGovBrConnector(base_url=DEFAULT_BASE_URL, jwt_token="test-token")

        with pytest.raises(ConnectionError, match="API error"):
            connector.list_listings()

    def test_list_listings_network_error_raises_connection_error(self, mocked_http):
        _, mock_http = mocked_http
        mock_http.request.side_effect = httpx.RequestError("Network down")
        connector = DadosGovBrConnector(base_url=DEFAULT_BASE_URL, jwt_token="test-token")

        with pytest.raises(ConnectionError, match="Unable to connect"):
            connector.list_listings()

    def test_get_listing_404_raises_not_found(self, mocked_http):
        _, mock_http = mocked_http
        mock_http.request.return_value = _json_response(404, {"error": "Not found"})
        connector = DadosGovBrConnector(base_url=DEFAULT_BASE_URL, jwt_token="test-token")

        with pytest.raises(NotFoundError, match="not found"):
            connector.get_listing("missing-dataset")

    def test_get_listing_api_error_dict_raises_not_found(self, mocked_http):
        _, mock_http = mocked_http
        mock_http.request.return_value = _json_response(
            200, {"success": False, "error": {"message": "Dataset not found"}}
        )
        connector = DadosGovBrConnector(base_url=DEFAULT_BASE_URL, jwt_token="test-token")

        with pytest.raises(NotFoundError, match="not found"):
            connector.get_listing("missing-dataset")

    def test_get_listing_5xx_raises_connection_error(self, mocked_http):
        _, mock_http = mocked_http
        mock_http.request.return_value = _json_response(500, {"error": "Internal error"})
        connector = DadosGovBrConnector(base_url=DEFAULT_BASE_URL, jwt_token="test-token")

        with pytest.raises(ConnectionError, match="API error"):
            connector.get_listing("dataset-001")


class TestDadosGovBrAuthenticate:
    """authenticate() / test_connection() against mocked HTTP responses."""

    def test_empty_credentials_raises_value_error(self):
        connector = DadosGovBrConnector(base_url=DEFAULT_BASE_URL, jwt_token="test-token")
        with pytest.raises(ValueError, match="Credentials dictionary is required"):
            connector.authenticate({})

    def test_missing_token_raises_value_error(self):
        connector = DadosGovBrConnector(base_url=DEFAULT_BASE_URL, jwt_token="test-token")
        with pytest.raises(ValueError, match="jwt_token or api_key is required"):
            connector.authenticate({"base_url": DEFAULT_BASE_URL})

    def test_success_returns_true_and_marks_authenticated(self, mocked_http):
        _, mock_http = mocked_http
        mock_http.request.return_value = _json_response(200, [DATASET_FIXTURE])
        connector = DadosGovBrConnector(base_url=DEFAULT_BASE_URL, jwt_token="old-token")

        result = connector.authenticate({"jwt_token": "new-token"})

        assert result is True
        assert connector._authenticated is True
        assert connector.jwt_token == "new-token"
        assert connector.client.jwt_token == "new-token"

    def test_non_list_response_returns_false(self, mocked_http):
        _, mock_http = mocked_http
        mock_http.request.return_value = _json_response(200, {"not": "a list"})
        connector = DadosGovBrConnector(base_url=DEFAULT_BASE_URL, jwt_token="test-token")

        result = connector.authenticate({"jwt_token": "test-token"})

        assert result is False
        assert connector._authenticated is False

    def test_connection_failure_wraps_in_connection_error(self, mocked_http):
        _, mock_http = mocked_http
        mock_http.request.side_effect = httpx.RequestError("Network down")
        connector = DadosGovBrConnector(base_url=DEFAULT_BASE_URL, jwt_token="test-token")

        with pytest.raises(ConnectionError, match="Unable to authenticate"):
            connector.authenticate({"jwt_token": "test-token"})

    def test_test_connection_true_for_list_response(self, mocked_http):
        _, mock_http = mocked_http
        mock_http.request.return_value = _json_response(200, [])
        connector = DadosGovBrConnector(base_url=DEFAULT_BASE_URL, jwt_token="test-token")

        assert connector.test_connection() is True

    def test_test_connection_false_for_dict_response(self, mocked_http):
        _, mock_http = mocked_http
        mock_http.request.return_value = _json_response(200, {"success": True, "result": {}})
        connector = DadosGovBrConnector(base_url=DEFAULT_BASE_URL, jwt_token="test-token")

        assert connector.test_connection() is False

    def test_test_connection_wraps_network_error(self, mocked_http):
        _, mock_http = mocked_http
        mock_http.request.side_effect = httpx.RequestError("Network down")
        connector = DadosGovBrConnector(base_url=DEFAULT_BASE_URL, jwt_token="test-token")

        with pytest.raises(ConnectionError, match="Unable to connect"):
            connector.test_connection()


class TestDadosGovBrPushNotSupported(TestCase):
    """Harvest-only: every push-side operation raises NotImplementedError.

    Subclasses ``unittest.TestCase`` so ``setUp`` runs before each test —
    plain pytest classes never call ``setUp``.
    """

    def setUp(self):
        self.connector = DadosGovBrConnector(base_url=DEFAULT_BASE_URL, jwt_token="test-token")
        self.listing = MarketplaceListing(
            marketplace_id="dataset-001",
            marketplace_type=MarketplaceType.CKAN_INSTANCE,
            title="Test",
        )
        self.resource = MarketplaceResource(
            resource_id="res-001", resource_type="FILE", name="Test Resource"
        )

    def test_create_listing_not_supported(self):
        with pytest.raises(NotImplementedError, match="harvest-only"):
            self.connector.create_listing(self.listing)

    def test_update_listing_not_supported(self):
        with pytest.raises(NotImplementedError, match="harvest-only"):
            self.connector.update_listing(self.listing)

    def test_publish_resource_not_supported(self):
        with pytest.raises(NotImplementedError, match="harvest-only"):
            self.connector.publish_resource("dataset-001", self.resource)

    def test_sync_push_not_supported(self):
        with pytest.raises(NotImplementedError, match="harvest-only"):
            self.connector.sync_push(["asset-1"])

    def test_map_from_hub_asset_not_supported(self):
        with pytest.raises(NotImplementedError, match="harvest-only"):
            self.connector.map_from_hub_asset({"name": "Test"})


class TestDadosGovBrHarvestSyncPull:
    """Harvest (sync_pull) against mocked HTTP responses."""

    def test_sync_pull_by_listing_ids(self, mocked_http):
        _, mock_http = mocked_http
        mock_http.request.return_value = _json_response(200, DATASET_FIXTURE)
        connector = DadosGovBrConnector(base_url=DEFAULT_BASE_URL, jwt_token="test-token")

        result = connector.sync_pull(listing_ids=["dataset-001"])

        assert result.status == SyncStatus.COMPLETED
        assert result.total_items == 1
        assert result.successful_items == 1
        assert result.failed_items == 0
        mappings = result.metadata["mappings"]
        assert len(mappings) == 1
        assert mappings[0].asset_data["name"] == "Despesas Públicas Federais"

    def test_sync_pull_empty_listing_ids_short_circuits(self, mocked_http):
        _, mock_http = mocked_http
        connector = DadosGovBrConnector(base_url=DEFAULT_BASE_URL, jwt_token="test-token")

        result = connector.sync_pull(listing_ids=[])

        assert result.status == SyncStatus.COMPLETED
        assert result.total_items == 0
        assert result.metadata["reason"] == "empty_listing_ids"
        mock_http.request.assert_not_called()

    def test_sync_pull_zero_limit_short_circuits(self, mocked_http):
        _, mock_http = mocked_http
        connector = DadosGovBrConnector(base_url=DEFAULT_BASE_URL, jwt_token="test-token")

        result = connector.sync_pull(options={"limit": 0})

        assert result.status == SyncStatus.COMPLETED
        assert result.total_items == 0
        assert result.metadata["reason"] == "zero_limit"
        mock_http.request.assert_not_called()

    def test_sync_pull_not_found_skips_listing(self, mocked_http):
        _, mock_http = mocked_http
        mock_http.request.return_value = _json_response(404, {"error": "Not found"})
        connector = DadosGovBrConnector(base_url=DEFAULT_BASE_URL, jwt_token="test-token")

        result = connector.sync_pull(listing_ids=["missing-dataset"])

        assert result.status == SyncStatus.FAILED
        assert result.skipped_items == 1
        assert result.successful_items == 0
        assert len(result.errors) == 1


class TestDadosGovBrMapToHubAsset:
    """map_to_hub_asset() metadata extraction (Portuguese schema)."""

    def test_map_to_hub_asset_public_status_and_metadata(self, mocked_http):
        _, mock_http = mocked_http
        mock_http.request.return_value = _json_response(200, DATASET_FIXTURE)
        connector = DadosGovBrConnector(base_url=DEFAULT_BASE_URL, jwt_token="test-token")

        listing = connector.get_listing("dataset-001")
        mapping = connector.map_to_hub_asset(listing, sync_job_id="job-1")

        assert mapping.source_type == AssetSourceType.FEDERATED
        assert mapping.asset_data["name"] == "Despesas Públicas Federais"
        assert mapping.asset_data["key"] == "dados-gov-br-dataset-001"
        # PUBLICA + ATUALIZADO + resources -> PUBLIC (D250.4 visibility rule).
        assert mapping.asset_data["status"] == "PUBLIC"
        assert mapping.source_metadata["listing_id"] == "dataset-001"
        assert mapping.source_metadata["sync_job_id"] == "job-1"
        assert mapping.odps_metadata is not None
        assert mapping.odps_metadata["open_data"] is True
        assert mapping.odcs_metadata["quality_seal"] == "Selo de Qualidade"
        assert len(mapping.resources) == 1

    def test_map_to_hub_asset_draft_for_private_dataset(self, mocked_http):
        _, mock_http = mocked_http
        private_fixture = {**DATASET_FIXTURE, "visibilidade": "PRIVADA"}
        mock_http.request.return_value = _json_response(200, private_fixture)
        connector = DadosGovBrConnector(base_url=DEFAULT_BASE_URL, jwt_token="test-token")

        listing = connector.get_listing("dataset-001")
        mapping = connector.map_to_hub_asset(listing)

        assert mapping.asset_data["status"] == "DRAFT"


@pytest.mark.integration
class TestDadosGovBrConnectorLive:
    """Live smoke tests against the real dados.gov.br Swagger API.

    Gated on DADOS_GOV_BR_API_KEY (or the deprecated CKAN_DADOS_GOV_BR_API_KEY)
    via the W16 environment policy: a missing key skips locally and fails CI
    loudly.
    """

    def test_list_listings_live(self):
        base_url, jwt_token = _dados_live_config()
        connector = DadosGovBrConnector(base_url=base_url, jwt_token=jwt_token)
        # Shorten the client timeout for the smoke call.
        connector.client.client.timeout = httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=5.0)
        listings = connector.list_listings(limit=10)
        assert isinstance(listings, list)
