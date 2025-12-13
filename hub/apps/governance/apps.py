"""
Governance App Configuration
"""
from django.apps import AppConfig


class GovernanceConfig(AppConfig):
    """Configuration for governance app"""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'hub.apps.governance'
    verbose_name = 'Governance'
    
    def ready(self):
        """Import signals when app is ready"""
        import hub.apps.governance.signals  # noqa

