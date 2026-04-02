"""
Contract management operations for DataHub SDK.

Provides high-level methods for managing contracts with support for
all new objects (Contact, Server, Terms, Definition, Lineage, ServiceLevel, Models).
"""
import re
import uuid
from typing import Dict, Any, List, Optional
from .client import DataHubClient
from .errors import (
    ODPSValidationError,
    ODPSExportError,
    ODPSLinkingError,
    parse_odps_error,
    ODCSValidationError,
    ODCSExportError,
    parse_odcs_error,
    ValidationError,
    NotFoundError,
)


class ContractsAPI:
    """
    Contract management API.

    Provides methods for creating, updating, listing, and managing contracts
    with support for all contract objects and filtering.
    """

    def __init__(self, client: DataHubClient):
        """
        Initialize Contracts API.

        Args:
            client: DataHub client instance
        """
        self.client = client

    # ODPS Validation Helper Methods

    def _validate_contract_id(self, contract_id: str, param_name: str = "contract_id") -> None:
        """
        Validate contract ID format (UUID).

        Args:
            contract_id: Contract ID to validate
            param_name: Parameter name for error messages

        Raises:
            ODPSValidationError: If contract ID is invalid
        """
        if not contract_id:
            raise ODPSValidationError(
                f"{param_name} is required",
                error_code="REQUIRED_FIELD_MISSING",
                field_path=f"/{param_name}",
                expected="non-empty string (UUID)",
                actual="empty or None",
            )

        if not isinstance(contract_id, str):
            raise ODPSValidationError(
                f"{param_name} must be a string",
                error_code="INVALID_DATA_TYPE",
                field_path=f"/{param_name}",
                expected="string (UUID)",
                actual=type(contract_id).__name__,
            )

        # Validate UUID format
        try:
            uuid.UUID(contract_id)
        except (ValueError, TypeError):
            raise ODPSValidationError(
                f"{param_name} must be a valid UUID",
                error_code="INVALID_VALUE",
                field_path=f"/{param_name}",
                expected="valid UUID format (e.g., '123e4567-e89b-12d3-a456-426614174000')",
                actual=contract_id[:50] if len(contract_id) > 50 else contract_id,
            )

    def _validate_odps_version(self, version: Optional[str], param_name: str = "version") -> None:
        """
        Validate ODPS version format.

        Args:
            version: Version string to validate (e.g., "4.1")
            param_name: Parameter name for error messages

        Raises:
            ODPSValidationError: If version format is invalid
        """
        if version is None:
            return  # Optional parameter

        if not isinstance(version, str):
            raise ODPSValidationError(
                f"{param_name} must be a string",
                error_code="INVALID_DATA_TYPE",
                field_path=f"/{param_name}",
                expected="string (e.g., '4.1')",
                actual=type(version).__name__,
            )

        # Validate version format (e.g., "4.1", "4.2", "3.0")
        version_pattern = r"^\d+\.\d+$"
        if not re.match(version_pattern, version.strip()):
            raise ODPSValidationError(
                f"{param_name} must be in format 'X.Y' (e.g., '4.1')",
                error_code="INVALID_VALUE",
                field_path=f"/{param_name}",
                expected="version string in format 'X.Y'",
                actual=version,
            )

    def _validate_odcs_version(self, version: Optional[str], param_name: str = "version") -> None:
        """
        Validate ODCS version format.

        Validates that the version string matches the expected format and is a supported version.
        ODCS versions follow the format: major.minor[.patch] or major.minor[-suffix]
        Supported versions: 3.0.2, 3.0.1, 3.0.0, 3.0.0-preview, 2.2.2

        Args:
            version: Version string to validate (e.g., "3.0.2", "3.0.1", "3.0.0-preview", "2.2.2")
            param_name: Parameter name for error messages

        Raises:
            ODCSValidationError: If version format is invalid or version is not supported
        """
        if version is None:
            return  # Optional parameter, None is valid

        if not isinstance(version, str):
            raise ODCSValidationError(
                f"{param_name} must be a string",
                error_code="INVALID_DATA_TYPE",
                field_path=f"/{param_name}",
                expected="string (e.g., '3.0.2', '3.0.0-preview')",
                actual=type(version).__name__,
            )

        version = version.strip()

        # ODCS version format: major.minor[.patch] or major.minor[-suffix]
        # Examples: "3.0.2", "3.0.1", "3.0.0", "3.0.0-preview", "2.2.2"
        version_pattern = r"^\d+\.\d+(\.\d+)?(-[a-zA-Z0-9-]+)?$"
        if not re.match(version_pattern, version):
            raise ODCSValidationError(
                f"{param_name} must be in format 'X.Y' or 'X.Y.Z' or 'X.Y-suffix' (e.g., '3.0.2', '3.0.0-preview')",
                error_code="INVALID_VALUE",
                field_path=f"/{param_name}",
                expected="version string in format 'X.Y' or 'X.Y.Z' or 'X.Y-suffix'",
                actual=version,
            )

        # Check if version is supported
        # Supported ODCS versions (must match backend supported versions)
        supported_versions = ['2.2.2', '3.0.0', '3.0.0-preview', '3.0.1', '3.0.2']
        if version not in supported_versions:
            raise ODCSValidationError(
                f"{param_name} '{version}' is not supported. Supported versions: {', '.join(supported_versions)}",
                error_code="INVALID_VALUE",
                field_path=f"/{param_name}",
                expected=f"one of: {', '.join(supported_versions)}",
                actual=version,
            )

    def _validate_format(self, format: str, param_name: str = "format", allowed: Optional[List[str]] = None) -> None:
        """
        Validate format parameter.

        Args:
            format: Format string to validate
            param_name: Parameter name for error messages
            allowed: List of allowed format values (default: ["json", "yaml"])

        Raises:
            ODPSValidationError: If format is invalid
        """
        if allowed is None:
            allowed = ["json", "yaml"]

        if not format:
            raise ODPSValidationError(
                f"{param_name} is required",
                error_code="REQUIRED_FIELD_MISSING",
                field_path=f"/{param_name}",
                expected=f"one of: {', '.join(allowed)}",
                actual="empty or None",
            )

        if not isinstance(format, str):
            raise ODPSValidationError(
                f"{param_name} must be a string",
                error_code="INVALID_DATA_TYPE",
                field_path=f"/{param_name}",
                expected=f"string (one of: {', '.join(allowed)})",
                actual=type(format).__name__,
            )

        format_lower = format.lower().strip()
        if format_lower not in allowed:
            raise ODPSValidationError(
                f"{param_name} must be one of: {', '.join(allowed)}",
                error_code="INVALID_VALUE",
                field_path=f"/{param_name}",
                expected=f"one of: {', '.join(allowed)}",
                actual=format,
            )

    def _validate_odps_content(self, original_raw: str, param_name: str = "original_raw") -> None:
        """
        Validate ODPS document content.

        Args:
            original_raw: ODPS document content to validate
            param_name: Parameter name for error messages

        Raises:
            ODPSValidationError: If content is invalid
        """
        if not original_raw:
            raise ODPSValidationError(
                f"{param_name} is required",
                error_code="REQUIRED_FIELD_MISSING",
                field_path=f"/{param_name}",
                expected="non-empty string (ODPS document)",
                actual="empty or None",
            )

        if not isinstance(original_raw, str):
            raise ODPSValidationError(
                f"{param_name} must be a string",
                error_code="INVALID_DATA_TYPE",
                field_path=f"/{param_name}",
                expected="string (ODPS document)",
                actual=type(original_raw).__name__,
            )

        # Check minimum length (ODPS documents should have some content)
        if len(original_raw.strip()) < 10:
            raise ODPSValidationError(
                f"{param_name} appears to be too short to be a valid ODPS document",
                error_code="INVALID_VALUE",
                field_path=f"/{param_name}",
                expected="valid ODPS document (minimum length)",
                actual=f"string of length {len(original_raw)}",
            )

    def _handle_odps_error(self, error: Exception, operation: str) -> Exception:
        """
        Handle and map ODPS-related errors from API responses.

        Args:
            error: Exception from API call
            operation: Operation name for error context

        Returns:
            Mapped ODPS error or original error
        """
        from .errors import DataHubError, NotFoundError

        # If it's already an ODPS error, return it
        if isinstance(error, (ODPSValidationError, ODPSExportError, ODPSLinkingError)):
            return error

        # Preserve NotFoundError for 404 cases
        if isinstance(error, NotFoundError):
            return error

        # If it's a DataHubError with 404 status, return NotFoundError
        if isinstance(error, DataHubError) and error.http_status == 404:
            return NotFoundError(
                error.message,
                error.request_id,
            )

        # If it's a DataHubError, try to parse as ODPS error
        if isinstance(error, DataHubError):
            # Try to extract error details from the error
            error_dict = error.to_dict() if hasattr(error, "to_dict") else {}
            if error_dict:
                try:
                    return parse_odps_error(error_dict)
                except Exception:
                    # If parsing fails, wrap in ODPS error with context
                    return ODPSValidationError(
                        f"ODPS {operation} failed: {error.message}",
                        error_code=error.code,
                        http_status=error.http_status,
                        request_id=error.request_id,
                        details=error.details,
                    )

        # For other errors, wrap in generic ODPS error
        return ODPSValidationError(
            f"ODPS {operation} failed: {str(error)}",
            error_code="ODPS_ERROR",
            http_status=500,
            details={"context": {"operation": operation, "original_error": str(error)}},
        )

    def _handle_odcs_error(self, error: Exception, operation: str) -> Exception:
        """
        Handle and map ODCS-related errors from API responses.

        Args:
            error: Exception from API call
            operation: Operation name for error context

        Returns:
            Mapped ODCS error or original error
        """
        from .errors import DataHubError, NotFoundError, NetworkError

        # If it's already an ODCS error, return it
        if isinstance(error, (ODCSValidationError, ODCSExportError)):
            return error

        # Preserve NotFoundError for 404 cases
        if isinstance(error, NotFoundError):
            return error

        # Preserve NetworkError for network/timeout errors
        if isinstance(error, NetworkError):
            return error

        # If it's a DataHubError with 404 status, return NotFoundError
        if isinstance(error, DataHubError) and error.http_status == 404:
            return NotFoundError(
                error.message,
                error.request_id,
            )

        # If it's a DataHubError, try to parse as ODCS error
        if isinstance(error, DataHubError):
            # Try to extract error details from the error
            error_dict = error.to_dict() if hasattr(error, "to_dict") else {}
            if error_dict:
                try:
                    return parse_odcs_error(error_dict)
                except Exception:
                    # If parsing fails, wrap in ODCS error with context
                    return ODCSValidationError(
                        f"ODCS {operation} failed: {error.message}",
                        error_code=error.code,
                        http_status=error.http_status,
                        request_id=error.request_id,
                        details=error.details,
                    )

        # For other errors, wrap in generic ODCS error
        return ODCSValidationError(
            f"ODCS {operation} failed: {str(error)}",
            error_code="ODCS_ERROR",
            http_status=500,
            details={"context": {"operation": operation, "original_error": str(error)}},
        )

    async def list(
        self,
        page: int = 1,
        page_size: int = 50,
        ordering: Optional[str] = None,
        owner_email: Optional[str] = None,
        owner_name: Optional[str] = None,
        tag: Optional[str] = None,
        quality_profile: Optional[str] = None,
        compliance_regime: Optional[str] = None,
        contact_email: Optional[str] = None,
        contact_name: Optional[str] = None,
        server_type: Optional[str] = None,
        server_url: Optional[str] = None,
        min_availability: Optional[float] = None,
        max_latency_ms: Optional[float] = None,
        model_name: Optional[str] = None,
        spec_type: Optional[str] = None,
        odps_version: Optional[str] = None,
        has_odps_link: Optional[bool] = None,
        spec_version: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        List contracts with filtering.

        Args:
            page: Page number (default: 1)
            page_size: Items per page (default: 50, max: 100)
            ordering: Sort fields (comma-separated, prefix with '-' for descending)
            owner_email: Filter by owner email (case-insensitive)
            owner_name: Filter by owner name (case-insensitive partial match)
            tag: Filter by tag (can specify multiple)
            quality_profile: Filter by quality profile key
            compliance_regime: Filter by compliance jurisdiction
            contact_email: Filter by contact email (case-insensitive)
            contact_name: Filter by contact name (case-insensitive partial match)
            server_type: Filter by server type
            server_url: Filter by server URL (case-insensitive partial match)
            min_availability: Filter by minimum availability SLA
            max_latency_ms: Filter by maximum latency SLA
            model_name: Filter by model name
            spec_type: Filter by original spec type (e.g., "ODPS", "ODCS")
            odps_version: Filter by ODPS version (e.g., "4.1", "4.0"). Only applies to ODPS contracts
            has_odps_link: Filter by whether contract has an ODPS link (True/False). Only applies to ODCS contracts
            spec_version: Filter by spec version (e.g., "4.1", "1.0"). Universal — works for both ODPS and ODCS

        Returns:
            Paginated response with contracts
        """
        params: Dict[str, Any] = {
            "page": page,
            "page_size": page_size,
        }

        if ordering:
            params["ordering"] = ordering
        if owner_email:
            params["owner_email"] = owner_email
        if owner_name:
            params["owner_name"] = owner_name
        if tag:
            params["tag"] = tag
        if quality_profile:
            params["quality_profile"] = quality_profile
        if compliance_regime:
            params["compliance_regime"] = compliance_regime
        if contact_email:
            params["contact_email"] = contact_email
        if contact_name:
            params["contact_name"] = contact_name
        if server_type:
            params["server_type"] = server_type
        if server_url:
            params["server_url"] = server_url
        if min_availability is not None:
            params["min_availability"] = min_availability
        if max_latency_ms is not None:
            params["max_latency_ms"] = max_latency_ms
        if model_name:
            params["model_name"] = model_name
        if spec_type:
            params["spec_type"] = spec_type
        if odps_version:
            params["odps_version"] = odps_version
        if has_odps_link is not None:
            params["has_odps_link"] = has_odps_link
        if spec_version:
            params["spec_version"] = spec_version

        return await self.client.get("contracts/", params=params)

    async def get(self, contract_id: str) -> Dict[str, Any]:
        """
        Get contract by ID.

        Args:
            contract_id: Contract UUID

        Returns:
            Contract data
        """
        return await self.client.get(f"contracts/{contract_id}/")

    async def export(
        self,
        contract_id: str,
        format: str = "hubcontract",
    ) -> Dict[str, Any]:
        """
        Export contract in specified format.

        Args:
            contract_id: Contract UUID
            format: Export format - "hubcontract", "odps", or "odcs" (default: "hubcontract")

        Returns:
            Exported contract data
        """
        params: Dict[str, Any] = {}
        if format:
            params["format"] = format
        return await self.client.get(f"contracts/{contract_id}/export/", params=params)

    async def download(
        self,
        contract_id: str,
        format: str = "hubcontract",
    ) -> Dict[str, Any]:
        """
        Download contract in specified format.

        Args:
            contract_id: Contract UUID
            format: Download format - "hubcontract", "odps", or "odcs" (default: "hubcontract")

        Returns:
            Downloaded contract data
        """
        params: Dict[str, Any] = {}
        if format:
            params["format"] = format
        return await self.client.get(f"contracts/{contract_id}/download/", params=params)

    async def create(
        self,
        original_raw: str,
        original_format: str = "JSON",
        asset_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create contract from ODCS format.

        Args:
            original_raw: Original contract content (JSON or YAML string)
            original_format: Format of original contract ("JSON" or "YAML")
            asset_id: Optional asset ID to attach contract to

        Returns:
            Created contract data
        """
        data: Dict[str, Any] = {
            "original_raw": original_raw,
            "original_format": original_format,
        }
        if asset_id:
            data["asset_id"] = asset_id

        return await self.client.post("contracts/", data=data)

    async def create_odps(
        self,
        original_raw: str,
        extract_odcs: bool = False,
        link_odcs_id: Optional[str] = None,
        original_format: Optional[str] = None,
        odps_version: Optional[str] = None,
        resolve_external_refs: bool = True,
        asset_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create ODPS (Open Data Product Standard) contract.

        Supports two flows:
        1. Product-First flow (extract_odcs=True): Automatically extracts ODCS from ODPS product.contract
        2. Link flow (link_odcs_id provided): Links ODPS to an existing ODCS contract

        These options are mutually exclusive.

        Args:
            original_raw: ODPS document content (JSON or YAML string)
            extract_odcs: If True, automatically extract ODCS from ODPS product.contract (Product-First flow)
            link_odcs_id: Optional ODCS contract ID to link to (Link flow)
            original_format: Format of ODPS document ("JSON" or "YAML"). Auto-detected from content if not provided
            odps_version: ODPS version (e.g., "4.1"). Used for validation/documentation. Version in document takes precedence
            resolve_external_refs: If True, resolve external $ref references (default: True)
            asset_id: Optional asset ID to attach contracts to

        Returns:
            Created contract data. For Product-First flow, returns dict with 'odps_contract', 'odcs_contract', and 'workflow_instance_id'.
            For Link flow, returns the created ODPS contract.

        Raises:
            ValueError: If both extract_odcs and link_odcs_id are provided, or if neither is provided
        """
        # Validate mutually exclusive options FIRST (before format validation)
        # This ensures we catch logical errors before format errors
        if extract_odcs and link_odcs_id:
            raise ODPSValidationError(
                "Cannot use both extract_odcs and link_odcs_id. Choose one flow.",
                error_code="INVALID_VALUE",
                field_path="/extract_odcs",
                expected="either extract_odcs=True OR link_odcs_id provided, not both",
                actual=f"extract_odcs={extract_odcs}, link_odcs_id={link_odcs_id}",
            )

        if not extract_odcs and not link_odcs_id:
            raise ODPSValidationError(
                "Must specify either extract_odcs=True or link_odcs_id",
                error_code="REQUIRED_FIELD_MISSING",
                field_path="/extract_odcs",
                expected="either extract_odcs=True OR link_odcs_id provided",
                actual="neither extract_odcs nor link_odcs_id provided",
            )

        # Validate parameters (after mutual exclusivity check)
        try:
            self._validate_odps_content(original_raw, "original_raw")
            if link_odcs_id:
                self._validate_contract_id(link_odcs_id, "link_odcs_id")
            if odps_version:
                self._validate_odps_version(odps_version, "odps_version")
        except ODPSValidationError:
            raise
        except Exception as e:
            raise ODPSValidationError(
                f"Parameter validation failed: {str(e)}",
                error_code="VALIDATION_ERROR",
                details={"context": {"operation": "create_odps", "original_error": str(e)}},
            ) from e

        # Auto-detect format if not provided
        if not original_format:
            original_raw_stripped = original_raw.strip()
            if original_raw_stripped.startswith('{'):
                detected_format = "JSON"
            else:
                detected_format = "YAML"
        else:
            # Normalize format to uppercase
            detected_format = original_format.upper()

        # Build base request data
        base_data: Dict[str, Any] = {
            "original_raw": original_raw,
            "original_format": detected_format,
            "resolve_external_refs": resolve_external_refs,
        }

        try:
            if extract_odcs:
                # Product-First flow: Use /api/v1/contracts/products/ endpoint
                product_data = base_data.copy()
                if asset_id:
                    product_data["asset_id"] = asset_id
                if odps_version:
                    product_data["odps_version"] = odps_version

                return await self.client.post("contracts/products/", data=product_data)
            else:
                # Link flow: Use /api/v1/contracts/{odcs_id}/link-odps/ endpoint
                link_data = base_data.copy()
                if odps_version:
                    link_data["odps_version"] = odps_version

                return await self.client.post(f"contracts/{link_odcs_id}/link-odps/", data=link_data)
        except Exception as e:
            # Map and re-raise with ODPS error context
            raise self._handle_odps_error(e, "create") from e

    async def update(
        self,
        contract_id: str,
        original_raw: Optional[str] = None,
        original_format: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Update contract (partial update supported).

        Args:
            contract_id: Contract UUID
            original_raw: Updated contract content (optional)
            original_format: Format of updated contract (optional)
            **kwargs: Additional fields to update

        Returns:
            Updated contract data
        """
        data: Dict[str, Any] = {}
        if original_raw:
            data["original_raw"] = original_raw
        if original_format:
            data["original_format"] = original_format
        data.update(kwargs)

        return await self.client.patch(f"contracts/{contract_id}/", data=data)

    async def delete(self, contract_id: str) -> None:
        """
        Delete contract (soft delete: sets status to RETIRED).

        Args:
            contract_id: Contract UUID
        """
        await self.client.delete(f"contracts/{contract_id}/")

    async def validate(self, contract_id: str) -> Dict[str, Any]:
        """
        Validate contract.

        Args:
            contract_id: Contract UUID

        Returns:
            Validation result with errors and warnings
        """
        return await self.client.post(f"contracts/{contract_id}/validate/")

    async def lint(self, contract_id: str) -> Dict[str, Any]:
        """
        Lint contract.

        Args:
            contract_id: Contract UUID

        Returns:
            Lint result with issues
        """
        return await self.client.post(f"contracts/{contract_id}/lint/")

    async def link_odps_to_odcs(
        self,
        odcs_contract_id: str,
        odps_contract_id: Optional[str] = None,
        odps_raw: Optional[str] = None,
        odps_format: Optional[str] = None,
        resolve_external_refs: bool = True,
    ) -> Dict[str, Any]:
        """
        Link ODPS contract to ODCS contract (bidirectional linking).

        This method supports two modes:
        1. Link to existing ODPS contract: Provide odps_contract_id
        2. Create and link new ODPS contract: Provide odps_raw and odps_format

        The linking creates bidirectional references:
        - ODPS contract stores ODCS link in hub_contract_json.extensions.x_odps.odcs_link
        - ODCS contract stores ODPS link in hub_contract_json.extensions.x_odps.odps_link

        Args:
            odcs_contract_id: ODCS contract ID to link to (must be ODCS type)
            odps_contract_id: Optional existing ODPS contract ID to link
            odps_raw: Optional ODPS document content (if creating new ODPS contract)
            odps_format: Optional ODPS document format ("JSON" or "YAML", required if odps_raw provided)
            resolve_external_refs: If True, resolve external $ref references (default: True)

        Returns:
            Linked ODPS contract data

        Raises:
            ODPSValidationError: If parameters are invalid
            ODPSLinkingError: If linking operation fails
            NotFoundError: If contract is not found
            DataHubError: On other API errors
        """
        # Validate parameters
        try:
            self._validate_contract_id(odcs_contract_id, "odcs_contract_id")
            if odps_contract_id:
                self._validate_contract_id(odps_contract_id, "odps_contract_id")
            if odps_raw:
                self._validate_odps_content(odps_raw, "odps_raw")
                if not odps_format:
                    raise ODPSValidationError(
                        "odps_format is required when odps_raw is provided",
                        error_code="REQUIRED_FIELD_MISSING",
                        field_path="/odps_format",
                        expected="string (JSON or YAML)",
                        actual="None",
                    )
                self._validate_format(odps_format.lower(), "odps_format", ["json", "yaml"])
        except ODPSValidationError:
            raise
        except Exception as e:
            raise ODPSValidationError(
                f"Parameter validation failed: {str(e)}",
                error_code="VALIDATION_ERROR",
                details={"context": {"operation": "link_odps_to_odcs", "original_error": str(e)}},
            ) from e

        # Validate that either odps_contract_id or odps_raw is provided
        if not odps_contract_id and not odps_raw:
            raise ODPSValidationError(
                "Must provide either odps_contract_id (to link existing) or odps_raw (to create new)",
                error_code="REQUIRED_FIELD_MISSING",
                field_path="/odps_contract_id",
                expected="either odps_contract_id OR odps_raw provided",
                actual="neither odps_contract_id nor odps_raw provided",
            )

        # Build request data
        data: Dict[str, Any] = {}

        if odps_contract_id:
            # Link to existing ODPS contract
            data["odps_contract_id"] = odps_contract_id
        else:
            # Create new ODPS contract from raw content
            data["original_raw"] = odps_raw
            data["original_format"] = odps_format.upper() if odps_format else "JSON"
            data["resolve_external_refs"] = resolve_external_refs

        try:
            return await self.client.post(f"contracts/{odcs_contract_id}/link-odps/", data=data)
        except Exception as e:
            # Map and re-raise with ODPS error context
            odps_error = self._handle_odps_error(e, "link")
            # If it's a linking-specific error, convert to ODPSLinkingError
            if isinstance(odps_error, ODPSValidationError):
                raise ODPSLinkingError(
                    f"Failed to link ODPS to ODCS contract: {odps_error.message}",
                    error_code=odps_error.code,
                    http_status=odps_error.http_status,
                    request_id=odps_error.request_id,
                    details=odps_error.details,
                ) from e
            raise odps_error from e

    async def unlink_odps_from_odcs(self, odcs_contract_id: str) -> Dict[str, Any]:
        """
        Unlink ODPS contract from ODCS contract (removes bidirectional links).

        This method removes the bidirectional links between an ODCS contract
        and its linked ODPS contract by:
        - Removing odcs_link from ODPS contract's hub_contract_json.extensions.x_odps
        - Removing odps_link from ODCS contract's hub_contract_json.extensions.x_odps

        Args:
            odcs_contract_id: ODCS contract ID to unlink from (must be ODCS type)

        Returns:
            Success message response

        Raises:
            ODPSValidationError: If parameters are invalid
            ODPSLinkingError: If unlinking operation fails
            NotFoundError: If ODCS contract is not found
            DataHubError: On other API errors
        """
        # Validate parameters
        try:
            self._validate_contract_id(odcs_contract_id, "odcs_contract_id")
        except ODPSValidationError:
            raise
        except Exception as e:
            raise ODPSValidationError(
                f"Parameter validation failed: {str(e)}",
                error_code="VALIDATION_ERROR",
                details={"context": {"operation": "unlink_odps_from_odcs", "original_error": str(e)}},
            ) from e

        try:
            return await self.client.post(f"contracts/{odcs_contract_id}/unlink-odps/")
        except Exception as e:
            # Map and re-raise with ODPS error context
            odps_error = self._handle_odps_error(e, "unlink")
            # If it's a linking-specific error, convert to ODPSLinkingError
            if isinstance(odps_error, ODPSValidationError):
                raise ODPSLinkingError(
                    f"Failed to unlink ODPS from ODCS contract: {odps_error.message}",
                    error_code=odps_error.code,
                    http_status=odps_error.http_status,
                    request_id=odps_error.request_id,
                    details=odps_error.details,
                ) from e
            raise odps_error from e

    async def get_linked_contracts(self, contract_id: str) -> Dict[str, Any]:
        """
        Get all linked contracts for a given contract (ODPS and ODCS links).

        Returns both directions of links:
        - If contract is ODCS: returns odps_link (if linked to an ODPS contract)
        - If contract is ODPS: returns odcs_link (if linked to an ODCS contract)

        Args:
            contract_id: Contract ID to get links for (can be either ODPS or ODCS)

        Returns:
            Dictionary with linked contract information:
            {
                "odps_link": {"id": "...", "status": "...", ...} or None,
                "odcs_link": {"id": "...", "status": "...", ...} or None
            }
        """
        return await self.client.get(f"contracts/{contract_id}/links/")

    # Helper methods for accessing contract objects

    def get_contact(self, contract: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """
        Get contact objects from contract.

        Args:
            contract: Contract data

        Returns:
            List of contact objects or None
        """
        hub_contract = contract.get("hub_contract_json", {})
        return hub_contract.get("contact")

    def get_servers(self, contract: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """
        Get server objects from contract.

        Args:
            contract: Contract data

        Returns:
            List of server objects or None
        """
        hub_contract = contract.get("hub_contract_json", {})
        return hub_contract.get("servers")

    def get_terms(self, contract: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Get terms object from contract.

        Args:
            contract: Contract data

        Returns:
            Terms object or None
        """
        hub_contract = contract.get("hub_contract_json", {})
        return hub_contract.get("terms")

    def get_definitions(self, contract: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """
        Get definition objects from contract.

        Args:
            contract: Contract data

        Returns:
            List of definition objects or None
        """
        hub_contract = contract.get("hub_contract_json", {})
        return hub_contract.get("definitions")

    def get_lineage(self, contract: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Get lineage object from contract.

        Args:
            contract: Contract data

        Returns:
            Lineage object or None
        """
        hub_contract = contract.get("hub_contract_json", {})
        return hub_contract.get("lineage")

    def get_servicelevels(self, contract: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """
        Get service level objects from contract.

        Args:
            contract: Contract data

        Returns:
            List of service level objects or None
        """
        hub_contract = contract.get("hub_contract_json", {})
        return hub_contract.get("servicelevels")

    def get_models(self, contract: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """
        Get models from contract.

        Args:
            contract: Contract data

        Returns:
            List of model objects or None
        """
        hub_contract = contract.get("hub_contract_json", {})
        return hub_contract.get("models")

    # ODPS helper methods

    def is_odps_contract(self, contract: Dict[str, Any]) -> bool:
        """
        Check if contract is an ODPS (Open Data Product Standard) contract.

        Args:
            contract: Contract data

        Returns:
            True if contract is ODPS, False otherwise
        """
        original_spec_type = contract.get("original_spec_type")
        return original_spec_type == "ODPS"

    def get_odps_version(self, contract: Dict[str, Any]) -> Optional[str]:
        """
        Get ODPS version from contract.

        Args:
            contract: Contract data (must be ODPS contract)

        Returns:
            ODPS version string (e.g., "4.1") or None if not available or not ODPS
        """
        if not self.is_odps_contract(contract):
            return None
        return contract.get("original_spec_version")

    def get_pricing_plans(self, contract: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """
        Get pricing plans from ODPS contract.

        Args:
            contract: Contract data (should be ODPS contract)

        Returns:
            List of pricing plan objects or None if not available
        """
        hub_contract = contract.get("hub_contract_json", {})
        if not isinstance(hub_contract, dict):
            return None

        marketplace = hub_contract.get("marketplace", {})
        if not isinstance(marketplace, dict):
            return None

        x_odps = marketplace.get("x_odps", {})
        if not isinstance(x_odps, dict):
            return None

        pricing_plans = x_odps.get("pricing_plans")
        if pricing_plans is None:
            return None

        # Ensure it's a list
        if isinstance(pricing_plans, list):
            return pricing_plans
        return None

    def get_access_methods(self, contract: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Get access methods from ODPS contract.

        Args:
            contract: Contract data (should be ODPS contract)

        Returns:
            Dictionary of access methods (key: method name, value: method config) or None if not available
        """
        hub_contract = contract.get("hub_contract_json", {})
        if not isinstance(hub_contract, dict):
            return None

        marketplace = hub_contract.get("marketplace", {})
        if not isinstance(marketplace, dict):
            return None

        x_odps = marketplace.get("x_odps", {})
        if not isinstance(x_odps, dict):
            return None

        access_methods = x_odps.get("access_methods")
        if access_methods is None:
            return None

        # Ensure it's a dict
        if isinstance(access_methods, dict):
            return access_methods
        return None

    def get_payment_gateways(self, contract: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Get payment gateways from ODPS contract.

        Args:
            contract: Contract data (should be ODPS contract)

        Returns:
            Dictionary of payment gateways (key: gateway name, value: gateway config) or None if not available
        """
        hub_contract = contract.get("hub_contract_json", {})
        if not isinstance(hub_contract, dict):
            return None

        marketplace = hub_contract.get("marketplace", {})
        if not isinstance(marketplace, dict):
            return None

        x_odps = marketplace.get("x_odps", {})
        if not isinstance(x_odps, dict):
            return None

        payment_gateways = x_odps.get("payment_gateways")
        if payment_gateways is None:
            return None

        # Ensure it's a dict
        if isinstance(payment_gateways, dict):
            return payment_gateways
        return None

    def get_product_strategy(self, contract: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Get product strategy from ODPS contract (ODPS 4.1+).

        Product strategy is stored in extensions.x_odps.product_strategy or
        info.x_odps.product_strategy as fallback.

        Args:
            contract: Contract data (should be ODPS contract)

        Returns:
            Product strategy dictionary with objectives, strategicAlignment, productKPIs,
            or None if not available
        """
        hub_contract = contract.get("hub_contract_json", {})
        if not isinstance(hub_contract, dict):
            return None

        # Check extensions.x_odps.product_strategy first (preferred location)
        extensions = hub_contract.get("extensions", {})
        if isinstance(extensions, dict):
            x_odps = extensions.get("x_odps", {})
            if isinstance(x_odps, dict):
                product_strategy = x_odps.get("product_strategy")
                if product_strategy is not None and isinstance(product_strategy, dict):
                    return product_strategy

        # Fallback to info.x_odps.product_strategy
        info = hub_contract.get("info", {})
        if isinstance(info, dict):
            x_odps = info.get("x_odps", {})
            if isinstance(x_odps, dict):
                product_strategy = x_odps.get("product_strategy")
                if product_strategy is not None and isinstance(product_strategy, dict):
                    return product_strategy

        return None

    def get_product_details(self, contract: Dict[str, Any], lang: str = "en") -> Optional[Dict[str, Any]]:
        """
        Get product details from ODPS contract for a specific language.

        Product details are extracted from the original_raw ODPS document's
        product.details[lang] structure. If original_raw is not available or
        cannot be parsed, attempts to reconstruct from hub_contract_json.

        Args:
            contract: Contract data (should be ODPS contract)
            lang: Language code (ISO 639-1, e.g., "en", "fi"). Defaults to "en"

        Returns:
            Product details dictionary for the specified language, or None if not available
        """
        # First, try to extract from original_raw (most accurate)
        original_raw = contract.get("original_raw")
        if original_raw:
            try:
                import json
                odps_data = json.loads(original_raw)
                product = odps_data.get("product", {})
                if isinstance(product, dict):
                    details = product.get("details", {})
                    if isinstance(details, dict):
                        lang_details = details.get(lang)
                        if lang_details is not None and isinstance(lang_details, dict):
                            return lang_details
            except (json.JSONDecodeError, ValueError, TypeError):
                # If JSON parsing fails, try to reconstruct from hub_contract_json
                pass

        # Fallback: reconstruct from hub_contract_json
        hub_contract = contract.get("hub_contract_json", {})
        if not isinstance(hub_contract, dict):
            return None

        info = hub_contract.get("info", {})
        if not isinstance(info, dict):
            return None

        # Reconstruct product details from hub_contract info
        product_details = {}
        product_id = hub_contract.get("id")
        if product_id:
            product_details["productID"] = product_id

        name = info.get("name")
        if name:
            product_details["name"] = name

        description = info.get("description")
        if description:
            product_details["description"] = description

        version = info.get("version")
        if version:
            product_details["productVersion"] = version

        # Only return if we have at least productID or name
        if product_details and (product_details.get("productID") or product_details.get("name")):
            return product_details

        return None

    async def export_odps(
        self,
        contract_id: str,
        version: Optional[str] = None,
        format: str = "json",
    ) -> Dict[str, Any]:
        """
        Export contract as ODPS (Open Data Product Standard) format.

        Args:
            contract_id: Contract UUID
            version: ODPS version (e.g., "4.1"). Defaults to "4.1" if not provided
            format: Output format ("json" or "yaml"). Defaults to "json"

        Returns:
            Contract data in ODPS format. For JSON format, returns a dictionary.
            For YAML format, returns a dictionary with 'content' (YAML string) and 'format' fields.

        Raises:
            ODPSValidationError: If parameters are invalid
            ODPSExportError: If export operation fails
            NotFoundError: If contract is not found
            DataHubError: On other API errors
        """
        # Validate parameters
        try:
            self._validate_contract_id(contract_id, "contract_id")
            self._validate_format(format, "format", ["json", "yaml"])
            if version:
                self._validate_odps_version(version, "version")
        except ODPSValidationError:
            raise
        except Exception as e:
            raise ODPSValidationError(
                f"Parameter validation failed: {str(e)}",
                error_code="VALIDATION_ERROR",
                details={"context": {"operation": "export_odps", "original_error": str(e)}},
            ) from e

        params: Dict[str, Any] = {
            "format": "odps",
            "output_format": format,
        }
        if version:
            params["version"] = version

        # Use request() to handle both JSON and YAML responses
        try:
            response = await self.client.request("GET", f"contracts/{contract_id}/export/", params=params)
        except Exception as e:
            # Map and re-raise with ODPS error context
            raise self._handle_odps_error(e, "export") from e

        # Check content type to determine how to parse
        content_type = response.headers.get("Content-Type", "").lower()

        if "yaml" in content_type or format == "yaml":
            # YAML response - return as text
            return {
                "content": response.text,
                "format": "yaml",
            }
        else:
            # JSON response - parse as JSON
            # The API may return JSON as a string (escaped), so try parsing the text first
            try:
                # Try parsing the response text as JSON (handles both JSON objects and JSON-encoded strings)
                import json
                parsed = json.loads(response.text)
                # If the parsed result is a string, parse it again (handles double-encoded JSON)
                if isinstance(parsed, str):
                    return json.loads(parsed)
                return parsed
            except (json.JSONDecodeError, ValueError):
                # Fallback to response.json() if direct parsing fails
                return response.json()

    async def download_odps(
        self,
        contract_id: str,
        version: Optional[str] = None,
        format: str = "json",
    ) -> bytes:
        """
        Download contract as ODPS (Open Data Product Standard) format file.

        Args:
            contract_id: Contract UUID
            version: ODPS version (e.g., "4.1"). Defaults to "4.1" if not provided
            format: Output format ("json" or "yaml"). Defaults to "json"

        Returns:
            Contract file content as bytes

        Raises:
            ODPSValidationError: If parameters are invalid
            ODPSExportError: If download operation fails
            NotFoundError: If contract is not found
            DataHubError: On other API errors
        """
        # Validate parameters
        try:
            self._validate_contract_id(contract_id, "contract_id")
            self._validate_format(format, "format", ["json", "yaml"])
            if version:
                self._validate_odps_version(version, "version")
        except ODPSValidationError:
            raise
        except Exception as e:
            raise ODPSValidationError(
                f"Parameter validation failed: {str(e)}",
                error_code="VALIDATION_ERROR",
                details={"context": {"operation": "download_odps", "original_error": str(e)}},
            ) from e

        params: Dict[str, Any] = {
            "format": "odps",
            "output_format": format,
        }
        if version:
            params["version"] = version

        # Use request() to get raw response for binary content
        try:
            response = await self.client.request("GET", f"contracts/{contract_id}/download/", params=params)
            return response.content
        except Exception as e:
            # Map and re-raise with ODPS error context
            raise self._handle_odps_error(e, "download") from e

    async def export_odcs(
        self,
        contract_id: str,
        version: Optional[str] = None,
        format: str = "json",
    ) -> Dict[str, Any]:
        """
        Export contract as ODCS (Open Data Contract Standard) format.

        Args:
            contract_id: Contract UUID
            version: ODCS version (e.g., "3.0.2", "3.0.0-preview"). Optional, defaults to contract's detected version
            format: Output format ("json" or "yaml"). Defaults to "json"

        Returns:
            Contract data in ODCS format. For JSON format, returns a dictionary.
            For YAML format, returns a dictionary with 'content' (YAML string) and 'format' fields.

        Raises:
            ODCSValidationError: If parameters are invalid
            ODCSExportError: If export operation fails
            NotFoundError: If contract is not found
            DataHubError: On other API errors
        """
        # Validate parameters
        # Convert ODPSValidationError to ODCSValidationError for ODCS operations
        try:
            self._validate_contract_id(contract_id, "contract_id")
        except ODPSValidationError as e:
            # Convert ODPS validation error to ODCS validation error
            raise ODCSValidationError(
                e.message,
                error_code=e.code,
                http_status=e.http_status,
                request_id=e.request_id,
                details=e.details,
                field_path=e.field_path,
                expected=e.expected,
                actual=e.actual,
            ) from e

        try:
            self._validate_format(format, "format", ["json", "yaml"])
        except ODPSValidationError as e:
            # Convert ODPS validation error to ODCS validation error
            raise ODCSValidationError(
                e.message,
                error_code=e.code,
                http_status=e.http_status,
                request_id=e.request_id,
                details=e.details,
                field_path=e.field_path,
                expected=e.expected,
                actual=e.actual,
            ) from e

        if version:
            self._validate_odcs_version(version, "version")

        params: Dict[str, Any] = {
            "format": "odcs",
            "output_format": format,
        }
        if version:
            params["version"] = version

        # Use request() to handle both JSON and YAML responses
        try:
            response = await self.client.request("GET", f"contracts/{contract_id}/export/", params=params)
        except Exception as e:
            # Map and re-raise with ODCS error context
            raise self._handle_odcs_error(e, "export") from e

        # Check content type to determine how to parse
        content_type = response.headers.get("Content-Type", "").lower()

        if "yaml" in content_type or format == "yaml":
            # YAML response - return as text
            return {
                "content": response.text,
                "format": "yaml",
            }
        else:
            # JSON response - parse as JSON
            # The API may return JSON as a string (escaped), so try parsing the text first
            try:
                # Try parsing the response text as JSON (handles both JSON objects and JSON-encoded strings)
                import json
                parsed = json.loads(response.text)
                # If the parsed result is a string, parse it again (handles double-encoded JSON)
                if isinstance(parsed, str):
                    return json.loads(parsed)
                return parsed
            except (json.JSONDecodeError, ValueError):
                # Fallback to response.json() if direct parsing fails
                return response.json()

