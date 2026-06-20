"""
WebSocket App Configuration
"""

from django.apps import AppConfig


class WebSocketConfig(AppConfig):
    """WebSocket app configuration"""

    default_auto_field = "django.db.models.BigAutoField"
    name = "hub.apps.websocket"
    verbose_name = "WebSocket API"

    def ready(self):
        """Initialize WebSocket app"""
        # Import signal handlers if needed
