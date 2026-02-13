"""
Cross-Tenant Access Helpers for Virtualization

Shared helpers for checking cross-tenant access to VirtualDataset and
QueryExecution resources.
Implements the pattern: get resource without tenant filter, compare tenant_id,
run ABAC if other tenant.

This module provides DRY helpers to avoid duplication across virtualization
views.
"""

import logging
from typing import Optional, Tuple

from django.http import HttpRequest
from rest_framework.exceptions import PermissionDenied

from hub.apps.governance.abac import ABACEngine
from hub.apps.tenants.request_tenant import get_request_tenant

from .models import QueryExecution, VirtualDataset

logger = logging.getLogger(__name__)


def get_dataset_for_cross_tenant_check(
    dataset_id: str, request: HttpRequest
) -> Tuple[Optional[VirtualDataset], Optional[PermissionDenied]]:
    """
    Get VirtualDataset without tenant filter and check cross-tenant access.

    Pattern: Get dataset without tenant filter, compare tenant_id, raise
    PermissionDenied if different tenant and user is not platform admin.

    Args:
        dataset_id: VirtualDataset UUID
        request: Django request object

    Returns:
        Tuple of (dataset or None, PermissionDenied exception or None)
        - If dataset doesn't exist: (None, None)
        - If same tenant or platform admin: (dataset, None)
        - If different tenant and not platform admin:
          (dataset, PermissionDenied)
    """
    try:
        dataset = VirtualDataset.objects.get(id=dataset_id)
    except VirtualDataset.DoesNotExist:
        return None, None

    tenant_id, tenant = get_request_tenant(request)
    if not tenant:
        return dataset, None

    # Check if dataset is from different tenant
    if str(dataset.tenant_id) != str(tenant.id):
        # Platform admins can access any tenant's resources
        is_admin = hasattr(request.user, "is_platform_admin") and request.user.is_platform_admin
        if not is_admin:
            msg = "Cannot access virtual dataset from different tenant"
            return (dataset, PermissionDenied(msg))

    return dataset, None


def get_execution_for_cross_tenant_check(
    execution_id: str, request: HttpRequest
) -> Tuple[Optional[QueryExecution], Optional[PermissionDenied]]:
    """
    Get QueryExecution without tenant filter and check cross-tenant access.

    Pattern: Get execution without tenant filter, compare tenant_id via
    virtual_dataset, raise PermissionDenied if different tenant and user is
    not platform admin.

    Args:
        execution_id: QueryExecution UUID
        request: Django request object

    Returns:
        Tuple of (execution or None, PermissionDenied exception or None)
        - If execution doesn't exist: (None, None)
        - If same tenant or platform admin: (execution, None)
        - If different tenant and not platform admin:
          (execution, PermissionDenied)
    """
    try:
        execution = QueryExecution.objects.select_related("virtual_dataset").get(id=execution_id)
    except QueryExecution.DoesNotExist:
        return None, None

    tenant_id, tenant = get_request_tenant(request)
    if not tenant:
        return execution, None

    # Check if execution's virtual_dataset is from different tenant
    if str(execution.virtual_dataset.tenant_id) != str(tenant.id):
        # Platform admins can access any tenant's resources
        is_admin = hasattr(request.user, "is_platform_admin") and request.user.is_platform_admin
        if not is_admin:
            msg = "Cannot access query execution from different tenant"
            return (execution, PermissionDenied(msg))

    return execution, None


def check_abac_for_dataset(
    dataset: VirtualDataset,
    request: HttpRequest,
    access_type: str = "READ",
) -> None:
    """
    Check ABAC policy for VirtualDataset access.

    Args:
        dataset: VirtualDataset instance
        request: Django request object
        access_type: Access type (READ, WRITE, DELETE)

    Raises:
        PermissionDenied: If ABAC policy denies access
    """
    if not request.user or not request.user.id:
        return

    tenant_id, tenant = get_request_tenant(request)
    if not tenant or not dataset.tenant:
        return

    # Skip ABAC for platform admins
    if hasattr(request.user, "is_platform_admin") and request.user.is_platform_admin:
        return

    try:
        result = ABACEngine.evaluate_access(
            user_id=str(request.user.id),
            tenant_id=str(dataset.tenant_id),
            resource_type="VIRTUAL_DATASET",
            resource_id=str(dataset.id),
            access_type=access_type,
        )

        if not result.allowed:
            # If a policy explicitly denied access, raise PermissionDenied
            if result.policy:
                policy_name = result.policy.name if result.policy else "Unknown Policy"
                msg = (
                    f"ABAC policy '{policy_name}' denies {access_type} "
                    f"access to VIRTUAL_DATASET {dataset.id}"
                )
                raise PermissionDenied(msg)
    except PermissionDenied:
        raise
    except Exception as e:
        logger.warning(
            "ABAC check failed for virtual dataset",
            extra={
                "user_id": str(request.user.id),
                "tenant_id": str(dataset.tenant_id),
                "dataset_id": str(dataset.id),
                "access_type": access_type,
                "error_type": type(e).__name__,
            },
            exc_info=True,
        )
        # On ABAC engine failure, allow access (fail open) but log the error


def check_abac_for_execution(
    execution: QueryExecution,
    request: HttpRequest,
    access_type: str = "READ",
) -> None:
    """
    Check ABAC policy for QueryExecution access.

    Args:
        execution: QueryExecution instance
        request: Django request object
        access_type: Access type (READ, WRITE, DELETE)

    Raises:
        PermissionDenied: If ABAC policy denies access
    """
    if not request.user or not request.user.id:
        return

    if not execution.virtual_dataset or not execution.virtual_dataset.tenant:
        return

    tenant_id, tenant = get_request_tenant(request)
    if not tenant:
        return

    # Skip ABAC for platform admins
    if hasattr(request.user, "is_platform_admin") and request.user.is_platform_admin:
        return

    try:
        result = ABACEngine.evaluate_access(
            user_id=str(request.user.id),
            tenant_id=str(execution.virtual_dataset.tenant_id),
            resource_type="QUERY_EXECUTION",
            resource_id=str(execution.id),
            access_type=access_type,
        )

        if not result.allowed:
            # If a policy explicitly denied access, raise PermissionDenied
            if result.policy:
                policy_name = result.policy.name if result.policy else "Unknown Policy"
                msg = (
                    f"ABAC policy '{policy_name}' denies {access_type} "
                    f"access to QUERY_EXECUTION {execution.id}"
                )
                raise PermissionDenied(msg)
    except PermissionDenied:
        raise
    except Exception as e:
        logger.warning(
            "ABAC check failed for query execution",
            extra={
                "user_id": str(request.user.id),
                "tenant_id": str(execution.virtual_dataset.tenant_id),
                "execution_id": str(execution.id),
                "access_type": access_type,
                "error_type": type(e).__name__,
            },
            exc_info=True,
        )
        # On ABAC engine failure, allow access (fail open) but log the error
