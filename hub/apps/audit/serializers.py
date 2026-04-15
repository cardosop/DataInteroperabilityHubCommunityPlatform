"""
Audit Event Serializers
"""
from rest_framework import serializers
from .models import AuditEvent


class AuditEventSerializer(serializers.ModelSerializer):
    """Serializer for audit events"""

    tenant_name = serializers.CharField(source='tenant.name', read_only=True)
    actor_user_email = serializers.CharField(source='actor_user.email', read_only=True)

    class Meta:
        model = AuditEvent
        fields = [
            'id',
            'tenant',
            'tenant_name',
            'actor_user',
            'actor_user_email',
            'resource_type',
            'resource_id',
            'action',
            'result',
            'details_json',
            'timestamp'
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
    - Nested dicts are sanitized recursively; nested lists are walked so nested
      dicts inside them are cleaned too.
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
        if isinstance(value, dict):
            clean[key] = sanitize_activity_details(value)
        elif isinstance(value, list):
            clean[key] = [
                sanitize_activity_details(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            clean[key] = value
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

