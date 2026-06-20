"""
Service-to-Service Communication

Provides patterns for service-to-service communication.
"""

from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

from hub.apps.core.services.base import BaseService, ServiceError

T = TypeVar("T")


class ServiceClient:
    """
    Client for service-to-service communication.

    Provides a pattern for services to call other services
    while maintaining tenant isolation and error handling.
    """

    def __init__(
        self,
        calling_service: BaseService,
        target_service_class: type,
        tenant_id: str | None = None,
        user_id: str | None = None,
    ):
        """
        Initialize service client.

        Args:
            calling_service: The service making the call
            target_service_class: Target service class
            tenant_id: Optional tenant ID (defaults to calling service's tenant)
            user_id: Optional user ID (defaults to calling service's user)
        """
        self.calling_service = calling_service
        self.target_service_class = target_service_class
        self.tenant_id = tenant_id or calling_service.tenant_id
        self.user_id = user_id or calling_service.user_id

    def call(self, method_name: str, *args, **kwargs) -> Any:
        """
        Call a method on the target service.

        Args:
            method_name: Method name to call
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Method return value

        Raises:
            ServiceError: If service call fails
        """
        # Create target service instance
        target_service = self.target_service_class(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            request_id=self.calling_service.request_id,
        )

        # Get method
        if not hasattr(target_service, method_name):
            raise ServiceError(
                f"Method {method_name} not found on {self.target_service_class.__name__}",
                code="METHOD_NOT_FOUND",
            )

        method = getattr(target_service, method_name)

        # Call method
        try:
            return method(*args, **kwargs)
        except ServiceError:
            # Re-raise service errors as-is
            raise
        except Exception as e:
            # Wrap unexpected errors
            raise ServiceError(
                f"Service call failed: {e!s}",
                code="SERVICE_CALL_ERROR",
                details={
                    "target_service": self.target_service_class.__name__,
                    "method": method_name,
                    "error_type": type(e).__name__,
                },
            )


def service_call(
    target_service_class: type,
    method_name: str,
    tenant_id: str | None = None,
    user_id: str | None = None,
):
    """
    Decorator for service-to-service calls.

    Usage:
        @service_call(ContractService, 'get_contract')
        def my_method(self, contract_id: str):
            # This will call ContractService.get_contract
            pass
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(self: BaseService, *args, **kwargs) -> T:
            client = ServiceClient(
                calling_service=self,
                target_service_class=target_service_class,
                tenant_id=tenant_id,
                user_id=user_id,
            )
            return client.call(method_name, *args, **kwargs)

        return wrapper

    return decorator
