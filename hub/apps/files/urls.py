"""
File URL Configuration.

Malformed-UUID guard: the DefaultRouter uses a UUID converter on
the ``id`` lookup field, so non-UUID URL segments (e.g.
``/files/not-a-uuid/``) return 404 before reaching the view.
Catch-all patterns re-route every endpoint for any non-UUID
``id`` value so the view's ``get_object()`` can return a
well-formed 400 (malformed identifier) instead of the router's
generic 404.

Phase 260.2.A contract: all detail endpoints MUST return 400
for malformed UUIDs in the path.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views  # single import — intentional

router = DefaultRouter()
router.register(r"", views.FileViewSet, basename="file")

# Primary URL patterns: router-generated routes with UUID converter
# match valid-UUID paths first.
urlpatterns = [
    path("", include(router.urls)),
]

# Catch-all for malformed-UUID requests — placed AFTER the router
# patterns so that valid UUIDs match the router's ``<uuid:id>``
# converter first. When ``id`` is not a valid UUID the router's
# pattern rejects it and Django resolves to these guards, which
# route to the view so it can return 400.
#
# Grouped by URL path because Django URL resolution is NOT method-
# aware — two patterns with the same ``<str:id>/`` path would both
# match but the first one wins, returning 405 for methods mapped
# only on the second. Combining methods on a single as_view() call
# avoids the ambiguity.

urlpatterns += [
    # GET retrieve + DELETE destroy (same URL, different methods)
    path(
        "<str:id>/",
        views.FileViewSet.as_view({"get": "retrieve", "delete": "destroy"}),
        name="file-detail-non-uuid-guard",
    ),
    # GET download
    path(
        "<str:id>/download/",
        views.FileViewSet.as_view({"get": "download"}),
        name="file-download-non-uuid-guard",
    ),
    # GET scan-status
    path(
        "<str:id>/scan-status/",
        views.FileViewSet.as_view({"get": "scan_status"}),
        name="file-scan-status-non-uuid-guard",
    ),
    # POST complete
    path(
        "<str:id>/complete/",
        views.FileViewSet.as_view({"post": "complete_upload"}),
        name="file-complete-non-uuid-guard",
    ),
    # POST chunks/init
    path(
        "<str:id>/chunks/init/",
        views.FileViewSet.as_view({"post": "init_chunk_upload"}),
        name="file-chunks-init-non-uuid-guard",
    ),
    # POST rename
    path(
        "<str:id>/rename/",
        views.FileViewSet.as_view({"post": "rename"}),
        name="file-rename-non-uuid-guard",
    ),
    # GET parts
    path(
        "<str:id>/parts/",
        views.FileViewSet.as_view({"get": "parts"}),
        name="file-parts-non-uuid-guard",
    ),
    # POST download/checksum-mismatch
    path(
        "<str:id>/download/checksum-mismatch/",
        views.FileViewSet.as_view({"post": "download_checksum_mismatch"}),
        name="file-checksum-mismatch-non-uuid-guard",
    ),
]
