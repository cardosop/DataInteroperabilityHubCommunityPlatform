from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'hub.apps.notifications'
    
    def ready(self):
        """Import signals when app is ready"""
        import hub.apps.notifications.signals  # noqa

