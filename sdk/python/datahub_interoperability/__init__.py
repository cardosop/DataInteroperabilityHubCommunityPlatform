"""
DataHub Interoperability Python SDK

Python client library for the Interoperable Data Hub API.
Generated from OpenAPI spec with custom authentication and error handling.
"""

from .client import DataHubClient
from .config import DataHubClientConfig
from .errors import (
    DataHubError,
    ValidationError,
    UnauthorizedError,
    ForbiddenError,
    NotFoundError,
    ConflictError,
    RateLimitError,
    ServerError,
    NetworkError,
    parse_error,
)

__version__ = "1.0.0"
__all__ = [
    "DataHubClient",
    "DataHubClientConfig",
    "DataHubError",
    "ValidationError",
    "UnauthorizedError",
    "ForbiddenError",
    "NotFoundError",
    "ConflictError",
    "RateLimitError",
    "ServerError",
    "NetworkError",
    "parse_error",
]

