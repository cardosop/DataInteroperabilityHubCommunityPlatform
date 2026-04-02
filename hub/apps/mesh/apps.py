from django.apps import AppConfig


class MeshConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'hub.apps.mesh'

    def ready(self):
        import hub.apps.mesh.signals  # noqa: F401

