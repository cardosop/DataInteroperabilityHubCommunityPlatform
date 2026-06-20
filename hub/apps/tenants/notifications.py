"""
Phase 285.13.9 — Plan lifecycle notification helpers.

Each function sends a notification (email / in-app / audit) for a
specific plan-related event.  Stub implementations — full notification
delivery will be wired when the notification service is integrated.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def notify_upgrade_confirmation(
    tenant_id, old_plan_slug: str = "", new_plan_slug: str = "", new_plan_tier: str = ""
) -> None:
    """Notify tenant admins of a successful plan upgrade."""
    logger.info(
        "notify_upgrade_confirmation: tenant=%s old=%s new=%s tier=%s",
        tenant_id,
        old_plan_slug,
        new_plan_slug,
        new_plan_tier,
    )


def notify_downgrade_confirmation(
    tenant_id, old_plan_slug: str = "", new_plan_slug: str = ""
) -> None:
    """Notify tenant admins of a successful plan downgrade."""
    logger.info(
        "notify_downgrade_confirmation: tenant=%s old=%s new=%s",
        tenant_id,
        old_plan_slug,
        new_plan_slug,
    )


def notify_price_change(
    tenant_id, plan_name: str = "", old_price: int = 0, new_price: int = 0
) -> None:
    """Notify tenant admins of an upcoming price change."""
    logger.info(
        "notify_price_change: tenant=%s plan=%s old=%d new=%d",
        tenant_id,
        plan_name,
        old_price,
        new_price,
    )


def notify_limit_warning(tenant_id: str, limit_key: str, usage_pct: float) -> None:
    """Notify tenant admins when usage approaches a plan limit (>= 80%)."""
    logger.info(
        "notify_limit_warning: tenant=%s key=%s pct=%.1f",
        tenant_id,
        limit_key,
        usage_pct,
    )


def notify_limit_critical(tenant_id: str, limit_key: str, usage_pct: float) -> None:
    """Notify tenant admins when usage is critically close to a limit (>= 95%)."""
    logger.info(
        "notify_limit_critical: tenant=%s key=%s pct=%.1f",
        tenant_id,
        limit_key,
        usage_pct,
    )


def notify_limit_exceeded(tenant_id: str, limit_key: str) -> None:
    """Notify tenant admins that a plan limit has been exceeded."""
    logger.info(
        "notify_limit_exceeded: tenant=%s key=%s",
        tenant_id,
        limit_key,
    )


def notify_payment_failure(tenant_id, amount_cents: int = 0, reason: str = "") -> None:
    """Notify tenant admins of a payment failure."""
    logger.info(
        "notify_payment_failure: tenant=%s amount=%d reason=%s",
        tenant_id,
        amount_cents,
        reason,
    )


def notify_enterprise_backfill(tenant_id, plan_name: str = "", affected_count: int = 0) -> None:
    """Notify tenant admins that enterprise backfill has completed."""
    logger.info(
        "notify_enterprise_backfill: tenant=%s plan=%s count=%d",
        tenant_id,
        plan_name,
        affected_count,
    )
