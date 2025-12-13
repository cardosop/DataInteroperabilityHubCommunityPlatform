"""
WebSocket URL routing configuration.
"""
from django.urls import re_path

from .consumers.event_consumer import EventConsumer

websocket_urlpatterns = [
    re_path(r"^ws/events/?$", EventConsumer.as_asgi()),
]

