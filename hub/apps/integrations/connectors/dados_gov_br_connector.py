"""
Dados.gov.br Swagger API Connector

Connector implementation for dados.gov.br using Swagger API endpoints.
Implements DataMarketplaceConnector interface with Swagger-based API calls.
"""

import logging
from datetime import datetime
from typing import Any
from urllib.parse import urljoin

import httpx
from django.conf import settings
from django.utils import timezone

# dateutil for Brazilian date format parsing
try:
    from dateutil import parser as date_parser
except ImportError:
    date_parser = None

from hub.apps.assets.models import AssetSourceType
from hub.apps.core.resilience.circuit_breaker import (
    CircuitBreaker,
    get_redis_client,
)
from hub.apps.core.services.base import ConnectionError, NotFoundError
from hub.apps.integrations.base import (
    DataMarketplaceConnector,
    MarketplaceAssetMapping,
    MarketplaceListing,
    MarketplaceResource,
    MarketplaceType,
    SyncDirection,
    SyncResult,
    SyncStatus,
)
from hub.apps.integrations.connectors.dados_gov_br_client import DadosGovBrAPIClient

logger = logging.getLogger(__name__)


class DadosGovBrConnector(DataMarketplaceConnector):
    """
    Connector for dados.gov.br using Swagger API endpoints (Harvest-Only).

    Implements harvest (pull) operations for discovering and retrieving data from
    dados.gov.br using Swagger API endpoints. This connector is read-only and does
    not support push operations as dados.gov.br is a public data portal that should
    be harvested FROM, not pushed TO.

    Supports:
    - Discovery: list_listings, get_listing, list_resources
    - Harvest: sync_pull (bulk synchronization from dados.gov.br to Hub)
    - Mapping: map_to_hub_asset (Swagger datasets → Hub assets)

    Does NOT support:
    - Push operations: create_listing, update_listing, publish_resource, sync_push
    - Write operations: All methods that modify dados.gov.br data

    Uses Swagger API specification for endpoint discovery and validation.
    """

    def __init__(
        self, base_url: str, jwt_token: str | None = None, swagger_spec_url: str | None = None
    ):
        """
        Initialize dados.gov.br Swagger connector.

        Args:
            base_url: Base URL of dados.gov.br (e.g., 'https://dados.gov.br')
            jwt_token: Optional JWT Bearer token for authentication.
                      Public endpoints may work without authentication.
            swagger_spec_url: Optional URL to Swagger JSON specification
        """
        if not base_url or (isinstance(base_url, str) and not base_url.strip()):
            raise ValueError("base_url must be a non-empty string")
        if jwt_token is None:
            raise TypeError("jwt_token must not be None")
        self.base_url = base_url.rstrip("/")
        self.jwt_token = jwt_token
        self.swagger_spec_url = swagger_spec_url or f"{self.base_url}/v3/api-docs"

        # Initialize Swagger API client.
        # The Swagger spec URL is stored for lazy loading — it will be fetched
        # on first use (via get_endpoint_path) rather than eagerly during
        # __init__.  This avoids a 10 s HTTP timeout when the external
        # dados.gov.br API is unreachable (e.g. in CI / offline test runs).
        self.client = DadosGovBrAPIClient(
            base_url=self.base_url,
            jwt_token=self.jwt_token,
            swagger_spec_url=self.swagger_spec_url,
        )

        # HTTP client configuration
        self.timeout = getattr(settings, "CKAN_CONNECTOR_TIMEOUT", 30)
        self.max_retries = 2
        self.backoff_factor = 1

        # Initialize circuit breaker
        self._circuit_breaker = CircuitBreaker(
            service_name="dados-gov-br-connector",
            failure_threshold=5,
            timeout_seconds=60,
            success_threshold=2,
            redis_client=get_redis_client(),
        )

        # Track authentication state
        self._authenticated = False

    @property
    def marketplace_type(self) -> MarketplaceType:
        """Get the marketplace type this connector supports."""
        return MarketplaceType.CKAN_INSTANCE  # Keep same type for compatibility

    @property
    def supported_sync_directions(self) -> list[SyncDirection]:
        """
        Get the list of sync directions supported by this connector.

        dados.gov.br connector is harvest-only (PULL only) as it's a public
        data portal that should be harvested FROM, not pushed TO.
        """
        return [SyncDirection.PULL]

    def authenticate(self, credentials: dict[str, Any]) -> bool:
        """
        Authenticate with dados.gov.br using provided credentials.

        Args:
            credentials: Dictionary containing:
                - jwt_token: JWT Bearer token (required)
                - base_url: Base URL (optional, uses existing if not provided)

        Returns:
            True if authentication successful, False otherwise

        Raises:
            ValueError: If credentials are invalid or missing required fields
            ConnectionError: If unable to connect to dados.gov.br
        """
        if not credentials:
            raise ValueError("Credentials dictionary is required")

        jwt_token = credentials.get("jwt_token") or credentials.get("api_key")
        if not jwt_token:
            raise ValueError("jwt_token or api_key is required in credentials")

        # Update JWT token
        self.jwt_token = jwt_token
        self.client.jwt_token = jwt_token

        # Update base URL if provided
        base_url = credentials.get("base_url")
        if base_url:
            self.base_url = base_url.rstrip("/")
            # Recreate client with new base URL; swagger spec loads lazily
            self.client = DadosGovBrAPIClient(
                base_url=self.base_url,
                jwt_token=self.jwt_token,
                swagger_spec_url=self.swagger_spec_url,
            )

        # Test authentication by calling search endpoint
        try:
            # Use page=1 (required parameter) for lightweight test
            response_data = self.client.search_datasets(page=1)
            # API returns direct array, so check if it's a list
            if isinstance(response_data, list):
                self._authenticated = True
                logger.info(f"Successfully authenticated with dados.gov.br at {self.base_url}")
                return True
            else:
                self._authenticated = False
                logger.warning("Authentication test failed: Invalid response format")
                return False
        except Exception as e:
            self._authenticated = False
            logger.error(f"Authentication test failed for dados.gov.br: {e}")
            raise ConnectionError(f"Unable to authenticate with dados.gov.br: {e}") from e

    def test_connection(self) -> bool:
        """
        Test the connection to dados.gov.br.

        Performs a lightweight operation (search with rows=0) to verify connectivity.

        Returns:
            True if connection test successful, False otherwise

        Raises:
            ConnectionError: If unable to connect to dados.gov.br
        """
        try:
            # Use page=1 (required parameter) for lightweight test
            response_data = self.client.search_datasets(page=1)
            # API returns direct array, so check if it's a list
            if isinstance(response_data, list):
                logger.info(f"Connection test successful for dados.gov.br at {self.base_url}")
                return True
            else:
                logger.warning("Connection test failed: Invalid response format")
                return False
        except Exception as e:
            logger.error(f"Connection test failed for dados.gov.br: {e}")
            raise ConnectionError(f"Unable to connect to dados.gov.br: {e}") from e

    def list_listings(
        self,
        filters: dict[str, Any] | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[MarketplaceListing]:
        """
        List available datasets from dados.gov.br.

        Args:
            filters: Optional dictionary of filters:
                - q: Search query string
                - fq: Filter query (e.g., 'tags:environment')
                - organization: Organization name
                - tags: List of tags
            limit: Optional maximum number of listings to return
            offset: Optional offset for pagination

        Returns:
            List of MarketplaceListing objects

        Raises:
            ConnectionError: If unable to connect to dados.gov.br
            ValueError: If filters or pagination parameters are invalid
        """
        if limit is not None and limit == 0:
            return []

        try:
            # Extract query from filters (maps to nomeConjuntoDados)
            query = filters.get("q") if filters else None

            # Convert offset/limit to page number for API
            # API uses page-based pagination (pagina parameter is required)
            page = 1
            if offset is not None and limit is not None and limit > 0:
                page = (offset // limit) + 1
            elif offset is not None:
                # If only offset provided, assume default page size of 20
                page = (offset // 20) + 1

            # Build filters dict for API (map to API parameter names)
            api_filters = {}
            if filters:
                if "idOrganizacao" in filters:
                    api_filters["idOrganizacao"] = filters["idOrganizacao"]
                if "dadosAbertos" in filters:
                    api_filters["dadosAbertos"] = filters["dadosAbertos"]
                if "isPrivado" in filters:
                    api_filters["isPrivado"] = filters["isPrivado"]

            # Call Swagger API search endpoint
            # API returns direct array according to Swagger spec
            response_data = self.client.search_datasets(
                query=query, filters=api_filters if api_filters else None, page=page
            )

            # API returns direct array according to Swagger spec
            results = []
            if isinstance(response_data, list):
                # Direct array response (expected format)
                results = response_data
                # Apply limit if specified (API doesn't support limit parameter)
                if limit is not None and limit > 0:
                    results = list(results[:limit])
            elif isinstance(response_data, dict):
                # Fallback: try to extract array from dict (for backward compatibility)
                for key in ["results", "data", "items", "content", "datasets", "conjuntos_dados"]:
                    if key in response_data and isinstance(response_data[key], list):
                        results = response_data[key]
                        if limit is not None and limit > 0:
                            results = results[:limit]
                        break
                else:
                    # If no array found, check for error
                    if response_data.get("success") is False:
                        error_msg = response_data.get("error", "Unknown error")
                        if isinstance(error_msg, dict):
                            error_msg = error_msg.get("message", str(error_msg))
                        raise ValueError(f"dados.gov.br API error: {error_msg}")

            listings = []

            for dataset_item in results:
                # Ensure dataset_item is a dictionary
                if not isinstance(dataset_item, dict):
                    logger.warning(f"Skipping non-dict dataset item: {type(dataset_item)}")
                    continue

                try:
                    dataset_data: dict[str, Any] = dataset_item
                    listing = self._swagger_dataset_to_listing(dataset_data)
                    listings.append(listing)
                except Exception as e:
                    logger.warning(f"Failed to convert dataset to listing: {e}")
                    continue

            return listings
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ConnectionError(f"dados.gov.br API endpoint not found: {e}") from e
            raise ConnectionError(f"dados.gov.br API error: {e}") from e
        except httpx.RequestError as e:
            raise ConnectionError(f"Unable to connect to dados.gov.br: {e}") from e

    def get_listing(self, listing_id: str) -> MarketplaceListing:
        """
        Get a specific dataset by its ID.

        Args:
            listing_id: Dataset ID or name

        Returns:
            MarketplaceListing object

        Raises:
            NotFoundError: If dataset not found
            ConnectionError: If unable to connect to dados.gov.br
        """
        try:
            response_data = self.client.get_dataset(listing_id)

            # Handle different response structures:
            # CKAN format: {'success': True, 'result': {...}}
            # dados.gov.br format: May be direct object or different structure
            dataset_data: dict[str, Any] | None = None
            if isinstance(response_data, dict):
                if response_data.get("success") and response_data.get("result"):
                    # CKAN-style response
                    result = response_data.get("result", {})
                    if isinstance(result, dict):
                        dataset_data = result
                elif response_data.get("success") is False:
                    # Error response
                    error_msg = response_data.get("error", "Unknown error")
                    if isinstance(error_msg, dict):
                        error_msg = error_msg.get("message", str(error_msg))
                    if "not found" in str(error_msg).lower() or "404" in str(
                        response_data.get("error", {})
                    ):
                        raise NotFoundError(f"Dataset '{listing_id}' not found in dados.gov.br")
                    raise ValueError(f"dados.gov.br API error: {error_msg}")
                else:
                    # Direct dataset object (dados.gov.br format)
                    dataset_data = response_data
            elif isinstance(response_data, dict):
                dataset_data = response_data

            if not dataset_data or not isinstance(dataset_data, dict) or not dataset_data:
                raise NotFoundError(f"Dataset '{listing_id}' not found in dados.gov.br")

            return self._swagger_dataset_to_listing(dataset_data)
        except NotFoundError:
            raise
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise NotFoundError(f"Dataset '{listing_id}' not found in dados.gov.br") from e
            raise ConnectionError(f"dados.gov.br API error: {e}") from e
        except httpx.RequestError as e:
            raise ConnectionError(f"Unable to connect to dados.gov.br: {e}") from e

    def list_resources(self, listing_id: str) -> list[MarketplaceResource]:
        """
        List resources associated with a dataset.

        Args:
            listing_id: Dataset ID or name

        Returns:
            List of MarketplaceResource objects

        Raises:
            NotFoundError: If dataset not found
            ConnectionError: If unable to connect to dados.gov.br
        """
        # Get dataset to retrieve resources (already includes recursos from get_listing)
        try:
            dataset = self.get_listing(listing_id)
        except NotFoundError:
            raise

        # Resources are already included in listing.resources from get_listing()
        if dataset.resources:
            return dataset.resources

        # Fallback: Extract from dataset metadata
        dataset_data = dataset.metadata.get("swagger_dataset", {})
        resources_data = dataset_data.get("recursos") or dataset_data.get("resources", [])

        # If resources not in dataset data, fetch dataset directly
        if not resources_data:
            try:
                response_data = self.client.get_dataset(listing_id)
                # Handle direct object response (dados.gov.br format)
                if isinstance(response_data, dict) and not response_data.get("success"):
                    resources_data = response_data.get("recursos") or response_data.get(
                        "resources", []
                    )
            except Exception as e:
                logger.warning(f"Failed to fetch resources directly for dataset {listing_id}: {e}")

        resources = []
        for resource_data in resources_data:
            try:
                resource = self._swagger_resource_to_marketplace_resource(resource_data)
                resources.append(resource)
            except Exception as e:
                logger.warning(f"Failed to convert resource to MarketplaceResource: {e}")
                continue

        return resources

    def _swagger_dataset_to_listing(self, dataset_data: dict[str, Any]) -> MarketplaceListing:
        """
        Map Swagger API dataset response to MarketplaceListing.

        Handles both English (CKAN-style) and Portuguese (dados.gov.br) field names.

        Args:
            dataset_data: Dataset data from Swagger API response

        Returns:
            MarketplaceListing object
        """
        # Handle Portuguese field names (dados.gov.br) and English field names (CKAN)
        # Portuguese: identificador, titulo, descricao
        # English: id, name, title, description, notes
        dataset_id = (
            dataset_data.get("identificador")
            or dataset_data.get("id")
            or dataset_data.get("name")
            or ""
        )
        title = (
            dataset_data.get("titulo")
            or dataset_data.get("title")
            or dataset_data.get("name")
            or "Untitled"
        )
        description = (
            dataset_data.get("descricao")
            or dataset_data.get("notes")
            or dataset_data.get("description")
            or ""
        )

        # Extract tags (handle both 'tags' and 'tag' fields, Portuguese and English)
        tags = []
        tags_data = dataset_data.get("tags") or dataset_data.get("tag") or []
        if tags_data:
            for tag in tags_data:
                if isinstance(tag, dict):
                    # Handle Portuguese: nome, display_name
                    # Handle English: name, display_name
                    tag_name = tag.get("nome") or tag.get("name") or tag.get("display_name") or ""
                    if tag_name:
                        tags.append(tag_name)
                else:
                    tags.append(str(tag))

        # Extract organization (handle both 'organization' and 'organizacao' fields)
        organization = dataset_data.get("organizacao") or dataset_data.get("organization", {})
        category = None
        if organization:
            if isinstance(organization, dict):
                # Handle Portuguese: nome, titulo
                # Handle English: name, title
                category = (
                    organization.get("nome")
                    or organization.get("name")
                    or organization.get("titulo")
                    or organization.get("title")
                )
            else:
                category = str(organization)

        # Extract timestamps (handle both English and Portuguese field names)
        # Handle Brazilian date format (DD/MM/YYYY HH:MM:SS) and ISO format
        created_at = None
        updated_at = None

        def _parse_brazilian_date(date_str: str | None) -> datetime | None:
            """Parse Brazilian date format (DD/MM/YYYY HH:MM:SS) or ISO format."""
            if not date_str:
                return None
            try:
                # Try Brazilian format first (DD/MM/YYYY HH:MM:SS)
                if isinstance(date_str, str) and "/" in date_str:
                    if date_parser:
                        return date_parser.parse(date_str, dayfirst=True)
                    # Fallback: manual parsing for DD/MM/YYYY HH:MM:SS
                    try:
                        parts = date_str.split(" ")
                        date_part = parts[0]
                        time_part = parts[1] if len(parts) > 1 else "00:00:00"
                        day, month, year = date_part.split("/")
                        hour, minute, second = time_part.split(":")
                        return datetime(
                            int(year), int(month), int(day), int(hour), int(minute), int(second)
                        )
                    except (ValueError, IndexError):
                        pass
                # Try ISO format
                return datetime.fromisoformat(str(date_str).replace("Z", "+00:00"))
            except (ValueError, AttributeError, TypeError):
                return None

        # Handle created timestamp (dataCatalogacao is primary in Portuguese)
        created_field = (
            dataset_data.get("dataCatalogacao")
            or dataset_data.get("metadata_created")
            or dataset_data.get("data_criacao")
            or dataset_data.get("criado_em")
        )
        created_at = _parse_brazilian_date(created_field)

        # Handle modified timestamp (dataUltimaAtualizacaoMetadados is primary in Portuguese)
        modified_field = (
            dataset_data.get("dataUltimaAtualizacaoMetadados")
            or dataset_data.get("metadata_modified")
            or dataset_data.get("data_modificacao")
            or dataset_data.get("modificado_em")
        )
        updated_at = _parse_brazilian_date(modified_field)

        # Build URL
        url = None
        if dataset_id:
            url = urljoin(self.base_url, f"/dataset/{dataset_id}")

        # Extract license (handle Portuguese: licenca_id, licenca_titulo)
        license_id = dataset_data.get("licenca_id") or dataset_data.get("license_id")
        license_title = dataset_data.get("licenca_titulo") or dataset_data.get("license_title")

        # Extract author/maintainer (handle Portuguese: responsavel, autor, mantenedor)
        author = (
            dataset_data.get("responsavel")
            or dataset_data.get("autor")
            or dataset_data.get("author")
        )
        maintainer = dataset_data.get("mantenedor") or dataset_data.get("maintainer")
        contact_email = dataset_data.get("emailResponsavel")

        # Extract recursos (resources) from dataset and convert to MarketplaceResource objects
        resources = []
        recursos_data = dataset_data.get("recursos") or dataset_data.get("resources") or []
        for resource_data in recursos_data:
            try:
                resource = self._swagger_resource_to_marketplace_resource(resource_data)
                resources.append(resource)
            except Exception as e:
                logger.warning(f"Failed to convert resource to MarketplaceResource: {e}")
                continue

        # Build comprehensive metadata with all Portuguese fields
        metadata = {
            "swagger_dataset": dataset_data,  # Preserve full original data
            "organization": organization,
            "license_id": license_id,
            "license_title": license_title,
            "author": author,
            "maintainer": maintainer,
            "contact_email": contact_email,
            "version": dataset_data.get("versao") or dataset_data.get("version"),
            # Temporal coverage
            "temporal_coverage_start": dataset_data.get("coberturaTemporalInicio"),
            "temporal_coverage_end": dataset_data.get("coberturaTemporalFim"),
            "update_frequency": dataset_data.get("periodicidade"),
            # Spatial coverage
            "spatial_coverage": dataset_data.get("coberturaEspacial"),
            "spatial_coverage_value": dataset_data.get("valorCoberturaEspacial"),
            "spatial_granularity": dataset_data.get("granularidadeEspacial"),
            # Versioning
            "version_update_flag": dataset_data.get("atualizacaoVersao"),
            "update_status": dataset_data.get("atualizado"),
            "data_last_updated": dataset_data.get("dataUltimaAtualizacaoArquivo"),
            # Visibility & Status
            "visibility": dataset_data.get("visibilidade"),
            "deprecated": dataset_data.get("descontinuado", False),
            "deprecation_date": dataset_data.get("dataDescontinuacao"),
            "reuse_allowed": dataset_data.get("reuso", False),
            # Themes
            "themes": dataset_data.get("temas", []),
            # Related data
            "related_datasets": dataset_data.get("conjuntoDadosAssociados", []),
            # Data quality & compliance
            "demographic_data_race_ethnicity": dataset_data.get("dadosRacaEtnia", False),
            "demographic_data_gender": dataset_data.get("dadosGenero", False),
            "legal_compliance": dataset_data.get("observanciaLegal"),
            "open_data": dataset_data.get("dadosAbertos"),
            "quality_seal": dataset_data.get("selo"),
            "origin": dataset_data.get("origemCadastro"),
            # Slug
            "slug": dataset_data.get("nome"),
        }

        return MarketplaceListing(
            marketplace_id=dataset_id,
            marketplace_type=MarketplaceType.CKAN_INSTANCE,
            title=title,
            description=description,
            category=category,
            tags=tags,
            resources=resources,  # Include converted resources
            metadata=metadata,
            created_at=created_at,
            updated_at=updated_at,
            url=url,
        )

    def _swagger_resource_to_marketplace_resource(
        self, resource_data: dict[str, Any]
    ) -> MarketplaceResource:
        """
        Map Swagger API resource response to MarketplaceResource.

        Comprehensive mapping of Portuguese (dados.gov.br) and English (CKAN) field names.
        Prioritizes Portuguese field names (titulo, link, dataCatalogacao, dataUltimaAtualizacaoArquivo).

        Args:
            resource_data: Resource data from Swagger API response

        Returns:
            MarketplaceResource object
        """
        # === RESOURCE ID ===
        resource_id = resource_data.get("id") or resource_data.get("identificador") or ""

        # === NAME (titulo is primary in Portuguese) ===
        name = (
            resource_data.get("titulo")
            or resource_data.get("title")
            or resource_data.get("nome")
            or resource_data.get("name")
            or resource_data.get("descricao")
            or resource_data.get("description")
            or "Unnamed Resource"
        )

        # === DESCRIPTION ===
        description = resource_data.get("descricao") or resource_data.get("description") or ""

        # === URL (link is primary in Portuguese) ===
        url = (
            resource_data.get("link")
            or resource_data.get("url")
            or resource_data.get("url_recurso")
            or None
        )

        # === FORMAT ===
        format_value = resource_data.get("formato") or resource_data.get("format") or ""
        format_type = format_value.upper() if format_value else None

        # === SIZE ===
        size_bytes = resource_data.get("tamanho") or resource_data.get("size")

        # === RESOURCE TYPE ===
        # Use the API's authoritative ``tipo`` field when present;
        # fall back to the URL-presence heuristic for backward compatibility.
        tipo = resource_data.get("tipo")
        if tipo:
            resource_type = str(tipo).upper()
        elif url:
            resource_type = "FILE"
        else:
            resource_type = "API"

        # === TIMESTAMPS ===
        # Created (dataCatalogacao is primary in Portuguese)
        created = (
            resource_data.get("dataCatalogacao")
            or resource_data.get("criado_em")
            or resource_data.get("created")
        )

        # Last modified (dataUltimaAtualizacaoArquivo is primary in Portuguese)
        last_modified = (
            resource_data.get("dataUltimaAtualizacaoArquivo")
            or resource_data.get("modificado_em")
            or resource_data.get("last_modified")
        )

        # === BUILD METADATA ===
        metadata = {
            "swagger_resource": resource_data,  # Preserve full original data
            # Timestamps
            "created": created,
            "last_modified": last_modified,
            # File information
            "filename": resource_data.get("nomeArquivo"),
            "order_number": resource_data.get("numOrdem"),
            "download_count": resource_data.get("quantidadeDownloads"),
            # Relationships
            "dataset_id": resource_data.get("idConjuntoDados"),
            # MIME types
            "mimetype": resource_data.get("mimetype") or resource_data.get("tipo_mime"),
            "mimetype_inner": resource_data.get("mimetype_inner")
            or resource_data.get("tipo_mime_interno"),
            # Integrity
            "hash": resource_data.get("hash") or resource_data.get("hash_recurso"),
            # Type
            "resource_type": resource_data.get("tipo"),
        }

        return MarketplaceResource(
            resource_id=resource_id,
            resource_type=resource_type,
            name=name,
            description=description,
            url=url,
            format=format_type,
            size_bytes=size_bytes,
            metadata=metadata,
        )

    def create_listing(self, listing: MarketplaceListing) -> MarketplaceListing:
        """
        Create a new dataset in dados.gov.br.

        **DEPRECATED**: dados.gov.br connector is harvest-only (PULL only).
        dados.gov.br is a public data portal that should be harvested FROM,
        not pushed TO. This method raises NotImplementedError.

        Args:
            listing: MarketplaceListing object with dataset details

        Returns:
            Created MarketplaceListing object

        Raises:
            NotImplementedError: dados.gov.br connector does not support push operations
        """
        raise NotImplementedError(
            "dados.gov.br connector is harvest-only (PULL only). "
            "dados.gov.br is a public data portal that should be harvested FROM, not pushed TO. "
            "Use sync_pull() to harvest data from dados.gov.br."
        )

    def update_listing(self, listing: MarketplaceListing) -> MarketplaceListing:
        """
        Update an existing dataset in dados.gov.br.

        **DEPRECATED**: dados.gov.br connector is harvest-only (PULL only).
        This method raises NotImplementedError.

        Args:
            listing: MarketplaceListing object with updated dataset details

        Returns:
            Updated MarketplaceListing object

        Raises:
            NotImplementedError: dados.gov.br connector does not support push operations
        """
        raise NotImplementedError(
            "dados.gov.br connector is harvest-only (PULL only). "
            "dados.gov.br is a public data portal that should be harvested FROM, not pushed TO."
        )

    def publish_resource(
        self, listing_id: str, resource: MarketplaceResource
    ) -> MarketplaceResource:
        """
        Publish a resource to a dataset in dados.gov.br.

        **DEPRECATED**: dados.gov.br connector is harvest-only (PULL only).
        This method raises NotImplementedError.

        Args:
            listing_id: Dataset ID
            resource: MarketplaceResource object with resource details

        Returns:
            Published MarketplaceResource object

        Raises:
            NotImplementedError: dados.gov.br connector does not support push operations
        """
        raise NotImplementedError(
            "dados.gov.br connector is harvest-only (PULL only). "
            "dados.gov.br is a public data portal that should be harvested FROM, not pushed TO."
        )

    def download_resource(self, resource_id: str, destination_path: str, **kwargs) -> str:
        """
        Download a resource from dados.gov.br.

        Args:
            resource_id: Resource ID
            destination_path: Local filesystem path where resource should be saved
            **kwargs: Additional connector-specific options.
                - listing_id: Optional dataset/listing ID that contains the
                  resource. When provided, the resource is looked up through
                  the dataset endpoint per the Swagger spec instead of the
                  (unreliable) direct-resource endpoints.

        Returns:
            Path to the downloaded file

        Raises:
            NotFoundError: If resource not found
            ConnectionError: If unable to connect to dados.gov.br
            IOError: If unable to write to destination path
            PermissionError: If user lacks permission to download resource
        """
        listing_id = kwargs.get("listing_id")
        try:
            # Get resource details — use dataset-scoped lookup when
            # listing_id is available, since the Swagger API nests
            # resources inside datasets.
            response_data = self.client.get_resource(resource_id, dataset_id=listing_id)

            if not response_data.get("success"):
                error_msg = response_data.get("error", {}).get("message", "Unknown error")
                if "not found" in error_msg.lower():
                    raise NotFoundError(f"Resource '{resource_id}' not found in dados.gov.br")
                raise ValueError(f"dados.gov.br API error: {error_msg}")

            resource_data = response_data.get("result", {})
            if not resource_data:
                raise NotFoundError(f"Resource '{resource_id}' not found in dados.gov.br")

            resource_url = (
                resource_data.get("link")
                or resource_data.get("url")
                or resource_data.get("url_recurso")
            )
            if not resource_url:
                raise ValueError(
                    f"Resource '{resource_id}' has no downloadable URL in dados.gov.br"
                )

            # Download resource using httpx
            import os

            # Ensure destination directory exists
            os.makedirs(
                os.path.dirname(destination_path) if os.path.dirname(destination_path) else ".",
                exist_ok=True,
            )

            # Download with chave-api-dados-abertos header
            headers = {}
            if self.jwt_token:
                headers["chave-api-dados-abertos"] = self.jwt_token
            with httpx.stream("GET", resource_url, headers=headers, timeout=300.0) as response:
                response.raise_for_status()

                with open(destination_path, "wb") as f:
                    for chunk in response.iter_bytes():
                        f.write(chunk)

            logger.info(f"Downloaded resource '{resource_id}' to {destination_path}")
            return destination_path

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise NotFoundError(
                    f"Resource '{resource_id}' not found in dados.gov.br"
                ) from e
            raise ConnectionError(f"dados.gov.br API error: {e}") from e
        except httpx.RequestError as e:
            raise ConnectionError(f"Unable to connect to dados.gov.br: {e}") from e
        except OSError:
            raise
        except (NotFoundError, PermissionError, ConnectionError, OSError, ValueError):
            raise
        except Exception as e:
            raise ConnectionError(f"Unexpected error downloading resource: {e}") from e

    def sync_pull(
        self,
        listing_ids: list[str] | None = None,
        filters: dict[str, Any] | None = None,
        options: dict[str, Any] | None = None,
    ) -> SyncResult:
        """
        Pull (harvest) datasets from dados.gov.br to Hub.

        Synchronizes dados.gov.br listings to Hub by:
        1. Fetching listings from dados.gov.br (by IDs or via filters)
        2. Fetching resources for each listing
        3. Mapping listings to Hub asset format using map_to_hub_asset
        4. Returning mappings in SyncResult metadata for asset creation

        Args:
            listing_ids: Optional list of specific dataset IDs to sync.
                If None, syncs all datasets matching filters.
            filters: Optional dictionary of filters to apply (passed to list_listings)
            options: Optional dictionary of sync options:
                - dry_run: If True, simulate sync without creating assets
                - limit: Maximum number of listings to sync (default: None, sync all)
                - include_resources: If True, fetch resources for each listing (default: True)

        Returns:
            SyncResult object with operation details and mappings in metadata

        Raises:
            ValueError: If filters or options are invalid
            ConnectionError: If unable to connect to dados.gov.br
        """
        options = options or {}
        dry_run = options.get("dry_run", False)
        limit = options.get("limit")
        include_resources = options.get("include_resources", True)
        started_at = timezone.now()

        successful_items = 0
        failed_items = 0
        skipped_items = 0
        errors = []
        mappings = []

        # Explicit empty listing_ids: sync nothing (do not fall through to list all)
        if listing_ids is not None and len(listing_ids) == 0:
            return SyncResult(
                status=SyncStatus.COMPLETED,
                total_items=0,
                successful_items=0,
                failed_items=0,
                skipped_items=0,
                errors=[],
                metadata={"dry_run": dry_run, "reason": "empty_listing_ids"},
                started_at=started_at,
                completed_at=timezone.now(),
            )

        # Zero limit: sync nothing
        if limit is not None and limit == 0:
            return SyncResult(
                status=SyncStatus.COMPLETED,
                total_items=0,
                successful_items=0,
                failed_items=0,
                skipped_items=0,
                errors=[],
                metadata={"dry_run": dry_run, "reason": "zero_limit"},
                started_at=started_at,
                completed_at=timezone.now(),
            )

        # Get listings to sync
        try:
            if listing_ids:
                # Fetch specific listings by ID
                listings = []
                for listing_id in listing_ids:
                    try:
                        listing = self.get_listing(listing_id)
                        listings.append(listing)
                    except NotFoundError:
                        skipped_items += 1
                        error_msg = f"Listing '{listing_id}' not found"
                        errors.append(error_msg)
                        logger.warning(error_msg)
                        continue
                    except Exception as e:
                        failed_items += 1
                        error_msg = f"Failed to fetch listing '{listing_id}': {e}"
                        errors.append(error_msg)
                        logger.warning(error_msg)
                        continue
            else:
                # Fetch listings using filters
                listings = self.list_listings(filters=filters, limit=limit)

            total_items = len(listings)

            # Process each listing
            for listing in listings:
                try:
                    # Resources are already included in listing.resources from get_listing()
                    # Only fetch separately if not included and include_resources is True
                    if include_resources and not listing.resources:
                        try:
                            resources = self.list_resources(listing.marketplace_id)
                            # Update listing with resources
                            listing.resources = resources
                        except Exception as e:
                            logger.warning(
                                f"Failed to fetch resources for listing '{listing.marketplace_id}': {e}"
                            )
                            # Continue without resources rather than failing the whole sync

                    # Map to Hub asset format
                    mapping = self.map_to_hub_asset(listing)
                    mappings.append(mapping)
                    successful_items += 1
                except Exception as e:
                    failed_items += 1
                    error_msg = f"Failed to sync listing '{listing.marketplace_id}': {e}"
                    errors.append(error_msg)
                    logger.warning(error_msg)
                    continue

            status = SyncStatus.COMPLETED if failed_items == 0 else SyncStatus.PARTIAL
            if successful_items == 0:
                status = SyncStatus.FAILED

            return SyncResult(
                status=status,
                total_items=total_items,
                successful_items=successful_items,
                failed_items=failed_items,
                skipped_items=skipped_items,
                errors=errors,
                started_at=started_at,
                completed_at=timezone.now(),
                metadata={
                    "mappings": mappings,
                    "dry_run": dry_run,
                    "include_resources": include_resources,
                },
            )
        except Exception as e:
            logger.error(f"Sync pull failed: {e}", exc_info=True)
            return SyncResult(
                status=SyncStatus.FAILED,
                total_items=0,
                successful_items=successful_items,
                failed_items=failed_items,
                skipped_items=skipped_items,
                errors=[str(e)],
                started_at=started_at,
                completed_at=timezone.now(),
            )

    def sync_push(self, hub_asset_ids: list[str], force_update: bool = False) -> SyncResult:
        """
        Push Hub assets to dados.gov.br.

        **DEPRECATED**: dados.gov.br connector is harvest-only (PULL only).
        This method raises NotImplementedError.

        Args:
            hub_asset_ids: List of Hub asset IDs to push
            force_update: Whether to force update existing listings

        Returns:
            SyncResult object

        Raises:
            NotImplementedError: dados.gov.br connector does not support push operations
        """
        raise NotImplementedError(
            "dados.gov.br connector is harvest-only (PULL only). "
            "dados.gov.br is a public data portal that should be harvested FROM, not pushed TO."
        )

    def map_to_hub_asset(
        self, listing: MarketplaceListing, sync_job_id: str | None = None
    ) -> MarketplaceAssetMapping:
        """
        Map a dados.gov.br dataset to a Hub asset representation.

        Comprehensive mapping including all Portuguese metadata fields for ODPS/ODCS contract creation.

        Args:
            listing: MarketplaceListing object to map
            sync_job_id: Optional sync job ID for tracking

        Returns:
            MarketplaceAssetMapping object containing all mapped data

        Raises:
            ValueError: If listing data cannot be mapped
        """
        if not listing:
            raise ValueError("Listing is required")

        # Get Swagger dataset data from metadata
        swagger_dataset = listing.metadata.get("swagger_dataset", {}) if listing.metadata else {}

        # Extract domain from organization/category
        domain = listing.category
        if not domain and swagger_dataset.get("organizacao"):
            org = swagger_dataset["organizacao"]
            if isinstance(org, dict):
                domain = org.get("nome") or org.get("name") or org.get("titulo") or org.get("title")
            elif isinstance(org, str):
                domain = org

        # === STATUS (visibility is derived from status per D250.4) ===
        status = "DRAFT"

        visibilidade = swagger_dataset.get("visibilidade", "").upper()
        if visibilidade == "PUBLICA":
            # Check if dataset has resources and is updated
            atualizado = swagger_dataset.get("atualizado", "").upper()
            if atualizado == "ATUALIZADO" and listing.resources:
                status = "PUBLIC"  # D250.4: PUBLIC status → PUBLIC visibility
            else:
                status = "DRAFT"  # no resources / not updated → INTERNAL visibility
        elif visibilidade == "PRIVADA":
            status = "DRAFT"  # INTERNAL visibility

        # Check deprecated flag
        if swagger_dataset.get("descontinuado", False):
            status = "DEPRECATED"

        # Extract tags
        tags = listing.tags or []
        if not tags and swagger_dataset.get("tags"):
            tags = [
                tag.get("nome") or tag.get("name") or tag if isinstance(tag, dict) else tag
                for tag in swagger_dataset.get("tags", [])
            ]

        # === BUILD ASSET DATA ===
        # ``visibility`` is not set — derived from ``status`` per D250.4.
        asset_data: dict[str, Any] = {
            "name": listing.title,
            "description": listing.description or "",
            "key": f"dados-gov-br-{listing.marketplace_id}",
            "tags": tags,
            "status": status,
        }

        if domain:
            asset_data["domain"] = domain

        if swagger_dataset.get("versao"):
            asset_data["version"] = swagger_dataset["versao"]

        # === RESOURCES ===
        # Resources are already in listing.resources from get_listing()
        resources = listing.resources or []
        if not resources:
            try:
                resources = self.list_resources(listing.marketplace_id)
            except Exception as e:
                logger.warning(f"Failed to get resources for listing {listing.marketplace_id}: {e}")

        # === BUILD SOURCE METADATA ===
        source_metadata: dict[str, Any] = {
            "marketplace_type": MarketplaceType.CKAN_INSTANCE.value,
            "marketplace_id": "dados.gov.br",
            "listing_id": listing.marketplace_id,
            "listing_url": listing.url,
            "synced_at": timezone.now().isoformat(),
            # Portuguese metadata fields
            "origin": swagger_dataset.get("origemCadastro"),
            "cataloged_at": swagger_dataset.get("dataCatalogacao"),
            "metadata_updated_at": swagger_dataset.get("dataUltimaAtualizacaoMetadados"),
            "data_updated_at": swagger_dataset.get("dataUltimaAtualizacaoArquivo"),
            "organization": swagger_dataset.get("organizacao"),
            "responsible_party": swagger_dataset.get("responsavel"),
            "contact_email": swagger_dataset.get("emailResponsavel"),
            "update_frequency": swagger_dataset.get("periodicidade"),
            "spatial_coverage": swagger_dataset.get("coberturaEspacial"),
            "temporal_coverage_start": swagger_dataset.get("coberturaTemporalInicio"),
            "temporal_coverage_end": swagger_dataset.get("coberturaTemporalFim"),
            "version": swagger_dataset.get("versao"),
            "quality_seal": swagger_dataset.get("selo"),
            "open_data": swagger_dataset.get("dadosAbertos"),
            "legal_compliance": swagger_dataset.get("observanciaLegal"),
        }

        if sync_job_id:
            source_metadata["sync_job_id"] = sync_job_id

        # === BUILD ODPS METADATA ===
        odps_metadata = None
        if swagger_dataset.get("dadosAbertos") == "Sim" or visibilidade == "PUBLICA":
            odps_metadata = {
                "license": swagger_dataset.get("licenca") or listing.metadata.get("license_id"),
                "open_data": swagger_dataset.get("dadosAbertos") == "Sim",
                "visibility": swagger_dataset.get("visibilidade"),
                "update_frequency": swagger_dataset.get("periodicidade"),
                "product": {
                    "name": listing.title,
                    "description": listing.description,
                    "version": swagger_dataset.get("versao"),
                    "details": {
                        "product_name": listing.title,
                        "product_description": listing.description,
                        "product_version": swagger_dataset.get("versao"),
                    },
                },
                "product_details": {
                    "product_name": listing.title,
                    "product_description": listing.description,
                    "product_version": swagger_dataset.get("versao"),
                },
                "contact": {
                    "name": swagger_dataset.get("responsavel"),
                    "email": swagger_dataset.get("emailResponsavel"),
                },
                "lifecycle": {
                    "refreshCadence": swagger_dataset.get("periodicidade"),
                    "lastUpdated": swagger_dataset.get("dataUltimaAtualizacaoArquivo"),
                },
            }

        # === BUILD ODCS METADATA ===
        odcs_metadata = {
            "quality_seal": swagger_dataset.get("selo"),
            "version": swagger_dataset.get("versao"),
            "update_status": swagger_dataset.get("atualizado"),
            "open_data_flag": swagger_dataset.get("dadosAbertos") == "Sim",
            "legal_compliance": swagger_dataset.get("observanciaLegal"),
            "lifecycle": {
                "refreshCadence": swagger_dataset.get("periodicidade"),
                "lastUpdated": swagger_dataset.get("dataUltimaAtualizacaoArquivo"),
            },
            "compliance": {
                "legalBasis": swagger_dataset.get("observanciaLegal"),
                "demographic_data_race_ethnicity": swagger_dataset.get("dadosRacaEtnia", False),
                "demographic_data_gender": swagger_dataset.get("dadosGenero", False),
            },
        }

        # Extract schema hints from recursos
        if resources:
            formats = [r.format for r in resources if r.format]
            sizes = [r.size_bytes for r in resources if r.size_bytes]
            if formats:
                odcs_metadata["schema"] = {
                    "hints": {
                        "formats": list(set(formats)),
                        "total_size": sum(sizes) if sizes else None,
                        "resource_count": len(resources),
                    }
                }

        return MarketplaceAssetMapping(
            asset_data=asset_data,
            source_type=AssetSourceType.FEDERATED,
            source_metadata=source_metadata,
            odps_metadata=odps_metadata,
            odcs_metadata=odcs_metadata,
            resources=resources,
        )

    def map_from_hub_asset(
        self, hub_asset: Any, sync_job_id: str | None = None
    ) -> MarketplaceListing:
        """
        Map a Hub asset to a dados.gov.br dataset representation.

        **DEPRECATED**: dados.gov.br connector is harvest-only (PULL only).
        This method raises NotImplementedError.

        Args:
            hub_asset: Hub asset object
            sync_job_id: Optional sync job ID

        Returns:
            MarketplaceListing object

        Raises:
            NotImplementedError: dados.gov.br connector does not support push operations
        """
        raise NotImplementedError(
            "dados.gov.br connector is harvest-only (PULL only). "
            "dados.gov.br is a public data portal that should be harvested FROM, not pushed TO."
        )
