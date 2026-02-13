"""
Management command to seed default tenant plans (FREE, PRO, ENTERPRISE).

Creates default plans with standard limits if they don't already exist.
"""

import structlog
from django.core.management.base import BaseCommand
from django.db import transaction

from hub.apps.tenants.models import PlanTier, TenantPlan

logger = structlog.get_logger(__name__)


class Command(BaseCommand):
    help = "Seed default tenant plans (FREE, PRO, ENTERPRISE) with standard limits"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be created without actually creating plan records",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        # Default plans configuration
        default_plans = [
            {
                "name": "Free Plan",
                "slug": "free",
                "tier": PlanTier.FREE,
                "limits_json": {
                    "max_assets": 10,
                    "max_datasets": 20,
                    "max_api_calls_per_month": 10000,
                    "max_scheduled_ingestions": 5,
                    "max_scheduled_runs_per_month": 50,
                    "max_scheduled_exports": 5,
                    "max_export_runs_per_month": 20,
                    "max_storage_gb": 1,
                },
            },
            {
                "name": "Pro Plan",
                "slug": "pro",
                "tier": PlanTier.PRO,
                "limits_json": {
                    "max_assets": 100,
                    "max_datasets": 500,
                    "max_api_calls_per_month": 100000,
                    "max_scheduled_ingestions": 50,
                    "max_scheduled_runs_per_month": 1000,
                    "max_scheduled_exports": 50,
                    "max_export_runs_per_month": 500,
                    "max_storage_gb": 100,
                },
            },
            {
                "name": "Enterprise Plan",
                "slug": "enterprise",
                "tier": PlanTier.ENTERPRISE,
                "limits_json": {
                    "max_assets": None,  # Unlimited
                    "max_datasets": None,  # Unlimited
                    "max_api_calls_per_month": None,  # Unlimited
                    "max_scheduled_ingestions": None,  # Unlimited
                    "max_scheduled_runs_per_month": None,  # Unlimited
                    "max_scheduled_exports": None,  # Unlimited
                    "max_export_runs_per_month": None,  # Unlimited
                    "max_storage_gb": None,  # Unlimited
                },
            },
        ]

        created_count = 0
        skipped_count = 0
        error_count = 0

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - No plan records will be created."))

        for plan_data in default_plans:
            slug = plan_data["slug"]

            # Check if plan already exists
            existing_plan = TenantPlan.objects.filter(slug=slug).first()
            if existing_plan:
                skipped_count += 1
                self.stdout.write(
                    f'  - Plan "{plan_data["name"]}" ({slug}) - already exists, skipping'
                )
                continue

            if dry_run:
                self.stdout.write(
                    f'  - Would create plan "{plan_data["name"]}" ({slug}) with tier {plan_data["tier"]}'
                )
                continue

            try:
                with transaction.atomic():
                    plan = TenantPlan.objects.create(
                        name=plan_data["name"],
                        slug=slug,
                        tier=plan_data["tier"],
                        limits_json=plan_data["limits_json"],
                        is_active=True,
                    )

                    created_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'  ✓ Created plan "{plan.name}" ({plan.slug}) with tier {plan.tier}'
                        )
                    )

                    logger.info(
                        "tenant_plan_created",
                        plan_id=str(plan.id),
                        plan_slug=plan.slug,
                        plan_tier=plan.tier,
                        message=f"Created default plan {plan.slug}",
                    )

            except Exception as e:
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(f'  ✗ Error creating plan "{plan_data["name"]}" ({slug}): {e}')
                )
                logger.error(
                    "tenant_plan_creation_failed",
                    plan_slug=slug,
                    error=str(e),
                    message=f"Failed to create plan {slug}",
                )

        # Summary
        if not dry_run:
            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS("=" * 60))
            self.stdout.write(self.style.SUCCESS("Summary:"))
            self.stdout.write(f"  - Created: {created_count} plan(s)")
            if skipped_count > 0:
                self.stdout.write(f"  - Skipped: {skipped_count} plan(s) (already exist)")
            if error_count > 0:
                self.stdout.write(self.style.ERROR(f"  - Errors: {error_count} plan(s)"))
            self.stdout.write(self.style.SUCCESS("=" * 60))
        else:
            self.stdout.write(self.style.WARNING("Dry run: no changes made."))
