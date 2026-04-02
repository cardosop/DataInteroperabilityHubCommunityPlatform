"""
Management command to seed default tenant plans (FREE, PRO, ENTERPRISE).

Creates default plans with standard limits if they don't already exist.
Idempotent: skips existing plans by slug. If create fails due to duplicate name
(e.g. plan exists with wrong slug), fixes slug so PersonalTenantService can find it.
"""

import structlog
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db import IntegrityError

from hub.apps.tenants.models import PlanCategory, PlanTier, TenantPlan

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
                    "max_transformation_pipelines": 5,
                    "max_transformation_runs_per_month": 20,
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
                    "max_transformation_pipelines": 50,
                    "max_transformation_runs_per_month": 500,
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
                    "max_transformation_pipelines": None,  # Unlimited
                    "max_transformation_runs_per_month": None,  # Unlimited
                },
            },
        ]

        # ── ML / AI plans (Phase 114A) ──
        ml_plans = [
            {
                "name": "ML Starter",
                "slug": "ml-starter",
                "tier": PlanTier.FREE,
                "category": PlanCategory.ML_AI,
                "limits_json": {
                    "max_ml_models": 3,
                    "max_ml_training_jobs_per_month": 10,
                    "max_ml_inference_requests_per_month": 500,
                    "max_ml_deployed_models": 1,
                    "max_ml_storage_gb": 5,
                },
            },
            {
                "name": "ML Professional",
                "slug": "ml-professional",
                "tier": PlanTier.PRO,
                "category": PlanCategory.ML_AI,
                "limits_json": {
                    "max_ml_models": 20,
                    "max_ml_training_jobs_per_month": 100,
                    "max_ml_inference_requests_per_month": 10000,
                    "max_ml_deployed_models": 10,
                    "max_ml_storage_gb": 100,
                },
            },
            {
                "name": "ML Enterprise",
                "slug": "ml-enterprise",
                "tier": PlanTier.ENTERPRISE,
                "category": PlanCategory.ML_AI,
                "limits_json": {
                    "max_ml_models": None,
                    "max_ml_training_jobs_per_month": None,
                    "max_ml_inference_requests_per_month": None,
                    "max_ml_deployed_models": None,
                    "max_ml_storage_gb": None,
                },
            },
        ]

        default_plans.extend(ml_plans)

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
                # Ensure is_active=True — onboarding and registration endpoints
                # query with is_active=True, so an inactive plan causes 404/503.
                needs_update = False
                update_fields = []
                if not existing_plan.is_active:
                    existing_plan.is_active = True
                    update_fields.append("is_active")
                    needs_update = True
                if existing_plan.tier != plan_data["tier"]:
                    existing_plan.tier = plan_data["tier"]
                    update_fields.append("tier")
                    needs_update = True
                if needs_update:
                    existing_plan.save(update_fields=update_fields)
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'  ✓ Plan "{plan_data["name"]}" ({slug}) - updated ({", ".join(update_fields)})'
                        )
                    )
                    created_count += 1
                else:
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
                    create_kwargs = {
                        "name": plan_data["name"],
                        "slug": slug,
                        "tier": plan_data["tier"],
                        "limits_json": plan_data["limits_json"],
                        "is_active": True,
                    }
                    if "category" in plan_data:
                        create_kwargs["category"] = plan_data["category"]
                    plan = TenantPlan.objects.create(**create_kwargs)

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

            except IntegrityError as e:
                # Plan may exist with same name (wrong slug, or race: another process created it)
                if "tenant_plans_name_key" in str(e) or "unique constraint" in str(e).lower():
                    existing = TenantPlan.objects.filter(name=plan_data["name"]).first()
                    if existing:
                        if existing.slug != slug:
                            existing.slug = slug
                            existing.tier = plan_data["tier"]
                            existing.limits_json = plan_data["limits_json"]
                            existing.is_active = True
                            existing.save()
                            created_count += 1
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f'  ✓ Fixed plan "{existing.name}" slug to {slug}'
                                )
                            )
                        else:
                            skipped_count += 1
                            self.stdout.write(
                                f'  - Plan "{plan_data["name"]}" ({slug}) - already exists, skipping'
                            )
                        continue
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
