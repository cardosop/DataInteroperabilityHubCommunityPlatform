"""
Scheduled Ingestion App Configuration
"""
from django.apps import AppConfig


class ScheduledIngestionConfig(AppConfig):
    """Configuration for scheduled ingestion app"""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'hub.apps.scheduled_ingestion'
    verbose_name = 'Scheduled Ingestion'

