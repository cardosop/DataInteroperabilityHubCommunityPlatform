"""
Event Bus Alerting

Alerting system for event bus failures, latency, and dead letter queue monitoring.
"""

from datetime import timedelta
from typing import Any

import structlog
from django.db.models import Count
from django.utils import timezone

from .models import DeadLetterQueue

logger = structlog.get_logger(__name__)


class EventBusAlerting:
    """
    Alerting system for event bus operations.

    Monitors:
    - Event publish failures
    - Event consumption failures
    - Dead letter queue size
    - High latency events
    - Redis connection issues
    """

    def __init__(self):
        """Initialize event bus alerting."""

    def check_publish_failures(
        self, min_failure_count: int = 10, time_window_minutes: int = 15
    ) -> list[dict[str, Any]]:
        """
        Check for high event publish failure rates.

        Args:
            min_failure_count: Minimum number of failures to trigger alert
            time_window_minutes: Time window to check

        Returns:
            List of alert dictionaries
        """
        alerts = []
        time_threshold = timezone.now() - timedelta(minutes=time_window_minutes)

        # Check for events that failed to persist (indicates publish failures)
        # Note: This is a simplified check - in production, you'd track publish failures separately
        # For now, we check DLQ entries that might indicate publish issues

        try:
            # Get recent DLQ entries grouped by event type
            recent_dlq = (
                DeadLetterQueue.objects.filter(created_at__gte=time_threshold)
                .values("event_type")
                .annotate(count=Count("id"))
                .filter(count__gte=min_failure_count)
            )

            for entry in recent_dlq:
                alerts.append(
                    {
                        "alert_type": "event_publish_failure_rate",
                        "event_type": entry["event_type"],
                        "failure_count": entry["count"],
                        "time_window_minutes": time_window_minutes,
                        "severity": "warning"
                        if entry["count"] < min_failure_count * 2
                        else "critical",
                        "timestamp": timezone.now().isoformat(),
                    }
                )
        except Exception as e:
            logger.error("alert_check_publish_failures_error", error=str(e))

        return alerts

    def check_consume_failures(
        self, min_failure_count: int = 10, time_window_minutes: int = 15
    ) -> list[dict[str, Any]]:
        """
        Check for high event consumption failure rates.

        Args:
            min_failure_count: Minimum number of failures to trigger alert
            time_window_minutes: Time window to check

        Returns:
            List of alert dictionaries
        """
        alerts = []
        time_threshold = timezone.now() - timedelta(minutes=time_window_minutes)

        try:
            # Get recent DLQ entries grouped by subscriber
            recent_dlq = (
                DeadLetterQueue.objects.filter(
                    created_at__gte=time_threshold, resolved_at__isnull=True
                )
                .values("subscriber", "event_type")
                .annotate(count=Count("id"))
                .filter(count__gte=min_failure_count)
            )

            for entry in recent_dlq:
                alerts.append(
                    {
                        "alert_type": "event_consume_failure_rate",
                        "subscriber": entry["subscriber"],
                        "event_type": entry["event_type"],
                        "failure_count": entry["count"],
                        "time_window_minutes": time_window_minutes,
                        "severity": "warning"
                        if entry["count"] < min_failure_count * 2
                        else "critical",
                        "timestamp": timezone.now().isoformat(),
                    }
                )
        except Exception as e:
            logger.error("alert_check_consume_failures_error", error=str(e))

        return alerts

    def check_dlq_size(self, max_size: int = 100) -> list[dict[str, Any]]:
        """
        Check if dead letter queue size exceeds threshold.

        Args:
            max_size: Maximum DLQ size before alerting

        Returns:
            List of alert dictionaries
        """
        alerts = []

        try:
            unresolved_dlq_count = DeadLetterQueue.objects.filter(resolved_at__isnull=True).count()

            if unresolved_dlq_count > max_size:
                # Get breakdown by event type and subscriber
                dlq_breakdown = (
                    DeadLetterQueue.objects.filter(resolved_at__isnull=True)
                    .values("event_type", "subscriber")
                    .annotate(count=Count("id"))
                    .order_by("-count")[:10]
                )

                alerts.append(
                    {
                        "alert_type": "event_dlq_size_exceeded",
                        "current_size": unresolved_dlq_count,
                        "max_size": max_size,
                        "breakdown": list(dlq_breakdown),
                        "severity": "critical"
                        if unresolved_dlq_count > max_size * 2
                        else "warning",
                        "timestamp": timezone.now().isoformat(),
                    }
                )
        except Exception as e:
            logger.error("alert_check_dlq_size_error", error=str(e))

        return alerts

    def check_high_latency_events(
        self, latency_threshold_seconds: float = 5.0, time_window_minutes: int = 15
    ) -> list[dict[str, Any]]:
        """
        Check for events with high processing latency.

        Note: This requires tracking event processing times, which would need
        to be stored in the Event model or a separate metrics table.

        Args:
            latency_threshold_seconds: Latency threshold in seconds
            time_window_minutes: Time window to check

        Returns:
            List of alert dictionaries
        """
        alerts = []

        # This is a placeholder - actual implementation would require
        # tracking processing times in the database or metrics system
        # For now, we return empty list

        return alerts

    def check_redis_connection_issues(self, time_window_minutes: int = 5) -> list[dict[str, Any]]:
        """
        Check for Redis connection issues.

        Note: This would typically be monitored via Prometheus metrics
        (event_bus_redis_connection_errors_total). This method provides
        a programmatic way to check.

        Args:
            time_window_minutes: Time window to check

        Returns:
            List of alert dictionaries
        """
        alerts = []

        # This would typically check Prometheus metrics or health check endpoints
        # For now, return empty list - actual implementation would query metrics

        return alerts

    def check_all_alerts(
        self,
        publish_failure_threshold: int = 10,
        consume_failure_threshold: int = 10,
        dlq_max_size: int = 100,
        time_window_minutes: int = 15,
    ) -> dict[str, list[dict[str, Any]]]:
        """
        Check all alert conditions.

        Args:
            publish_failure_threshold: Minimum publish failures to alert
            consume_failure_threshold: Minimum consume failures to alert
            dlq_max_size: Maximum DLQ size before alerting
            time_window_minutes: Time window for failure checks

        Returns:
            Dictionary with all alert types and their alerts
        """
        return {
            "publish_failures": self.check_publish_failures(
                min_failure_count=publish_failure_threshold, time_window_minutes=time_window_minutes
            ),
            "consume_failures": self.check_consume_failures(
                min_failure_count=consume_failure_threshold, time_window_minutes=time_window_minutes
            ),
            "dlq_size": self.check_dlq_size(max_size=dlq_max_size),
            "high_latency": self.check_high_latency_events(
                latency_threshold_seconds=5.0, time_window_minutes=time_window_minutes
            ),
            "redis_connection": self.check_redis_connection_issues(
                time_window_minutes=time_window_minutes
            ),
        }
