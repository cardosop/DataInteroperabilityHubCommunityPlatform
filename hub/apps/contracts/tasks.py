"""
Phase 26.15.1 — Async re-normalization task for ODCS v3.1.0 contracts.

Processes contracts in batches with per-contract error isolation,
cache invalidation, and progress events.
"""
import hashlib
import json

import structlog

logger = structlog.get_logger(__name__)

try:
    from hub.apps.observability.otel_metrics import (
        normalization_backfill_remaining,
    )
    _BACKFILL_METRICS = True
except ImportError:
    _BACKFILL_METRICS = False

_INVALIDATION_CHANNEL = "datacontract:invalidate"


def renormalize_contracts_v310(
    tenant_id: str | None = None,
    batch_size: int = 200,
    dry_run: bool = False,
) -> dict:
    """Re-normalize ODCS v3.1.0 contracts.

    Args:
        tenant_id: Restrict to a single tenant (None = all).
        batch_size: Contracts per batch.
        dry_run: Preview only — don't write to DB.

    Returns:
        Summary dict with processed/failed/skipped counts.
    """
    from hub.apps.contracts.models import Contract
    from hub.apps.contracts.normalization import (
        normalize_contract,
    )

    qs = Contract.objects.filter(
        original_spec_type="ODCS",
        original_spec_version="3.1.0",
        normalization_status="NORMALIZED_OK",
    ).order_by("id")

    if tenant_id:
        qs = qs.filter(tenant_id=tenant_id)

    contract_ids = list(qs.values_list("id", flat=True))
    total = len(contract_ids)

    if total == 0:
        return {"total": 0, "processed": 0, "failed": 0}

    # 26.17: Set initial backfill gauge so alerts can track progress
    _set_backfill_remaining(total, tenant_id)

    processed = 0
    failed = 0
    dry_run_warnings: dict = {}

    for offset in range(0, total, batch_size):
        batch_ids = contract_ids[offset:offset + batch_size]
        batch = list(Contract.objects.filter(id__in=batch_ids))

        for contract in batch:
            try:
                result = normalize_contract(
                    contract.original_raw,
                    contract.original_format,
                    spec_type="ODCS",
                )
                hub_json, _, _, status, errors, warnings = result

                if dry_run:
                    dry_run_warnings[str(contract.id)] = (
                        warnings or []
                    )
                    processed += 1
                    continue

                if hub_json and str(status) == "NORMALIZED_OK":
                    contract.hub_contract_json = hub_json
                    contract.normalization_warnings = (
                        warnings or []
                    )
                    contract.save(update_fields=[
                        "hub_contract_json",
                        "normalization_warnings",
                    ])
                    processed += 1

                    # 26.15.4: Cache invalidation
                    _invalidate_contract_cache(contract)
                else:
                    contract.normalization_status = (
                        "NORMALIZATION_FAILED"
                    )
                    existing = contract.normalization_errors or []
                    existing.append({
                        "task": "renormalize_contracts_v310",
                        "errors": errors or [],
                    })
                    contract.normalization_errors = existing
                    contract.save(update_fields=[
                        "normalization_status",
                        "normalization_errors",
                    ])
                    failed += 1

            except Exception as exc:
                logger.warning(
                    "renormalize_contract_failed",
                    contract_id=str(contract.id),
                    error=str(exc),
                )
                if not dry_run:
                    try:
                        contract.normalization_status = (
                            "NORMALIZATION_FAILED"
                        )
                        existing = (
                            contract.normalization_errors or []
                        )
                        existing.append({
                            "task": "renormalize_contracts_v310",
                            "error": str(exc),
                        })
                        contract.normalization_errors = existing
                        contract.save(update_fields=[
                            "normalization_status",
                            "normalization_errors",
                        ])
                    except Exception:
                        pass
                failed += 1

        # Progress event every batch
        remaining = total - processed - failed
        logger.info(
            "normalization.backfill.progress",
            processed=processed,
            failed=failed,
            remaining=remaining,
            total=total,
        )
        # 26.17: Update backfill gauge for HubContractBackfillStalled alert
        _set_backfill_remaining(remaining, tenant_id)

    summary = {
        "total": total,
        "processed": processed,
        "failed": failed,
    }
    if dry_run:
        summary["dry_run_warnings"] = dry_run_warnings

    # 26.17: Reset gauge to 0 on completion so alert clears
    _set_backfill_remaining(0, tenant_id)

    logger.info(
        "renormalize_contracts_v310_complete",
        **summary,
    )
    return summary


# 26.17: Track last-reported backfill remaining for gauge delta
_last_backfill_remaining: int = 0


def _set_backfill_remaining(
    remaining: int,
    tenant_id: str | None = None,
) -> None:
    """Set the normalization_backfill_remaining gauge via delta."""
    global _last_backfill_remaining
    if not _BACKFILL_METRICS:
        return
    delta = remaining - _last_backfill_remaining
    if delta == 0:
        return
    labels: dict[str, str] = {}
    if tenant_id:
        labels["tenant_id"] = str(tenant_id)
    normalization_backfill_remaining.labels(**labels).inc(delta)
    _last_backfill_remaining = remaining


_redis_pub_client = None


def _get_redis_pub_client():
    """Lazy singleton Redis client for pub/sub invalidation."""
    global _redis_pub_client
    if _redis_pub_client is None:
        import os
        import redis as redis_lib
        url = os.getenv(
            "REDIS_CACHE_URL", "redis://localhost:6379/0",
        )
        _redis_pub_client = redis_lib.Redis.from_url(
            url, socket_timeout=2,
        )
    return _redis_pub_client


def _invalidate_contract_cache(contract) -> None:
    """Publish cache invalidation for a re-normalized contract."""
    try:
        from django.core.cache import caches

        # Delete semantic relationship cache
        cache = caches["default"]
        cache.delete(
            f"semantic:relationships:{contract.id}",
        )

        # Publish to invalidation channel
        raw = getattr(contract, "original_raw", "") or ""
        if raw:
            client = _get_redis_pub_client()
            spec_hash = hashlib.sha256(
                raw.encode(),
            ).hexdigest()
            client.publish(
                _INVALIDATION_CHANNEL,
                json.dumps({"spec_hash": spec_hash}),
            )
    except Exception as exc:
        logger.debug(
            "renormalize_cache_invalidation_failed",
            contract_id=str(contract.id),
            error=str(exc),
        )
