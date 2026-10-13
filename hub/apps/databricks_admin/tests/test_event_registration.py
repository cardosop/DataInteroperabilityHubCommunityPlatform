"""0.16 — databricks audit-event registration + error-catalogue doc pins.

Two registries are pinned here:

1. ``hub/apps/audit/event_types.py`` — every databricks event constant
   must exist AND be exported via ``__all__`` (the repo's registration
   contract; consumers import the constant, tooling enumerates ``__all__``).
2. ``docs/api/error-codes.md`` — the canonical error catalogue
   (``scripts/check_error_codes_catalogue.py`` is the reverse-direction
   gate: code-emitted codes must be catalogued). These pins assert the
   REQUIRED rows are present so a doc regression fails fast in pytest,
   not only in the gate job.
"""

from pathlib import Path

from django.test import TestCase

REPO_ROOT = Path(__file__).resolve().parents[4]

DATABRICKS_EVENTS = (
    "DATABRICKS_WORKSPACE_REGISTERED",
    "DATABRICKS_WORKSPACE_UPDATED",
    "DATABRICKS_WORKSPACE_DELETED",
    "DATABRICKS_WORKSPACE_TEST_PASSED",
    "DATABRICKS_WORKSPACE_TEST_FAILED",
    "DATABRICKS_CREDENTIAL_STORED",
    "DATABRICKS_CREDENTIAL_ROTATED",
    # 0b.6 — the D12 identity decision emits resource_type=
    # DATABRICKS_EXECUTION_IDENTITY + action=RESOLVED; the combined
    # constant must be registered like every other emitted event.
    "DATABRICKS_EXECUTION_IDENTITY_RESOLVED",
    # 0b.11 — the SSO + OBO lifecycle events.
    "DATABRICKS_SSO_LOGIN_SUCCESS",
    "DATABRICKS_SSO_LOGIN_FAILED",
    "DATABRICKS_OBO_TOKEN_REFRESHED",
    "DATABRICKS_OBO_TOKEN_REVOKED",
    # 1.5/1.10 — the UC metadata sync outcomes (emitted per workspace by
    # uc_sync._emit_sync_audit; wired ahead of 1.10 which owns the
    # dashboards + alerts).
    "DATABRICKS_UC_METADATA_SYNCED",
    "DATABRICKS_UC_METADATA_SYNC_FAILED",
    # P2 — UC write (openspec add-databricks-uc-write task 2.9): the
    # change lifecycle (one row per transition, resource_type=
    # DATABRICKS_UC_CHANGE) + the grants bridge (resource_type=
    # DATABRICKS_GRANT).
    "DATABRICKS_UC_CHANGE_REQUESTED",
    "DATABRICKS_UC_CHANGE_APPROVED",
    "DATABRICKS_UC_CHANGE_REJECTED",
    "DATABRICKS_UC_CHANGE_EXECUTING",
    "DATABRICKS_UC_CHANGE_EXECUTED",
    "DATABRICKS_UC_CHANGE_FAILED",
    "DATABRICKS_UC_CHANGE_ROLLED_BACK",
    "DATABRICKS_GRANT_PLAN_COMPUTED",
    "DATABRICKS_GRANT_APPLIED",
    "DATABRICKS_GRANT_REVOKED",
    "DATABRICKS_GRANT_VERIFIED",
    # P3 — SQL warehouses (task 3.8): the compute lifecycle audit set
    # (resource_type=DATABRICKS_WAREHOUSE, one row per performed
    # lifecycle operation — created/started/stopped/resized/deleted).
    "DATABRICKS_WAREHOUSE_CREATED",
    "DATABRICKS_WAREHOUSE_STARTED",
    "DATABRICKS_WAREHOUSE_STOPPED",
    "DATABRICKS_WAREHOUSE_RESIZED",
    "DATABRICKS_WAREHOUSE_DELETED",
    # P4 — Databricks jobs (tasks 4.4/4.6): the job lifecycle + run set
    # (resource_type=DATABRICKS_JOB; the RUN_* rows carry the SHORT
    # action verbs, the lifecycle rows the FULL constants — the repo's
    # two audit-action conventions).
    "DATABRICKS_JOB_CREATED",
    "DATABRICKS_JOB_UPDATED",
    "DATABRICKS_JOB_DELETED",
    "DATABRICKS_JOB_RUN_STARTED",
    "DATABRICKS_JOB_RUN_SUCCEEDED",
    "DATABRICKS_JOB_RUN_FAILED",
    # P5 — Delta Sharing (tasks 5.3/5.7): the protocol access set
    # (resource_type=ASSET, one row per consumer request / 401 / 429)
    # + the snapshot job's terminal outcomes (resource_type=
    # DELTA_SHARE_SNAPSHOT).
    "WAREHOUSE_SHARE_ACCESSED",
    "WAREHOUSE_SHARE_AUTH_FAILED",
    "DELTA_SHARE_RATE_LIMIT_EXCEEDED",
    "DATABRICKS_SHARE_SNAPSHOT_COMPLETED",
    "DATABRICKS_SHARE_SNAPSHOT_FAILED",
)

REQUIRED_ERROR_CODES = (
    "DATABRICKS_AUTH_FAILED",
    "DATABRICKS_CONTROL_PLANE_DISABLED",
    "DATABRICKS_WORKSPACES_DISABLED",
    "DATABRICKS_WORKSPACE_HAS_DEPENDENTS",
    "DATABRICKS_SSO_UNAVAILABLE",
    "DATABRICKS_SSO_STATE_MISMATCH",
    "DATABRICKS_OBO_REFRESH_FAILED",
    # P2 — UC write (task 2.9): the 403 execution gate + the bridge's
    # ownership/representability refusal (400, shipped by 2.6).
    "DATABRICKS_DDL_APPROVAL_REQUIRED",
    "DATABRICKS_GRANT_UNSUPPORTED",
    # P3 — SQL warehouses (task 3.5): the pool's per-tenant exhaustion
    # (429) + the hand-out tenant re-check refusal (500).
    "DATABRICKS_WAREHOUSE_POOL_EXHAUSTED",
    "DATABRICKS_WAREHOUSE_POOL_TENANT_MISMATCH",
    # P3 — SQL warehouses (task 3.3/3.8): the Hub's own state failure —
    # the compute client cannot reason about the warehouse's lifecycle
    # state (catalogued in 3.3, required by 3.8's task contract).
    "DATABRICKS_WAREHOUSE_STATE_ERROR",
    # P4 — Databricks jobs (task 4.3): the D3 gate-first refusal
    # (catalogued as it ships).
    "DATABRICKS_JOB_TASK_FORBIDDEN",
)


class TestDatabricksEventRegistration(TestCase):
    """Every databricks audit event is registered (constant + ``__all__``)."""

    def test_constants_and_all_membership(self):
        from hub.apps.audit import event_types

        for name in DATABRICKS_EVENTS:
            value = getattr(event_types, name, None)
            assert value == name, f"{name} constant missing or misnamed"
            assert name in event_types.__all__, f"{name} missing from __all__"


class TestDatabricksErrorCatalogueRows(TestCase):
    """Every REQUIRED databricks error code has a row in the canonical
    catalogue (``docs/api/error-codes.md``)."""

    def test_required_codes_are_catalogued(self):
        catalogue = (REPO_ROOT / "docs/api/error-codes.md").read_text()
        for code in REQUIRED_ERROR_CODES:
            assert f"`{code}`" in catalogue, (
                f"{code} missing from docs/api/error-codes.md catalogue"
            )

    def test_byo_runbook_documents_the_gcp_fallback(self):
        """0b.8 — the BYO runbook documents the GCP fallback: U2M is
        unsupported there, execution falls back to PAT/M2M credentials,
        and an SSO attempt surfaces DATABRICKS_SSO_UNAVAILABLE."""
        runbook = (REPO_ROOT / "docs/user-guides/databricks-control-plane.md").read_text()
        lowered = runbook.lower()
        assert "gcp" in lowered
        assert "u2m" in lowered
        assert "databricks_sso_unavailable" in lowered
        assert "pat" in lowered or "m2m" in lowered

    def test_byo_runbook_documents_app_connection_registration(self):
        """0b.9 — the customer-side "App connection" section covers the
        redirect URI, the client id, the scopes (sql / all-apis /
        offline_access, matching the 0b.2 contract), and the token TTLs
        (access-token expiry, refresh-token lifetime, half-TTL refresh,
        5-minute countdown)."""
        runbook = (REPO_ROOT / "docs/user-guides/databricks-control-plane.md").read_text()
        lowered = runbook.lower()
        assert "redirect uri" in lowered
        assert "client id" in lowered
        assert "app connection" in lowered or "app connections" in lowered
        assert "sql" in lowered
        assert "all-apis" in lowered
        assert "offline_access" in lowered
        # Token TTL guidance — access token, refresh token, and the Hub-side
        # policies (half-TTL refresh + countdown).
        assert "access token" in lowered
        assert "refresh token" in lowered
        assert "half" in lowered
        assert "countdown" in lowered
        # The canonical redirect URI shape the provider builds against.
        assert "/auth/databricks/callback" in lowered
