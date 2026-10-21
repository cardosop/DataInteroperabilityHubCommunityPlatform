import contextlib

from django.apps import AppConfig


class AuthConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "hub.apps.auth"
    label = "hub_auth"  # Avoid conflict with Django's built-in 'auth' app

    def ready(self):
        """Load OpenAPI extensions so their schema hooks register."""
        from importlib import import_module

        # Side-effect import: the module self-registers its schema
        # extensions on load — the name itself is never used.
        with contextlib.suppress(ImportError):
            import_module("hub.apps.auth.openapi_extensions")
