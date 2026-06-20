"""Typed exceptions for warehouse operations (Phase 275)."""

from __future__ import annotations


class WarehouseError(Exception):
    """Base exception for all warehouse errors."""

    default_message = "A warehouse error occurred."

    def __init__(self, message=None, code=None, details=None):
        self.message = message or self.default_message
        self.code = code or "WAREHOUSE_ERROR"
        self.details = details or {}
        super().__init__(self.message)


class WarehouseConnectionError(WarehouseError):
    default_message = "Cannot connect to warehouse."
    code = "WAREHOUSE_CONNECTION_FAILED"


class WarehouseCredentialExpiredError(WarehouseError):
    default_message = "Warehouse credentials have expired."
    code = "WAREHOUSE_CREDENTIAL_EXPIRED"


class WarehouseQueryTimeoutError(WarehouseError):
    default_message = "Warehouse query timed out."
    code = "WAREHOUSE_QUERY_TIMEOUT"


class WarehouseUnsupportedTypeError(WarehouseError):
    default_message = "Unsupported warehouse type."
    code = "WAREHOUSE_UNSUPPORTED_DIALECT"


class WarehousePermissionDeniedError(WarehouseError):
    default_message = "Permission denied on warehouse resource."
    code = "WAREHOUSE_PERMISSION_DENIED"


class WarehouseTableNotFoundError(WarehouseError):
    default_message = "Table not found in warehouse."
    code = "WAREHOUSE_TABLE_NOT_FOUND"


class ReadOnlyViolationError(WarehouseError):
    default_message = "Write operations are forbidden on warehouse connections."
    code = "READ_ONLY_VIOLATION"


class ResidencyMismatchError(WarehouseError):
    default_message = "Warehouse region does not match tenant data residency region."
    code = "DATA_RESIDENCY_REGION_MISMATCH"
