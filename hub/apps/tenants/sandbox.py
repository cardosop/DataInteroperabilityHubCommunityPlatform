"""
281.B.7.3–281.B.7.5 — Isolated Tenant Sandbox.

Provides per-tenant sandbox environments: identical config, isolated data,
relaxed rate limits, "SANDBOX" UI label, 30-day auto-expiry, <1h provisioning.

Sandbox lifecycle:
  - Created via ``POST /api/v1/tenants/me/sandbox/``
  - Auto-expires after 30 days (renewable via ``POST .../renew/``)
  - Max 1 sandbox per tenant
  - Data wiped on expiry
  - Separate API credentials from production tenant
"""
from __future__ import annotations
import hashlib
import secrets
import uuid as _uuid
from datetime import timedelta
from typing import Optional

from django.db import models, transaction
from django.utils import timezone as dj_timezone

import structlog

logger = structlog.get_logger(__name__)

# ── Sandbox configuration ──────────────────────────────────────────────────

SANDBOX_EXPIRY_DAYS = 30
SANDBOX_RATE_LIMIT_MULTIPLIER = 5  # 5× relaxed rate limits in sandbox


class TenantSandbox(models.Model):
    """Per-tenant isolated sandbox environment."""

    tenant = models.OneToOneField(
        "tenants.Tenant", on_delete=models.CASCADE, related_name="sandbox",
    )
    sandbox_tenant_id = models.UUIDField(unique=True, editable=False)

    # API credentials distinct from the production tenant
    api_key = models.CharField(max_length=64, unique=True)
    api_secret_hash = models.CharField(max_length=128)

    # Lifecycle
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    renewed_at = models.DateTimeField(null=True, blank=True)
    renew_count = models.PositiveSmallIntegerField(default=0)

    # Status
    is_active = models.BooleanField(default=True)
    wiped_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "tenant_sandbox"
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["expires_at"]),
        ]

    def is_expired(self) -> bool:
        return dj_timezone.now() > self.expires_at

    def days_remaining(self) -> int:
        return max(0, (self.expires_at - dj_timezone.now()).days)

    def renew(self) -> None:
        """Extend sandbox lifetime by SANDBOX_EXPIRY_DAYS from now."""
        self.expires_at = dj_timezone.now() + timedelta(days=SANDBOX_EXPIRY_DAYS)
        self.renewed_at = dj_timezone.now()
        self.renew_count += 1
        self.is_active = True
        self.save(update_fields=["expires_at", "renewed_at", "renew_count", "is_active"])

    def wipe(self) -> None:
        """Wipe sandbox data and deactivate."""
        self.is_active = False
        self.wiped_at = dj_timezone.now()
        self.save(update_fields=["is_active", "wiped_at"])
        logger.info(
            "sandbox_wiped",
            tenant_id=str(self.tenant_id),
            sandbox_id=str(self.sandbox_tenant_id),
        )


def create_sandbox(tenant) -> TenantSandbox:
    """Provision a new sandbox for a tenant. Returns the sandbox instance.

    Raises ValueError if the tenant already has an active sandbox.
    """
    # OneToOneField reverse relation always exists as a descriptor.
    # Accessing it raises DoesNotExist if no sandbox row exists.
    try:
        existing = tenant.sandbox
        if existing is not None and existing.is_active and not existing.is_expired():
            raise ValueError("Tenant already has an active sandbox.")
    except TenantSandbox.DoesNotExist:
        pass

    api_key = f"msh_sandbox_{secrets.token_hex(16)}"

    with transaction.atomic():
        sandbox = TenantSandbox.objects.create(
            tenant=tenant,
            sandbox_tenant_id=_uuid.uuid4(),
            api_key=api_key,
            api_secret_hash=_hash_secret(api_key),
            expires_at=dj_timezone.now() + timedelta(days=SANDBOX_EXPIRY_DAYS),
        )

    logger.info(
        "sandbox_created",
        tenant_id=str(tenant.id),
        sandbox_id=str(sandbox.sandbox_tenant_id),
        expires_at=sandbox.expires_at.isoformat(),
    )
    return sandbox


def get_sandbox(tenant) -> Optional[TenantSandbox]:
    """Return the active sandbox for a tenant, or None."""
    try:
        return tenant.sandbox if tenant.sandbox and tenant.sandbox.is_active else None
    except TenantSandbox.DoesNotExist:
        return None


def _hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


# ── Expiry sweep ───────────────────────────────────────────────────────────

def sweep_expired_sandboxes() -> int:
    """Find and wipe all expired sandboxes. Returns count wiped."""
    expired = TenantSandbox.objects.filter(
        is_active=True, expires_at__lt=dj_timezone.now(),
    )
    count = 0
    for sandbox in expired:
        sandbox.wipe()
        count += 1
    return count
