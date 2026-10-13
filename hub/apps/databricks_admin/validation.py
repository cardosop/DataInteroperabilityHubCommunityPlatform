"""P0 (openspec add-databricks-control-plane task 0.4) — workspace host + residency validation.

Three layers, all REUSED from the canonical repo infrastructure (no
re-implementation):

1. **Host-family allowlist** — pure syntactic check that the host is a
   Databricks workspace host (``*.cloud.databricks.com`` plus regional/gov
   variants). Offline-deterministic; runs first because it is the cheapest
   rejection.
2. **SSRF** — the canonical ``SSRFGuard`` (Phase 250.5.B,
   ``hub.apps.security.url_validators``): save-time ``validate()`` (IP-literal
   + stdlib-DNS blocked-network checks) and dispatch-time
   ``revalidate_resolved_ip()`` (dnspython re-resolution — the DNS-rebinding
   guard). Violations are mapped to Django ``ValidationError`` with the
   workspace-registry spec codes.
3. **Residency** — reuses ``validate_warehouse_region``
   (``hub.apps.warehouses.residency_validator``, Phase 277.B.093): the
   workspace region's ISO country must be within the tenant's
   ``data_residency_region`` allowlist.

Dispatch-time re-resolution is the model's ``validate_for_dispatch()``
path (called by the API client before any outbound call, task 0.5+).
"""

from __future__ import annotations

import re

from django.core.exceptions import ValidationError

# Regional/gov Databricks workspace host families (BYO model).
ALLOWED_DATABRICKS_HOST_SUFFIXES: tuple[str, ...] = (
    ".cloud.databricks.com",
    ".azuredatabricks.net",
    ".gcp.databricks.com",
    ".databricks.us",
)

# Matches the hostname BEFORE the family suffix — one or more DNS labels
# (letters/digits/hyphens, no leading/trailing hyphen per label). Splitting
# on the suffix (rather than one big regex) is unambiguous: a greedy label
# group would otherwise swallow the family's own "cloud" label.
_HOSTNAME_PREFIX_RE = re.compile(
    r"[a-z0-9]([a-z0-9-]*[a-z0-9])?"
    r"(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)*"
)


def normalise_host(host: str) -> str:
    """Strip scheme, path, and port; lowercase; trim whitespace.

    ``https://dbc-1.Cloud.Databricks.com:443/api/2.0`` →
    ``dbc-1.cloud.databricks.com``.
    """
    host = host.strip().lower()
    host = re.sub(r"^[a-z][a-z0-9+.-]*://", "", host)
    host = host.split("/", 1)[0]
    if ":" in host and not host.startswith("["):
        host = host.rsplit(":", 1)[0]
    return host


def check_host_family(host: str) -> str:
    """Pure syntactic family check; returns the normalised host.

    The host must END with a Databricks family suffix and carry at least one
    valid DNS label before it — the bare family apex is not a workspace
    host, and suffix-confusion names ("...attacker.com") never match the
    anchored suffix.

    Raises a DICT-FORM ValidationError (``{"host": ...}``) — Django does
    NOT propagate a top-level ``code`` into dict-form field errors (the
    ``validate_workspace_region`` precedent), so the machine-readable code
    lives on the nested field error and survives the serializer/exception
    envelope intact.
    """
    normalised = normalise_host(host)
    for suffix in ALLOWED_DATABRICKS_HOST_SUFFIXES:
        if normalised.endswith(suffix):
            prefix = normalised[: -len(suffix)]
            if _HOSTNAME_PREFIX_RE.fullmatch(prefix):
                return normalised
            break  # family matched but prefix is malformed
    raise ValidationError(
        {
            "host": ValidationError(
                f"Host '{host}' is not a Databricks workspace host. "
                f"Allowed families: {ALLOWED_DATABRICKS_HOST_SUFFIXES}",
                code="DATABRICKS_HOST_NOT_ALLOWED",
            )
        }
    )


def validate_workspace_host(host: str) -> str:
    """Save-time validation: family allowlist + SSRFGuard (incl. DNS).

    Returns the normalised host (persist the normalised form).
    """
    normalised = check_host_family(host)

    from hub.apps.security.url_validators import SSRFGuard, SSRFViolationError

    try:
        SSRFGuard.validate(f"https://{normalised}")
    except SSRFViolationError as exc:
        raise ValidationError(
            {
                "host": ValidationError(
                    str(exc),
                    code="SSRF_PROTECTION_TRIGGERED",
                )
            }
        ) from exc
    return normalised


def revalidate_workspace_host(host: str) -> None:
    """Dispatch-time re-resolution (dnspython) — the DNS-rebinding guard."""
    normalised = check_host_family(host)

    from hub.apps.security.url_validators import SSRFGuard, SSRFViolationError

    try:
        SSRFGuard.revalidate_resolved_ip(normalised)
    except SSRFViolationError as exc:
        raise ValidationError(
            {
                "host": ValidationError(
                    str(exc),
                    code="SSRF_DNS_REBINDING",
                )
            }
        ) from exc


def validate_workspace_region(tenant, region: str) -> None:
    """Residency cross-validation (Phase 277.B.093 reuse).

    Unknown regions and tenants without a residency regime are skipped —
    same semantics as ``WarehouseConnection._validate_residency``.
    """
    if not region:
        return
    residency = getattr(tenant, "data_residency_region", None)
    if not residency:
        return

    from hub.apps.warehouses.residency_validator import validate_warehouse_region

    result = validate_warehouse_region(residency, region)
    if not result.valid:
        message = (
            f"Workspace region '{region}' (ISO {result.warehouse_iso}) "
            f"is not compatible with tenant data residency "
            f"'{residency}'. Allowed ISO codes: "
            f"{sorted(result.allowed_iso)[:10]}..."
        )
        # Inner ValidationError carries the code explicitly — Django does
        # NOT propagate the top-level code into dict-form field errors.
        raise ValidationError(
            {"region": ValidationError(message, code="DATA_RESIDENCY_MISMATCH")},
        )
