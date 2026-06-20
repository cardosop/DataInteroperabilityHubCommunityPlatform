#!/usr/bin/env python
"""
Migration Report Script for DCS Removal

This script identifies all contracts with original_spec_type = 'DATACONTRACT_COM'
and generates a migration report showing affected contracts.

Usage:
    python scripts/migration_report_dcs_removal.py

Output:
    - Console report with contract counts and details
    - JSON report file: migration_report_dcs_removal.json
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

import django

# Setup Django
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hub.settings")
django.setup()

from django.db.models import Count

from hub.apps.contracts.models import Contract


def generate_migration_report():
    """Generate migration report for DCS removal"""

    print("=" * 80)
    print("DCS Removal Migration Report")
    print("=" * 80)
    print(f"Generated: {datetime.now().isoformat()}\n")

    # Find all contracts with DATACONTRACT_COM
    dcs_contracts = Contract.objects.filter(original_spec_type="DATACONTRACT_COM")
    total_count = dcs_contracts.count()

    # Get statistics
    stats = {
        "total_dcs_contracts": total_count,
        "by_tenant": {},
        "by_status": {},
        "by_version": {},
        "contracts": [],
    }

    if total_count > 0:
        print(
            f"[WARNING] Found {total_count} contract(s) with original_spec_type='DATACONTRACT_COM'\n"
        )

        # Group by tenant
        by_tenant = (
            dcs_contracts.values("tenant__name", "tenant__id")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        print("Contracts by Tenant:")
        print("-" * 80)
        for item in by_tenant:
            tenant_name = item["tenant__name"] or "Unknown"
            tenant_id = item["tenant__id"]
            count = item["count"]
            stats["by_tenant"][str(tenant_id)] = {"name": tenant_name, "count": count}
            print(f"  {tenant_name} (ID: {tenant_id}): {count} contract(s)")

        # Group by status
        by_status = dcs_contracts.values("status").annotate(count=Count("id")).order_by("-count")

        print("\nContracts by Status:")
        print("-" * 80)
        for item in by_status:
            status = item["status"]
            count = item["count"]
            stats["by_status"][status] = count
            print(f"  {status}: {count} contract(s)")

        # Group by version
        by_version = (
            dcs_contracts.values("original_spec_version")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        print("\nContracts by Original Spec Version:")
        print("-" * 80)
        for item in by_version:
            version = item["original_spec_version"] or "Unknown"
            count = item["count"]
            stats["by_version"][version] = count
            print(f"  {version}: {count} contract(s)")

        # Get contract details (limit to first 100 for report)
        print("\nContract Details (showing first 100):")
        print("-" * 80)
        contracts_list = dcs_contracts.select_related("tenant", "asset", "created_by")[:100]

        for contract in contracts_list:
            contract_info = {
                "id": str(contract.id),
                "tenant_id": str(contract.tenant.id) if contract.tenant else None,
                "tenant_name": contract.tenant.name if contract.tenant else None,
                "asset_id": str(contract.asset.id) if contract.asset else None,
                "version": contract.version,
                "status": contract.status,
                "original_spec_version": contract.original_spec_version,
                "original_format": contract.original_format,
                "created_at": contract.created_at.isoformat() if contract.created_at else None,
                "created_by": contract.created_by.email if contract.created_by else None,
                "normalization_status": contract.normalization_status,
                "validation_status": contract.validation_status,
            }
            stats["contracts"].append(contract_info)

            print(f"\n  Contract ID: {contract.id}")
            print(f"    Tenant: {contract.tenant.name if contract.tenant else 'N/A'}")
            print(f"    Status: {contract.status}")
            print(f"    Version: {contract.version}")
            print(f"    Original Spec Version: {contract.original_spec_version}")
            print(f"    Created: {contract.created_at}")

        if total_count > 100:
            print(f"\n  ... and {total_count - 100} more contract(s) (not shown in detail)")

        # Migration recommendations
        print("\n" + "=" * 80)
        print("Migration Recommendations:")
        print("=" * 80)
        print("1. Review all affected contracts listed above")
        print("2. Manually convert DCS contracts to ODCS format where possible")
        print("3. Run database migration: python manage.py migrate contracts 0004")
        print("4. The migration will automatically convert DATACONTRACT_COM to ODCS")
        print("5. After migration, review contracts and update to proper ODCS format")
        print("\nFor ODCS migration guidance, see:")
        print("  https://bitol-io.github.io/open-data-contract-standard/v3.0.2/")

    else:
        print("[INFO] No contracts with original_spec_type='DATACONTRACT_COM' found.")
        print("Migration can proceed without data conversion.")

    # Save JSON report
    report_file = project_root / "migration_report_dcs_removal.json"
    with open(report_file, "w") as f:
        json.dump(stats, f, indent=2, default=str)

    print(f"\n[INFO] Detailed report saved to: {report_file}")
    print("=" * 80)

    return stats


if __name__ == "__main__":
    try:
        stats = generate_migration_report()
        sys.exit(0 if stats["total_dcs_contracts"] == 0 else 1)
    except Exception as e:
        print(f"\n[ERROR] Failed to generate migration report: {e!s}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
