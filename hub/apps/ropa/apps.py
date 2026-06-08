from django.apps import AppConfig


class RopaConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "hub.apps.ropa"
    label = "ropa"
    verbose_name = "RoPA"

    def ready(self) -> None:
        from hub.apps.ropa import signals  # noqa: F401
