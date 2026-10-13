"""
DataHub Interoperability Python SDK

Python client library for the Interoperable Data Hub API.
Generated from OpenAPI spec with custom authentication and error handling.
Includes high-level APIs for contracts, lineage, scheduled ingestion, versioning,
governance, mesh, search, observability, virtualization, and webhooks.
"""

from ._mvp_gates import MVP_GATED_PREFIXES

# Phase 5 / 279 APIs — re-exported for top-level access
from .admin import AdminAPI
from .ai import AIAPI
from .assets import AssetsAPI
from .audit import AuditAPI
from .auth import AuthAPI
from .baas import BaaSAPI
from .billing import BillingAPI
from .capabilities import CapabilitiesAPI
from .client import DataHubClient
from .compliance import ComplianceAPI as ComplianceSDKAPI
from .config import DataHubClientConfig
from .contracts import ContractsAPI
from .datasets import DatasetsAPI
from .developer import DeveloperAPI
from .dpia import DpiaAPI
from .dq import DQAPI
from .drafts import DraftsAPI
from .errors import (
    ABTestError,
    BaaSError,
    BaaSValidationError,
    BillingError,
    BillingValidationError,
    CircuitBreakerOpenError,
    ComplianceError,
    ComplianceValidationError,
    ConflictError,
    DataHubError,
    DLQError,
    DowngradeLimitExceededError,
    EntitlementRequiredError,
    FeatureNotEnabledError,
    ForbiddenError,
    MarketplaceConnectionError,
    MarketplaceError,
    MarketplaceValidationError,
    ModelDeploymentError,
    ModelServingDeploymentError,
    ModelServingError,
    ModelServingNotFoundError,
    ModelServingValidationError,
    MVPGatedFeatureError,
    NetworkError,
    NotFoundError,
    ODHMLConflictError,
    ODHMLError,
    ODHMLNotFoundError,
    ODHMLValidationError,
    RateLimitError,
    SemanticError,
    ServerError,
    SHACLValidationError,
    SPARQLError,
    TransformationError,
    TransformationValidationError,
    UnauthorizedError,
    UnprocessableEntityError,
    ValidationError,
    WorkflowError,
    parse_error,
)
from .events import EventsAPI
from .files import FilesAPI
from .governance import GovernanceAPI
from .integrations import IntegrationsAPI
from .jobs import JobsAPI
from .lineage import LineageAPI
from .lineage_subscriptions import LineageSubscriptionsAPI
from .marketplace import MarketplaceIntegrationAPI
from .marketplace_listings import MarketplaceListingsAPI
from .mesh import MeshAPI
from .ml import InferenceAPI, ODHIntegrationAPI, TrainingAPI
from .model_serving import ModelServingAPI
from .notifications import NotificationAPI
from .observability import ObservabilityAPI
from .openlineage import OpenLineageAPI
from .platform import PlatformAPI
from .public_dsar import PublicDsarAPI
from .ropa import RopaAPI
from .scheduled_export import ScheduledExportAPI
from .scheduled_ingestion import ScheduledIngestionAPI
from .search import SearchAPI
from .security import SecurityAPI
from .semantic import SemanticAPI
from .social import SocialAPI
from .tenants import TenantsAPI
from .transformation import TransformationAPI
from .users import UsersAPI
from .versioning import VersioningAPI
from .virtualization import VirtualizationAPI
from .webhooks import WebhooksAPI
from .workflows import WorkflowsAPI

__version__ = "2.0.0"
__all__ = [
    # API modules (118F new)
    "AIAPI",
    "DQAPI",
    "MVP_GATED_PREFIXES",
    "ABTestError",
    # Phase 5 / 279 API modules
    "AdminAPI",
    "AssetsAPI",
    "AuditAPI",
    "AuthAPI",
    "BaaSAPI",
    "BaaSError",
    "BaaSValidationError",
    "BillingAPI",
    # Domain errors (118F.20)
    "BillingError",
    "BillingValidationError",
    "CapabilitiesAPI",
    "CircuitBreakerOpenError",
    "ComplianceError",
    "ComplianceSDKAPI",
    "ComplianceValidationError",
    "ConflictError",
    # API modules (existing)
    "ContractsAPI",
    "DLQError",
    # Client
    "DataHubClient",
    "DataHubClientConfig",
    # Base errors
    "DataHubError",
    "DatasetsAPI",
    "DeveloperAPI",
    "DowngradeLimitExceededError",
    "DpiaAPI",
    "DraftsAPI",
    "EntitlementRequiredError",
    "EventsAPI",
    "FeatureNotEnabledError",
    "FilesAPI",
    "ForbiddenError",
    "GovernanceAPI",
    "InferenceAPI",
    "IntegrationsAPI",
    "JobsAPI",
    "LineageAPI",
    "LineageSubscriptionsAPI",
    "MVPGatedFeatureError",
    "MarketplaceConnectionError",
    # Domain errors (existing)
    "MarketplaceError",
    "MarketplaceIntegrationAPI",
    "MarketplaceListingsAPI",
    "MarketplaceValidationError",
    "MeshAPI",
    "ModelDeploymentError",
    "ModelServingAPI",
    "ModelServingDeploymentError",
    "ModelServingError",
    "ModelServingNotFoundError",
    "ModelServingValidationError",
    "NetworkError",
    "NotFoundError",
    "NotificationAPI",
    "ODHIntegrationAPI",
    "ODHMLConflictError",
    "ODHMLError",
    "ODHMLNotFoundError",
    "ODHMLValidationError",
    "ObservabilityAPI",
    "OpenLineageAPI",
    "PlatformAPI",
    "PublicDsarAPI",
    "RateLimitError",
    "RopaAPI",
    "SHACLValidationError",
    "SPARQLError",
    "ScheduledExportAPI",
    "ScheduledIngestionAPI",
    "SearchAPI",
    "SecurityAPI",
    "SemanticAPI",
    "SemanticError",
    "ServerError",
    "SocialAPI",
    "TenantsAPI",
    "TrainingAPI",
    "TransformationAPI",
    "TransformationError",
    "TransformationValidationError",
    "UnauthorizedError",
    "UnprocessableEntityError",
    "UsersAPI",
    "ValidationError",
    "VersioningAPI",
    "VirtualizationAPI",
    "WebhooksAPI",
    "WorkflowError",
    "WorkflowsAPI",
    "parse_error",
]
