from django.apps import AppConfig


class ComplianceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "hub.apps.compliance"

    def ready(self):
        # Register @receiver-decorated signal handlers (Phase 231.x).
        import hub.apps.compliance.signals  # noqa: F401 — registers @receiver
        from . import business_rules  # noqa: F401 — preload @register_rule
