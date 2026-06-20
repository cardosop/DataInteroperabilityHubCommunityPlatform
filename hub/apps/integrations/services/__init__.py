"""
Marketplace Integration Service -- Thin facade.

Re-exports MarketplaceIntegrationService from its decomposed modules.
All existing ``from hub.apps.integrations.services import X`` paths are preserved.
"""

from typing import TYPE_CHECKING, Any, Dict, List, Optional

import structlog

from hub.apps.integrations.services.connection_service import ConnectionServiceMixin
from hub.apps.integrations.services.discovery_service import DiscoveryServiceMixin
from hub.apps.integrations.services.mapping_service import MappingServiceMixin
from hub.apps.integrations.services.sync_service import SyncServiceMixin

# Keep the same imports the original __init__ had for type checking
if TYPE_CHECKING:
    from django.contrib.auth import get_user_model

    from hub.apps.assets.models import Asset
    from hub.apps.contracts.models import Contract
    from hub.apps.tenants.models import Tenant

    User = get_user_model()

from hub.apps.core.events.service_publishers import IntegrationEventPublisher
from hub.apps.core.services.base import (
    BaseService,
    ConflictError,
    NotFoundError,
    ServiceError,
    ValidationError,
)
from hub.apps.integrations.event_publishers import MarketplaceEventPublisher

logger = structlog.get_logger(__name__)


class MarketplaceIntegrationService(
    ConnectionServiceMixin,
    SyncServiceMixin,
    MappingServiceMixin,
    DiscoveryServiceMixin,
    BaseService,
    IntegrationEventPublisher,
    MarketplaceEventPublisher,
):
    """
    Marketplace Integration Service -- assembled from focused mixins.

    Provides business logic for:
    - Marketplace connection CRUD operations (ConnectionServiceMixin)
    - Connection testing and validation (ConnectionServiceMixin)
    - Sync workflows and job management (SyncServiceMixin)
    - Field mapping CRUD operations (MappingServiceMixin)
    - Marketplace discovery and federated asset creation (DiscoveryServiceMixin)

    All operations include:
    - Distributed tracing via OpenTelemetry
    - Audit logging for compliance
    - Event publishing for asynchronous coordination
    """

    service_name = "marketplace_integration_service"

    def __init__(
        self,
        tenant_id: str | None = None,
        user_id: str | None = None,
        request_id: str | None = None,
    ):
        """
        Initialize MarketplaceIntegrationService.

        Args:
            tenant_id: Optional tenant ID
            user_id: Optional user ID
            request_id: Optional request ID for tracing
        """
        # Set attributes directly (BaseService doesn't have __init__)
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.request_id = request_id
        # Initialize event publishers
        IntegrationEventPublisher.__init__(self)
        MarketplaceEventPublisher.__init__(self, tenant_id=tenant_id, user_id=user_id)


__all__ = [
    "ConnectionServiceMixin",
    "DiscoveryServiceMixin",
    "MappingServiceMixin",
    "MarketplaceIntegrationService",
    "SyncServiceMixin",
]
