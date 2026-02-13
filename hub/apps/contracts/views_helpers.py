"""
Contract Views Shared Helpers

Shared helper functions used across contract views.
"""

from hub.apps.tenants.request_tenant import get_request_tenant_id


def _get_tenant_id_from_request(request) -> str:
    """
    Get tenant_id from request (Phase 16: delegates to central helper).

    Returns tenant ID as string, or "unknown" if not found.
    See hub.apps.tenants.request_tenant.get_request_tenant_id and
    docs/TENANT_ISOLATION.md.
    """
    return get_request_tenant_id(request) or "unknown"


def _categorize_export_size(size_bytes: int) -> str:
    """
    Categorize export size into size categories (Task 6.6.1).

    Categories:
    - small: < 10 KB
    - medium: 10 KB - 100 KB
    - large: 100 KB - 1 MB
    - xlarge: >= 1 MB

    Args:
        size_bytes: Size in bytes

    Returns:
        Size category string
    """
    if size_bytes < 10 * 1024:  # < 10 KB
        return "small"
    elif size_bytes < 100 * 1024:  # 10 KB - 100 KB
        return "medium"
    elif size_bytes < 1024 * 1024:  # 100 KB - 1 MB
        return "large"
    else:  # >= 1 MB
        return "xlarge"
