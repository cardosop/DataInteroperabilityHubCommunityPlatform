"""
Event Replay and Dead Letter Queue API Views

REST API endpoints for event replay and dead letter queue functionality.
"""

import uuid

import structlog
from django.core.cache import cache
from django.db import transaction
from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from hub.apps.api.standards.pagination import StandardPageNumberPagination
from hub.apps.auth.permissions import HasAnyRole
from hub.apps.core.events.bus import get_event_bus
from hub.apps.core.events.dlq_processor import resolve_dlq_entry, retry_dlq_entry
from hub.apps.core.events.models import DeadLetterQueue, Event

logger = structlog.get_logger(__name__)


class IsAdmin(HasAnyRole):
    """Permission class for admin-only endpoints (PLATFORM_ADMIN or TENANT_ADMIN)."""

    def __init__(self):
        super().__init__(["PLATFORM_ADMIN", "TENANT_ADMIN"])


# Rate limit: 10 replays per hour per tenant
REPLAY_RATE_LIMIT_PER_HOUR = 10
REPLAY_RATE_LIMIT_WINDOW = 3600  # 1 hour in seconds

# Maximum events per replay
MAX_EVENTS_PER_REPLAY = 1000


class EventReplayRequestSerializer(serializers.Serializer):
    """Serializer for event replay request."""

    event_type = serializers.CharField(
        required=False, allow_null=True, help_text="Filter by event type (e.g., 'odps.created')"
    )
    tenant_id = serializers.UUIDField(
        required=False, allow_null=True, help_text="Filter by tenant ID"
    )
    start_time = serializers.DateTimeField(
        required=False, allow_null=True, help_text="Start time for replay (ISO 8601 format)"
    )
    end_time = serializers.DateTimeField(
        required=False, allow_null=True, help_text="End time for replay (ISO 8601 format)"
    )
    limit = serializers.IntegerField(
        required=False,
        default=100,
        min_value=1,
        max_value=MAX_EVENTS_PER_REPLAY,
        help_text=f"Maximum number of events to replay (default: 100, max: {MAX_EVENTS_PER_REPLAY})",
    )


class EventReplayResponseSerializer(serializers.Serializer):
    """Serializer for event replay response."""

    success = serializers.BooleanField(help_text="Whether replay was successful")
    events_replayed = serializers.IntegerField(help_text="Number of events replayed")
    events_skipped = serializers.IntegerField(help_text="Number of events skipped (duplicates)")
    total_events_found = serializers.IntegerField(
        help_text="Total number of events found matching filters"
    )
    event_ids = serializers.ListField(
        child=serializers.UUIDField(), help_text="List of event IDs that were replayed"
    )
    skipped_event_ids = serializers.ListField(
        child=serializers.UUIDField(), help_text="List of event IDs that were skipped (duplicates)"
    )


def _check_replay_rate_limit(request, tenant_id: str | None):
    """
    Check rate limit for event replay.

    Args:
        request: HTTP request object
        tenant_id: Tenant ID for rate limiting

    Returns:
        Tuple of (is_allowed, error_response)
        - is_allowed: True if within rate limit, False otherwise
        - error_response: Response object if rate limit exceeded, None otherwise
    """
    if not tenant_id:
        # If no tenant_id, use a default key (shouldn't happen in normal flow)
        tenant_id = "default"

    rate_limit_key = f"event_replay:tenant:{tenant_id}:hour"

    # Get current count
    count = cache.get(rate_limit_key, 0)

    if count >= REPLAY_RATE_LIMIT_PER_HOUR:
        # Rate limit exceeded
        # Try to get TTL, but handle gracefully if cache backend doesn't support it
        ttl = REPLAY_RATE_LIMIT_WINDOW  # Default to full window
        try:
            if hasattr(cache, "ttl"):
                ttl = cache.ttl(rate_limit_key)
                if ttl is None or ttl < 0:
                    ttl = REPLAY_RATE_LIMIT_WINDOW
        except (AttributeError, NotImplementedError):
            # Cache backend doesn't support TTL (e.g., LocMemCache)
            ttl = REPLAY_RATE_LIMIT_WINDOW

        logger.warning(
            "event_replay_rate_limit_exceeded",
            tenant_id=tenant_id,
            count=count,
            limit=REPLAY_RATE_LIMIT_PER_HOUR,
            retry_after=ttl,
        )

        return False, Response(
            {
                "error": {
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": f"Event replay rate limit exceeded. Maximum {REPLAY_RATE_LIMIT_PER_HOUR} replays per hour per tenant. Please retry after {ttl} seconds.",
                    "retry_after": ttl,
                    "limit": REPLAY_RATE_LIMIT_PER_HOUR,
                    "window_seconds": REPLAY_RATE_LIMIT_WINDOW,
                }
            },
            status=status.HTTP_429_TOO_MANY_REQUESTS,
            headers={"Retry-After": str(ttl)},
        )

    # Increment counter
    cache.set(rate_limit_key, count + 1, REPLAY_RATE_LIMIT_WINDOW)

    return True, None


def _check_event_duplicate(event_id: str) -> bool:
    """
    Check if an event has already been replayed (idempotency check).

    Uses Redis to track replayed events with a 24-hour TTL.
    Falls back to Django cache if Redis is unavailable.

    Args:
        event_id: Event ID to check

    Returns:
        True if event was already replayed, False otherwise
    """
    from hub.apps.core.events.deduplication import get_redis_client

    replay_key = f"event_replay:event_id:{event_id}"

    # Try Redis first
    redis_client = get_redis_client()
    if redis_client:
        try:
            exists = redis_client.exists(replay_key)
            return exists > 0
        except Exception as e:
            logger.warning(
                "event_replay_duplicate_check_redis_error",
                event_id=event_id,
                error=str(e),
                message="Redis error, falling back to Django cache",
            )

    # Fallback to Django cache if Redis is unavailable
    try:
        cached_value = cache.get(replay_key)
        return cached_value is not None
    except Exception as e:
        logger.warning(
            "event_replay_duplicate_check_cache_error",
            event_id=event_id,
            error=str(e),
            message="Cache unavailable, cannot check for duplicate replays",
        )
        return False


def _mark_event_replayed(event_id: str):
    """
    Mark an event as replayed for idempotency.

    Uses Redis if available, falls back to Django cache.

    Args:
        event_id: Event ID to mark as replayed
    """
    from hub.apps.core.events.deduplication import get_redis_client

    replay_key = f"event_replay:event_id:{event_id}"
    ttl = 24 * 60 * 60  # 24 hours

    # Try Redis first
    redis_client = get_redis_client()
    if redis_client:
        try:
            redis_client.setex(replay_key, ttl, "1")
            return
        except Exception as e:
            logger.warning(
                "event_replay_mark_redis_error",
                event_id=event_id,
                error=str(e),
                message="Redis error, falling back to Django cache",
            )

    # Fallback to Django cache if Redis is unavailable
    try:
        cache.set(replay_key, "1", ttl)
    except Exception as e:
        logger.warning(
            "event_replay_mark_cache_error",
            event_id=event_id,
            error=str(e),
            message="Cache unavailable, cannot mark event as replayed",
        )


@extend_schema(
    request=EventReplayRequestSerializer,
    responses={
        200: EventReplayResponseSerializer,
        400: inline_serializer(name="ErrorResponse", fields={"error": serializers.DictField()}),
        401: inline_serializer(
            name="UnauthorizedResponse", fields={"error": serializers.DictField()}
        ),
        403: inline_serializer(name="ForbiddenResponse", fields={"error": serializers.DictField()}),
        429: inline_serializer(name="RateLimitResponse", fields={"error": serializers.DictField()}),
    },
    summary="Replay events",
    description="Replay events from the event store. Supports filtering by event_type, tenant_id, and time range. "
    "Rate limited to 10 replays per hour per tenant. Events are idempotent (duplicate events are skipped).",
    tags=["Events"],
    parameters=[
        OpenApiParameter(
            name="event_type",
            type=str,
            location=OpenApiParameter.QUERY,
            description='Filter by event type (e.g., "odps.created")',
            required=False,
        ),
        OpenApiParameter(
            name="tenant_id",
            type=uuid.UUID,
            location=OpenApiParameter.QUERY,
            description="Filter by tenant ID",
            required=False,
        ),
        OpenApiParameter(
            name="start_time",
            type=str,
            location=OpenApiParameter.QUERY,
            description="Start time for replay (ISO 8601 format)",
            required=False,
        ),
        OpenApiParameter(
            name="end_time",
            type=str,
            location=OpenApiParameter.QUERY,
            description="End time for replay (ISO 8601 format)",
            required=False,
        ),
        OpenApiParameter(
            name="limit",
            type=int,
            location=OpenApiParameter.QUERY,
            description=f"Maximum number of events to replay (default: 100, max: {MAX_EVENTS_PER_REPLAY})",
            required=False,
        ),
    ],
)
@api_view(["POST"])
@permission_classes([IsAuthenticated, IsAdmin])
def replay_events(request):
    """
    Replay events from the event store.

    This endpoint allows administrators to replay events that were previously published.
    Events are replayed by republishing them to the event bus, allowing subscribers to
    process them again.

    Features:
    - Filtering by event_type, tenant_id, and time range
    - Rate limiting (10 replays per hour per tenant)
    - Idempotency (duplicate events are skipped)
    - Maximum 1000 events per replay

    Requires PLATFORM_ADMIN or TENANT_ADMIN role.
    """
    # Validate request data
    serializer = EventReplayRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Invalid request data",
                    "details": serializer.errors,
                }
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Get request parameters
    event_type = serializer.validated_data.get("event_type")
    tenant_id = serializer.validated_data.get("tenant_id")
    start_time = serializer.validated_data.get("start_time")
    end_time = serializer.validated_data.get("end_time")
    limit = serializer.validated_data.get("limit", 100)

    # Get tenant_id from request if not provided
    if not tenant_id:
        tenant = getattr(request, "tenant", None)
        if tenant:
            tenant_id = str(tenant.id)
        elif hasattr(request.user, "tenant"):
            tenant_id = str(request.user.tenant.id)

    # Check rate limit
    is_allowed, rate_limit_response = _check_replay_rate_limit(request, tenant_id)
    if not is_allowed:
        return rate_limit_response

    try:
        # Get event bus instance
        event_bus = get_event_bus()

        # Query events from persistence store
        queryset = Event.objects.all()

        # Note: We don't filter out replay results at query level to avoid JSONField query issues
        # Instead, we rely on idempotency checks and marking newly created events

        if event_type:
            queryset = queryset.filter(event_type=event_type)

        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)

        if start_time:
            queryset = queryset.filter(timestamp__gte=start_time)

        if end_time:
            queryset = queryset.filter(timestamp__lte=end_time)

        # Order by timestamp (oldest first for replay)
        queryset = queryset.order_by("timestamp")

        # Get total count BEFORE filtering replay results and applying limit
        # This represents all events matching the filters
        total_events_found = queryset.count()

        # Apply limit
        events = list(queryset[:limit])

        # Filter out replay results before processing (don't count them as skipped)
        # This prevents infinite replay loops
        events_to_process = []
        for event_obj in events:
            event_tags = event_obj.metadata.get("tags", []) if event_obj.metadata else []
            if "replay_result" not in event_tags:
                events_to_process.append(event_obj)

        # Replay events (with idempotency check)
        events_replayed = 0
        events_skipped = 0
        replayed_event_ids = []
        skipped_event_ids = []

        for event_obj in events_to_process:
            event_id = str(event_obj.event_id)

            # Check for duplicate (idempotency)
            if _check_event_duplicate(event_id):
                events_skipped += 1
                skipped_event_ids.append(event_obj.event_id)
                logger.debug(
                    "event_replay_skipped_duplicate",
                    event_id=event_id,
                    event_type=event_obj.event_type,
                )
                continue

            # Reconstruct event payload
            event_payload = {
                "event_id": event_id,
                "event_type": event_obj.event_type,
                "event_version": event_obj.event_version,
                "timestamp": event_obj.timestamp.isoformat() + "Z",
                "source": {
                    "service": event_obj.source_service,
                    "tenant_id": str(event_obj.tenant_id) if event_obj.tenant_id else None,
                },
                "data": event_obj.data,
                "metadata": event_obj.metadata or {},
            }

            if event_obj.user_id:
                event_payload["source"]["user_id"] = str(event_obj.user_id)

            if event_obj.request_id:
                event_payload["source"]["request_id"] = event_obj.request_id

            # Republish event
            try:
                with transaction.atomic():
                    # Republish event to event bus
                    # Add tag to mark this as a replay result
                    replay_tags = list(event_payload.get("metadata", {}).get("tags", []))
                    if "replay_result" not in replay_tags:
                        replay_tags.append("replay_result")

                    new_event_id = event_bus.publish(
                        event_type=event_obj.event_type,
                        data=event_obj.data,
                        tenant_id=str(event_obj.tenant_id) if event_obj.tenant_id else None,
                        user_id=str(event_obj.user_id) if event_obj.user_id else None,
                        request_id=event_obj.request_id,
                        event_version=event_obj.event_version,
                        correlation_id=event_payload.get("metadata", {}).get("correlation_id"),
                        causation_id=event_payload.get("metadata", {}).get("causation_id"),
                        tags=replay_tags,
                    )

                    # Mark original event as replayed (idempotency)
                    _mark_event_replayed(event_id)

                    # Also mark the newly created event as a replay result (prevent re-replay)
                    _mark_event_replayed(new_event_id)

                    events_replayed += 1
                    replayed_event_ids.append(event_obj.event_id)

                    logger.info(
                        "event_replayed",
                        event_id=event_id,
                        event_type=event_obj.event_type,
                        tenant_id=str(event_obj.tenant_id) if event_obj.tenant_id else None,
                    )
            except Exception as e:
                logger.error(
                    "event_replay_failed",
                    event_id=event_id,
                    event_type=event_obj.event_type,
                    error=str(e),
                    exc_info=True,
                )
                # Continue with next event (don't fail entire replay)
                continue

        logger.info(
            "event_replay_completed",
            events_replayed=events_replayed,
            events_skipped=events_skipped,
            total_events_found=total_events_found,
            event_type=event_type,
            tenant_id=tenant_id,
        )

        # Return response
        response_data = {
            "success": True,
            "events_replayed": events_replayed,
            "events_skipped": events_skipped,
            "total_events_found": total_events_found,
            "event_ids": replayed_event_ids,
            "skipped_event_ids": skipped_event_ids,
        }

        return Response(response_data, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(
            "event_replay_error",
            error=str(e),
            exc_info=True,
            event_type=event_type,
            tenant_id=tenant_id,
        )
        return Response(
            {"error": {"code": "REPLAY_ERROR", "message": f"Failed to replay events: {e!s}"}},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# ============================================================================
# Dead Letter Queue API Views
# ============================================================================


class DLQEntrySerializer(serializers.ModelSerializer):
    """Serializer for Dead Letter Queue entry."""

    class Meta:
        model = DeadLetterQueue
        fields = [
            "id",
            "event_type",
            "subscriber",
            "error_message",
            "error_details",
            "retry_count",
            "last_attempt_at",
            "created_at",
            "resolved_at",
            "resolved_by",
        ]
        read_only_fields = fields


class DLQListView(ListAPIView):
    """
    List dead letter queue entries.

    GET /api/v1/events/dlq/
    """

    permission_classes = [IsAuthenticated, IsAdmin]
    serializer_class = DLQEntrySerializer
    pagination_class = StandardPageNumberPagination

    def get_queryset(self):
        """Filter queryset based on query parameters."""
        queryset = DeadLetterQueue.objects.all()

        # Filter by event_type
        event_type = self.request.query_params.get("event_type")
        if event_type:
            queryset = queryset.filter(event_type=event_type)

        # Filter by subscriber
        subscriber = self.request.query_params.get("subscriber")
        if subscriber:
            queryset = queryset.filter(subscriber=subscriber)

        # Filter by resolved status
        resolved = self.request.query_params.get("resolved")
        if resolved is not None:
            resolved_bool = resolved.lower() == "true"
            if resolved_bool:
                queryset = queryset.exclude(resolved_at__isnull=True)
            else:
                queryset = queryset.filter(resolved_at__isnull=True)

        # Order by created_at (newest first)
        queryset = queryset.order_by("-created_at")

        return queryset

    @extend_schema(
        summary="List dead letter queue entries",
        description="List dead letter queue entries with optional filtering. "
        "Requires PLATFORM_ADMIN or TENANT_ADMIN role.",
        parameters=[
            OpenApiParameter(
                name="event_type",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Filter by event type",
                required=False,
            ),
            OpenApiParameter(
                name="subscriber",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Filter by subscriber name",
                required=False,
            ),
            OpenApiParameter(
                name="resolved",
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                description="Filter by resolved status (true/false)",
                required=False,
            ),
        ],
        responses={
            200: DLQEntrySerializer(many=True),
            401: {"description": "Unauthorized"},
            403: {"description": "Forbidden"},
        },
        tags=["Events"],
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class DLQRetryView(APIView):
    """
    Retry a dead letter queue entry.

    POST /api/v1/events/dlq/{id}/retry/
    """

    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(
        summary="Retry dead letter queue entry",
        description="Retry processing a dead letter queue entry by republishing the event. "
        "Requires PLATFORM_ADMIN or TENANT_ADMIN role.",
        responses={
            200: inline_serializer(
                name="DLQRetryResponse",
                fields={
                    "success": serializers.BooleanField(),
                    "message": serializers.CharField(),
                    "retry_count": serializers.IntegerField(),
                },
            ),
            400: {"description": "Bad Request"},
            401: {"description": "Unauthorized"},
            403: {"description": "Forbidden"},
            404: {"description": "Not Found"},
        },
        tags=["Events"],
    )
    def post(self, request, dlq_id):
        """Retry a DLQ entry."""
        # Convert to string (dlq_id is already a UUID from URL pattern)
        dlq_id_str = str(dlq_id)

        # Get user ID for tracking
        user_id = str(request.user.id) if request.user and request.user.is_authenticated else None

        # Retry entry
        success, error_msg = retry_dlq_entry(dlq_id_str, user_id=user_id)

        if success:
            # Get updated entry
            try:
                entry = DeadLetterQueue.objects.get(id=dlq_id_str)
                return Response(
                    {
                        "success": True,
                        "message": "DLQ entry retried successfully",
                        "retry_count": entry.retry_count,
                    },
                    status=status.HTTP_200_OK,
                )
            except DeadLetterQueue.DoesNotExist:
                return Response(
                    {"error": {"code": "NOT_FOUND", "message": "DLQ entry not found"}},
                    status=status.HTTP_404_NOT_FOUND,
                )
        else:
            return Response(
                {
                    "error": {
                        "code": "RETRY_FAILED",
                        "message": error_msg or "Failed to retry DLQ entry",
                    }
                },
                status=status.HTTP_400_BAD_REQUEST,
            )


class DLQResolveView(APIView):
    """
    Resolve a dead letter queue entry.

    POST /api/v1/events/dlq/{id}/resolve/
    """

    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(
        summary="Resolve dead letter queue entry",
        description="Mark a dead letter queue entry as resolved without retrying. "
        "Requires PLATFORM_ADMIN or TENANT_ADMIN role.",
        request=inline_serializer(
            name="DLQResolveRequest",
            fields={
                "notes": serializers.CharField(
                    required=False, allow_blank=True, help_text="Optional resolution notes"
                )
            },
        ),
        responses={
            200: inline_serializer(
                name="DLQResolveResponse",
                fields={
                    "success": serializers.BooleanField(),
                    "message": serializers.CharField(),
                },
            ),
            400: {"description": "Bad Request"},
            401: {"description": "Unauthorized"},
            403: {"description": "Forbidden"},
            404: {"description": "Not Found"},
        },
        tags=["Events"],
    )
    def post(self, request, dlq_id):
        """Resolve a DLQ entry."""
        # Convert to string (dlq_id is already a UUID from URL pattern)
        try:
            dlq_id_str = str(dlq_id)
        except ValueError:
            return Response(
                {"error": {"code": "INVALID_ID", "message": f"Invalid DLQ entry ID: {dlq_id}"}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get user ID and notes
        user_id = str(request.user.id) if request.user and request.user.is_authenticated else None
        notes = request.data.get("notes", "") if hasattr(request, "data") and request.data else None

        # Resolve entry
        success, error_msg = resolve_dlq_entry(dlq_id_str, user_id=user_id, resolution_notes=notes)

        if success:
            return Response(
                {"success": True, "message": "DLQ entry resolved successfully"},
                status=status.HTTP_200_OK,
            )
        else:
            status_code = (
                status.HTTP_404_NOT_FOUND
                if error_msg and "not found" in error_msg.lower()
                else status.HTTP_400_BAD_REQUEST
            )
            return Response(
                {
                    "error": {
                        "code": "RESOLVE_FAILED",
                        "message": error_msg or "Failed to resolve DLQ entry",
                    }
                },
                status=status_code,
            )
