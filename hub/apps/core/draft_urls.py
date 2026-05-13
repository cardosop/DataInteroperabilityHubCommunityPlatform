"""Phase 278.B.4 — form draft URL routing."""
from django.urls import path

from .draft_views import draft_delete, draft_retrieve, draft_save

urlpatterns = [
    path("", draft_retrieve, name="draft-retrieve"),
    path("save/", draft_save, name="draft-save"),
    path("delete/", draft_delete, name="draft-delete"),
]
