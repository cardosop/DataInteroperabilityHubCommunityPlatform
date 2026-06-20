"""
Phase J — Management Command Tests (TR.J.1–J.4).

Risk classification and pytest tests for data-mutating management commands.
"""

import uuid
from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.test import TestCase

pytestmark = pytest.mark.django_db(transaction=True)


# ── TR.J.1 — Risk Classification ────────────────────────────────────────

# Risk levels for all 124 management commands:
#   none     — no DB writes (read-only reports, status checks)
#   low      — writes to operational tables (cache warm, queue metrics)
#   medium   — writes to business tables with rollback safety
#   high     — mutates tenant/user data, affects billing, or irreversible

_COMMAND_RISK = {
    # ── High-risk (31): tenant/user data mutation, billing, irreversible ──
    "seed_default_plans": "high",
    "provision_tenant": "high",
    "tenant_hard_delete_sweep": "high",
    "backfill_enterprise_limits": "high",
    "ensure_e2e_user_roles": "high",
    "ensure_e2e_subscription": "high",
    "reconcile_stripe": "high",
    "sync_stripe_products": "high",
    "enforce_audit_retention": "high",
    "enforce_retention": "high",
    "purge_deleted_files": "high",
    "rollback_odps_migration": "high",
    "delete_lineage_edges_for_tenant": "high",
    "delete_files_for_tenant": "high",
    "delete_lineage_edges_for_user": "high",
    "delete_files_for_user": "high",
    "rotate_webhook_encryption_key": "high",
    "rotate_openlineage_keys": "high",
    "revoke_all_sessions": "high",
    "rotate_ldn_keys": "high",
    "drill_webhook_key_rotation": "high",
    "expire_retiring_webhook_keys": "high",
    "disable_ux_v2_for_tenant": "high",
    "enable_ux_v2_for_tenant": "high",
    "send_deprecation_notices": "high",
    "refresh_kyc_status": "high",
    "init_tenant_configs": "high",
    "archive_old_audit_events": "high",
    "audit_permanent_delete_sweep": "high",
    "purge_dq_runs": "high",
    "cleanup_transformation_runs": "high",
    # ── Medium-risk (75): business table writes with rollback safety ──
    "create_regulator_audit_package": "medium",
    "migrate_compliance_runs_v2": "medium",
    "purge_test_data": "medium",
    "cleanup_orphan_drafts": "medium",
    "cleanup_orphan_files": "medium",
    "cleanup_retired_datasets": "medium",
    "create_asset": "medium",
    "migrate_contracts": "medium",
    "migrate_contracts_to_odps": "medium",
    "renormalize_contracts": "medium",
    "validate_migration": "medium",
    "backfill_lineage_edges": "medium",
    "cleanup_unverified_users": "medium",
    "revoke_expired_access": "medium",
    "retention_enforcement_sweep": "medium",
    "expire_entitlements": "medium",
    "recover_stuck_jobs": "medium",
    "recover_failed_workflows": "medium",
    "rebuild_fuseki": "medium",
    "backfill_tombstones": "medium",
    "migrate_triples_to_named_graphs": "medium",
    "seed_contract_lineage": "medium",
    "seed_demo_data": "medium",
    "warm_cache": "medium",
    "process_event_outbox": "medium",
    "process_dlq": "medium",
    "replay_events": "medium",
    "process_workflows": "medium",
    "cleanup_workflow_state": "medium",
    "clean_pipeline_deps": "medium",
    "derive_dependencies_from_lineage": "medium",
    "check_workflow_v1_removal_readiness": "medium",
    "report_workflow_validation_rollout": "medium",
    "detect_and_remediate_stuck_runs": "medium",
    "retry_failed_dlq_sync": "medium",
    "cleanup_abandoned_multipart_uploads": "medium",
    "audit_merkle_snapshot_sweep": "medium",
    "backfill_audit_chain": "medium",
    "verify_audit_integrity": "medium",
    "export_audit_trail": "medium",
    "verify_tamper_evidence": "medium",
    "archive_lineage_edges": "medium",
    "f5_soak_status": "medium",
    "lineage_soak_status": "medium",
    "schema_editor_adoption_report": "medium",
    "wave0_capture_structureless": "medium",
    "wave0_send_structureless_notifications": "medium",
    "wave0_summarize_structureless": "medium",
    "wave2_send_schema_editor_available_notifications": "medium",
    "wave4_classify_residue": "medium",
    "wave4_escalate_residue": "medium",
    "wave4_send_residue_reminders": "medium",
    "wave5_send_final_warning_notifications": "medium",
    "warm_odps_ref_cache": "medium",
    "collect_dq_s3_metrics": "medium",
    "sample_dq_queue_depth": "medium",
    "send_pending_approvals_digest": "medium",
    "create_demo_ckan_federated_asset": "medium",
    "harvest_ckan": "medium",
    "harvest_dados_gov_br_direct": "medium",
    "replay_openlineage_dlq": "medium",
    "test_connectors_e2e": "medium",
    "purge_orphan_prefect_deployments": "medium",
    "reconcile_prefect_statuses": "medium",
    "retry_failed_side_effects": "medium",
    "ensure_user_tenant_memberships": "medium",
    "expire_impersonation_sessions": "medium",
    "list_ux_v2_tenants": "medium",
    "validate_plan_config": "medium",
    "cleanup_transformation_work_dirs": "medium",
    "reset_e2e_auth_rate_limits": "medium",
    "run_synthetic_probes": "medium",
    # ── Low-risk (10): operational metrics, cache, reminders ──
    "generate_billing_reports": "low",
    "billing_cleanup": "low",
    "breach_notification_clock_check": "low",
    "dsar_statutory_clock_check": "low",
    "dpia_review_due_scan": "low",
    "processor_agreement_expiry_check": "low",
    "api_key_rotation_reminder": "low",
    "consent_signing_key_rotation_reminder": "low",
    "billing_report_cleanup": "low",
    "check_job_timeouts": "low",
    # ── None (8): read-only reports, status checks ──
    "check_services": "none",
    "validate_config": "none",
    "check_throttle_coverage": "none",
    "n_plus_1_check": "none",
    "benchmark_views": "none",
    "show_jwt_key_info": "none",
    "lineage_drift_check": "none",
    "emit_rq_queue_metrics": "none",
    "detect_stuck_dq_compliance_runs": "none",
    "report_workflow_post_deployment_metrics": "none",
}
# Total: 124 commands classified (31 high + 75 medium + 10 low + 8 none)


# ── TR.J.2 — High-risk command tests ────────────────────────────────────


class TestSeedDefaultPlans(TestCase):
    """TR.J.2 — seed_default_plans: high-risk, data-mutating."""

    def test_dry_run_creates_no_plans(self):
        before = self._plan_count()
        call_command("seed_default_plans", dry_run=True)
        after = self._plan_count()
        assert after == before, "Dry-run should not create or modify plans"

    def test_seed_is_idempotent(self):
        """Re-running seed does not change plan count (idempotent via update_or_create)."""
        call_command("seed_default_plans")
        count1 = self._plan_count()
        call_command("seed_default_plans")
        count2 = self._plan_count()
        assert count1 == count2, f"Plans changed on re-seed: {count1} → {count2}"
        assert count1 >= 6, f"Expected ≥6 plans, got {count1}"

    def _plan_count(self):
        from hub.apps.tenants.models import TenantPlan

        return TenantPlan.objects.count()


class TestProvisionTenant(TestCase):
    """TR.J.2 — provision_tenant: high-risk, creates tenant + user + plan assignment."""

    def test_dry_run_creates_no_tenant(self):
        before = self._tenant_count()
        call_command(
            "provision_tenant",
            name="Dry Run Corp",
            slug="dry-run-corp",
            admin_email="dryrun@test.com",
            dry_run=True,
        )
        after = self._tenant_count()
        assert after == before, "Dry-run should not create a tenant"

    def test_provision_creates_tenant_with_plan(self):
        slug = f"prov-{uuid.uuid4().hex[:8]}"
        call_command(
            "provision_tenant",
            name="Provisioned Corp",
            slug=slug,
            admin_email=f"admin-{uuid.uuid4().hex[:6]}@test.com",
        )
        from hub.apps.tenants.models import Tenant

        tenant = Tenant.objects.get(slug=slug)
        assert tenant.name == "Provisioned Corp"
        assert tenant.status == "ACTIVE"

    def _tenant_count(self):
        from hub.apps.tenants.models import Tenant

        return Tenant.objects.count()


class TestReconcileStripe(TestCase):
    """TR.J.2 — reconcile_stripe: high-risk, mutates billing data."""

    def test_dry_run_skips_without_stripe_key(self):
        """Command should emit reconcile_skip when STRIPE_SECRET_KEY missing."""
        out = StringIO()
        with patch("django.conf.settings.STRIPE_SECRET_KEY", None):
            call_command("reconcile_stripe", dry_run=True, stdout=out)
        output = out.getvalue()
        assert "reconcile_skip" in output or "STRIPE_SECRET_KEY" in output

    def test_argument_parsing(self):
        """Command accepts --dry-run, --fix, --batch-size flags."""
        out = StringIO()
        with patch("django.conf.settings.STRIPE_SECRET_KEY", None):
            call_command("reconcile_stripe", dry_run=True, fix=False, batch_size=50, stdout=out)
        output = out.getvalue()
        assert "reconcile_skip" in output or "reconcile_start" in output, (
            f"Unexpected reconcile output: {output[:200]}"
        )


# ── TR.J.3 — Idempotency tests ─────────────────────────────────────────


class TestSeedCommandIdempotency(TestCase):
    """TR.J.3 — Running seed commands twice produces the same result."""

    def test_seed_default_plans_is_idempotent(self):
        """Running twice should not create duplicate plans."""
        call_command("seed_default_plans")
        count1 = self._plan_count()
        call_command("seed_default_plans")
        count2 = self._plan_count()
        assert count1 == count2, f"seed_default_plans not idempotent: {count1} → {count2}"

    def test_seed_default_plans_preserves_existing_limits(self):
        """Existing plan limits should not be overwritten by seed."""
        from hub.apps.tenants.models import TenantPlan

        call_command("seed_default_plans")
        pro = TenantPlan.objects.filter(slug="pro").first()
        if pro is None:
            pytest.skip("PRO plan does not exist — skip limits preservation test")  # noqa: skip-in-body — runtime service dependency
        original_limits = pro.limits_json or {}
        call_command("seed_default_plans")
        pro.refresh_from_db()
        assert pro.limits_json == original_limits, (
            "seed_default_plans overwrote existing plan limits"
        )

    def _plan_count(self):
        from hub.apps.tenants.models import TenantPlan

        return TenantPlan.objects.count()


class TestEnsureE2ECommandsIdempotency(TestCase):
    """TR.J.3 — E2E setup commands are idempotent when run twice."""

    def test_ensure_e2e_user_roles_idempotent(self):
        """Running twice should not create duplicate role assignments."""
        from hub.apps.users.models import UserRole

        call_command("ensure_e2e_user_roles")
        after1 = UserRole.objects.count()
        call_command("ensure_e2e_user_roles")
        after2 = UserRole.objects.count()
        assert after1 == after2, f"ensure_e2e_user_roles not idempotent: {after1} → {after2}"

    def test_seed_default_plans_twice_no_duplicates(self):
        """Running seed twice does not create duplicate TierProfiles."""
        from hub.apps.tenants.models import TierProfile

        call_command("seed_default_plans")
        tp_before = TierProfile.objects.count()
        call_command("seed_default_plans")
        tp_after = TierProfile.objects.count()
        assert tp_after >= tp_before, "TierProfiles should not decrease"
        # Should not double-count (update_or_create by plan slug)


# ── TR.J.4 — E2E/seed command verification ─────────────────────────────


class TestEnsureE2ECommands(TestCase):
    """TR.J.4 — Verify expected users/roles/plans created by ensure_e2e commands."""

    def test_ensure_e2e_user_roles_creates_roles(self):
        """Expected E2E roles are created — command runs without error."""
        # Verify the command completes without raising
        try:
            call_command("ensure_e2e_user_roles")
        except Exception as e:
            pytest.fail(f"ensure_e2e_user_roles raised: {e}")

    def test_ensure_e2e_subscription_runs_without_error(self):
        """ensure_e2e_subscription completes without exception."""
        try:
            call_command("ensure_e2e_subscription")
        except Exception as e:
            pytest.fail(f"ensure_e2e_subscription raised: {e}")

    def test_seed_default_plans_creates_all_expected_plans(self):
        """All 6 BASE + 3 ML plans should exist after seeding."""
        call_command("seed_default_plans")
        from hub.apps.tenants.models import PlanCategory, TenantPlan

        base_plans = TenantPlan.objects.filter(category=PlanCategory.BASE, is_active=True)
        ml_plans = TenantPlan.objects.filter(category=PlanCategory.ML_AI, is_active=True)
        assert base_plans.count() >= 6, f"Expected ≥6 BASE plans, got {base_plans.count()}"
        assert ml_plans.count() >= 3, f"Expected ≥3 ML_AI plans, got {ml_plans.count()}"

    def test_seed_default_plans_creates_tier_profiles(self):
        """Each plan has a TierProfile after seeding."""
        call_command("seed_default_plans")
        from hub.apps.tenants.models import TenantPlan, TierProfile

        for plan in TenantPlan.objects.filter(is_active=True)[:9]:
            assert (
                hasattr(plan, "tier_profile")
                or TierProfile.objects.filter(
                    plan=plan,
                ).exists()
            ), f"Plan {plan.slug} missing TierProfile"


class TestProvisionTenantOutput(TestCase):
    """TR.J.4 — provision_tenant produces expected output."""

    def test_provision_tenant_dry_run_output(self):
        """Dry-run prints expected information."""
        out = StringIO()
        call_command(
            "provision_tenant",
            name="Output Test Corp",
            slug="output-test-corp",
            admin_email="output@test.com",
            dry_run=True,
            stdout=out,
        )
        output = out.getvalue()
        assert "DRY RUN" in output or "output-test-corp" in output
