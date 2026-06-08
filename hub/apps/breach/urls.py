from django.urls import include, path
from rest_framework.routers import DefaultRouter

from hub.apps.breach import views

router = DefaultRouter()
router.register(r"incidents", views.BreachIncidentViewSet, basename="breach-incident")
router.register(
    r"notifications", views.BreachNotificationViewSet, basename="breach-notification"
)
router.register(
    r"template-overrides",
    views.BreachTenantTemplateOverrideViewSet,
    basename="breach-template-override",
)

urlpatterns = [
    path("dashboard/", views.breach_dashboard, name="breach-dashboard"),
    path("templates/catalog/", views.breach_template_catalog, name="breach-template-catalog"),
    *router.urls,
]
