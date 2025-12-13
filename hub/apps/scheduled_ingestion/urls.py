"""
Scheduled Ingestion URLs

URL routing for scheduled ingestion API endpoints.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ScheduledIngestionViewSet, ScheduledIngestionRunViewSet

router = DefaultRouter()
# Register without prefix since it's already included at 'scheduled-ingestions/' in api/urls.py
router.register(r'', ScheduledIngestionViewSet, basename='scheduled-ingestion')
router.register(r'runs', ScheduledIngestionRunViewSet, basename='scheduled-ingestion-run')

urlpatterns = [
    path('', include(router.urls)),
]

