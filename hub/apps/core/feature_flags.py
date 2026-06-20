"""
Feature Flags Utility

Provides centralized feature flag management for enabling/disabling features
without code deployment. Useful for gradual rollouts, A/B testing, and
safe feature removal.
"""

from django.conf import settings
from rest_framework import status
from rest_framework.response import Response


class FeatureDisabledError(Exception):
    """Raised when a feature is disabled via feature flag."""


def is_feature_enabled(feature_name: str) -> bool:
    """
    Check if a feature is enabled via feature flag.

    Args:
        feature_name: Name of the feature flag (e.g., 'ENABLE_TRANSFORMATION_FEATURE')

    Returns:
        bool: True if feature is enabled, False otherwise
    """
    return getattr(settings, feature_name, False)


def check_feature_enabled(feature_name: str):
    """
    Check if a feature is enabled, raise exception if disabled.

    Args:
        feature_name: Name of the feature flag

    Raises:
        FeatureDisabledError: If feature is disabled
    """
    if not is_feature_enabled(feature_name):
        raise FeatureDisabledError(f"Feature '{feature_name}' is disabled")


def get_feature_disabled_response(message: str = "This feature has been disabled") -> Response:
    """
    Get a 410 Gone response for disabled features.

    Args:
        message: Error message to return

    Returns:
        Response: 410 Gone HTTP response
    """
    return Response(
        {"error": "Feature Disabled", "message": message, "status_code": status.HTTP_410_GONE},
        status=status.HTTP_410_GONE,
    )
