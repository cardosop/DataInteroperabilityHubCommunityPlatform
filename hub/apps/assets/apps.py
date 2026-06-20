from django.apps import AppConfig


class AssetsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "hub.apps.assets"

    def ready(self):
        import hub.apps.assets.signals  # noqa: F401 — registers @receiver
