"""
DataHub Interoperability Python SDK

Python client library for the Interoperable Data Hub API.
Generated from OpenAPI spec with custom authentication and error handling.
Includes high-level APIs for contracts, lineage, scheduled ingestion, versioning,
governance, search, observability, and webhooks.
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
from .contracts import ContractsAPI
from .lineage import LineageAPI
from .scheduled_ingestion import ScheduledIngestionAPI
from .versioning import VersioningAPI
from .governance import GovernanceAPI
from .search import SearchAPI
from .observability import ObservabilityAPI
from .webhooks import WebhooksAPI

__version__ = "2.0.0"
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
    "ContractsAPI",
    "LineageAPI",
    "ScheduledIngestionAPI",
    "VersioningAPI",
    "GovernanceAPI",
    "SearchAPI",
    "ObservabilityAPI",
    "WebhooksAPI",
]

