from django.apps import AppConfig


class ComplianceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "hub.apps.compliance"

    def ready(self):
        # Register @receiver-decorated signal handlers (Phase 231.x).
        import hub.apps.compliance.signals  # side-effect import: registers @receiver signal handlers

        from . import business_rules  # side-effect import: registers business rules
