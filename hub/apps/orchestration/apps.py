from django.apps import AppConfig


class OrchestrationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'hub.apps.orchestration'
    
    def ready(self):
        """Initialize orchestration app when Django starts"""
        # Import signal handlers if needed
        pass

