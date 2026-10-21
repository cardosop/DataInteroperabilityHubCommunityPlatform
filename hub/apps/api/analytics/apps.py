"""
API Analytics App Configuration
"""

from django.apps import AppConfig


class APIAnalyticsConfig(AppConfig):
    """Configuration for API Analytics app"""

    default_auto_field = "django.db.models.BigAutoField"
    name = "hub.apps.api.analytics"
    verbose_name = "API Analytics"
