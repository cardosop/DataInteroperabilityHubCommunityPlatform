"""Databricks control-plane app configuration (openspec add-databricks-control-plane, P0).

The app is registered in ``hub/apps/manifest.py`` directly after ``warehouses`` —
the ordering is locked by ``hub/tests/test_manifest.py``.
"""

from django.apps import AppConfig


class DatabricksAdminConfig(AppConfig):
    name = "hub.apps.databricks_admin"
    verbose_name = "Databricks Control Plane"

    def ready(self):
        # W4.6 (openspec oss-release-remediation, G1) — register the
        # databricks business-rules chains at app-ready (the Phase 313.1
        # owning-app convention, the marketplace/semantic precedent).
        # The core chain registry no longer references this app — the
        # provider-boundary inversion: core NEVER imports the estate.
        from hub.apps.databricks_admin import chains  # noqa: F401

        # P7 (openspec add-databricks-cost-guardrails task 7.5, design D4)
        # — register the cost-ledger writer into the warehouses
        # cost-recording seam. The provider-boundary inversion:
        # databricks_admin → warehouses (this app already imports
        # warehouses.base elsewhere); warehouses NEVER imports this app.
        from hub.apps.databricks_admin.cost_ledger import record_ledger_cost
        from hub.apps.warehouses.cost_recording import register_cost_backend

        register_cost_backend(record_ledger_cost)

        # W4.6 (openspec oss-release-remediation, G1) — register the REAL
        # budget enforcer into the warehouses budget-gate seam (the same
        # inversion as cost-recording above: warehouses NEVER imports
        # this app; an unregistered seam means "no budget concept").
        from hub.apps.databricks_admin.budget_enforce import enforce_budget
        from hub.apps.warehouses.budget_gate import register_budget_enforcer

        register_budget_enforcer(enforce_budget)

        # W4.6 (openspec oss-release-remediation, G1) — register the REAL
        # M2M token-cache factory into the integrations seam (data_movement
        # + transformation consume the DEFAULT through the seam; they
        # never import estate code).
        from hub.apps.databricks_admin.token_cache import M2MTokenCache
        from hub.apps.integrations.m2m_token_cache import (
            register_m2m_token_cache_factory,
        )

        register_m2m_token_cache_factory(M2MTokenCache)

        # W4.6 (openspec oss-release-remediation, G1) — register the
        # estate job handlers into the jobs dispatch seam (the executor
        # surfaces live here; the provider-agnostic jobs dispatcher
        # never imports estate code).
        from hub.apps.databricks_admin.cost_sync_jobs import (
            _execute_databricks_cost_sync_job,
        )
        from hub.apps.databricks_admin.uc_change_reaper_jobs import (
            _execute_databricks_uc_change_reaper_job,
        )
        from hub.apps.databricks_admin.uc_sync_jobs import (
            _execute_databricks_uc_metadata_sync_job,
        )
        from hub.apps.jobs.estate_handlers import register_estate_job_handler

        register_estate_job_handler(
            "DATABRICKS_UC_METADATA_SYNC",
            _execute_databricks_uc_metadata_sync_job,
        )
        register_estate_job_handler(
            "DATABRICKS_COST_SYNC",
            _execute_databricks_cost_sync_job,
        )
        register_estate_job_handler(
            "DATABRICKS_UC_CHANGE_REAPER",
            _execute_databricks_uc_change_reaper_job,
        )

        # W4.6 (openspec oss-release-remediation, G1) — register the
        # staging-volume provisioner into the data_movement seam (the
        # consumer never imports estate executor code).
        from hub.apps.databricks_admin.staging_provisioner import (
            provision_staging_volume,
        )
        from hub.data_movement.staging import register_staging_volume_provisioner

        register_staging_volume_provisioner(provision_staging_volume)

        # P11 (openspec run-transformation-on-databricks task 11.2,
        # design D1) — register the REAL dbt-as-job dispatcher into the
        # transformation facade. The same provider-boundary inversion:
        # transformation NEVER imports this app; the facade refuses
        # classified when no dispatcher is registered.
        from hub.apps.databricks_admin.dbt_job_dispatch import (
            dispatch_dbt_run_as_databricks_job,
        )
        from hub.apps.transformation.execution_targets import (
            register_dbt_job_dispatcher,
        )

        register_dbt_job_dispatcher(dispatch_dbt_run_as_databricks_job)

        # W4.3 (openspec oss-release-remediation, R2-B6/E2) — register
        # the Delta Sharing estate offboarding sweeper into the tenant
        # offboarding registry. Same provider-boundary inversion as the
        # two seams above: tenants NEVER imports this app; the tenant
        # hard-delete sweep runs the registered sweeper inside
        # tenant_context() to clear the PROTECT-FK estate rows.
        from hub.apps.databricks_admin.offboarding import sweep_delta_share_estate
        from hub.apps.tenants.offboarding import register_tenant_offboard_sweeper

        register_tenant_offboard_sweeper(
            "databricks_delta_share", sweep_delta_share_estate
        )
