"""
DataHub Interoperability Python SDK

Python client library for the Interoperable Data Hub API.
Generated from OpenAPI spec with custom authentication and error handling.
Includes high-level APIs for contracts, lineage, scheduled ingestion, versioning,
governance, mesh, search, observability, virtualization, and webhooks.
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
    MarketplaceError,
    MarketplaceValidationError,
    MarketplaceConnectionError,
    BaaSError,
    BaaSValidationError,
    ODHMLError,
    ODHMLValidationError,
    ODHMLNotFoundError,
    ODHMLConflictError,
    ModelServingError,
    ModelServingValidationError,
    ModelServingNotFoundError,
    ModelServingDeploymentError,
    ABTestError,
)
from .contracts import ContractsAPI
from .lineage import LineageAPI
from .scheduled_ingestion import ScheduledIngestionAPI
from .versioning import VersioningAPI
from .governance import GovernanceAPI
from .mesh import MeshAPI
from .search import SearchAPI
from .observability import ObservabilityAPI
from .virtualization import VirtualizationAPI
from .webhooks import WebhooksAPI
from .marketplace import MarketplaceIntegrationAPI
from .baas import BaaSAPI
from .ml import ODHIntegrationAPI, TrainingAPI, InferenceAPI
from .model_serving import ModelServingAPI

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
    "MarketplaceError",
    "MarketplaceValidationError",
    "MarketplaceConnectionError",
    "BaaSError",
    "BaaSValidationError",
    "ODHMLError",
    "ODHMLValidationError",
    "ODHMLNotFoundError",
    "ODHMLConflictError",
    "ModelServingError",
    "ModelServingValidationError",
    "ModelServingNotFoundError",
    "ModelServingDeploymentError",
    "ABTestError",
    "ContractsAPI",
    "LineageAPI",
    "ScheduledIngestionAPI",
    "VersioningAPI",
    "GovernanceAPI",
    "MeshAPI",
    "SearchAPI",
    "ObservabilityAPI",
    "VirtualizationAPI",
    "WebhooksAPI",
    "MarketplaceIntegrationAPI",
    "BaaSAPI",
    "ODHIntegrationAPI",
    "TrainingAPI",
    "InferenceAPI",
    "ModelServingAPI",
]

