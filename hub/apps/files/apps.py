from django.apps import AppConfig


class FilesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'hub.apps.files'

    def ready(self):
        """Import business rules to register them."""
        import hub.apps.files.business_rules  # noqa: F401 - Import to register business rules
