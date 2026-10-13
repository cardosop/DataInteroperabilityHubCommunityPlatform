"""Phase 6 (openspec wire-databricks-dlt-movement task 6.4) — the
managed-volume staging default + the S3 external-location opt-in.

dlt stages through the tenant's UC managed volume by default: the
volume name resolves from the tenant's ``databricks_staging_volume_name``
(blank = the auto ``_dlt_staging_load_volume`` — a UC identifier is
required, invalid names are refused fail-closed). The volume is
auto-created ONCE per tenant through the P2 ``UCChangeExecutor`` (the
REST-first uc.volumes.create — the executor's own CREATE idempotency is
the source of truth; the Redis sentinel saves the existence re-check
per run, never per run: a cache miss re-runs the CREATE, a cache
failure never blocks, a failed create never poisons the sentinel).

The S3 external-location path is an explicit per-tenant opt-in
(``databricks_s3_external_location_enabled``, DRAFT default-off in the
feature-flag registry): a requested S3 location with the flag off is
REFUSED (``DatabricksStagingRefused``, fail-closed) — the managed
volume is the only staging surface until the tenant opts in.

Contracts:

- **The caller owns the client** (the 2.2 executor contract) — the
  pinned ``DatabricksApiClient`` is the required keyword; identity
  resolution is the caller's concern.
- **The sentinel is tenant-scoped**: the cache key carries the tenant
  id + the (catalog, schema) target — tenant A's creation never
  suppresses tenant B's.
"""

from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.conf import settings

if TYPE_CHECKING:
    from hub.apps.databricks_admin.client import DatabricksApiClient

logger = logging.getLogger(__name__)

# The auto default (design D2) — applied when the tenant's field is blank.
DEFAULT_STAGING_VOLUME_NAME = "_dlt_staging_load_volume"

# The UC identifier shape (the 2.2 guard's discipline — alphanumeric +
# underscore, never a path or a SQL fragment).
_UC_IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

# The staging specs' kinds.
KIND_MANAGED_VOLUME = "MANAGED_VOLUME"
KIND_EXTERNAL_LOCATION = "EXTERNAL_LOCATION"

# The sentinel prefix (the Phase 273 tenant-scoped key discipline).
_SENTINEL_PREFIX = "databricks_staging_volume_created"


class DatabricksStagingRefused(Exception):
    """A staging request the policy refuses (fail-closed)."""

    code = "DLT_STAGING_REFUSED"


@dataclass
class StagingSpec:
    """The resolved staging target for a movement run."""

    kind: str
    volume_name: str | None
    location: str | None


@dataclass(frozen=True)
class StagingTarget:
    """The UC staging target for a movement run: the managed volume under
    the per-tenant staging schema (task 6.5)."""

    catalog: str
    schema: str
    volume_name: str

    @property
    def qualified(self) -> str:
        return f"{self.catalog}.{self.schema}.{self.volume_name}"


def staging_schema_for(tenant, *, target_schema: str) -> str:
    """The per-tenant staging schema — the tenant's
    ``databricks_staging_schema_name`` override or the destination's
    target schema when blank. BOTH are UC-identifier guarded (an invalid
    identifier is refused fail-closed)."""
    value = (getattr(tenant, "databricks_staging_schema_name", "") or "").strip()
    if value:
        if not _UC_IDENTIFIER_RE.match(value):
            raise DatabricksStagingRefused(
                f"invalid staging schema name {value!r} — a UC identifier is required"
            )
        return value
    if not target_schema or not _UC_IDENTIFIER_RE.match(target_schema):
        raise DatabricksStagingRefused(
            f"invalid target schema {target_schema!r} — a UC identifier is required"
        )
    return target_schema


def resolve_staging_target(tenant, *, destination_config: dict) -> StagingTarget:
    """Resolve the managed-volume staging target from the destination
    config (the ``catalog`` + ``schema`` of the Databricks target) and the
    tenant's staging surfaces (the volume name from 6.4, the schema
    override from 6.5). Refused fail-closed on a missing or non-UC
    identifier."""
    catalog = (destination_config or {}).get("catalog")
    if not catalog or not _UC_IDENTIFIER_RE.match(str(catalog)):
        raise DatabricksStagingRefused(
            f"invalid staging catalog {catalog!r} — a UC identifier is required"
        )
    schema = staging_schema_for(
        tenant, target_schema=str((destination_config or {}).get("schema") or "")
    )
    return StagingTarget(
        catalog=str(catalog),
        schema=schema,
        volume_name=staging_volume_name_for(tenant),
    )


def staging_volume_name_for(tenant) -> str:
    """The tenant's managed staging volume name — the tenant override
    (a UC identifier, refused fail-closed otherwise) or the auto
    ``_dlt_staging_load_volume`` default when blank."""
    value = (getattr(tenant, "databricks_staging_volume_name", "") or "").strip()
    if not value:
        return DEFAULT_STAGING_VOLUME_NAME
    if not _UC_IDENTIFIER_RE.match(value):
        raise DatabricksStagingRefused(
            f"invalid staging volume name {value!r} — a UC identifier is required"
        )
    return value


def s3_external_location_enabled(tenant) -> bool:
    """The per-tenant S3 external-location opt-in (off by default)."""
    return bool(getattr(tenant, "databricks_s3_external_location_enabled", False))


def resolve_staging(tenant, *, requested_location: str | None = None) -> StagingSpec:
    """Resolve the staging target: no request → the managed volume
    (the default); a requested S3 location → honored ONLY under the
    tenant's opt-in (refused fail-closed otherwise); a non-S3 location
    is refused regardless (the opt-in is S3-specific)."""
    if requested_location:
        if not isinstance(requested_location, str) or not requested_location.strip():
            raise DatabricksStagingRefused(
                "a requested staging location must be a non-empty string"
            )
        location = requested_location.strip()
        if not location.startswith("s3://"):
            raise DatabricksStagingRefused(
                f"staging location {location!r} is not an S3 external location — "
                "the opt-in path is S3-specific"
            )
        if not s3_external_location_enabled(tenant):
            raise DatabricksStagingRefused(
                "the S3 external-location path is opt-in per tenant "
                "(databricks_s3_external_location_enabled) — refused fail-closed"
            )
        return StagingSpec(
            kind=KIND_EXTERNAL_LOCATION, volume_name=None, location=location
        )
    return StagingSpec(
        kind=KIND_MANAGED_VOLUME,
        volume_name=staging_volume_name_for(tenant),
        location=None,
    )


def ensure_staging_volume(
    *,
    tenant,
    catalog: str,
    schema: str,
    client: DatabricksApiClient,
    statement_executor=None,
    warehouse_id: str | None = None,
    cache=None,
) -> str:
    """Create the tenant's managed staging volume ONCE through the P2
    executor (uc.volumes.create, REST-first) and return the volume name.

    The create rides the provider-boundary provisioner seam (W4.6):
    the executor construction lives in databricks_admin (registered at
    app-ready); the caller still OWNS the client (the 2.2 executor
    contract). An unregistered seam refuses with
    ``DatabricksStagingRefused`` — never an ImportError.

    The Redis sentinel skips the create on subsequent runs within the
    TTL; a cache miss re-runs the CREATE (idempotent by the executor's
    contract); a cache failure never blocks; a failed create propagates
    and never poisons the sentinel.
    """
    volume = staging_volume_name_for(tenant)
    target = f"{catalog}.{schema}"
    sentinel_key = _sentinel_key(tenant.id, target)

    provisioner = get_staging_volume_provisioner()
    if provisioner is None:
        raise DatabricksStagingRefused(
            "no staging-volume provisioner registered — the provider "
            "estate app is not installed or its ready() registration is "
            "missing"
        )

    cache_client = cache or _default_cache()
    if _cache_get(cache_client, sentinel_key):
        return volume

    provisioner(
        client,
        tenant=tenant,
        catalog=catalog,
        schema=schema,
        volume=volume,
        statement_executor=statement_executor,
        warehouse_id=warehouse_id,
    )

    ttl = settings.DLT_STAGING_VOLUME_CACHE_TTL_SECONDS
    _cache_set(cache_client, sentinel_key, "created", ttl_seconds=ttl)
    return volume


def _sentinel_key(tenant_id, target: str) -> str:
    # The Phase 273 discipline — the key carries the tenant id so one
    # tenant's sentinel can never collide with another's.
    import hashlib

    digest = hashlib.sha256(target.encode()).hexdigest()[:16]
    return f"{_SENTINEL_PREFIX}_{tenant_id}_{digest}"


def _default_cache():
    import redis

    from hub.apps.core.redis_pools import get_redis_cache_pool

    return redis.Redis(connection_pool=get_redis_cache_pool())


def _cache_get(cache_client, key: str) -> bool:
    try:
        return bool(cache_client.get(key))
    except Exception:
        logger.warning("dlt_staging_sentinel_read_failed", extra={"key": key})
        return False


def _cache_set(cache_client, key: str, value: str, *, ttl_seconds: int) -> None:
    try:
        cache_client.setex(key, ttl_seconds, value)
    except Exception:
        logger.warning("dlt_staging_sentinel_write_failed", extra={"key": key})


# ── Staging-volume provisioner seam (W4.6 provider-boundary inversion) ──────
# The executor construction (UCChangeExecutor + UCDdlPayload) is provider
# estate code — it lives in hub.apps.databricks_admin.staging_provisioner
# and registers HERE at app-ready (the 7.5 cost-recording convention).
# This module is the provider-agnostic consumer side only: a future
# provider estate registers its own provisioner the same way.

_StagingVolumeProvisioner = object  # duck-typed callable, see register()

#: A one-slot registry (list-held so the slot mutates without
#: ``global``).
_registered_provisioner: list = []
_registry_lock = threading.Lock()


def register_staging_volume_provisioner(provisioner) -> None:
    """Register the provider's real staging-volume provisioner.

    Keyword contract: ``(client, *, tenant, catalog, schema, volume,
    statement_executor=None, warehouse_id=None) -> None`` — it owns the
    executor construction and the CREATE wire call. Idempotent —
    ``ready()`` may run more than once per process.
    """
    with _registry_lock:
        _registered_provisioner[:] = [provisioner]


def get_staging_volume_provisioner():
    """The registered provisioner, or None when no provider registered
    one (``ensure_staging_volume`` then refuses classified)."""
    with _registry_lock:
        return _registered_provisioner[0] if _registered_provisioner else None
