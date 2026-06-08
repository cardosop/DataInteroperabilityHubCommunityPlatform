"""285.6.2 — Data Movement Django app configuration."""
from django.apps import AppConfig


class DataMovementConfig(AppConfig):
    name = "hub.data_movement"
    label = "data_movement"
    verbose_name = "Data Movement (dlt)"
