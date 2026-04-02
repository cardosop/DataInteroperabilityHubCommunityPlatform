"""
Datasets App Configuration
"""
from django.apps import AppConfig


class DatasetsConfig(AppConfig):
    """Configuration for datasets app"""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'hub.apps.datasets'
    verbose_name = 'Datasets'

    def ready(self):
        import hub.apps.datasets.signals  # noqa: F401

