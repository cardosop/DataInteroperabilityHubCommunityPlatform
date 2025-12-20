"""
Developer Experience App Configuration
"""
from django.apps import AppConfig


class DeveloperConfig(AppConfig):
    """Configuration for developer experience app"""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'hub.apps.developer'
    verbose_name = 'Developer Experience'

