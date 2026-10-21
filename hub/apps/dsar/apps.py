from django.apps import AppConfig


class DsarConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "hub.apps.dsar"
    label = "dsar"
    verbose_name = "DSAR (Data Subject Requests)"
