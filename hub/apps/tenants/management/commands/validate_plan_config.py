"""
285.13.10.4 — validate plan configuration integrity.

Checks:
1. Every ``FeatureFlag`` with ``minimum_plan_order > 0`` references a
   tier that actually exists in the TenantPlan table (a plan with
   ``order >= minimum_plan_order`` in the right category).
2. In ``--strict`` mode: also verifies no TenantPlan has a negative
   ``order`` value.

CI exit: 0 on PASS, 1 on any violation.
"""

from django.core.management.base import BaseCommand

from hub.apps.tenants.feature_flag_registry import REGISTRY
from hub.apps.tenants.models import PlanCategory, TenantPlan


class Command(BaseCommand):
    help = "285.13.10 — validate plan config integrity."

    def add_arguments(self, parser):
        parser.add_argument(
            "--strict",
            action="store_true",
            default=False,
            help="Also verify no TenantPlan has a negative order value.",
        )

    def handle(self, **options):
        strict = options["strict"]
        errors = []

        # ── Validate: every tier-gated flag references existing tiers ──
        gated_flags = [f for f in REGISTRY if f.minimum_plan_order > 0]
        if not gated_flags:
            self.stdout.write("No tier-gated feature flags registered.")
            return

        for flag in gated_flags:
            # Determine which category this flag belongs to.
            # By convention, flags are implicitly BASE unless they
            # explicitly reference ML_AI in their name or description.
            category = PlanCategory.BASE
            if "ml" in flag.name.lower() or "ML" in flag.description:
                category = PlanCategory.ML_AI

            exists = TenantPlan.objects.filter(
                is_active=True,
                category=category,
                order__gte=flag.minimum_plan_order,
            ).exists()
            if not exists:
                msg = (
                    f"Flag '{flag.name}' requires "
                    f"minimum_plan_order={flag.minimum_plan_order} "
                    f"(category={category}), but no active plan satisfies "
                    f"order >= {flag.minimum_plan_order} in that category."
                )
                errors.append(msg)

        # ── Strict mode: verify no plan has a negative order value ────
        if strict:
            for plan in TenantPlan.objects.filter(is_active=True):
                if plan.order < 0:
                    errors.append(f"Plan '{plan.slug}' has negative order={plan.order}.")

        if errors:
            self.stderr.write(
                self.style.ERROR(f"validate_plan_config FAILED: {len(errors)} violation(s).")
            )
            for err in errors:
                self.stderr.write(f"  - {err}")
            raise SystemExit(1)

        self.stdout.write(
            self.style.SUCCESS(
                f"validate_plan_config PASSED "
                f"({len(gated_flags)} tier-gated flags checked"
                f"{', strict mode on' if strict else ''})."
            )
        )
