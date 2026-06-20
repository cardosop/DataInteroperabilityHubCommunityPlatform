"""
Virtualization App Configuration
"""

from django.apps import AppConfig


class VirtualizationConfig(AppConfig):
    """Configuration for the virtualization app"""

    default_auto_field = "django.db.models.BigAutoField"
    name = "hub.apps.virtualization"
    verbose_name = "Data Virtualization"

    def ready(self):
        from . import business_rules  # noqa: F401 — preload @register_rule
