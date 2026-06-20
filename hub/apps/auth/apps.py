from django.apps import AppConfig


class AuthConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "hub.apps.auth"
    label = "hub_auth"  # Avoid conflict with Django's built-in 'auth' app

    def ready(self):
        """Import OpenAPI extensions to register them"""
        try:
            from . import openapi_extensions  # noqa: F401
        except ImportError:
            pass  # Extensions may not be needed in all environments
