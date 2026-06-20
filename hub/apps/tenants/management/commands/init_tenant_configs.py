"""
Management command to initialize default TenantConfig for existing tenants.

Creates TenantConfig with platform defaults for all tenants that don't have one.
"""

import structlog
from django.core.management.base import BaseCommand
from django.db import transaction

from hub.apps.tenants.models import Tenant, TenantConfig
from hub.apps.tenants.validators import get_platform_defaults

logger = structlog.get_logger(__name__)


class Command(BaseCommand):
    help = "Initialize TenantConfig with platform defaults for existing tenants"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be created without actually creating TenantConfig records",
        )
        parser.add_argument(
            "--tenant-id",
            type=str,
            help="Initialize config for specific tenant ID only",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        tenant_id = options.get("tenant_id")

        platform_defaults = get_platform_defaults()

        # Find tenants without TenantConfig
        if tenant_id:
            try:
                tenants = Tenant.objects.filter(id=tenant_id)
                if not tenants.exists():
                    self.stdout.write(self.style.ERROR(f"Tenant with ID {tenant_id} not found."))
                    return
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Invalid tenant ID: {e}"))
                return
        else:
            # Find all tenants without TenantConfig
            tenants_with_config = TenantConfig.objects.values_list("tenant_id", flat=True)
            tenants = Tenant.objects.exclude(id__in=tenants_with_config)

        count = tenants.count()

        if count == 0:
            self.stdout.write(
                self.style.SUCCESS("All tenants already have TenantConfig. Nothing to do.")
            )
            return

        self.stdout.write(f"Found {count} tenant(s) without TenantConfig.")

        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN - No TenantConfig records will be created.")
            )
            for tenant in tenants[:10]:  # Show first 10
                self.stdout.write(
                    f"  - Tenant {tenant.id} ({tenant.name}) - would create TenantConfig with platform defaults"
                )
            if count > 10:
                self.stdout.write(f"  ... and {count - 10} more")
            return

        # Create TenantConfig for each tenant
        created_count = 0
        skipped_count = 0
        error_count = 0

        for tenant in tenants:
            try:
                # Check if config already exists (race condition protection)
                if TenantConfig.objects.filter(tenant=tenant).exists():
                    skipped_count += 1
                    self.stdout.write(
                        f"  - Tenant {tenant.id} ({tenant.name}) - TenantConfig already exists, skipping"
                    )
                    continue

                # Create TenantConfig with platform defaults
                with transaction.atomic():
                    TenantConfig.objects.create(
                        tenant=tenant,
                        default_dq_profile=platform_defaults.get("default_dq_profile"),
                        allowed_compliance_regimes=platform_defaults.get(
                            "allowed_compliance_regimes", []
                        ),
                        default_compliance_regimes=platform_defaults.get(
                            "default_compliance_regimes", []
                        ),
                        data_retention_days=platform_defaults.get("data_retention_days"),
                        rate_limits=platform_defaults.get("rate_limits", {}),
                        max_file_size_bytes=platform_defaults.get("max_file_size_bytes"),
                        max_job_concurrency=platform_defaults.get("max_job_concurrency"),
                        max_queued_jobs=platform_defaults.get("max_queued_jobs"),
                    )

                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  ✓ Created TenantConfig for tenant {tenant.id} ({tenant.name})"
                    )
                )

                logger.info(
                    "tenant_config_initialized",
                    tenant_id=str(tenant.id),
                    tenant_name=tenant.name,
                    message=f"Initialized TenantConfig for tenant {tenant.id}",
                )

            except Exception as e:
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(
                        f"  ✗ Error creating TenantConfig for tenant {tenant.id} ({tenant.name}): {e}"
                    )
                )
                # Per-tenant failures are logged at WARNING — the command
                # handles them gracefully by continuing to the next tenant
                # and the error is already reported to stdout.  ERROR is
                # reserved for systemic failures that require operator
                # intervention (e.g. the entire command cannot proceed).
                logger.warning(
                    "tenant_config_init_failed",
                    tenant_id=str(tenant.id),
                    tenant_name=tenant.name,
                    error=str(e),
                    message=f"Failed to initialize TenantConfig for tenant {tenant.id}",
                )

        # Summary
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(self.style.SUCCESS("Summary:"))
        self.stdout.write(f"  - Created: {created_count} TenantConfig record(s)")
        if skipped_count > 0:
            self.stdout.write(f"  - Skipped: {skipped_count} tenant(s) (already have config)")
        if error_count > 0:
            self.stdout.write(self.style.ERROR(f"  - Errors: {error_count} tenant(s)"))
        self.stdout.write(self.style.SUCCESS("=" * 60))
