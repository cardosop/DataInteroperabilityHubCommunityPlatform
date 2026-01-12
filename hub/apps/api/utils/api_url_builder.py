"""
Django API URL Construction Utility

Provides utilities for constructing Django API URLs following naming standards.
This utility ensures consistent URL construction and prevents duplication issues.

For internal Django API calls, use this utility instead of hardcoding URLs.
For external microservice calls, use the respective service client classes.
"""
from typing import Optional, Dict, Any, Tuple
from django.urls import reverse, NoReverseMatch
from django.conf import settings
import structlog

logger = structlog.get_logger(__name__)

# API base path
API_V1_BASE = '/api/v1'


class APIURLBuilder:
    """
    Builder for constructing Django API URLs following naming standards.

    This class ensures URLs are constructed correctly and follow the API naming
    standards (no duplication, kebab-case, plural resources, etc.).

    Example:
        builder = APIURLBuilder()
        url = builder.build('contracts', resource_id='123')
        # Returns: '/api/v1/contracts/123/'

        url = builder.build('contracts', resource_id='123', action='lineage-visualization')
        # Returns: '/api/v1/contracts/123/lineage-visualization/'
    """

    def __init__(self, base_path: str = API_V1_BASE):
        """
        Initialize the URL builder.

        Args:
            base_path: Base path for API (default: '/api/v1')
        """
        self.base_path = base_path.rstrip('/')

    def build(
        self,
        resource: str,
        resource_id: Optional[str] = None,
        action: Optional[str] = None,
        query_params: Optional[Dict[str, Any]] = None,
        use_reverse: bool = False,
        url_name: Optional[str] = None
    ) -> str:
        """
        Build an API URL following naming standards.

        Args:
            resource: Resource name (plural, kebab-case, e.g., 'contracts', 'data-assets')
            resource_id: Optional resource ID (UUID or string)
            action: Optional action name (kebab-case, e.g., 'lineage-visualization')
            query_params: Optional query parameters dictionary
            use_reverse: If True, use Django's reverse() with url_name
            url_name: URL name for reverse lookup (required if use_reverse=True)

        Returns:
            Constructed URL path (e.g., '/api/v1/contracts/123/lineage-visualization/')

        Raises:
            ValueError: If resource name doesn't follow naming standards
            NoReverseMatch: If use_reverse=True and url_name doesn't exist
        """
        # Validate resource name follows kebab-case
        if not self._is_kebab_case(resource):
            raise ValueError(
                f"Resource name '{resource}' must be in kebab-case. "
                f"Use 'data-assets' instead of 'dataAssets' or 'data_assets'."
            )

        # Build URL path
        if use_reverse and url_name:
            # Use Django's reverse() for URL name-based construction
            try:
                if resource_id:
                    url = reverse(url_name, kwargs={'id': resource_id})
                else:
                    url = reverse(url_name)
            except NoReverseMatch as e:
                logger.warning(
                    "api_url_reverse_failed",
                    url_name=url_name,
                    error=str(e),
                    message="Falling back to manual construction"
                )
                # Fall back to manual construction
                url = self._build_manual(resource, resource_id, action)
        else:
            # Manual construction
            url = self._build_manual(resource, resource_id, action)

        # Add query parameters
        if query_params:
            from urllib.parse import urlencode
            query_string = urlencode(query_params)
            url = f"{url}?{query_string}"

        return url

    def _build_manual(
        self,
        resource: str,
        resource_id: Optional[str] = None,
        action: Optional[str] = None
    ) -> str:
        """
        Manually build URL path.

        Args:
            resource: Resource name
            resource_id: Optional resource ID
            action: Optional action name

        Returns:
            URL path
        """
        # Start with base path
        parts = [self.base_path]

        # Add resource (plural, kebab-case)
        parts.append(resource)

        # Add resource ID if provided
        if resource_id:
            parts.append(str(resource_id))

        # Add action if provided
        if action:
            # Validate action is kebab-case
            if not self._is_kebab_case(action):
                raise ValueError(
                    f"Action name '{action}' must be in kebab-case. "
                    f"Use 'lineage-visualization' instead of 'lineageVisualization'."
                )
            parts.append(action)

        # Join parts and ensure trailing slash for consistency
        url = '/'.join(parts) + '/'

        # Normalize multiple slashes
        url = url.replace('//', '/').replace('//', '/')

        return url

    def build_full_url(
        self,
        resource: str,
        resource_id: Optional[str] = None,
        action: Optional[str] = None,
        query_params: Optional[Dict[str, Any]] = None,
        base_url: Optional[str] = None
    ) -> str:
        """
        Build a full URL (with protocol and domain).

        Args:
            resource: Resource name
            resource_id: Optional resource ID
            action: Optional action name
            query_params: Optional query parameters
            base_url: Base URL (defaults to settings.API_BASE_URL or 'http://localhost:8000')

        Returns:
            Full URL (e.g., 'http://localhost:8000/api/v1/contracts/123/')
        """
        if base_url is None:
            base_url = getattr(settings, 'API_BASE_URL', 'http://localhost:8000')

        path = self.build(resource, resource_id, action, query_params)

        # Ensure base_url doesn't have trailing slash
        base_url = base_url.rstrip('/')

        # Ensure path starts with /
        if not path.startswith('/'):
            path = '/' + path

        return f"{base_url}{path}"

    @staticmethod
    def _is_kebab_case(text: str) -> bool:
        """
        Check if text is in kebab-case.

        Args:
            text: Text to check

        Returns:
            True if text is in kebab-case
        """
        if not text:
            return False

        # Kebab-case: lowercase letters, numbers, and hyphens
        # Cannot start or end with hyphen
        # Cannot have consecutive hyphens
        import re
        pattern = r'^[a-z0-9]+(?:-[a-z0-9]+)*$'
        return bool(re.match(pattern, text))

    def validate_url(self, url: str) -> Tuple[bool, Optional[str]]:
        """
        Validate a URL follows naming standards.

        Args:
            url: URL to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not url.startswith(self.base_path):
            return False, f"URL must start with {self.base_path}"

        # Remove base path and trailing slash
        path = url[len(self.base_path):].strip('/')

        if not path:
            return True, None

        # Split into segments
        segments = [s for s in path.split('/') if s]

        # Check for duplicate consecutive segments
        for i in range(len(segments) - 1):
            if segments[i] == segments[i + 1]:
                return False, f"Duplicate segment '{segments[i]}' found in URL"

        # Check all segments are kebab-case (except IDs which might be UUIDs)
        for segment in segments:
            # Skip UUID-like segments
            import re
            uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
            if re.match(uuid_pattern, segment, re.IGNORECASE):
                continue

            if not self._is_kebab_case(segment):
                return False, f"Segment '{segment}' is not in kebab-case"

        return True, None


# Convenience functions
def build_api_url(
    resource: str,
    resource_id: Optional[str] = None,
    action: Optional[str] = None,
    query_params: Optional[Dict[str, Any]] = None
) -> str:
    """
    Convenience function to build an API URL.

    Args:
        resource: Resource name (plural, kebab-case)
        resource_id: Optional resource ID
        action: Optional action name (kebab-case)
        query_params: Optional query parameters

    Returns:
        URL path

    Example:
        url = build_api_url('contracts', resource_id='123', action='lineage-visualization')
        # Returns: '/api/v1/contracts/123/lineage-visualization/'
    """
    builder = APIURLBuilder()
    return builder.build(resource, resource_id, action, query_params)


def build_full_api_url(
    resource: str,
    resource_id: Optional[str] = None,
    action: Optional[str] = None,
    query_params: Optional[Dict[str, Any]] = None,
    base_url: Optional[str] = None
) -> str:
    """
    Convenience function to build a full API URL.

    Args:
        resource: Resource name (plural, kebab-case)
        resource_id: Optional resource ID
        action: Optional action name (kebab-case)
        query_params: Optional query parameters
        base_url: Optional base URL

    Returns:
        Full URL

    Example:
        url = build_full_api_url('contracts', resource_id='123')
        # Returns: 'http://localhost:8000/api/v1/contracts/123/'
    """
    builder = APIURLBuilder()
    return builder.build_full_url(resource, resource_id, action, query_params, base_url)

