"""
Virtualization Service — Thin facade.

Re-exports VirtualizationService from its decomposed modules.
All existing ``from hub.apps.virtualization.services import X`` paths are preserved.
"""

import logging
from typing import Any, Dict, List, Optional

from django.db import transaction
from django.utils import timezone

from hub.apps.core.events.service_publishers import VirtualizationEventPublisher
from hub.apps.core.services.base import (
    BaseService,
    ConflictError,
    NotFoundError,
    PermissionError,
    ValidationError,
)
from hub.apps.virtualization.services.dataset_service import DatasetServiceMixin
from hub.apps.virtualization.services.query_service import QueryServiceMixin
from hub.apps.virtualization.services.source_builder_service import SourceBuilderServiceMixin

logger = logging.getLogger(__name__)


class VirtualizationService(
    QueryServiceMixin,
    DatasetServiceMixin,
    SourceBuilderServiceMixin,
    BaseService,
    VirtualizationEventPublisher,
):
    """Virtualization Service — assembled from focused mixins."""

    service_name = "virtualization_service"

    def __init__(self, tenant_id=None, user_id=None):
        """
        Initialize VirtualizationService.

        Args:
            tenant_id: Optional tenant ID
            user_id: Optional user ID
        """
        # Set attributes directly (BaseService doesn't have __init__)
        self.tenant_id = tenant_id
        self.user_id = user_id
        # Initialize event publisher
        VirtualizationEventPublisher.__init__(self)
