"""
Observability App Configuration
"""
from django.apps import AppConfig


class ObservabilityConfig(AppConfig):
    """Observability app configuration"""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'hub.apps.observability'
    label = 'observability'

