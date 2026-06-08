"""URL routing for warehouse connections, ACLs, query, and Delta Sharing."""
from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    DeltaShareView,
    LiveQueryViewSet,
    WarehouseConnectionACLViewSet,
    WarehouseConnectionViewSet,
)

router = DefaultRouter()
router.register(r"connections", WarehouseConnectionViewSet, basename="warehouse-connection")
router.register(r"acls", WarehouseConnectionACLViewSet, basename="warehouse-acl")

urlpatterns = router.urls + [
    path("query/", LiveQueryViewSet.as_view({"get": "list"})),
    path("share/<uuid:asset_id>/", DeltaShareView.as_view({"get": "list_tables"})),
    path("share/<uuid:asset_id>/query/", DeltaShareView.as_view({"get": "query_table"})),
]
