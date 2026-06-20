"""
Phase 278.P.1 — FormDraft test factory.

Minimal helper for creating FormDraft instances in tests.
Follows the project convention of direct ORM creation (no factory_boy).
"""

from hub.apps.core.drafts import FormDraft


def create_form_draft(*, user, tenant, resource_type="dpia", draft_key="default", data=None):
    """Create a FormDraft for testing. All kwargs required for clarity."""
    return FormDraft.objects.create(
        user=user,
        tenant=tenant,
        resource_type=resource_type,
        draft_key=draft_key,
        data=data or {"field1": "value1"},
    )
