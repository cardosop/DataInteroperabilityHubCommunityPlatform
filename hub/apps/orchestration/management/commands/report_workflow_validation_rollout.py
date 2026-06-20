"""
Management command to report current workflow business rules validation
rollout status. Supports gradual rollout verification (Task 5.2).
Uses real feature flags and settings; no mocks.
"""

from django.conf import settings
from django.core.management.base import BaseCommand

from hub.apps.orchestration.feature_flags import (
    get_feature_flags,
    reset_feature_flags,
)


class Command(BaseCommand):
    help = (
        "Report workflow business rules validation rollout status (Task 5.2). "
        "Uses real feature flags and settings."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--no-reset",
            action="store_true",
            help="Do not reset feature flags cache (default: reset)",
        )

    def handle(self, *args, **options):
        if not options.get("no_reset"):
            reset_feature_flags()

        flags = get_feature_flags()
        summary = flags.get_config_summary()

        # Current config
        self.stdout.write("=== Workflow Business Rules Validation Rollout ===\n")
        self.stdout.write(f"  Global enabled: {summary['enabled_globally']}\n")
        self.stdout.write(f"  Rollout percentage: {summary['rollout_percentage']}%\n")
        self.stdout.write(f"  Per-workflow config: {summary['workflow_config_count']}\n")
        self.stdout.write(f"  Disabled workflows: {summary['disabled_workflows_count']}\n")
        self.stdout.write(f"  Enabled workflows: {summary['enabled_workflows_count']}\n")
        self.stdout.write(f"  Per-tenant config: {summary['tenant_config_count']}\n")

        # Workflow tiers from settings (for gradual rollout reference)
        test_workflows = getattr(
            settings,
            "WORKFLOW_BUSINESS_RULES_VALIDATION_TEST_WORKFLOWS",
            [],
        )
        critical_workflows = getattr(
            settings,
            "WORKFLOW_BUSINESS_RULES_VALIDATION_CRITICAL_WORKFLOWS",
            [],
        )
        all_known = sorted(set(test_workflows) | set(critical_workflows))

        if not all_known:
            self.stdout.write("\nNo test/critical workflow lists in settings.\n")
            return

        self.stdout.write("\n--- Validation enabled per workflow ---\n")
        for name in all_known:
            enabled = flags.is_enabled(name, tenant_id=None, workflow_instance_id=None)
            tier = "test" if name in test_workflows else "critical"
            status = "enabled" if enabled else "disabled"
            self.stdout.write(f"  {name} ({tier}): {status}\n")

        self.stdout.write("\nDone.\n")
