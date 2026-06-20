"""
Marketplace integration operations for DataHub SDK.

Provides high-level methods for managing marketplace connections, sync jobs,
mappings, and connectors.
"""

import uuid
from typing import Any, Dict, List, Optional

from .client import DataHubClient
from .errors import (
    ConflictError,
    MarketplaceConnectionError,
    MarketplaceValidationError,
    NotFoundError,
)


class MarketplaceIntegrationAPI:
    """
    Marketplace integration API.

    Provides methods for managing marketplace connections, synchronization jobs,
    mappings, and connector information.
    """

    def __init__(self, client: DataHubClient):
        """
        Initialize Marketplace Integration API.

        Args:
            client: DataHub client instance
        """
        self.client = client

    # Validation Helper Methods

    def _validate_uuid(self, value: str, param_name: str = "id") -> None:
        """
        Validate UUID format.

        Args:
            value: UUID string to validate
            param_name: Parameter name for error messages

        Raises:
            MarketplaceValidationError: If UUID is invalid
        """
        if not value:
            raise MarketplaceValidationError(
                f"{param_name} is required",
                error_code="REQUIRED_FIELD_MISSING",
                field_path=f"/{param_name}",
                expected="non-empty string (UUID)",
                actual="empty or None",
            )

        if not isinstance(value, str):
            raise MarketplaceValidationError(
                f"{param_name} must be a string",
                error_code="INVALID_DATA_TYPE",
                field_path=f"/{param_name}",
                expected="string (UUID)",
                actual=type(value).__name__,
            )

        # Validate UUID format
        try:
            uuid.UUID(value)
        except (ValueError, TypeError):
            raise MarketplaceValidationError(
                f"{param_name} must be a valid UUID",
                error_code="INVALID_VALUE",
                field_path=f"/{param_name}",
                expected="valid UUID format (e.g., '123e4567-e89b-12d3-a456-426614174000')",
                actual=value[:50] if len(value) > 50 else value,
            )

    def _validate_marketplace_type(self, marketplace_type: str) -> None:
        """
        Validate marketplace type.

        Args:
            marketplace_type: Marketplace type string to validate

        Raises:
            MarketplaceValidationError: If marketplace type is invalid
        """
        if not marketplace_type:
            raise MarketplaceValidationError(
                "marketplace_type is required",
                error_code="REQUIRED_FIELD_MISSING",
                field_path="/marketplace_type",
                expected="non-empty string",
                actual="empty or None",
            )

        if not isinstance(marketplace_type, str):
            raise MarketplaceValidationError(
                "marketplace_type must be a string",
                error_code="INVALID_DATA_TYPE",
                field_path="/marketplace_type",
                expected="string",
                actual=type(marketplace_type).__name__,
            )

    def _validate_config(self, config: Dict[str, Any]) -> None:
        """
        Validate connection configuration.

        Args:
            config: Configuration dictionary to validate

        Raises:
            MarketplaceValidationError: If config is invalid
        """
        if not config:
            raise MarketplaceValidationError(
                "config is required",
                error_code="REQUIRED_FIELD_MISSING",
                field_path="/config",
                expected="non-empty dictionary",
                actual="empty or None",
            )

        if not isinstance(config, dict):
            raise MarketplaceValidationError(
                "config must be a dictionary",
                error_code="INVALID_DATA_TYPE",
                field_path="/config",
                expected="dict",
                actual=type(config).__name__,
            )

    def _validate_asset_ids(self, asset_ids: List[str]) -> None:
        """
        Validate asset IDs list.

        Args:
            asset_ids: List of asset IDs to validate

        Raises:
            MarketplaceValidationError: If asset_ids is invalid
        """
        if not asset_ids:
            raise MarketplaceValidationError(
                "asset_ids is required and cannot be empty",
                error_code="REQUIRED_FIELD_MISSING",
                field_path="/asset_ids",
                expected="non-empty list of UUIDs",
                actual="empty list or None",
            )

        if not isinstance(asset_ids, list):
            raise MarketplaceValidationError(
                "asset_ids must be a list",
                error_code="INVALID_DATA_TYPE",
                field_path="/asset_ids",
                expected="list",
                actual=type(asset_ids).__name__,
            )

        # Validate each asset ID
        for idx, asset_id in enumerate(asset_ids):
            if not asset_id:
                raise MarketplaceValidationError(
                    f"asset_ids[{idx}] is required",
                    error_code="REQUIRED_FIELD_MISSING",
                    field_path=f"/asset_ids/{idx}",
                    expected="non-empty string (UUID)",
                    actual="empty or None",
                )
            self._validate_uuid(asset_id, f"asset_ids[{idx}]")

    def _handle_marketplace_error(self, error: Exception, operation: str) -> Exception:
        """
        Handle and map marketplace-related errors from API responses.

        Args:
            error: Exception from API call
            operation: Operation name for error context

        Returns:
            Mapped marketplace error or original error
        """
        from .errors import DataHubError

        # If it's already a marketplace error, return it
        if isinstance(error, (MarketplaceValidationError, MarketplaceConnectionError)):
            return error

        # Preserve NotFoundError for 404 cases
        if isinstance(error, NotFoundError):
            return error

        # Preserve ConflictError for 409 cases (e.g., duplicate connection names)
        if isinstance(error, ConflictError):
            return error

        # If it's a DataHubError with 404 status, return NotFoundError
        if isinstance(error, DataHubError) and error.http_status == 404:
            return NotFoundError(
                error.message,
                error.request_id,
            )

        # If it's a DataHubError with 409 status, return ConflictError
        if isinstance(error, DataHubError) and error.http_status == 409:
            return ConflictError(
                error.message,
                error.request_id,
                error.details,
            )

        # If it's a DataHubError, try to parse as marketplace error
        if isinstance(error, DataHubError):
            # Try to extract error details from the error
            error_dict = error.to_dict() if hasattr(error, "to_dict") else {}
            if error_dict:
                # Check if it's a marketplace-related error
                code = (
                    error_dict.get("error", {}).get("code", "")
                    if isinstance(error_dict.get("error"), dict)
                    else ""
                )
                if "MARKETPLACE" in code.upper() or "CONNECTION" in code.upper():
                    return MarketplaceConnectionError(
                        f"Marketplace {operation} failed: {error.message}",
                        error_code=error.code,
                        http_status=error.http_status,
                        request_id=error.request_id,
                        details=error.details,
                    )

        # For other errors, wrap in generic marketplace error
        return MarketplaceConnectionError(
            f"Marketplace {operation} failed: {str(error)}",
            error_code="MARKETPLACE_ERROR",
            http_status=500,
            details={"context": {"operation": operation, "original_error": str(error)}},
        )

    # Connection Management Methods

    async def create_connection(
        self,
        marketplace_type: str,
        name: str,
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Create a new marketplace connection.

        Args:
            marketplace_type: Type of marketplace (e.g., "SNOWFLAKE_DATA_MARKETPLACE")
            name: Connection name
            config: Connection configuration dictionary

        Returns:
            Connection data dictionary

        Raises:
            MarketplaceValidationError: If parameters are invalid
            MarketplaceConnectionError: If connection creation fails
        """
        # Validate parameters
        try:
            self._validate_marketplace_type(marketplace_type)
            if not name:
                raise MarketplaceValidationError(
                    "name is required",
                    error_code="REQUIRED_FIELD_MISSING",
                    field_path="/name",
                    expected="non-empty string",
                    actual="empty or None",
                )
            if not isinstance(name, str):
                raise MarketplaceValidationError(
                    "name must be a string",
                    error_code="INVALID_DATA_TYPE",
                    field_path="/name",
                    expected="string",
                    actual=type(name).__name__,
                )
            self._validate_config(config)
        except MarketplaceValidationError:
            raise
        except Exception as e:
            raise MarketplaceValidationError(
                f"Parameter validation failed: {str(e)}",
                error_code="VALIDATION_ERROR",
                details={"context": {"operation": "create_connection", "original_error": str(e)}},
            ) from e

        # Build request data
        data: Dict[str, Any] = {
            "marketplace_type": marketplace_type,
            "name": name,
            "config": config,
        }

        try:
            return await self.client.post("integrations/marketplace/connections/", data=data)
        except Exception as e:
            raise self._handle_marketplace_error(e, "create_connection") from e

    async def list_connections(
        self,
        marketplace_type: Optional[str] = None,
        is_active: Optional[bool] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        List marketplace connections.

        Args:
            marketplace_type: Filter by marketplace type (optional)
            is_active: Filter by active status (optional)
            limit: Maximum number of results (optional)
            offset: Number of results to skip (optional)

        Returns:
            List of connection data dictionaries
        """
        params: Dict[str, Any] = {}

        if marketplace_type:
            self._validate_marketplace_type(marketplace_type)
            params["marketplace_type"] = marketplace_type

        if is_active is not None:
            params["is_active"] = is_active

        if limit is not None:
            if not isinstance(limit, int) or limit < 1:
                raise MarketplaceValidationError(
                    "limit must be a positive integer",
                    error_code="INVALID_VALUE",
                    field_path="/limit",
                    expected="positive integer",
                    actual=limit,
                )
            params["limit"] = limit

        if offset is not None:
            if not isinstance(offset, int) or offset < 0:
                raise MarketplaceValidationError(
                    "offset must be a non-negative integer",
                    error_code="INVALID_VALUE",
                    field_path="/offset",
                    expected="non-negative integer",
                    actual=offset,
                )
            params["offset"] = offset

        try:
            response = await self.client.get("integrations/marketplace/connections/", params=params)
            # Handle paginated response
            if isinstance(response, dict) and "results" in response:
                return response["results"]
            # Handle list response
            if isinstance(response, list):
                return response
            # Handle single item wrapped in dict
            if isinstance(response, dict) and "id" in response:
                return [response]
            return []
        except Exception as e:
            raise self._handle_marketplace_error(e, "list_connections") from e

    async def get_connection(self, connection_id: str) -> Dict[str, Any]:
        """
        Get a marketplace connection by ID.

        Args:
            connection_id: Connection UUID

        Returns:
            Connection data dictionary

        Raises:
            MarketplaceValidationError: If connection_id is invalid
            NotFoundError: If connection is not found
        """
        self._validate_uuid(connection_id, "connection_id")

        try:
            return await self.client.get(f"integrations/marketplace/connections/{connection_id}/")
        except NotFoundError:
            raise
        except Exception as e:
            raise self._handle_marketplace_error(e, "get_connection") from e

    async def update_connection(
        self,
        connection_id: str,
        name: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        is_active: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        Update a marketplace connection.

        Args:
            connection_id: Connection UUID
            name: Updated connection name (optional)
            config: Updated connection configuration (optional)
            is_active: Updated active status (optional)

        Returns:
            Updated connection data dictionary

        Raises:
            MarketplaceValidationError: If parameters are invalid
            NotFoundError: If connection is not found
        """
        self._validate_uuid(connection_id, "connection_id")

        data: Dict[str, Any] = {}

        if name is not None:
            if not isinstance(name, str):
                raise MarketplaceValidationError(
                    "name must be a string",
                    error_code="INVALID_DATA_TYPE",
                    field_path="/name",
                    expected="string",
                    actual=type(name).__name__,
                )
            data["name"] = name

        if config is not None:
            self._validate_config(config)
            data["config"] = config

        if is_active is not None:
            if not isinstance(is_active, bool):
                raise MarketplaceValidationError(
                    "is_active must be a boolean",
                    error_code="INVALID_DATA_TYPE",
                    field_path="/is_active",
                    expected="boolean",
                    actual=type(is_active).__name__,
                )
            data["is_active"] = is_active

        if not data:
            raise MarketplaceValidationError(
                "At least one field (name, config, is_active) must be provided for update",
                error_code="REQUIRED_FIELD_MISSING",
                field_path="/",
                expected="at least one update field",
                actual="no update fields provided",
            )

        try:
            return await self.client.patch(
                f"integrations/marketplace/connections/{connection_id}/", data=data
            )
        except NotFoundError:
            raise
        except Exception as e:
            raise self._handle_marketplace_error(e, "update_connection") from e

    async def delete_connection(self, connection_id: str) -> None:
        """
        Delete a marketplace connection.

        Args:
            connection_id: Connection UUID

        Raises:
            MarketplaceValidationError: If connection_id is invalid
            NotFoundError: If connection is not found
        """
        self._validate_uuid(connection_id, "connection_id")

        try:
            await self.client.delete(f"integrations/marketplace/connections/{connection_id}/")
        except NotFoundError:
            raise
        except Exception as e:
            raise self._handle_marketplace_error(e, "delete_connection") from e

    async def test_connection(self, connection_id: str) -> Dict[str, Any]:
        """
        Test a marketplace connection.

        Args:
            connection_id: Connection UUID

        Returns:
            Test results dictionary

        Raises:
            MarketplaceValidationError: If connection_id is invalid
            NotFoundError: If connection is not found
            MarketplaceConnectionError: If connection test fails
        """
        self._validate_uuid(connection_id, "connection_id")

        try:
            return await self.client.post(
                f"integrations/marketplace/connections/{connection_id}/test/"
            )
        except NotFoundError:
            raise
        except Exception as e:
            raise self._handle_marketplace_error(e, "test_connection") from e

    # Sync Job Methods

    async def sync_assets_to_marketplace(
        self,
        connection_id: str,
        asset_ids: List[str],
    ) -> Dict[str, Any]:
        """
        Sync assets to marketplace (PUSH direction).

        Args:
            connection_id: Connection UUID
            asset_ids: List of asset UUIDs to sync

        Returns:
            Sync job data dictionary

        Raises:
            MarketplaceValidationError: If parameters are invalid
            NotFoundError: If connection is not found
        """
        self._validate_uuid(connection_id, "connection_id")
        self._validate_asset_ids(asset_ids)

        data: Dict[str, Any] = {
            "connection_id": connection_id,
            "direction": "PUSH",
            "asset_ids": asset_ids,
        }

        try:
            return await self.client.post("integrations/marketplace/sync/", data=data)
        except NotFoundError:
            raise
        except Exception as e:
            raise self._handle_marketplace_error(e, "sync_assets_to_marketplace") from e

    async def sync_from_marketplace(
        self,
        connection_id: str,
        listing_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Sync from marketplace (PULL direction).

        Args:
            connection_id: Connection UUID
            listing_ids: Optional list of listing IDs to sync (if None, syncs all)

        Returns:
            Sync job data dictionary

        Raises:
            MarketplaceValidationError: If parameters are invalid
            NotFoundError: If connection is not found
        """
        self._validate_uuid(connection_id, "connection_id")

        data: Dict[str, Any] = {
            "connection_id": connection_id,
            "direction": "PULL",
        }

        if listing_ids is not None:
            if not isinstance(listing_ids, list):
                raise MarketplaceValidationError(
                    "listing_ids must be a list",
                    error_code="INVALID_DATA_TYPE",
                    field_path="/listing_ids",
                    expected="list",
                    actual=type(listing_ids).__name__,
                )
            data["listing_ids"] = listing_ids

        try:
            return await self.client.post("integrations/marketplace/sync/", data=data)
        except NotFoundError:
            raise
        except Exception as e:
            raise self._handle_marketplace_error(e, "sync_from_marketplace") from e

    async def sync_bidirectional(
        self,
        connection_id: str,
        asset_ids: List[str],
        listing_ids: List[str],
    ) -> Dict[str, Any]:
        """
        Sync bidirectionally between hub and marketplace.

        Args:
            connection_id: Connection UUID
            asset_ids: List of asset UUIDs to sync to marketplace
            listing_ids: List of listing IDs to sync from marketplace

        Returns:
            Sync job data dictionary

        Raises:
            MarketplaceValidationError: If parameters are invalid
            NotFoundError: If connection is not found
        """
        self._validate_uuid(connection_id, "connection_id")
        self._validate_asset_ids(asset_ids)

        if not listing_ids:
            raise MarketplaceValidationError(
                "listing_ids is required and cannot be empty",
                error_code="REQUIRED_FIELD_MISSING",
                field_path="/listing_ids",
                expected="non-empty list",
                actual="empty list or None",
            )

        if not isinstance(listing_ids, list):
            raise MarketplaceValidationError(
                "listing_ids must be a list",
                error_code="INVALID_DATA_TYPE",
                field_path="/listing_ids",
                expected="list",
                actual=type(listing_ids).__name__,
            )

        data: Dict[str, Any] = {
            "connection_id": connection_id,
            "direction": "BIDIRECTIONAL",
            "asset_ids": asset_ids,
            "listing_ids": listing_ids,
        }

        try:
            return await self.client.post("integrations/marketplace/sync/", data=data)
        except NotFoundError:
            raise
        except Exception as e:
            raise self._handle_marketplace_error(e, "sync_bidirectional") from e

    async def get_sync_job(self, sync_job_id: str) -> Dict[str, Any]:
        """
        Get a sync job by ID.

        Args:
            sync_job_id: Sync job UUID

        Returns:
            Sync job data dictionary with progress information

        Raises:
            MarketplaceValidationError: If sync_job_id is invalid
            NotFoundError: If sync job is not found
        """
        self._validate_uuid(sync_job_id, "sync_job_id")

        try:
            return await self.client.get(f"integrations/marketplace/sync/{sync_job_id}/")
        except NotFoundError:
            raise
        except Exception as e:
            raise self._handle_marketplace_error(e, "get_sync_job") from e

    async def list_sync_jobs(
        self,
        connection_id: Optional[str] = None,
        status: Optional[str] = None,
        direction: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        List sync jobs.

        Args:
            connection_id: Filter by connection ID (optional)
            status: Filter by status (optional)
            direction: Filter by direction (PUSH, PULL, BIDIRECTIONAL) (optional)
            limit: Maximum number of results (optional)
            offset: Number of results to skip (optional)

        Returns:
            List of sync job data dictionaries
        """
        params: Dict[str, Any] = {}

        if connection_id:
            self._validate_uuid(connection_id, "connection_id")
            params["connection_id"] = connection_id

        if status:
            if not isinstance(status, str):
                raise MarketplaceValidationError(
                    "status must be a string",
                    error_code="INVALID_DATA_TYPE",
                    field_path="/status",
                    expected="string",
                    actual=type(status).__name__,
                )
            params["status"] = status

        if direction:
            if not isinstance(direction, str):
                raise MarketplaceValidationError(
                    "direction must be a string",
                    error_code="INVALID_DATA_TYPE",
                    field_path="/direction",
                    expected="string",
                    actual=type(direction).__name__,
                )
            params["direction"] = direction

        if limit is not None:
            if not isinstance(limit, int) or limit < 1:
                raise MarketplaceValidationError(
                    "limit must be a positive integer",
                    error_code="INVALID_VALUE",
                    field_path="/limit",
                    expected="positive integer",
                    actual=limit,
                )
            params["limit"] = limit

        if offset is not None:
            if not isinstance(offset, int) or offset < 0:
                raise MarketplaceValidationError(
                    "offset must be a non-negative integer",
                    error_code="INVALID_VALUE",
                    field_path="/offset",
                    expected="non-negative integer",
                    actual=offset,
                )
            params["offset"] = offset

        try:
            response = await self.client.get("integrations/marketplace/sync/", params=params)
            # Handle paginated response
            if isinstance(response, dict) and "results" in response:
                return response["results"]
            # Handle list response
            if isinstance(response, list):
                return response
            # Handle single item wrapped in dict
            if isinstance(response, dict) and "id" in response:
                return [response]
            return []
        except Exception as e:
            raise self._handle_marketplace_error(e, "list_sync_jobs") from e

    async def cancel_sync_job(self, sync_job_id: str) -> None:
        """
        Cancel a sync job.

        Args:
            sync_job_id: Sync job UUID

        Raises:
            MarketplaceValidationError: If sync_job_id is invalid
            NotFoundError: If sync job is not found
        """
        self._validate_uuid(sync_job_id, "sync_job_id")

        data: Dict[str, Any] = {
            "reason": "User requested cancellation",
        }

        try:
            await self.client.post(
                f"integrations/marketplace/sync/{sync_job_id}/cancel/", data=data
            )
        except NotFoundError:
            raise
        except Exception as e:
            raise self._handle_marketplace_error(e, "cancel_sync_job") from e

    # Mapping Methods

    async def create_mapping(
        self,
        connection_id: str,
        hub_asset_id: str,
        external_listing_id: str,
    ) -> Dict[str, Any]:
        """
        Create a mapping between a hub asset and an external marketplace listing.

        Args:
            connection_id: Connection UUID
            hub_asset_id: Hub asset UUID
            external_listing_id: External marketplace listing ID

        Returns:
            Mapping data dictionary

        Raises:
            MarketplaceValidationError: If parameters are invalid
            NotFoundError: If connection or asset is not found
        """
        self._validate_uuid(connection_id, "connection_id")
        self._validate_uuid(hub_asset_id, "hub_asset_id")

        if not external_listing_id:
            raise MarketplaceValidationError(
                "external_listing_id is required",
                error_code="REQUIRED_FIELD_MISSING",
                field_path="/external_listing_id",
                expected="non-empty string",
                actual="empty or None",
            )

        if not isinstance(external_listing_id, str):
            raise MarketplaceValidationError(
                "external_listing_id must be a string",
                error_code="INVALID_DATA_TYPE",
                field_path="/external_listing_id",
                expected="string",
                actual=type(external_listing_id).__name__,
            )

        data: Dict[str, Any] = {
            "connection_id": connection_id,
            "hub_asset_id": hub_asset_id,
            "external_listing_id": external_listing_id,
        }

        try:
            return await self.client.post("integrations/marketplace/mappings/", data=data)
        except NotFoundError:
            raise
        except Exception as e:
            raise self._handle_marketplace_error(e, "create_mapping") from e

    async def get_mapping(self, mapping_id: str) -> Dict[str, Any]:
        """
        Get a mapping by ID.

        Args:
            mapping_id: Mapping UUID

        Returns:
            Mapping data dictionary

        Raises:
            MarketplaceValidationError: If mapping_id is invalid
            NotFoundError: If mapping is not found
        """
        self._validate_uuid(mapping_id, "mapping_id")

        try:
            return await self.client.get(f"integrations/marketplace/mappings/{mapping_id}/")
        except NotFoundError:
            raise
        except Exception as e:
            raise self._handle_marketplace_error(e, "get_mapping") from e

    async def list_mappings(
        self,
        connection_id: Optional[str] = None,
        asset_id: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        List marketplace mappings.

        Args:
            connection_id: Filter by connection ID (optional)
            asset_id: Filter by hub asset ID (optional)
            limit: Maximum number of results (optional)
            offset: Number of results to skip (optional)

        Returns:
            List of mapping data dictionaries
        """
        params: Dict[str, Any] = {}

        if connection_id:
            self._validate_uuid(connection_id, "connection_id")
            params["connection_id"] = connection_id

        if asset_id:
            self._validate_uuid(asset_id, "asset_id")
            params["hub_asset_id"] = asset_id

        if limit is not None:
            if not isinstance(limit, int) or limit < 1:
                raise MarketplaceValidationError(
                    "limit must be a positive integer",
                    error_code="INVALID_VALUE",
                    field_path="/limit",
                    expected="positive integer",
                    actual=limit,
                )
            params["limit"] = limit

        if offset is not None:
            if not isinstance(offset, int) or offset < 0:
                raise MarketplaceValidationError(
                    "offset must be a non-negative integer",
                    error_code="INVALID_VALUE",
                    field_path="/offset",
                    expected="non-negative integer",
                    actual=offset,
                )
            params["offset"] = offset

        try:
            response = await self.client.get("integrations/marketplace/mappings/", params=params)
            # Handle paginated response
            if isinstance(response, dict) and "results" in response:
                return response["results"]
            # Handle list response
            if isinstance(response, list):
                return response
            # Handle single item wrapped in dict
            if isinstance(response, dict) and "id" in response:
                return [response]
            return []
        except Exception as e:
            raise self._handle_marketplace_error(e, "list_mappings") from e

    async def update_mapping(
        self,
        mapping_id: str,
        sync_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Update a mapping.

        Args:
            mapping_id: Mapping UUID
            sync_metadata: Optional sync metadata dictionary to update

        Returns:
            Updated mapping data dictionary

        Raises:
            MarketplaceValidationError: If parameters are invalid
            NotFoundError: If mapping is not found
        """
        self._validate_uuid(mapping_id, "mapping_id")

        data: Dict[str, Any] = {}

        if sync_metadata is not None:
            if not isinstance(sync_metadata, dict):
                raise MarketplaceValidationError(
                    "sync_metadata must be a dictionary",
                    error_code="INVALID_DATA_TYPE",
                    field_path="/sync_metadata",
                    expected="dict",
                    actual=type(sync_metadata).__name__,
                )
            data["sync_metadata"] = sync_metadata

        if not data:
            raise MarketplaceValidationError(
                "At least one field (sync_metadata) must be provided for update",
                error_code="REQUIRED_FIELD_MISSING",
                field_path="/",
                expected="at least one update field",
                actual="no update fields provided",
            )

        try:
            return await self.client.patch(
                f"integrations/marketplace/mappings/{mapping_id}/", data=data
            )
        except NotFoundError:
            raise
        except Exception as e:
            raise self._handle_marketplace_error(e, "update_mapping") from e

    async def delete_mapping(self, mapping_id: str) -> None:
        """
        Delete a mapping.

        Args:
            mapping_id: Mapping UUID

        Raises:
            MarketplaceValidationError: If mapping_id is invalid
            NotFoundError: If mapping is not found
        """
        self._validate_uuid(mapping_id, "mapping_id")

        try:
            await self.client.delete(f"integrations/marketplace/mappings/{mapping_id}/")
        except NotFoundError:
            raise
        except Exception as e:
            raise self._handle_marketplace_error(e, "delete_mapping") from e

    # Connector Methods

    async def list_connectors(self) -> List[Dict[str, Any]]:
        """
        List all available marketplace connectors.

        Returns:
            List of connector information dictionaries
        """
        try:
            response = await self.client.get("integrations/marketplace/connectors/")
            # Handle response with connectors key
            if isinstance(response, dict) and "connectors" in response:
                return response["connectors"]
            # Handle list response
            if isinstance(response, list):
                return response
            return []
        except Exception as e:
            raise self._handle_marketplace_error(e, "list_connectors") from e

    async def get_connector_info(self, connector_type: str) -> Dict[str, Any]:
        """
        Get information about a specific connector type.

        Args:
            connector_type: Connector type (e.g., "SNOWFLAKE_DATA_MARKETPLACE")

        Returns:
            Connector information dictionary

        Raises:
            MarketplaceValidationError: If connector_type is invalid
            NotFoundError: If connector type is not found
        """
        if not connector_type:
            raise MarketplaceValidationError(
                "connector_type is required",
                error_code="REQUIRED_FIELD_MISSING",
                field_path="/connector_type",
                expected="non-empty string",
                actual="empty or None",
            )

        if not isinstance(connector_type, str):
            raise MarketplaceValidationError(
                "connector_type must be a string",
                error_code="INVALID_DATA_TYPE",
                field_path="/connector_type",
                expected="string",
                actual=type(connector_type).__name__,
            )

        try:
            return await self.client.get(f"integrations/marketplace/connectors/{connector_type}/")
        except NotFoundError:
            raise
        except Exception as e:
            raise self._handle_marketplace_error(e, "get_connector_info") from e
