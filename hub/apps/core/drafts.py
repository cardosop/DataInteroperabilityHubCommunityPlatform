"""
Phase 278.B.4 — multi-step form draft storage.

Generic ``FormDraft`` model for auto-saving in-progress forms (DPIA wizard,
contract creation, asset onboarding, breach incident reporting) so users
can resume where they left off across sessions.
"""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


class FormDraft(models.Model):
    """A single in-progress form draft scoped to (user, resource_type, draft_key).

    One draft per (user, resource_type, draft_key) — creating a new draft
    for the same key overwrites the previous one (upsert via save).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="form_drafts",
    )
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="form_drafts",
    )
    resource_type = models.CharField(
        max_length=64,
        help_text="Form resource type, e.g. dpia, contract, asset, breach.",
    )
    draft_key = models.CharField(
        max_length=128,
        default="default",
        help_text="Unique key per form, e.g. 'create' or 'edit-<uuid>'.",
    )
    data = models.JSONField(
        default=dict,
        help_text="The serialized form state as JSON.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "form_drafts"
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "tenant", "resource_type", "draft_key"],
                name="unique_form_draft_per_user_tenant_resource_key",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "resource_type"]),
            models.Index(fields=["tenant", "resource_type"]),
        ]

    def __str__(self):
        return f"Draft for {self.user.email}: {self.resource_type}/{self.draft_key}"
