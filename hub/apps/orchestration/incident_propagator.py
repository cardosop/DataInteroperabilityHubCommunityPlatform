"""
285.11.5.3 — PipelineIncidentPropagator.

When a pipeline execution FAILED, finds all downstream pipelines
via the dependency resolver and notifies their owners via audit
events, webhook POST, and in-app notifications.

Deduplicates owner notifications: max 1 email per owner per hour.
"""
from __future__ import annotations
import json
import logging
import time
from typing import Any, Dict, List

from django.core.cache import cache

from hub.apps.audit.utils import create_audit_event

from .dependency_resolver import PipelineDependencyResolver
from .models import PipelineDependency

logger = logging.getLogger(__name__)

# Dedup window: max 1 notification per owner per hour.
_DEDUP_TTL_SECONDS = 3600


class PipelineIncidentPropagator:
    """Propagate upstream pipeline failures to downstream owners."""

    def __init__(self, tenant_id: str):
        self.tenant_id = str(tenant_id)
        self._resolver = PipelineDependencyResolver(self.tenant_id)

    def propagate(
        self,
        upstream_type: str,
        upstream_id: str,
        upstream_run_id: str,
        failure_reason: str = "",
    ) -> Dict[str, Any]:
        """Find downstream pipelines affected by an upstream failure
        and emit alerts.

        Returns a summary dict::

            {"downstream_count": int, "notified_owners": int, "webhook_sent": int}
        """
        downstream = self._resolver.resolve_downstream(upstream_type, upstream_id)
        if not downstream:
            return {"downstream_count": 0, "notified_owners": 0, "webhook_sent": 0}

        # Group by downstream owner (pipeline_type + pipeline_id).
        owner_keys: set[str] = set()
        webhook_sent = 0

        for dep in downstream:
            owner_key = f"{dep.downstream_pipeline_type}:{dep.downstream_pipeline_id}"
            if self._is_deduped(owner_key):
                continue
            owner_keys.add(owner_key)
            self._mark_deduped(owner_key)

            # Emit audit event per downstream.
            try:
                create_audit_event(
                    resource_type="PIPELINE_DEPENDENCY",
                    action="PIPELINE_INCIDENT_DOWNSTREAM_ALERT",
                    actor_user=None,
                    tenant=dep.tenant,
                    resource_id=str(dep.id),
                    details={
                        "upstream_type": upstream_type,
                        "upstream_id": upstream_id,
                        "upstream_run_id": upstream_run_id,
                        "failure_reason": failure_reason[:500],
                        "downstream_type": dep.downstream_pipeline_type,
                        "downstream_id": str(dep.downstream_pipeline_id),
                    },
                )
            except Exception as exc:
                logger.warning(
                    "incident_audit_failed", dep_id=str(dep.id), error=str(exc),
                )

            # Send webhook if configured.
            if dep.alert_webhook_url:
                self._send_webhook(dep, upstream_type, upstream_id,
                                   upstream_run_id, failure_reason)
                webhook_sent += 1

        # Emit batch audit event.
        try:
            create_audit_event(
                resource_type="PIPELINE_DEPENDENCY",
                action="PIPELINE_DEPENDENCY_ALERT_BATCH",
                actor_user=None,
                tenant=downstream[0].tenant if downstream else None,
                resource_id=upstream_id,
                details={
                    "upstream_type": upstream_type,
                    "upstream_id": upstream_id,
                    "upstream_run_id": upstream_run_id,
                    "downstream_count": len(downstream),
                    "notified_owners": len(owner_keys),
                    "webhook_sent": webhook_sent,
                },
            )
        except Exception as exc:
            logger.error("incident_batch_audit_failed", error=str(exc))

        logger.warning(
            "pipeline_incident_propagated",
            upstream_type=upstream_type,
            upstream_id=upstream_id,
            downstream_count=len(downstream),
            notified=len(owner_keys),
        )

        return {
            "downstream_count": len(downstream),
            "notified_owners": len(owner_keys),
            "webhook_sent": webhook_sent,
        }

    # ── Dedup helpers ──────────────────────────────────────────────

    def _dedup_key(self, owner_key: str) -> str:
        return f"incident_dedup:{self.tenant_id}:{owner_key}"

    def _is_deduped(self, owner_key: str) -> bool:
        try:
            return bool(cache.get(self._dedup_key(owner_key)))
        except Exception:
            return False

    def _mark_deduped(self, owner_key: str) -> None:
        try:
            cache.set(self._dedup_key(owner_key), 1, timeout=_DEDUP_TTL_SECONDS)
        except Exception:
            pass

    # ── Webhook ────────────────────────────────────────────────────

    @staticmethod
    def _send_webhook(
        dep, upstream_type, upstream_id, upstream_run_id, failure_reason,
    ) -> None:
        try:
            import hashlib
            import hmac
            import os

            import httpx

            secret = os.environ.get("INTERNAL_PAYLOAD_SECRET", "meshant-internal-default")
            body = json.dumps({
                "event": "PIPELINE_INCIDENT_DOWNSTREAM_ALERT",
                "upstream_type": upstream_type,
                "upstream_id": upstream_id,
                "upstream_run_id": upstream_run_id,
                "failure_reason": failure_reason[:500],
                "downstream_type": dep.downstream_pipeline_type,
                "downstream_id": str(dep.downstream_pipeline_id),
                "recommended_action": (
                    "Investigate upstream failure. "
                    "Downstream pipeline will remain SKIPPED_UPSTREAM_FAILED "
                    "until the upstream is resolved and re-triggered."
                ),
            }).encode("utf-8")
            timestamp = str(int(time.time()))
            canonical = timestamp.encode("utf-8") + b"\n" + body
            signature = hmac.new(
                secret.encode("utf-8"), canonical, hashlib.sha256,
            ).hexdigest()

            with httpx.Client(timeout=10.0) as client:
                client.post(
                    dep.alert_webhook_url,
                    content=body,
                    headers={
                        "Content-Type": "application/json",
                        "X-Meshant-Signature": signature,
                        "X-Meshant-Timestamp": timestamp,
                        "X-Meshant-Event": "PIPELINE_INCIDENT_DOWNSTREAM_ALERT",
                    },
                )
        except Exception as exc:
            logger.warning(
                "incident_webhook_failed", dep_id=str(dep.id), error=str(exc),
            )
