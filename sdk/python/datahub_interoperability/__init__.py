"""
DataHub Interoperability Python SDK

Python client library for the Interoperable Data Hub API.
Generated from OpenAPI spec with custom authentication and error handling.
Includes high-level APIs for contracts, lineage, scheduled ingestion, versioning,
governance, mesh, search, observability, virtualization, and webhooks.
"""

from .client import DataHubClient
from .config import DataHubClientConfig
from ._mvp_gates import MVP_GATED_PREFIXES
from .errors import (
    DataHubError,
    ValidationError,
    UnauthorizedError,
    ForbiddenError,
    NotFoundError,
    MVPGatedFeatureError,
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
from .ai import AIAPI
from .assets import AssetsAPI
from .audit import AuditAPI
from .auth import AuthAPI
from .baas import BaaSAPI
from .billing import BillingAPI
from .compliance import ComplianceAPI as ComplianceSDKAPI
from .contracts import ContractsAPI
from .datasets import DatasetsAPI
from .dq import DQAPI
from .files import FilesAPI
from .governance import GovernanceAPI
from .jobs import JobsAPI
from .lineage import LineageAPI
from .marketplace import MarketplaceIntegrationAPI
from .marketplace_listings import MarketplaceListingsAPI
from .mesh import MeshAPI
from .ml import ODHIntegrationAPI, TrainingAPI, InferenceAPI
from .model_serving import ModelServingAPI
from .observability import ObservabilityAPI
from .scheduled_export import ScheduledExportAPI
from .scheduled_ingestion import ScheduledIngestionAPI
from .search import SearchAPI
from .semantic import SemanticAPI
from .social import SocialAPI
from .tenants import TenantsAPI
from .transformation import TransformationAPI
from .users import UsersAPI
from .versioning import VersioningAPI
from .virtualization import VirtualizationAPI
from .webhooks import WebhooksAPI
from .workflows import WorkflowsAPI
from .errors import (
    BillingError,
    BillingValidationError,
    DowngradeLimitExceededError,
    TransformationError,
    TransformationValidationError,
    ComplianceError,
    ComplianceValidationError,
    SemanticError,
    SPARQLError,
    SHACLValidationError,
    WorkflowError,
    DLQError,
    EntitlementRequiredError,
    CircuitBreakerOpenError,
    ModelDeploymentError,
)

__version__ = "2.0.0"
__all__ = [
    # Client
    "DataHubClient",
    "DataHubClientConfig",
    # Base errors
    "DataHubError",
    "ValidationError",
    "UnauthorizedError",
    "ForbiddenError",
    "NotFoundError",
    "MVPGatedFeatureError",
    "MVP_GATED_PREFIXES",
    "ConflictError",
    "RateLimitError",
    "ServerError",
    "NetworkError",
    "parse_error",
    # Domain errors (existing)
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
    # Domain errors (118F.20)
    "BillingError",
    "BillingValidationError",
    "DowngradeLimitExceededError",
    "TransformationError",
    "TransformationValidationError",
    "ComplianceError",
    "ComplianceValidationError",
    "SemanticError",
    "SPARQLError",
    "SHACLValidationError",
    "WorkflowError",
    "DLQError",
    "EntitlementRequiredError",
    "CircuitBreakerOpenError",
    "ModelDeploymentError",
    # API modules (existing)
    "ContractsAPI",
    "LineageAPI",
    "ScheduledIngestionAPI",
    "ScheduledExportAPI",
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
    "TenantsAPI",
    "BillingAPI",
    # API modules (118F new)
    "AIAPI",
    "AssetsAPI",
    "AuditAPI",
    "AuthAPI",
    "ComplianceSDKAPI",
    "DatasetsAPI",
    "DQAPI",
    "FilesAPI",
    "JobsAPI",
    "MarketplaceListingsAPI",
    "SemanticAPI",
    "SocialAPI",
    "TransformationAPI",
    "UsersAPI",
    "WorkflowsAPI",
]

