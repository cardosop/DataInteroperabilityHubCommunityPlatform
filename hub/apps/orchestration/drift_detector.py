"""
285.11.5.1 + 285.11.5.2 — ContractDriftDetector.

Hooks into Contract post_save (via lineage_sync signal path).
When a contract's schema changes, diffs old vs new fields, classifies
changes as BREAKING or WARNING, finds downstream pipeline dependencies
via the resolver, and emits CONTRACT_DRIFT_DETECTED audit events +
batched webhook alerts.
"""
from __future__ import annotations
import json
import logging
from typing import Any, Dict, List

from django.db.models import Q

from hub.apps.audit.utils import create_audit_event

from .dependency_resolver import PipelineDependencyResolver

logger = logging.getLogger(__name__)

# ── Drift classification ────────────────────────────────────────────────


class DriftSeverity:
    BREAKING = "BREAKING"
    WARNING = "WARNING"


# Field-level change types that constitute breaking changes.
_BREAKING_CHANGE_TYPES: frozenset[str] = frozenset({
    "field_removed",
    "type_changed_incompatible",
    "not_null_added",
})

_WARNING_CHANGE_TYPES: frozenset[str] = frozenset({
    "field_added",
    "constraint_removed",
    "type_widened",
})

# Compatible type widening — old_type → new_type is safe.
_COMPATIBLE_WIDENING: set[Tuple[str, str]] = {
    ("int", "bigint"), ("int", "float"), ("float", "double"),
    ("varchar", "text"), ("string", "text"),
}


class ContractDriftDetector:
    """Detect and propagate contract schema drift to downstream pipelines."""

    def __init__(self, tenant_id: str):
        self.tenant_id = str(tenant_id)
        self._resolver = PipelineDependencyResolver(self.tenant_id)

    def detect(
        self,
        contract,
        new_schema: List[Dict[str, Any]] | None = None,
    ) -> Dict[str, Any]:
        """Compare the contract's current schema against the previous version.

        If *new_schema* is omitted, extracts it from
        ``contract.hub_contract_json`` automatically.

        Returns a drift report::

            {
                "contract_id": str,
                "version": {"old": int, "new": int},
                "changes": [{"field": str, "change": str, "severity": str, "detail": str}, ...],
                "breaking_count": int,
                "warning_count": int,
            }
        """
        from hub.apps.contracts.models import Contract

        if new_schema is None:
            new_schema = self._extract_schema(contract)

        old_version = contract.version
        # Find the previous version for this asset.
        previous = (
            Contract.objects
            .filter(
                tenant_id=self.tenant_id,
                asset_id=contract.asset_id,
                version__lt=old_version,
            )
            .order_by("-version")
            .only("hub_contract_json", "version")
            .first()
        )

        old_schema = self._extract_schema(previous) if previous else []
        changes = self._diff_schemas(old_schema, new_schema)

        breaking = sum(1 for c in changes if c["severity"] == DriftSeverity.BREAKING)
        warnings = sum(1 for c in changes if c["severity"] == DriftSeverity.WARNING)

        return {
            "contract_id": str(contract.id),
            "version": {
                "old": previous.version if previous else None,
                "new": old_version,
            },
            "changes": changes,
            "breaking_count": breaking,
            "warning_count": warnings,
        }

    def alert_downstream(
        self,
        contract,
        drift_report: Dict[str, Any],
    ) -> int:
        """Find downstream pipelines of this contract's asset and
        emit CONTRACT_DRIFT_DETECTED audit events + webhook alerts.

        Returns the number of downstream pipelines alerted.
        """
        asset_id = str(contract.asset_id) if contract.asset_id else None
        if not asset_id:
            return 0

        # Find pipeline dependencies linked to this asset.
        from .models import PipelineDependency

        deps = PipelineDependency.objects.filter(
            tenant_id=self.tenant_id,
            is_active=True,
        ).filter(
            Q(pipeline_id=asset_id) | Q(downstream_pipeline_id=asset_id),
        )

        count = 0
        for dep in deps:
            try:
                self._emit_drift_alert(dep, contract, drift_report)
                count += 1
            except Exception as exc:
                logger.warning(
                    "drift_alert_emit_failed",
                    dep_id=str(dep.id),
                    contract_id=str(contract.id),
                    error=str(exc),
                )

        # Emit batch audit event.
        try:
            create_audit_event(
                resource_type="PIPELINE_DEPENDENCY",
                action="CONTRACT_DRIFT_DETECTED",
                actor_user=None,
                tenant=contract.tenant,
                resource_id=str(contract.id),
                details={
                    "contract_id": str(contract.id),
                    "asset_id": asset_id,
                    "breaking_count": drift_report["breaking_count"],
                    "warning_count": drift_report["warning_count"],
                    "downstream_alerted": count,
                },
            )
        except Exception as exc:
            logger.error("drift_audit_failed", error=str(exc))

        return count

    # ── Internal helpers ────────────────────────────────────────────

    @staticmethod
    def _extract_schema(contract) -> List[Dict[str, Any]]:
        """Extract field definitions from hub_contract_json."""
        hc = contract.hub_contract_json or {}
        models = hc.get("models", [])
        if not models:
            return []
        fields = []
        for model in models:
            for field in (model.get("fields") or []):
                fields.append({
                    "name": field.get("name", ""),
                    "type": field.get("type", field.get("data_type", "")),
                    "nullable": field.get("nullable", True),
                })
        return fields

    @staticmethod
    def _diff_schemas(
        old: List[Dict], new: List[Dict],
    ) -> List[Dict[str, Any]]:
        """Diff two field lists and classify changes."""
        old_by_name = {f["name"]: f for f in old}
        new_by_name = {f["name"]: f for f in new}
        changes: List[Dict[str, Any]] = []

        # Detect removals and type changes.
        for name, old_field in old_by_name.items():
            if name not in new_by_name:
                changes.append({
                    "field": name, "change": "field_removed",
                    "severity": DriftSeverity.BREAKING,
                    "detail": f"Field '{name}' was removed",
                })
                continue

            new_field = new_by_name[name]
            old_type = (old_field.get("type") or "").lower()
            new_type = (new_field.get("type") or "").lower()

            if old_type != new_type:
                if (old_type, new_type) in _COMPATIBLE_WIDENING:
                    changes.append({
                        "field": name, "change": "type_widened",
                        "severity": DriftSeverity.WARNING,
                        "detail": f"Type widened: {old_type} → {new_type}",
                    })
                else:
                    changes.append({
                        "field": name, "change": "type_changed_incompatible",
                        "severity": DriftSeverity.BREAKING,
                        "detail": f"Incompatible type change: {old_type} → {new_type}",
                    })

            # Detect not_null_added.
            if not old_field.get("nullable", True) and new_field.get("nullable", True) is False:
                pass  # already not-null
            elif old_field.get("nullable", True) and not new_field.get("nullable", True):
                changes.append({
                    "field": name, "change": "not_null_added",
                    "severity": DriftSeverity.BREAKING,
                    "detail": f"NOT NULL constraint added to '{name}'",
                })

        # Detect additions.
        for name in new_by_name:
            if name not in old_by_name:
                changes.append({
                    "field": name, "change": "field_added",
                    "severity": DriftSeverity.WARNING,
                    "detail": f"Field '{name}' was added",
                })

        return changes

    def _emit_drift_alert(
        self, dep, contract, drift_report: Dict[str, Any],
    ) -> None:
        """Emit an alert for a single downstream dependency."""
        # Audit event per downstream.
        create_audit_event(
            resource_type="PIPELINE_DEPENDENCY",
            action="CONTRACT_DRIFT_DETECTED",
            actor_user=None,
            tenant=contract.tenant,
            resource_id=str(dep.id),
            details={
                "dependency_id": str(dep.id),
                "contract_id": str(contract.id),
                "downstream_type": dep.downstream_pipeline_type,
                "downstream_id": str(dep.downstream_pipeline_id),
                "breaking_count": drift_report["breaking_count"],
                "changes": drift_report["changes"][:20],
            },
        )

        # Batch webhook POST if alert_webhook_url is configured.
        if dep.alert_webhook_url:
            self._post_webhook_alert(dep, drift_report)

    @staticmethod
    def _post_webhook_alert(dep, drift_report: Dict[str, Any]) -> None:
        """POST a drift alert to the configured webhook URL (best-effort)."""
        try:
            import hmac
            import hashlib
            import time

            import httpx

            body = json.dumps({
                "event": "CONTRACT_DRIFT_DETECTED",
                "dependency_id": str(dep.id),
                "downstream_type": dep.downstream_pipeline_type,
                "downstream_id": str(dep.downstream_pipeline_id),
                "breaking_count": drift_report["breaking_count"],
                "changes": drift_report["changes"][:10],
            }).encode("utf-8")
            timestamp = str(int(time.time()))
            # HMAC signature using INTERNAL_PAYLOAD_SECRET.
            secret = _get_internal_secret()
            signature = hmac.new(
                secret.encode("utf-8"),
                timestamp.encode("utf-8") + b"\n" + body,
                hashlib.sha256,
            ).hexdigest()

            with httpx.Client(timeout=10.0) as client:
                client.post(
                    dep.alert_webhook_url,
                    content=body,
                    headers={
                        "Content-Type": "application/json",
                        "X-Meshant-Signature": signature,
                        "X-Meshant-Timestamp": timestamp,
                        "X-Meshant-Event": "CONTRACT_DRIFT_DETECTED",
                    },
                )
        except Exception as exc:
            logger.warning(
                "drift_webhook_post_failed",
                dep_id=str(dep.id),
                error=str(exc),
            )


def _get_internal_secret() -> str:
    """Return the internal payload signing secret."""
    import os
    return os.environ.get(
        "INTERNAL_PAYLOAD_SECRET",
        "meshant-internal-default",
    )
