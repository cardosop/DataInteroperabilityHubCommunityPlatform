from django.apps import AppConfig


class OrchestrationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "hub.apps.orchestration"

    def ready(self):
        """Initialize orchestration app when Django starts"""
        from . import business_rules  # noqa: F401 — preload @register_rule
