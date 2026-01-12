from django.apps import AppConfig


class JobsConfig(AppConfig):
    """Configuration for jobs app"""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'hub.apps.jobs'
    verbose_name = 'Jobs'

    def ready(self):
        """Import signals and business rules when app is ready"""
        import hub.apps.jobs.business_rules  # noqa: F401 - Import to register business rules
