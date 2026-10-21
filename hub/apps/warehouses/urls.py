"""URL routing for warehouse connections, ACLs, and query.

(The fabricated DeltaShareView routes were removed with 5.5 — the
native bearer-token protocol surface lives under
/api/v1/databricks/delta-sharing.)
"""

from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    LiveQueryViewSet,
    WarehouseConnectionACLViewSet,
    WarehouseConnectionViewSet,
)

router = DefaultRouter()
router.register(r"connections", WarehouseConnectionViewSet, basename="warehouse-connection")
router.register(r"acls", WarehouseConnectionACLViewSet, basename="warehouse-acl")

urlpatterns = [
    *router.urls,
    path("query/", LiveQueryViewSet.as_view({"get": "list"}), name="livequery-list"),
]
