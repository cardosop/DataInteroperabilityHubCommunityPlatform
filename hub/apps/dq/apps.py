from django.apps import AppConfig


class DqConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "hub.apps.dq"

    def ready(self):
        from . import business_rules  # noqa: F401 — preload @register_rule
