"""
Governance App Configuration
"""

from django.apps import AppConfig


class GovernanceConfig(AppConfig):
    """Configuration for governance app"""

    default_auto_field = "django.db.models.BigAutoField"
    name = "hub.apps.governance"
    verbose_name = "Governance"

    def ready(self):
        """Import signals and business rules when app is ready"""
        import hub.apps.governance.business_rules
        import hub.apps.governance.signals
