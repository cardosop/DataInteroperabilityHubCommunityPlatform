"""
Dados.gov.br Swagger API Client

Client for interacting with dados.gov.br Swagger API endpoints.
Supports Swagger specification loading, endpoint resolution, and JWT Bearer token authentication.
"""

import contextlib
import logging
import re
from typing import Any
from urllib.parse import urljoin

import httpx

logger = logging.getLogger(__name__)


class DadosGovBrAPIClient:
    """
    Client for dados.gov.br Swagger API.

    Provides methods for interacting with dados.gov.br API endpoints using
    Swagger specification for endpoint discovery and JWT Bearer token authentication.

    Attributes:
        base_url: Base URL of the dados.gov.br API
        jwt_token: JWT Bearer token for authentication
        _swagger_spec: Cached Swagger specification (loaded on demand)
        client: HTTP client for making requests
    """

    def __init__(self, base_url: str, jwt_token: str | None = None, swagger_spec_url: str | None = None):
        """
        Initialize dados.gov.br API client.

        Args:
            base_url: Base URL of the dados.gov.br API (e.g., "https://dados.gov.br")
            jwt_token: Optional JWT Bearer token for authentication.
                      Public endpoints may work without authentication.
            swagger_spec_url: Optional URL to Swagger JSON specification.
                             When provided, the spec is loaded lazily on first use
                             (via get_endpoint_path), not eagerly during __init__.
        """
        self.base_url = base_url.rstrip("/")
        self.jwt_token = jwt_token
        self._swagger_spec: dict[str, Any] | None = None
        self._swagger_spec_url = swagger_spec_url  # stored for lazy loading

        # Initialize HTTP client with Bearer token authentication
        # Note: follow_redirects=True allows following redirects, but we check for signin redirects
        # to detect authentication failures.
        # Use httpx.Timeout for granular control: connect=10s, read=25s, write=10s.
        # A single float timeout (30.0) maps to connect/read/write/pool=30s,
        # but follow_redirects=True can reset the timer per redirect, allowing
        # a hung server to hold the socket open much longer than expected.
        self.client = httpx.Client(
            base_url=self.base_url,
            timeout=httpx.Timeout(connect=10.0, read=25.0, write=10.0, pool=5.0),
            headers=self._get_default_headers(),
            follow_redirects=True,
            # Track redirects to detect authentication failures
            max_redirects=10,
        )

    def _get_default_headers(self) -> dict[str, str]:
        """
        Get default HTTP headers with optional JWT token.

        dados.gov.br API uses 'chave-api-dados-abertos' header (not 'Authorization: Bearer').
        According to Swagger spec: https://dados.gov.br/swagger-ui/index.html
        """
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        if self.jwt_token:
            # dados.gov.br API uses 'chave-api-dados-abertos' header, not 'Authorization: Bearer'
            headers["chave-api-dados-abertos"] = self.jwt_token

        return headers

    def load_swagger_spec(self, swagger_url: str | None = None) -> dict[str, Any] | None:
        """
        Load Swagger JSON specification from URL.

        Args:
            swagger_url: URL to Swagger JSON specification (defaults to /v3/api-docs)

        Returns:
            Swagger specification dictionary if successful, None otherwise
        """
        if swagger_url is None:
            swagger_url = urljoin(self.base_url, "/v3/api-docs")

        try:
            response = httpx.get(swagger_url, timeout=10.0, follow_redirects=True)
            response.raise_for_status()

            # Check if response is JSON
            content_type = response.headers.get("content-type", "")
            if content_type and "application/json" not in str(content_type):
                logger.warning(
                    f"Swagger spec URL returned non-JSON content: {content_type}. "
                    f"Response preview: {response.text[:200]}"
                )
                return None

            spec = response.json()
            self._swagger_spec = spec

            logger.info(
                f"Loaded Swagger specification from {swagger_url} "
                f"(paths: {len(spec.get('paths', {}))})"
            )

            return spec
        except httpx.RequestError as e:
            logger.warning(f"Failed to load Swagger spec from {swagger_url}: {e}")
            return None
        except httpx.HTTPStatusError as e:
            logger.warning(f"Swagger spec URL returned {e.response.status_code}: {swagger_url}")
            return None
        except Exception as e:
            logger.warning(f"Unexpected error loading Swagger spec: {e}")
            return None

    def get_endpoint_path(self, operation_id: str) -> str:
        """
        Resolve endpoint path from Swagger spec using operation ID.

        Loads the Swagger spec lazily on first call (if a URL was provided),
        then falls back to a hardcoded endpoint map if the spec is unavailable.

        Args:
            operation_id: Operation ID from Swagger spec (e.g., "listDatasets")

        Returns:
            Endpoint path (e.g., "/dados/api/publico/conjuntos-dados")
        """
        # Lazy-load the Swagger spec on first use — avoids making an HTTP
        # request during __init__ (which causes 10 s timeouts in tests and
        # slows down application startup).
        if self._swagger_spec is None and self._swagger_spec_url is not None:
            self.load_swagger_spec(self._swagger_spec_url)

        if self._swagger_spec:
            paths = self._swagger_spec.get("paths", {})
            for path, methods in paths.items():
                for _method, operation in methods.items():
                    if operation.get("operationId") == operation_id:
                        logger.debug(
                            f"Resolved endpoint '{operation_id}' to '{path}' from Swagger spec"
                        )
                        return path

        # Fallback to dados.gov.br Swagger API endpoint pattern (NOT CKAN-style)
        # Map common operation IDs to dados.gov.br endpoints
        endpoint_map = {
            "package_search": "/dados/api/publico/conjuntos-dados",
            "listDatasets": "/dados/api/publico/conjuntos-dados",
            "package_show": "/dados/api/publico/conjuntos-dados",  # Will be appended with {id}
            "getDataset": "/dados/api/publico/conjuntos-dados",  # Will be appended with {id}
            "resource_show": "/dados/api/publico/conjuntos-dados",  # Resources are nested in datasets
            "getResource": "/dados/api/publico/conjuntos-dados",  # Resources are nested in datasets
        }

        fallback_path = endpoint_map.get(operation_id)
        if not fallback_path:
            # Default fallback to dados.gov.br public API pattern
            fallback_path = f"/dados/api/publico/{operation_id}"

        logger.debug(
            f"Using fallback endpoint path '{fallback_path}' for operation '{operation_id}'"
        )
        return fallback_path

    def _parse_html_error(self, html_content: str) -> dict[str, Any]:
        """
        Parse HTML error response to extract error messages and diagnostic information.

        Args:
            html_content: HTML content from error response

        Returns:
            Dictionary with parsed error information:
            - error_message: Extracted error message
            - redirect_url: Redirect URL if present
            - status_code: HTTP status code if found
            - details: Additional diagnostic information
        """
        error_info = {
            "error_message": None,
            "redirect_url": None,
            "status_code": None,
            "details": [],
        }

        # Try to extract error messages from common HTML patterns
        # Look for error messages in common tags
        error_patterns = [
            r"<title[^>]*>(.*?)</title>",
            r"<h1[^>]*>(.*?)</h1>",
            r"<h2[^>]*>(.*?)</h2>",
            r'<div[^>]*class=["\']error["\'][^>]*>(.*?)</div>',
            r'<div[^>]*class=["\']alert["\'][^>]*>(.*?)</div>',
            r'<p[^>]*class=["\']error["\'][^>]*>(.*?)</p>',
        ]

        for pattern in error_patterns:
            matches = re.findall(pattern, html_content, re.IGNORECASE | re.DOTALL)
            if matches:
                error_info["error_message"] = matches[0].strip()
                break

        # Extract redirect URL if present
        redirect_patterns = [
            r'<meta[^>]*http-equiv=["\']refresh["\'][^>]*content=["\']\d+;\s*url=([^"\']+)["\']',
            r'window\.location\s*=\s*["\']([^"\']+)["\']',
            r'location\.href\s*=\s*["\']([^"\']+)["\']',
        ]

        for pattern in redirect_patterns:
            matches = re.findall(pattern, html_content, re.IGNORECASE)
            if matches:
                error_info["redirect_url"] = matches[0]
                break

        # Extract status code if present
        status_patterns = [
            r"<h1[^>]*>(\d{3})[^<]*</h1>",
            r"Status[:\s]+(\d{3})",
            r"HTTP[/\d\.]+\s+(\d{3})",
        ]

        for pattern in status_patterns:
            matches = re.findall(pattern, html_content, re.IGNORECASE)
            if matches:
                with contextlib.suppress(ValueError):
                    error_info["status_code"] = int(matches[0])
                break

        # Extract additional details from common error page elements
        detail_patterns = [
            r"<p[^>]*>(.*?)</p>",
            r"<li[^>]*>(.*?)</li>",
        ]

        for pattern in detail_patterns:
            matches = re.findall(pattern, html_content, re.IGNORECASE | re.DOTALL)
            for match in matches[:5]:  # Limit to first 5 matches
                text = re.sub(r"<[^>]+>", "", match).strip()
                if text and len(text) > 10:  # Only include substantial text
                    error_info["details"].append(text)

        return error_info

    def _request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Make authenticated API request.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            params: Query parameters
            body: Request body (for POST/PUT requests)

        Returns:
            Response JSON as dictionary

        Raises:
            httpx.HTTPStatusError: For HTTP errors (with parsed HTML error messages if applicable)
            httpx.RequestError: For network errors
            ValueError: If response is HTML and cannot be parsed
        """
        kwargs: dict[str, Any] = {"headers": self._get_default_headers()}

        if params:
            kwargs["params"] = params
        if body:
            kwargs["json"] = body

        try:
            response = self.client.request(method, endpoint, **kwargs)

            # Check if we were redirected to signin (authentication failure)
            if response.status_code == 200:
                # Check if the final URL after redirects is the signin page
                final_url = str(response.url)
                if "/signin" in final_url or "/login" in final_url:
                    logger.error(
                        f"API endpoint redirected to signin page: {method} {endpoint} -> {final_url}. "
                        f"This indicates authentication failure - JWT token may be expired or invalid."
                    )
                    raise ValueError(
                        f"dados.gov.br API authentication failed: Endpoint '{endpoint}' redirected to signin page. "
                        f"JWT token may be expired or invalid. Please check DADOS_GOV_BR_API_KEY environment variable "
                        f"(or CKAN_DADOS_GOV_BR_API_KEY for backward compatibility)."
                    )

            response.raise_for_status()

            # Check if response is JSON
            content_type = response.headers.get("content-type", "")
            if content_type and "application/json" not in str(content_type):
                # Check if it's HTML (error response)
                if "text/html" in str(content_type) or response.text.strip().startswith("<"):
                    error_info = self._parse_html_error(response.text)
                    error_msg = error_info.get("error_message") or "API returned HTML error page"
                    if error_info.get("redirect_url"):
                        error_msg += f" (redirects to: {error_info['redirect_url']})"
                    if error_info.get("details"):
                        error_msg += f" - {error_info['details'][0]}"

                    logger.warning(
                        f"API endpoint returned HTML error: {method} {endpoint} - {error_msg}"
                    )
                    raise ValueError(
                        f"dados.gov.br API returned HTML error: {error_msg}. "
                        f"Endpoint: {endpoint}, Status: {response.status_code}"
                    )

                logger.warning(
                    f"API endpoint returned non-JSON content: {content_type}. "
                    f"Endpoint: {endpoint}, Status: {response.status_code}"
                )
                # Try to parse as JSON anyway (some APIs don't set content-type correctly)
                try:
                    return response.json()
                except (ValueError, TypeError, AttributeError):
                    raise ValueError(
                        f"API endpoint returned non-JSON response: {response.text[:200]}"
                    )

            return response.json()
        except httpx.HTTPStatusError as e:
            # Check if we were redirected to signin (authentication failure)
            final_url = str(e.response.url) if hasattr(e.response, "url") else ""
            if "/signin" in final_url or "/login" in final_url:
                logger.error(
                    f"API endpoint redirected to signin page: {method} {endpoint} -> {final_url}. "
                    f"This indicates authentication failure - JWT token may be expired or invalid."
                )
                raise ValueError(
                    f"dados.gov.br API authentication failed: Endpoint '{endpoint}' redirected to signin page. "
                    f"JWT token may be expired or invalid. Please check CKAN_DADOS_GOV_BR_API_KEY environment variable."
                ) from e

            # Check if error response is HTML
            content_type = e.response.headers.get("content-type", "")
            if "text/html" in str(content_type) or e.response.text.strip().startswith("<"):
                error_info = self._parse_html_error(e.response.text)
                error_msg = (
                    error_info.get("error_message") or f"HTTP {e.response.status_code} error"
                )
                if error_info.get("redirect_url"):
                    error_msg += f" (redirects to: {error_info['redirect_url']})"
                if error_info.get("details"):
                    error_msg += f" - {error_info['details'][0]}"

                logger.warning(
                    f"API request failed with HTML error: {method} {endpoint} - "
                    f"Status {e.response.status_code}: {error_msg}"
                )
                # Create a new exception with parsed error message
                raise httpx.HTTPStatusError(
                    error_msg, request=e.request, response=e.response
                ) from e

            # Log 4xx (client errors) at WARNING — they are expected outcomes
            # for normal API usage (e.g. 404 for non-existent datasets).
            # Log 5xx (server errors) at ERROR — they indicate infrastructure issues.
            if e.response.status_code < 500:
                logger.warning(
                    f"API request failed: {method} {endpoint} - "
                    f"Status {e.response.status_code}: {e.response.text[:200]}"
                )
            else:
                logger.error(
                    f"API request failed: {method} {endpoint} - "
                    f"Status {e.response.status_code}: {e.response.text[:200]}"
                )
            raise
        except httpx.RequestError as e:
            logger.error(f"Network error making API request: {method} {endpoint} - {e}")
            raise

    def search_datasets(
        self,
        query: str | None = None,
        filters: dict[str, Any] | None = None,
        limit: int | None = None,
        offset: int | None = None,
        page: int | None = None,
    ) -> dict[str, Any]:
        """
        Search datasets using dados.gov.br Swagger API endpoint.

        Uses GET /dados/api/publico/conjuntos-dados endpoint.
        According to Swagger spec: https://dados.gov.br/swagger-ui/index.html

        Args:
            query: Search query string (mapped to nomeConjuntoDados parameter)
            filters: Additional filters:
                - idOrganizacao: Organization ID (string)
                - dadosAbertos: Open data flag (boolean)
                - isPrivado: Private flag (string, default "false")
            limit: Maximum number of results per page (not directly supported, converted to page)
            offset: Offset for pagination (converted to page number)
            page: Page number (required by API, defaults to 1 if not provided)

        Returns:
            List of datasets (array response from API)
        """
        # Use dados.gov.br Swagger API endpoint directly
        endpoint = "/dados/api/publico/conjuntos-dados"

        # Calculate page number from offset/limit if page not provided
        if page is None:
            if offset is not None and limit is not None and limit > 0:
                # Convert offset to page number (assuming limit items per page)
                page = (offset // limit) + 1
            else:
                # Default to page 1 if not specified
                page = 1

        params: dict[str, Any] = {
            "pagina": page  # Required parameter
        }

        # Map query to nomeConjuntoDados parameter
        if query:
            params["nomeConjuntoDados"] = query

        # Map filters to API parameters
        if filters:
            if "idOrganizacao" in filters:
                params["idOrganizacao"] = filters["idOrganizacao"]
            if "dadosAbertos" in filters:
                params["dadosAbertos"] = filters["dadosAbertos"]
            if "isPrivado" in filters:
                params["isPrivado"] = filters["isPrivado"]
            # Note: tags filtering is not directly supported by this endpoint
            # Tags are available via get_dataset_tags() method

        return self._request("GET", endpoint, params=params)

    def get_dataset(self, dataset_id: str) -> dict[str, Any]:
        """
        Get dataset details by ID using dados.gov.br Swagger API endpoint.

        Uses GET /dados/api/publico/conjuntos-dados/{id} endpoint.

        Args:
            dataset_id: Dataset ID or identifier

        Returns:
            Dataset details dictionary (may vary based on dados.gov.br API response format)
        """
        # Use dados.gov.br Swagger API endpoint directly with ID in path
        endpoint = f"/dados/api/publico/conjuntos-dados/{dataset_id}"

        return self._request("GET", endpoint)

    def get_resource(self, resource_id: str, dataset_id: str | None = None) -> dict[str, Any]:
        """
        Get resource details by ID.

        Note: Resources in dados.gov.br are typically nested within datasets.
        When ``dataset_id`` is provided, the resource is looked up through the
        dataset endpoint per the Swagger spec.  When omitted, the method falls
        back to legacy direct-resource paths (which may not exist on the live
        API) and raises ``ValueError`` if they return HTML.

        Args:
            resource_id: Resource ID
            dataset_id: Optional dataset / listing ID that contains the resource

        Returns:
            Resource details dictionary

        Raises:
            ValueError: If the resource cannot be found through any endpoint
        """
        # 1) If we know the parent dataset, use the Swagger-spec path.
        if dataset_id:
            dataset_endpoint = f"/dados/api/publico/conjuntos-dados/{dataset_id}"
            try:
                dataset_data = self._request("GET", dataset_endpoint)
            except (httpx.HTTPStatusError, ValueError) as e:
                raise ValueError(
                    f"Failed to fetch dataset {dataset_id} for resource {resource_id}: {e}"
                ) from e

            # Resources are nested under "recursos" or "resources"
            result = dataset_data.get("result") or dataset_data
            recursos = result.get("recursos") or result.get("resources") or []
            for r in recursos:
                if r.get("id") == resource_id or r.get("resource_id") == resource_id:
                    return {"success": True, "result": r}

            # Resource not found in this dataset
            raise ValueError(f"Resource '{resource_id}' not found in dataset {dataset_id}")

        # 2) Legacy fallback — direct resource endpoints.
        #    These endpoints are *not* part of the published Swagger spec
        #    and frequently return HTML (the portal page) rather than JSON.
        endpoint = f"/dados/api/publico/recurso/{resource_id}"
        try:
            return self._request("GET", endpoint)
        except (httpx.HTTPStatusError, ValueError):
            logger.warning("Direct resource endpoint /recurso/ failed, trying /recursos/ fallback")
            endpoint = f"/dados/api/publico/recursos/{resource_id}"
            return self._request("GET", endpoint)

    def get_dataset_tags(self, dataset_id: str) -> dict[str, Any]:
        """
        Get tags for a specific dataset.

        Uses GET /dados/api/publico/conjuntos-dados/{id}/tag endpoint.

        Args:
            dataset_id: Dataset ID or identifier

        Returns:
            Tags dictionary (may vary based on dados.gov.br API response format)
        """
        endpoint = f"/dados/api/publico/conjuntos-dados/{dataset_id}/tag"
        return self._request("GET", endpoint)

    def get_themes(self) -> dict[str, Any]:
        """
        List all available themes.

        Uses GET /dados/api/temas endpoint.

        Returns:
            Themes dictionary (may vary based on dados.gov.br API response format)
        """
        endpoint = "/dados/api/temas"
        return self._request("GET", endpoint)

    def get_tags(self, nome: str = "") -> dict[str, Any]:
        """
        List available tags matching a name pattern.

        Uses GET /dados/api/tags endpoint.
        According to Swagger spec: https://dados.gov.br/swagger-ui/index.html

        Args:
            nome: Tag name pattern to search for (required parameter)

        Returns:
            List of tags matching the name pattern (array response from API)
        """
        endpoint = "/dados/api/tags"
        params = {"nome": nome}  # Required parameter
        return self._request("GET", endpoint, params=params)

    def list_organizations(self, nome: str | None = None, page: int = 1) -> dict[str, Any]:
        """
        List organizations.

        Uses GET /dados/api/publico/organizacao endpoint.
        According to Swagger spec: https://dados.gov.br/swagger-ui/index.html

        Args:
            nome: Organization name filter (optional)
            page: Page number (required, defaults to 1)

        Returns:
            List of organizations (array response from API)
        """
        endpoint = "/dados/api/publico/organizacao"
        params: dict[str, Any] = {
            "pagina": page  # Required parameter
        }
        if nome:
            params["nome"] = nome
        return self._request("GET", endpoint, params=params)

    def get_organization(self, organization_id: str) -> dict[str, Any]:
        """
        Get organization details by ID.

        Uses GET /dados/api/publico/organizacao/{id} endpoint.

        Args:
            organization_id: Organization ID or identifier

        Returns:
            Organization details dictionary (may vary based on dados.gov.br API response format)
        """
        endpoint = f"/dados/api/publico/organizacao/{organization_id}"
        return self._request("GET", endpoint)
