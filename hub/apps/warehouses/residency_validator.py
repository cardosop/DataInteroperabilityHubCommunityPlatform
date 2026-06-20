"""
Phase 277.B.093 — data residency cross-validation.

Ensures ``WarehouseConnection.region`` is compatible with the owning
tenant's ``data_residency_region``.  A mismatch is rejected with
``ValidationError(code=DATA_RESIDENCY_MISMATCH)``.

Also provides an audit helper for flagging existing mismatches in the
admin dashboard or management commands.
"""

from __future__ import annotations

from typing import NamedTuple

# ── Region mappings ────────────────────────────────────────────────

#: Map a cloud region to its ISO 3166-1 alpha-2 country code.
#: Regions NOT listed here are treated as "unknown" → validation skipped.
_REGION_TO_ISO: dict[str, str] = {
    # AWS
    "us-east-1": "US",
    "us-east-2": "US",
    "us-west-1": "US",
    "us-west-2": "US",
    "eu-west-1": "IE",
    "eu-west-2": "GB",
    "eu-west-3": "FR",
    "eu-central-1": "DE",
    "eu-central-2": "CH",
    "eu-north-1": "SE",
    "eu-south-1": "IT",
    "eu-south-2": "ES",
    "ap-southeast-1": "SG",
    "ap-southeast-2": "AU",
    "ap-southeast-3": "MY",
    "ap-southeast-4": "AU",
    "ap-south-1": "IN",
    "ap-south-2": "IN",
    "ap-northeast-1": "JP",
    "ap-northeast-2": "KR",
    "ap-northeast-3": "JP",
    "ca-central-1": "CA",
    "ca-west-1": "CA",
    "sa-east-1": "BR",
    "af-south-1": "ZA",
    "me-south-1": "BH",
    "me-central-1": "AE",
    "il-central-1": "IL",
    # GCP
    "us-central1": "US",
    "us-east1": "US",
    "us-east4": "US",
    "us-west1": "US",
    "us-west2": "US",
    "us-west3": "US",
    "us-west4": "US",
    "europe-west1": "BE",
    "europe-west2": "GB",
    "europe-west3": "DE",
    "europe-west4": "NL",
    "europe-west6": "CH",
    "europe-west8": "IT",
    "europe-west9": "FR",
    "europe-west10": "DE",
    "europe-west12": "IT",
    "europe-north1": "FI",
    "europe-central2": "PL",
    "europe-southwest1": "ES",
    "asia-southeast1": "SG",
    "asia-southeast2": "ID",
    "asia-east1": "TW",
    "asia-east2": "HK",
    "asia-south1": "IN",
    "asia-south2": "IN",
    "asia-northeast1": "JP",
    "asia-northeast2": "JP",
    "asia-northeast3": "KR",
    "australia-southeast1": "AU",
    "australia-southeast2": "AU",
    "northamerica-northeast1": "CA",
    "northamerica-northeast2": "CA",
    "southamerica-east1": "BR",
    "southamerica-west1": "CL",
    # Azure
    "eastus": "US",
    "eastus2": "US",
    "westus": "US",
    "westus2": "US",
    "centralus": "US",
    "northcentralus": "US",
    "southcentralus": "US",
    "westeurope": "NL",
    "northeurope": "IE",
    "uksouth": "GB",
    "ukwest": "GB",
    "francecentral": "FR",
    "francesouth": "FR",
    "germanywestcentral": "DE",
    "germanynorth": "DE",
    "switzerlandnorth": "CH",
    "switzerlandwest": "CH",
    "norwayeast": "NO",
    "norwaywest": "NO",
    "swedencentral": "SE",
    "italynorth": "IT",
    "canadacentral": "CA",
    "canadaeast": "CA",
    "australiaeast": "AU",
    "australiasoutheast": "AU",
    "australiacentral": "AU",
    "southeastasia": "SG",
    "eastasia": "HK",
    "japaneast": "JP",
    "japanwest": "JP",
    "koreacentral": "KR",
    "koreasouth": "KR",
    "southindia": "IN",
    "centralindia": "IN",
    "westindia": "IN",
    "uaenorth": "AE",
    "uaecentral": "AE",
    "southafricanorth": "ZA",
    "southafricawest": "ZA",
    "brazilsouth": "BR",
    "brazilsoutheast": "BR",
    "israelcentral": "IL",
    "qatarcentral": "QA",
}

#: Map tenant residency regions (ISO codes) to allowed ISO country values.
_TENANT_REGION_ALLOWLIST: dict[str, set[str]] = {
    # EU tenant — data must stay within EU/EEA
    "eu-west-1": {
        "IE",
        "GB",
        "FR",
        "DE",
        "CH",
        "SE",
        "IT",
        "ES",
        "NL",
        "FI",
        "PL",
        "BE",
        "NO",
        "PT",
        "AT",
        "DK",
        "GR",
        "CZ",
        "RO",
        "HU",
        "SK",
        "BG",
        "HR",
        "SI",
        "LT",
        "LV",
        "EE",
        "IS",
        "LI",
        "LU",
        "MT",
        "CY",
    },
    "eu": {
        "IE",
        "GB",
        "FR",
        "DE",
        "CH",
        "SE",
        "IT",
        "ES",
        "NL",
        "FI",
        "PL",
        "BE",
        "NO",
        "PT",
        "AT",
        "DK",
        "GR",
        "CZ",
        "RO",
        "HU",
        "SK",
        "BG",
        "HR",
        "SI",
        "LT",
        "LV",
        "EE",
        "IS",
        "LI",
        "LU",
        "MT",
        "CY",
    },
    # US tenant — data must stay within US
    "us-east-1": {"US"},
    "us": {"US"},
    # UK tenant — data within UK
    "uk": {"GB"},
    # Canada
    "ca": {"CA"},
    # Australia
    "au": {"AU"},
    # Japan
    "jp": {"JP"},
    # Switzerland
    "ch": {"CH"},
    # India
    "in": {"IN"},
    # Brazil
    "br": {"BR"},
}


class ResidencyValidationResult(NamedTuple):
    valid: bool
    tenant_region: str | None
    warehouse_region: str
    warehouse_iso: str | None
    allowed_iso: set[str]


def validate_warehouse_region(
    tenant_data_residency_region: str | None,
    warehouse_region: str,
) -> ResidencyValidationResult:
    """Check that a warehouse region is compatible with the tenant's residency.

    Returns a ``ResidencyValidationResult``.  Callers should raise
    ``ValidationError`` with ``code="DATA_RESIDENCY_MISMATCH"`` when
    ``valid`` is False.

    Args:
        tenant_data_residency_region: Tenant's configured data residency
            region (ISO region code like ``eu-west-1`` or country like ``EU``).
        warehouse_region: Cloud region of the warehouse connection
            (e.g. ``us-east-1``, ``europe-west1``).

    Returns:
        ResidencyValidationResult
    """
    # No tenant residency rule → always allowed
    if not tenant_data_residency_region:
        return ResidencyValidationResult(
            valid=True,
            tenant_region=None,
            warehouse_region=warehouse_region,
            warehouse_iso=None,
            allowed_iso=set(),
        )

    # Empty warehouse region → can't validate, allow (best-effort)
    if not warehouse_region or not warehouse_region.strip():
        return ResidencyValidationResult(
            valid=True,
            tenant_region=tenant_data_residency_region,
            warehouse_region=warehouse_region or "",
            warehouse_iso=None,
            allowed_iso=set(),
        )

    tenant_key = tenant_data_residency_region.strip().lower()
    wh_key = warehouse_region.strip().lower()

    # Get allowed ISO codes for the tenant's residency region
    allowed_iso = _TENANT_REGION_ALLOWLIST.get(tenant_key)
    if allowed_iso is None:
        # Unknown tenant region → allow (no mapping to enforce)
        return ResidencyValidationResult(
            valid=True,
            tenant_region=tenant_data_residency_region,
            warehouse_region=warehouse_region,
            warehouse_iso=None,
            allowed_iso=set(),
        )

    # Resolve warehouse region to ISO code
    warehouse_iso = _REGION_TO_ISO.get(wh_key)

    if warehouse_iso is None:
        # Unknown warehouse region → allow (can't validate)
        return ResidencyValidationResult(
            valid=True,
            tenant_region=tenant_data_residency_region,
            warehouse_region=warehouse_region,
            warehouse_iso=None,
            allowed_iso=allowed_iso,
        )

    valid = warehouse_iso in allowed_iso

    return ResidencyValidationResult(
        valid=valid,
        tenant_region=tenant_data_residency_region,
        warehouse_region=warehouse_region,
        warehouse_iso=warehouse_iso,
        allowed_iso=allowed_iso,
    )


def find_residency_mismatches() -> list[dict]:
    """Audit all active WarehouseConnections for residency mismatches.

    Returns a list of ``{tenant_id, warehouse_id, tenant_region,
    warehouse_region, warehouse_iso}`` dicts for dashboard/admin use.
    """
    from hub.apps.warehouses.models import WarehouseConnection

    mismatches: list[dict] = []
    for conn in (
        WarehouseConnection.objects.select_related("tenant")
        .filter(
            is_active=True,
        )
        .exclude(region="")
    ):
        tenant = conn.tenant
        residency = getattr(tenant, "data_residency_region", None)
        if not residency:
            continue
        result = validate_warehouse_region(residency, conn.region)
        if not result.valid:
            mismatches.append(
                {
                    "tenant_id": str(tenant.id),
                    "tenant_name": getattr(tenant, "name", ""),
                    "warehouse_id": str(conn.id),
                    "warehouse_name": conn.name,
                    "tenant_region": result.tenant_region,
                    "warehouse_region": result.warehouse_region,
                    "warehouse_iso": result.warehouse_iso,
                }
            )
    return mismatches
