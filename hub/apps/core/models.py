"""Phase 278.B.4 — discover FormDraft model via Django app registry."""
from hub.apps.core.drafts import FormDraft  # noqa: F401

__all__ = ["FormDraft"]
