from django.apps import AppConfig


class FilesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "hub.apps.files"

    def ready(self):
        """Import business rules and signals to register them."""
        import hub.apps.files.business_rules
        import hub.apps.files.signals  # side-effect import: registers pre_delete receiver
