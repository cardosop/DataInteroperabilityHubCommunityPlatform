"""
Core Services Module

Provides base service classes and utilities for the service layer.
"""

from .base import (
    BaseService,
    ConflictError,
    NotFoundError,
    PermissionError,
    ServiceError,
    ValidationError,
)
from .discovery import (
    ServiceRegistry,
    get_health_check_url,
    get_service_url,
    list_services,
    register_service,
)
from .health import (
    ServiceHealthCheck,
    ServiceHealthMonitor,
    check_all_services_health,
    check_service_health,
    is_service_healthy,
)
from .reference import ReferenceService

__all__ = [
    "BaseService",
    "ConflictError",
    "NotFoundError",
    "PermissionError",
    "ReferenceService",
    "ServiceError",
    "ServiceHealthCheck",
    "ServiceHealthMonitor",
    "ServiceRegistry",
    "ValidationError",
    "check_all_services_health",
    "check_service_health",
    "get_health_check_url",
    "get_service_url",
    "is_service_healthy",
    "list_services",
    "register_service",
]
