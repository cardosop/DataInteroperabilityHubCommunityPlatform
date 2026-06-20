from django.apps import AppConfig


class MeshConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "hub.apps.mesh"

    def ready(self):
        import hub.apps.mesh.signals  # noqa: F401
        from . import business_rules  # noqa: F401 — preload @register_rule
