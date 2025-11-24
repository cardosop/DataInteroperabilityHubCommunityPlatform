from django.apps import AppConfig


class TenantsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'hub.apps.tenants'
    
    def ready(self):
        """Import signals when app is ready"""
        import hub.apps.tenants.signals  # noqa
