"""
BaaS (Backend as a Service) operations for DataHub SDK.

Provides high-level methods for managing API keys, usage tracking, and developer portal.
"""
import re
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime

from .client import DataHubClient
from .errors import (
    BaaSValidationError,
    BaaSError,
    NotFoundError,
    ValidationError,
    ForbiddenError,
    parse_error,
)


class BaaSAPI:
    """
    BaaS (Backend as a Service) API.

    Provides methods for managing API keys, tracking usage, and accessing developer portal.
    """

    def __init__(self, client: DataHubClient):
        """
        Initialize BaaS API.

        Args:
            client: DataHub client instance
        """
        self.client = client

    # Validation Helper Methods

    def _validate_api_key_id(self, api_key_id: str, param_name: str = "api_key_id") -> None:
        """
        Validate API key ID format (UUID).

        Args:
            api_key_id: API key ID to validate
            param_name: Parameter name for error messages

        Raises:
            BaaSValidationError: If API key ID is invalid
        """
        if not api_key_id:
            raise BaaSValidationError(
                f"{param_name} is required",
                error_code="REQUIRED_FIELD_MISSING",
                field_path=f"/{param_name}",
                expected="non-empty string (UUID)",
                actual="empty or None",
            )

        if not isinstance(api_key_id, str):
            raise BaaSValidationError(
                f"{param_name} must be a string",
                error_code="INVALID_DATA_TYPE",
                field_path=f"/{param_name}",
                expected="string (UUID)",
                actual=type(api_key_id).__name__,
            )

        # Validate UUID format
        try:
            uuid.UUID(api_key_id)
        except (ValueError, TypeError):
            raise BaaSValidationError(
                f"{param_name} must be a valid UUID",
                error_code="INVALID_VALUE",
                field_path=f"/{param_name}",
                expected="valid UUID format (e.g., '123e4567-e89b-12d3-a456-426614174000')",
                actual=api_key_id[:50] if len(api_key_id) > 50 else api_key_id,
            )

    def _validate_date_format(self, date_str: str, param_name: str = "date") -> None:
        """
        Validate ISO date format.

        Args:
            date_str: Date string to validate
            param_name: Parameter name for error messages

        Raises:
            BaaSValidationError: If date format is invalid
        """
        if not date_str:
            raise BaaSValidationError(
                f"{param_name} is required",
                error_code="REQUIRED_FIELD_MISSING",
                field_path=f"/{param_name}",
                expected="non-empty ISO date string",
                actual="empty or None",
            )

        if not isinstance(date_str, str):
            raise BaaSValidationError(
                f"{param_name} must be a string",
                error_code="INVALID_DATA_TYPE",
                field_path=f"/{param_name}",
                expected="ISO date string (e.g., '2024-01-01T00:00:00Z')",
                actual=type(date_str).__name__,
            )

        # Try to parse ISO format - must include time component
        # Check for basic ISO format with time (must have 'T' separator)
        if 'T' not in date_str:
            raise BaaSValidationError(
                f"{param_name} must be in ISO format with time component (e.g., '2024-01-01T00:00:00Z')",
                error_code="INVALID_VALUE",
                field_path=f"/{param_name}",
                expected="ISO date string with time component",
                actual=date_str[:50] if len(date_str) > 50 else date_str,
            )

        try:
            # Handle both Z and +00:00 timezone formats
            date_str_normalized = date_str.replace('Z', '+00:00')
            datetime.fromisoformat(date_str_normalized)
        except (ValueError, TypeError):
            raise BaaSValidationError(
                f"{param_name} must be in ISO format (e.g., '2024-01-01T00:00:00Z')",
                error_code="INVALID_VALUE",
                field_path=f"/{param_name}",
                expected="ISO date string",
                actual=date_str[:50] if len(date_str) > 50 else date_str,
            )

    def _validate_tier(self, tier: str) -> None:
        """
        Validate API tier name.

        Args:
            tier: Tier name to validate

        Raises:
            BaaSValidationError: If tier is invalid
        """
        valid_tiers = {"FREE", "PRO", "ENTERPRISE"}
        if tier.upper() not in valid_tiers:
            raise BaaSValidationError(
                f"tier must be one of {valid_tiers}",
                error_code="INVALID_VALUE",
                field_path="/tier",
                expected=f"one of {valid_tiers}",
                actual=tier,
            )

    def _handle_baas_error(self, error: Exception, operation: str) -> Exception:
        """
        Handle and map BaaS-related errors from API responses.

        Args:
            error: Exception from API call
            operation: Operation name for error context

        Returns:
            Mapped BaaS error or original error
        """
        from .errors import DataHubError

        # If it's already a BaaS error, return it
        if isinstance(error, (BaaSValidationError, BaaSError)):
            return error

        # Preserve NotFoundError for 404 cases
        if isinstance(error, NotFoundError):
            return error

        # Preserve ForbiddenError for 403 cases
        if isinstance(error, ForbiddenError):
            return error

        # If it's a DataHubError, try to parse as BaaS error
        if isinstance(error, DataHubError):
            error_dict = error.to_dict() if hasattr(error, "to_dict") else {}
            if error_dict:
                code = error_dict.get("error", {}).get("code", "") if isinstance(error_dict.get("error"), dict) else ""
                if "BAAS" in code.upper() or "VALIDATION" in code.upper():
                    return BaaSValidationError(
                        f"BaaS {operation} failed: {error.message}",
                        error_code=error.code,
                        http_status=error.http_status,
                        request_id=error.request_id,
                        details=error.details,
                    )

        # For other errors, wrap in generic BaaS error
        return BaaSError(
            f"BaaS {operation} failed: {str(error)}",
            error_code="BAAS_ERROR",
            http_status=500,
            details={"context": {"operation": operation, "original_error": str(error)}},
        )

    # API Key Management Methods

    async def create_api_key(
        self,
        name: str,
        tier: str = "FREE",
        expires_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a new API key.

        Args:
            name: API key name
            tier: API tier (FREE, PRO, ENTERPRISE). Default: FREE
            expires_at: Optional expiration date in ISO format

        Returns:
            API key data dictionary including:
            - id: API key ID
            - name: API key name
            - api_key: Plaintext API key (shown only once)
            - tier: API tier
            - expires_at: Expiration date (if set)
            - created_at: Creation timestamp

        Raises:
            BaaSValidationError: If parameters are invalid
            BaaSError: If API key creation fails
        """
        # Validate parameters
        try:
            if not name:
                raise BaaSValidationError(
                    "name is required",
                    error_code="REQUIRED_FIELD_MISSING",
                    field_path="/name",
                    expected="non-empty string",
                    actual="empty or None",
                )
            if not isinstance(name, str):
                raise BaaSValidationError(
                    "name must be a string",
                    error_code="INVALID_DATA_TYPE",
                    field_path="/name",
                    expected="string",
                    actual=type(name).__name__,
                )
            name = name.strip()
            if not name:
                raise BaaSValidationError(
                    "name cannot be empty or whitespace",
                    error_code="INVALID_VALUE",
                    field_path="/name",
                    expected="non-empty string",
                    actual="empty string",
                )

            tier = tier.upper() if tier else "FREE"
            self._validate_tier(tier)

            if expires_at:
                self._validate_date_format(expires_at, "expires_at")
        except BaaSValidationError:
            raise
        except Exception as e:
            raise BaaSValidationError(
                f"Parameter validation failed: {str(e)}",
                error_code="VALIDATION_ERROR",
                details={"context": {"operation": "create_api_key", "original_error": str(e)}},
            ) from e

        # Build request data
        data: Dict[str, Any] = {
            "name": name,
            "tier": tier,
        }
        if expires_at:
            data["expires_at"] = expires_at

        # Make API call
        try:
            response = await self.client.post(
                "baas/api-keys/",
                data=data,
            )
            return response
        except Exception as e:
            raise self._handle_baas_error(e, "create_api_key")

    async def list_api_keys(
        self,
        tier: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        List API keys.

        Args:
            tier: Optional filter by tier (FREE, PRO, ENTERPRISE)
            limit: Optional maximum number of results
            offset: Optional offset for pagination

        Returns:
            List of API key dictionaries (without plaintext keys)

        Raises:
            BaaSValidationError: If parameters are invalid
            BaaSError: If listing fails
        """
        # Validate parameters
        try:
            if tier:
                tier = tier.upper()
                self._validate_tier(tier)

            if limit is not None:
                if not isinstance(limit, int) or limit < 1:
                    raise BaaSValidationError(
                        "limit must be a positive integer",
                        error_code="INVALID_VALUE",
                        field_path="/limit",
                        expected="positive integer",
                        actual=limit,
                    )

            if offset is not None:
                if not isinstance(offset, int) or offset < 0:
                    raise BaaSValidationError(
                        "offset must be a non-negative integer",
                        error_code="INVALID_VALUE",
                        field_path="/offset",
                        expected="non-negative integer",
                        actual=offset,
                    )
        except BaaSValidationError:
            raise
        except Exception as e:
            raise BaaSValidationError(
                f"Parameter validation failed: {str(e)}",
                error_code="VALIDATION_ERROR",
                details={"context": {"operation": "list_api_keys", "original_error": str(e)}},
            ) from e

        # Build query parameters
        params: Dict[str, Any] = {}
        if tier:
            params["tier"] = tier
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset

        # Make API call
        try:
            response = await self.client.get(
                "baas/api-keys/",
                params=params,
            )
            # Handle both list and paginated response formats
            if isinstance(response, list):
                return response
            elif isinstance(response, dict) and "results" in response:
                return response["results"]
            else:
                return [response] if response else []
        except Exception as e:
            raise self._handle_baas_error(e, "list_api_keys")

    async def get_api_key(self, api_key_id: str) -> Dict[str, Any]:
        """
        Get API key details.

        Args:
            api_key_id: API key ID

        Returns:
            API key data dictionary (without plaintext key)

        Raises:
            BaaSValidationError: If api_key_id is invalid
            NotFoundError: If API key not found
            BaaSError: If retrieval fails
        """
        # Validate parameters
        try:
            self._validate_api_key_id(api_key_id)
        except BaaSValidationError:
            raise
        except Exception as e:
            raise BaaSValidationError(
                f"Parameter validation failed: {str(e)}",
                error_code="VALIDATION_ERROR",
                details={"context": {"operation": "get_api_key", "original_error": str(e)}},
            ) from e

        # Make API call
        try:
            response = await self.client.get(
                f"baas/api-keys/{api_key_id}/",
            )
            return response
        except Exception as e:
            raise self._handle_baas_error(e, "get_api_key")

    async def update_api_key(
        self,
        api_key_id: str,
        name: Optional[str] = None,
        tier: Optional[str] = None,
        expires_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Update API key.

        Args:
            api_key_id: API key ID
            name: Optional new name
            tier: Optional new tier (note: tier changes may be restricted)
            expires_at: Optional new expiration date in ISO format

        Returns:
            Updated API key data dictionary

        Raises:
            BaaSValidationError: If parameters are invalid
            NotFoundError: If API key not found
            BaaSError: If update fails
        """
        # Validate parameters
        try:
            self._validate_api_key_id(api_key_id)

            if name is not None:
                if not isinstance(name, str):
                    raise BaaSValidationError(
                        "name must be a string",
                        error_code="INVALID_DATA_TYPE",
                        field_path="/name",
                        expected="string",
                        actual=type(name).__name__,
                    )
                name = name.strip()
                if not name:
                    raise BaaSValidationError(
                        "name cannot be empty or whitespace",
                        error_code="INVALID_VALUE",
                        field_path="/name",
                        expected="non-empty string",
                        actual="empty string",
                    )

            if tier is not None:
                tier = tier.upper()
                self._validate_tier(tier)

            if expires_at is not None:
                self._validate_date_format(expires_at, "expires_at")
        except BaaSValidationError:
            raise
        except Exception as e:
            raise BaaSValidationError(
                f"Parameter validation failed: {str(e)}",
                error_code="VALIDATION_ERROR",
                details={"context": {"operation": "update_api_key", "original_error": str(e)}},
            ) from e

        # Build request data (only include provided fields)
        data: Dict[str, Any] = {}
        if name is not None:
            data["name"] = name
        if tier is not None:
            data["tier"] = tier
        if expires_at is not None:
            data["expires_at"] = expires_at

        if not data:
            raise BaaSValidationError(
                "At least one field (name, tier, expires_at) must be provided",
                error_code="REQUIRED_FIELD_MISSING",
                field_path="/",
                expected="at least one update field",
                actual="no fields provided",
            )

        # Make API call
        try:
            response = await self.client.patch(
                f"baas/api-keys/{api_key_id}/",
                data=data,
            )
            return response
        except Exception as e:
            raise self._handle_baas_error(e, "update_api_key")

    async def revoke_api_key(self, api_key_id: str) -> None:
        """
        Revoke (delete) an API key.

        Args:
            api_key_id: API key ID

        Raises:
            BaaSValidationError: If api_key_id is invalid
            NotFoundError: If API key not found
            BaaSError: If revocation fails
        """
        # Validate parameters
        try:
            self._validate_api_key_id(api_key_id)
        except BaaSValidationError:
            raise
        except Exception as e:
            raise BaaSValidationError(
                f"Parameter validation failed: {str(e)}",
                error_code="VALIDATION_ERROR",
                details={"context": {"operation": "revoke_api_key", "original_error": str(e)}},
            ) from e

        # Make API call
        try:
            await self.client.delete(
                f"baas/api-keys/{api_key_id}/",
            )
        except Exception as e:
            raise self._handle_baas_error(e, "revoke_api_key")

    # Usage Tracking Methods

    async def get_usage_stats(
        self,
        api_key_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get usage statistics.

        Args:
            api_key_id: Optional filter by API key ID
            start_date: Optional start date in ISO format
            end_date: Optional end date in ISO format

        Returns:
            Usage statistics dictionary with:
            - total_requests: Total number of requests
            - success_count: Number of successful requests
            - error_count: Number of failed requests
            - success_rate: Success rate percentage
            - avg_response_time_ms: Average response time in milliseconds
            - total_request_bytes: Total request bytes
            - total_response_bytes: Total response bytes

        Raises:
            BaaSValidationError: If parameters are invalid
            BaaSError: If retrieval fails
        """
        # Validate parameters
        try:
            if api_key_id:
                self._validate_api_key_id(api_key_id)
            if start_date:
                self._validate_date_format(start_date, "start_date")
            if end_date:
                self._validate_date_format(end_date, "end_date")
        except BaaSValidationError:
            raise
        except Exception as e:
            raise BaaSValidationError(
                f"Parameter validation failed: {str(e)}",
                error_code="VALIDATION_ERROR",
                details={"context": {"operation": "get_usage_stats", "original_error": str(e)}},
            ) from e

        # Build query parameters
        params: Dict[str, Any] = {}
        if api_key_id:
            params["api_key_id"] = api_key_id
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date

        # Make API call
        try:
            response = await self.client.get(
                "baas/usage/stats/",
                params=params,
            )
            return response
        except Exception as e:
            raise self._handle_baas_error(e, "get_usage_stats")

    async def get_usage_by_endpoint(
        self,
        api_key_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get usage breakdown by endpoint.

        Args:
            api_key_id: Optional filter by API key ID
            start_date: Optional start date in ISO format
            end_date: Optional end date in ISO format

        Returns:
            List of usage dictionaries by endpoint with:
            - endpoint: Endpoint path
            - method: HTTP method
            - request_count: Number of requests
            - success_count: Number of successful requests
            - error_count: Number of failed requests
            - avg_response_time_ms: Average response time in milliseconds

        Raises:
            BaaSValidationError: If parameters are invalid
            BaaSError: If retrieval fails
        """
        # Validate parameters
        try:
            if api_key_id:
                self._validate_api_key_id(api_key_id)
            if start_date:
                self._validate_date_format(start_date, "start_date")
            if end_date:
                self._validate_date_format(end_date, "end_date")
        except BaaSValidationError:
            raise
        except Exception as e:
            raise BaaSValidationError(
                f"Parameter validation failed: {str(e)}",
                error_code="VALIDATION_ERROR",
                details={"context": {"operation": "get_usage_by_endpoint", "original_error": str(e)}},
            ) from e

        # Build query parameters
        params: Dict[str, Any] = {}
        if api_key_id:
            params["api_key_id"] = api_key_id
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date

        # Make API call
        try:
            response = await self.client.get(
                "baas/usage/by-endpoint/",
                params=params,
            )
            # Handle both list and paginated response formats
            if isinstance(response, list):
                return response
            elif isinstance(response, dict) and "results" in response:
                return response["results"]
            else:
                return [response] if response else []
        except Exception as e:
            raise self._handle_baas_error(e, "get_usage_by_endpoint")

    async def get_usage_by_tenant(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get usage breakdown by tenant (admin only).

        Args:
            start_date: Optional start date in ISO format
            end_date: Optional end date in ISO format

        Returns:
            List of usage dictionaries by tenant with:
            - tenant_id: Tenant ID
            - tenant_name: Tenant name
            - total_requests: Total number of requests
            - success_count: Number of successful requests
            - error_count: Number of failed requests
            - avg_response_time_ms: Average response time in milliseconds

        Raises:
            BaaSValidationError: If parameters are invalid
            ForbiddenError: If user is not an admin
            BaaSError: If retrieval fails
        """
        # Validate parameters
        try:
            if start_date:
                self._validate_date_format(start_date, "start_date")
            if end_date:
                self._validate_date_format(end_date, "end_date")
        except BaaSValidationError:
            raise
        except Exception as e:
            raise BaaSValidationError(
                f"Parameter validation failed: {str(e)}",
                error_code="VALIDATION_ERROR",
                details={"context": {"operation": "get_usage_by_tenant", "original_error": str(e)}},
            ) from e

        # Build query parameters
        params: Dict[str, Any] = {}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date

        # Make API call
        try:
            response = await self.client.get(
                "baas/usage/by-tenant/",
                params=params,
            )
            # Handle both list and paginated response formats
            if isinstance(response, list):
                return response
            elif isinstance(response, dict) and "results" in response:
                return response["results"]
            else:
                return [response] if response else []
        except Exception as e:
            raise self._handle_baas_error(e, "get_usage_by_tenant")

    async def check_quota(self, api_key_id: str) -> Dict[str, Any]:
        """
        Check quota information for an API key.

        Args:
            api_key_id: API key ID

        Returns:
            Quota information dictionary with:
            - api_key_id: API key ID
            - tier: API tier
            - rate_limit_per_hour: Rate limit per hour
            - rate_limit_per_day: Rate limit per day
            - max_requests_per_month: Maximum requests per month (if applicable)
            - current_usage_hour: Current usage in the current hour
            - current_usage_day: Current usage in the current day
            - current_usage_month: Current usage in the current month (if applicable)
            - remaining_hour: Remaining requests in the current hour
            - remaining_day: Remaining requests in the current day
            - remaining_month: Remaining requests in the current month (if applicable)

        Raises:
            BaaSValidationError: If api_key_id is invalid
            NotFoundError: If API key not found
            BaaSError: If retrieval fails
        """
        # Validate parameters
        try:
            self._validate_api_key_id(api_key_id)
        except BaaSValidationError:
            raise
        except Exception as e:
            raise BaaSValidationError(
                f"Parameter validation failed: {str(e)}",
                error_code="VALIDATION_ERROR",
                details={"context": {"operation": "check_quota", "original_error": str(e)}},
            ) from e

        # Make API call
        try:
            response = await self.client.get(
                f"baas/api-keys/{api_key_id}/quota/",
            )
            return response
        except Exception as e:
            raise self._handle_baas_error(e, "check_quota")

    # Developer Portal Methods

    async def get_api_docs(self, format: str = "html") -> str:
        """
        Get API documentation.

        Args:
            format: Output format ("html" or "json"). Default: "html"

        Returns:
            Documentation content as string

        Raises:
            BaaSValidationError: If format is invalid
            BaaSError: If retrieval fails
        """
        # Validate parameters
        try:
            if format not in ("html", "json"):
                raise BaaSValidationError(
                    "format must be 'html' or 'json'",
                    error_code="INVALID_VALUE",
                    field_path="/format",
                    expected="'html' or 'json'",
                    actual=format,
                )
        except BaaSValidationError:
            raise
        except Exception as e:
            raise BaaSValidationError(
                f"Parameter validation failed: {str(e)}",
                error_code="VALIDATION_ERROR",
                details={"context": {"operation": "get_api_docs", "original_error": str(e)}},
            ) from e

        # Make API call
        try:
            response = await self.client.get(
                "baas/docs/",
            )
            # If format is json, return JSON string
            if format == "json":
                import json
                return json.dumps(response, indent=2)
            # Otherwise return formatted string representation
            return str(response)
        except Exception as e:
            raise self._handle_baas_error(e, "get_api_docs")

    async def get_openapi_schema(self, format: str = "json") -> Any:
        """
        Get OpenAPI schema.

        Args:
            format: Output format ("json" or "yaml"). Default: "json"

        Returns:
            OpenAPI schema as dictionary (for JSON) or string (for YAML)

        Raises:
            BaaSValidationError: If format is invalid
            BaaSError: If retrieval fails
        """
        # Validate parameters
        try:
            if format not in ("json", "yaml"):
                raise BaaSValidationError(
                    "format must be 'json' or 'yaml'",
                    error_code="INVALID_VALUE",
                    field_path="/format",
                    expected="'json' or 'yaml'",
                    actual=format,
                )
        except BaaSValidationError:
            raise
        except Exception as e:
            raise BaaSValidationError(
                f"Parameter validation failed: {str(e)}",
                error_code="VALIDATION_ERROR",
                details={"context": {"operation": "get_openapi_schema", "original_error": str(e)}},
            ) from e

        # Make API call (with trailing slash to avoid redirect)
        try:
            response = await self.client.get(
                "baas/docs/openapi.json/",
            )
            # If format is yaml, convert to YAML string
            if format == "yaml":
                try:
                    import yaml
                    return yaml.dump(response, default_flow_style=False)
                except ImportError:
                    raise BaaSValidationError(
                        "yaml format requires PyYAML package. Install with: pip install pyyaml",
                        error_code="DEPENDENCY_MISSING",
                        field_path="/format",
                        expected="yaml format with PyYAML installed",
                        actual="yaml format without PyYAML",
                    )
            # Otherwise return as dictionary
            return response
        except Exception as e:
            raise self._handle_baas_error(e, "get_openapi_schema")

    async def get_sdk_download_links(self) -> Dict[str, str]:
        """
        Get SDK download links.

        Returns:
            Dictionary mapping language names to download URLs:
            - python: Python SDK download URL
            - javascript: JavaScript SDK download URL
            - (other languages as available)

        Raises:
            BaaSError: If retrieval fails
        """
        # Make API call
        try:
            response = await self.client.get(
                "baas/docs/sdks/",
            )
            # Extract SDK links from response
            if isinstance(response, dict):
                # Response might be in different formats, extract SDK links
                if "sdks" in response:
                    return response["sdks"]
                elif "python" in response or "javascript" in response:
                    return response
                else:
                    # Try to find SDK links in nested structure
                    sdk_links = {}
                    for key, value in response.items():
                        if isinstance(value, dict) and ("download_url" in value or "url" in value):
                            sdk_links[key] = value.get("download_url") or value.get("url")
                    if sdk_links:
                        return sdk_links
            return response if isinstance(response, dict) else {}
        except Exception as e:
            raise self._handle_baas_error(e, "get_sdk_download_links")

    # ── 118F.17: Expanded BaaS methods ───────────────────

    async def set_api_key_pricing(self, api_key_id: str, pricing: dict) -> dict:
        return await self.client.post(f"baas/api-keys/{api_key_id}/pricing/", data=pricing)

    async def get_api_key_pricing(self, api_key_id: str) -> dict:
        return await self.client.get(f"baas/api-keys/{api_key_id}/pricing/")

    async def list_customers(self, **kwargs) -> dict:
        return await self.client.get("baas/customers/", params=kwargs or None)

    async def get_customer_usage(self, customer_id: str, period: str = None) -> dict:
        params = {"period": period} if period else None
        return await self.client.get(f"baas/customers/{customer_id}/usage/", params=params)

    async def list_billing_reports(self, **kwargs) -> dict:
        return await self.client.get("baas/billing-reports/", params=kwargs or None)

    async def get_billing_report(self, report_id: str) -> dict:
        return await self.client.get(f"baas/billing-reports/{report_id}/")

    async def generate_billing_report(self, period: str) -> dict:
        return await self.client.post("baas/billing-reports/", data={"period": period})

    async def finalize_billing_report(self, report_id: str) -> dict:
        return await self.client.post(f"baas/billing-reports/{report_id}/finalize/")

    async def export_billing_report_pdf(self, report_id: str) -> dict:
        return await self.client.post(f"baas/billing-reports/{report_id}/export/", data={"format": "pdf"})

    async def send_billing_report(self, report_id: str, email: str) -> dict:
        return await self.client.post(f"baas/billing-reports/{report_id}/send/", data={"email": email})

    async def rotate_api_key(self, api_key_id: str, grace_period_hours: int = 24) -> dict:
        return await self.client.post(
            f"baas/api-keys/{api_key_id}/rotate/",
            data={"grace_period_hours": grace_period_hours},
        )

    async def get_dashboard(self) -> dict:
        return await self.client.get("baas/dashboard/")
