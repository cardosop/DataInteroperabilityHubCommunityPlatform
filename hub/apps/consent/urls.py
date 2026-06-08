from django.urls import path
from rest_framework.routers import DefaultRouter

from hub.apps.consent import views

router = DefaultRouter()
router.register(r"consent-purposes", views.ConsentPurposeViewSet, basename="consent-purpose")
router.register(r"consent-records", views.ConsentRecordViewSet, basename="consent-record")

urlpatterns = [
    path("consent-dashboard/", views.consent_dashboard, name="consent-dashboard"),
    *router.urls,
]
