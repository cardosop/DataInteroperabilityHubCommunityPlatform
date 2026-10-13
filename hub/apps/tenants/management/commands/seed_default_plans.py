"""
Management command to seed default tenant plans.

R2-B7 (W2.7) — SINGLE SEEDER SOURCE: every plan seeded here comes from
``tenants/plan_defaults.py`` (the canonical catalog).  The pre-fix
command carried an INLINE plan list that diverged from the canonical
data (seeded FREE: max_assets=10 vs canonical 3, max_storage_gb=1GB vs
canonical unlimited, …) — the free-plan divergence class.

Idempotent: skips existing plans by slug (existing rows are
operator-owned — the command repairs is_active/tier/order but never
clobbers a tenant-customized ``limits_json``).  If create fails due to
duplicate name (e.g. plan exists with wrong slug), fixes slug so
PersonalTenantService can find it.  Legacy slug ``ml-professional`` is
adopted as ``ml-pro`` (the canonical name) so re-seeding cannot mint a
duplicate ML-pro-tier plan.
"""

import structlog
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import IntegrityError, transaction

from hub.apps.tenants.models import TenantPlan

logger = structlog.get_logger(__name__)


def _stripe_price_for(slug: str) -> str | None:
    """The configured canonical price id for a plan slug, or None.

    Resolved AT COMMAND RUNTIME so a fresh seed is checkout-ready AND
    override_settings()-driven pins and per-invocation env changes take
    effect.  Blank/unset → None (the historical inline price_data path
    stays intact).  FREE stays optional by design (free subscriptions
    are local-only; Stripe has no $0 recurring price).
    """
    if slug == "free":
        return getattr(settings, "STRIPE_FREE_PRICE_ID", "") or None
    if slug == "pro":
        return getattr(settings, "STRIPE_PRO_PRICE_ID", "") or None
    return None


#: Legacy → canonical slug adoption (R2-B7).  The pre-fix seeder named
#: the ML pro tier ``ml-professional``; the canonical catalog calls it
#: ``ml-pro``.  Adopting the legacy row prevents a duplicate plan.
LEGACY_SLUG_ADOPTIONS: dict[str, str] = {
    "ml-professional": "ml-pro",
}


def _canonical_catalog() -> list[dict]:
    """The ONE seed source: plan_defaults.PLATFORM_PLANS + ML_PLANS."""
    from hub.apps.tenants.plan_defaults import ML_PLANS, PLATFORM_PLANS

    return list(PLATFORM_PLANS) + list(ML_PLANS)


def _plan_create_kwargs(canonical: dict, stripe_price: str | None) -> dict:
    """Map a canonical catalog entry to TenantPlan model fields.

    Catalog-only keys (``tier_profile``, ``includes_regulations``) have
    no model column yet and are intentionally dropped at the boundary.
    """
    kwargs = {
        "name": canonical["name"],
        "slug": canonical["slug"],
        "tier": canonical["tier"],
        "category": canonical["category"],
        "order": canonical["order"],
        "limits_json": canonical["limits_json"],
        "is_active": True,
        "compliance_pro_pack": canonical.get("compliance_pro_pack", False),
        "price_currency": canonical.get("price_currency", "USD"),
        "billing_interval": canonical.get("billing_interval", "monthly"),
    }
    for key in (
        "price_amount_cents",
        "flsc_estimate_cents",
        "markup_bps",
        "marketplace_take_rate_bps",
    ):
        value = canonical.get(key)
        if value is not None:
            kwargs[key] = value
    if stripe_price:
        kwargs["stripe_price_id"] = stripe_price
    return kwargs


class Command(BaseCommand):
    help = "Seed default tenant plans from the canonical plan_defaults catalog"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be created without actually creating plan records",
        )

    def handle(self, *_args, **options):
        dry_run = options["dry_run"]

        default_plans = _canonical_catalog()

        created_count = 0
        skipped_count = 0
        error_count = 0

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - No plan records will be created."))

        for plan_data in default_plans:
            slug = plan_data["slug"]

            # R2-B7 — adopt a legacy-slug row (ml-professional → ml-pro)
            # so re-seeding upgrades in place instead of minting a
            # duplicate ML-pro-tier plan.
            existing_plan = TenantPlan.objects.filter(slug=slug).first()
            if existing_plan is None:
                legacy = LEGACY_SLUG_ADOPTIONS.get(slug)
                if legacy:
                    legacy_plan = TenantPlan.objects.filter(slug=legacy).first()
                    if legacy_plan and not TenantPlan.objects.filter(slug=slug).exists():
                        legacy_plan.slug = slug
                        legacy_plan.save(update_fields=["slug"])
                        existing_plan = legacy_plan
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'  ✓ Adopted legacy plan slug "{legacy}" → "{slug}"'
                            )
                        )

            # Check if plan already exists
            if existing_plan:
                # Ensure is_active=True — onboarding and registration endpoints
                # query with is_active=True, so an inactive plan causes 404/503.
                # W2.2 (R2-D2): also repair the canonical order — the
                # change-plan downgrade guard compares plan orders, and a
                # seeded plan left on the stale default (0) makes the
                # guard structurally dead.
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
                if existing_plan.order != plan_data["order"]:
                    existing_plan.order = plan_data["order"]
                    update_fields.append("order")
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
                    create_kwargs = _plan_create_kwargs(
                        plan_data,
                        _stripe_price_for(slug),
                    )
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
                logger.exception(
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
                logger.exception(
                    "tenant_plan_creation_failed",
                    plan_slug=slug,
                    error=str(e),
                    message=f"Failed to create plan {slug}",
                )

        # Summary
        if not dry_run:
            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS("=" * 60))
            self.stdout.write(
                self.style.SUCCESS(
                    f"Seed complete: {created_count} created/updated, "
                    f"{skipped_count} skipped, {error_count} errors."
                )
            )
            self.stdout.write(self.style.SUCCESS("=" * 60))
        else:
            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS("=" * 60))
            self.stdout.write(
                self.style.SUCCESS(
                    f"Dry run complete: {created_count} would be created, "
                    f"{skipped_count} skipped, {error_count} errors."
                )
            )
            self.stdout.write(self.style.SUCCESS("=" * 60))
