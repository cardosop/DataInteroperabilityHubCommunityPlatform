"""
Core Services Module

Provides base service classes and utilities for the service layer.
"""
from .base import (
    BaseService,
    ServiceError,
    ValidationError,
    NotFoundError,
    PermissionError,
    ConflictError,
)
from .reference import ReferenceService
from .discovery import (
    ServiceRegistry,
    get_service_url,
    get_health_check_url,
    list_services,
    register_service,
)
from .health import (
    ServiceHealthCheck,
    ServiceHealthMonitor,
    check_service_health,
    is_service_healthy,
    check_all_services_health,
)

__all__ = [
    'BaseService',
    'ServiceError',
    'ValidationError',
    'NotFoundError',
    'PermissionError',
    'ConflictError',
    'ReferenceService',
    'ServiceRegistry',
    'get_service_url',
    'get_health_check_url',
    'list_services',
    'register_service',
    'ServiceHealthCheck',
    'ServiceHealthMonitor',
    'check_service_health',
    'is_service_healthy',
    'check_all_services_health',
]

