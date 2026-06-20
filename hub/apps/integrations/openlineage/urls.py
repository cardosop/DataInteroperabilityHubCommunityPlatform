"""
Phase 228 F4 — URL routing for the OpenLineage endpoints.

Mounted under ``/api/v1/lineage/openlineage/`` from the contracts
URL conf (the lineage feature surface lives under contracts).
"""

from __future__ import annotations

from django.urls import path

from hub.apps.integrations.openlineage.views import (
    openlineage_events_view,
    openlineage_keys_collection_view,
    openlineage_keys_detail_view,
)

urlpatterns = [
    # POST inbound RunEvent — REQ-LIN-F4-002.
    path(
        "events/",
        openlineage_events_view,
        name="openlineage-events",
    ),
    # Key admin — REQ-LIN-F4-003.
    path(
        "keys/",
        openlineage_keys_collection_view,
        name="openlineage-keys",
    ),
    path(
        "keys/<uuid:pk>/",
        openlineage_keys_detail_view,
        name="openlineage-keys-detail",
    ),
]
