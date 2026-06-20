"""Warehouses app configuration."""

from django.apps import AppConfig


class WarehousesConfig(AppConfig):
    name = "hub.apps.warehouses"
    verbose_name = "Warehouses"

    def ready(self):
        import hub.apps.warehouses.signals  # noqa: F401
