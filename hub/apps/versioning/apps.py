"""
Versioning app: minimal Versioning API for contracts and datasets.

Exposes list versions, get version, and compare under /api/v1/versioning/.
Reuses existing version data from hub.apps.contracts (Contract.version) and
hub.apps.datasets (Dataset.version, semantic_version, etc.).
"""

from django.apps import AppConfig


class VersioningConfig(AppConfig):
    name = "hub.apps.versioning"
    verbose_name = "Versioning API"
    default_auto_field = "django.db.models.BigAutoField"
