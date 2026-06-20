"""
Audit Event Serializers
"""

from rest_framework import serializers

from .models import AuditEvent, AuditEventRetentionPolicy
from .utils import _sanitize


class AuditEventRetentionPolicySerializer(serializers.ModelSerializer):
    """Phase 234.5 — TENANT_ADMIN-facing serializer for per-event-type overrides.

    The ``tenant`` FK is read-only on the wire — the viewset assigns it
    from the request's tenant context on create, and a PATCH that
    tries to move a row to another tenant would otherwise let an admin
    silently re-scope a policy they shouldn't own.

    ``retention_days`` is BOTH writable (operators may supply an explicit
    integer) AND a read-back of the registry-derived value (when
    ``regulation_keys`` is non-empty, the model's ``clean()`` overrides
    the inbound value with the registry result). Clients posting both
    will see the resolved value in the response.
    """

    class Meta:
        model = AuditEventRetentionPolicy
        fields = [
            "id",
            "tenant",
            "event_type",
            "retention_days",
            "regulation_keys",
            "enabled",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "tenant", "created_by", "created_at", "updated_at"]


class AuditEventSerializer(serializers.ModelSerializer):
    """Serializer for audit events"""

    tenant_name = serializers.CharField(source="tenant.name", read_only=True)
    actor_user_email = serializers.CharField(source="actor_user.email", read_only=True)

    class Meta:
        model = AuditEvent
        fields = [
            "id",
            "tenant",
            "tenant_name",
            "actor_user",
            "actor_user_email",
            "resource_type",
            "resource_id",
            "action",
            "result",
            "details_json",
            "timestamp",
            "trace_id",
        ]
        read_only_fields = fields


# Keys that must never leak through the sanitized resource-activity feed.
# These are either security-sensitive (IPs, user agents, raw tokens) or
# internal implementation details that don't belong in an end-user timeline.
# Keys are compared case-insensitively and anything starting with "_" is also
# dropped (our code uses leading underscores to flag private details).
RESOURCE_ACTIVITY_FORBIDDEN_KEYS = frozenset(
    {
        "ip_address",
        "ip",
        "user_agent",
        "user-agent",
        "request_id",
        "trace_id",
        "session_id",
        "access_token",
        "refresh_token",
        "token",
        "password",
        "secret",
        "api_key",
        "authorization",
        "cookies",
        "cookie",
        "internal_notes",
        "stack_trace",
        "raw_payload",
    }
)


def sanitize_activity_details(details):
    """Strip internal/sensitive keys from an audit event details_json blob.

    Rules:
    - Any key starting with ``_`` is dropped (our private-field convention).
    - Any key (case-insensitive) in ``RESOURCE_ACTIVITY_FORBIDDEN_KEYS`` is
      dropped regardless of value.
    - Dict keys that survive filtering are normalized via ``_sanitize`` (Phase 260.2.G).
    - Nested dicts are sanitized recursively; nested lists and tuples are walked so nested
      dicts inside them are cleaned too; string scalars are sanitized.
    - Non-dict inputs are returned unchanged.
    """
    if not isinstance(details, dict):
        return details
    clean = {}
    for key, value in details.items():
        if not isinstance(key, str):
            # Keep unusual non-string keys verbatim; JSON round-trip would have
            # coerced them to strings anyway, but we don't enforce that here.
            clean[key] = value
            continue
        if key.startswith("_"):
            continue
        if key.lower() in RESOURCE_ACTIVITY_FORBIDDEN_KEYS:
            continue
        safe_key = _sanitize(key)
        if isinstance(value, dict):
            clean[safe_key] = sanitize_activity_details(value)
        elif isinstance(value, list):
            clean[safe_key] = [
                sanitize_activity_details(item)
                if isinstance(item, dict)
                else _sanitize(item)
                if isinstance(item, str)
                else item
                for item in value
            ]
        elif isinstance(value, tuple):
            clean[safe_key] = tuple(
                sanitize_activity_details(item)
                if isinstance(item, dict)
                else _sanitize(item)
                if isinstance(item, str)
                else item
                for item in value
            )
        else:
            clean[safe_key] = _sanitize(value) if isinstance(value, str) else value
    return clean


class ResourceActivityEventSerializer(serializers.ModelSerializer):
    """Scoped, sanitized view of an ``AuditEvent`` for the resource-activity feed.

    Unlike ``AuditEventSerializer`` this intentionally omits tenant internals,
    the raw actor FK, and scrubs ``details_json`` via
    :func:`sanitize_activity_details` so the feed is safe to expose to any
    authenticated tenant user (not just AUDITOR / TENANT_ADMIN).
    """

    actor_display_name = serializers.SerializerMethodField()
    details = serializers.SerializerMethodField()

    class Meta:
        model = AuditEvent
        fields = [
            "id",
            "action",
            "result",
            "timestamp",
            "resource_type",
            "resource_id",
            "actor_display_name",
            "details",
        ]
        read_only_fields = fields

    def get_actor_display_name(self, obj):
        """Return the actor's display name/email, or 'System' when null."""
        actor = obj.actor_user
        if actor is None:
            return "System"
        # Prefer a display name if the user model exposes one; fall back to
        # email. We check attributes defensively because different User model
        # variants surface different fields.
        for attr in ("display_name", "full_name", "name"):
            value = getattr(actor, attr, None)
            if value:
                return value
        return getattr(actor, "email", None) or "Unknown"

    def get_details(self, obj):
        return sanitize_activity_details(obj.details_json or {})
