"""
Search App Configuration
"""
from django.apps import AppConfig


class SearchConfig(AppConfig):
    """Search app configuration"""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'hub.apps.search'
    verbose_name = 'Search'

