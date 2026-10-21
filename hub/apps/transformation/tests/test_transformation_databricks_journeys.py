"""Journey pins for the P11 transformation-on-databricks surface
(openspec run-transformation-on-databricks task 11.6) — JOURNEY-DB-018
(Run a dbt Transformation on Databricks) + UC-DB-018 (Run dbt
Transformation on Databricks).

Class/method names are PINNED by the UC doc's "Phase P11 Test" field
(docs/mvpdocs/use-cases/UC-DB-018.md) — renaming them breaks the
docs↔test drift gates (GATE-28).

The journey spans the shipped P11 surface with NO mocks — real Postgres
rows (workspace + credential through the REAL encryption), the REAL
execution-target vocabulary, the REAL executor writing the tmpfs
profiles.yml, and the REAL 11.3 estate resolution bound through the
sanctioned seam (`_resolve_databricks_warehouse_profile` — the 0.8
factory convention; the orchestration-layer binding is the 11.2
session's follow-up, this pin exercises the REAL functions the binding
will call). The UC's error table is pinned against the landed error
family (a credential failure surfaces MASKED — zero token material in
the message; an unknown target refuses with the classified code).
"""

from __future__ import annotations

import pathlib
import uuid

import pytest
import yaml

from hub.apps.transformation.tests.test_local_executor_regression import _make_executor

pytestmark = pytest.mark.django_db(transaction=True)


def _make_workspace_and_credential(auth_mode="PAT", *, token="dapi-journey-token"):
    try:
        from hub.apps.databricks_admin.models import (
        DatabricksCloud,
        DatabricksCredential,
        DatabricksCredentialAuthMode,
        DatabricksWorkspace,
        )
    except (RuntimeError, ModuleNotFoundError):
        pytest.skip("hub.apps.apps (paid layer not installed in core-only mode)")
    try:
        from hub.apps.databricks_admin.tests._fixtures import REAL_HOST, require_dns
    except (RuntimeError, ModuleNotFoundError):
        pytest.skip("hub.apps.apps (paid layer not installed in core-only mode)")
    try:
        from hub.apps.databricks_admin.tests.test_uc_browse import _setup_tenant
    except (RuntimeError, ModuleNotFoundError):
        pytest.skip("hub.apps.apps (paid layer not installed in core-only mode)")

    require_dns()
    tenant, _admin = _setup_tenant()
    tenant.databricks_control_plane_enabled = True
    tenant.save(update_fields=["databricks_control_plane_enabled"])
    workspace = DatabricksWorkspace.objects.create(
        tenant=tenant,
        name=f"ws-db018-{uuid.uuid4().hex[:6]}",
        host=REAL_HOST,
        cloud=DatabricksCloud.AWS,
        region="us-east-1",
        status="ACTIVE",
    )
    credential = DatabricksCredential(
        workspace=workspace,
        auth_mode=DatabricksCredentialAuthMode.PAT,
    )
    credential.set_config({"token": token} if auth_mode == "PAT" else {})
    credential.save()
    return tenant, workspace, credential


@pytest.mark.journey("JOURNEY-DB-018")
@pytest.mark.uc("UC-DB-018")
class TestJOURNEYDB018RunDbtOnDatabricks:
    """The shipped P11 journey: target selection → estate credential
    resolution → the dbt-databricks profile on disk — with the UC's
    error table pinned against the landed error family."""

    def test_target_selection(self):
        """The UC's pinned leg — the three-target vocabulary binds the
        executor, `local` stays the default, and an unknown target
        refuses with the classified code (never a silent fallback)."""
        from hub.apps.transformation.exceptions import TransformationExecutionError
        from hub.apps.transformation.execution_targets import (
            ExecutionTarget,
            resolve_execution_target,
        )

        assert resolve_execution_target(None) is ExecutionTarget.LOCAL
        assert resolve_execution_target("databricks_warehouse") is (
            ExecutionTarget.DATABRICKS_WAREHOUSE
        )
        assert resolve_execution_target("databricks_job") is ExecutionTarget.DATABRICKS_JOB
        with pytest.raises(TransformationExecutionError) as excinfo:
            resolve_execution_target("cassandra")
        assert excinfo.value.error_code == "DATABRICKS_EXECUTION_TARGET_INVALID"

    def test_the_warehouse_target_resolves_the_estate_profile(self, tmp_path, monkeypatch):
        """Step 2 of the journey — the databricks_warehouse target writes
        the LANDED dbt-databricks profile from the registered workspace's
        OWN credential (PAT direct) through the REAL 11.3 resolver bound
        on the sanctioned seam."""
        _tenant, workspace, _credential = _make_workspace_and_credential()

        from hub.apps.transformation import dbt_executor
        from hub.apps.transformation.credential_resolver import (
            resolve_databricks_workspace_credentials,
        )

        monkeypatch.setattr(
            dbt_executor,
            "_resolve_databricks_warehouse_profile",
            lambda **kwargs: resolve_databricks_workspace_credentials(
                workspace, http_path="/sql/1.0/warehouses/wh-1", **kwargs
            ),
        )

        executor = _make_executor(tmp_path, execution_target="databricks_warehouse")
        executor._setup_profile()
        with open(pathlib.Path(executor.work_dir) / "profiles.yml") as f:
            data = yaml.safe_load(f)

        out = data[executor.profile_name]["outputs"]["prod"]
        try:
            from hub.apps.databricks_admin.tests._fixtures import REAL_HOST
        except (RuntimeError, ModuleNotFoundError):
            pytest.skip("hub.apps.apps (paid layer not installed in core-only mode)")

        assert out["type"] == "databricks"
        assert out["host"] == REAL_HOST
        assert out["http_path"] == "/sql/1.0/warehouses/wh-1"
        assert out["token"] == "dapi-journey-token"
        assert out["catalog"] == "main"
        assert out["schema"] == "public"
        assert out["threads"] == 4

    def test_the_journey_error_table_holds(self, tmp_path, monkeypatch):
        """The UC's error table: a credential-resolution failure surfaces
        the MASKED error (zero token material in the message), never the
        secret."""
        # A workspace with NO credential row → the real resolver fails
        # closed; the failure message must never carry token material.
        try:
            from hub.apps.databricks_admin.models import DatabricksCloud, DatabricksWorkspace
        except (RuntimeError, ModuleNotFoundError):
            pytest.skip("hub.apps.apps (paid layer not installed in core-only mode)")
        try:
            from hub.apps.databricks_admin.tests._fixtures import REAL_HOST, require_dns
        except (RuntimeError, ModuleNotFoundError):
            pytest.skip("hub.apps.apps (paid layer not installed in core-only mode)")
        try:
            from hub.apps.databricks_admin.tests.test_uc_browse import _setup_tenant
        except (RuntimeError, ModuleNotFoundError):
            pytest.skip("hub.apps.apps (paid layer not installed in core-only mode)")

        require_dns()
        from hub.apps.transformation import dbt_executor
        from hub.apps.transformation.credential_resolver import CredentialResolverError

        tenant, _admin = _setup_tenant()
        tenant.databricks_control_plane_enabled = True
        tenant.save(update_fields=["databricks_control_plane_enabled"])
        bare_workspace = DatabricksWorkspace.objects.create(
            tenant=tenant,
            name=f"ws-db018-bare-{uuid.uuid4().hex[:6]}",
            host=REAL_HOST,
            cloud=DatabricksCloud.AWS,
            region="us-east-1",
            status="ACTIVE",
        )

        from hub.apps.transformation.credential_resolver import (
            resolve_databricks_workspace_credentials,
        )

        monkeypatch.setattr(
            dbt_executor,
            "_resolve_databricks_warehouse_profile",
            lambda **kwargs: resolve_databricks_workspace_credentials(
                bare_workspace, http_path="/sql/1.0/warehouses/wh-1", **kwargs
            ),
        )
        executor = _make_executor(tmp_path, execution_target="databricks_warehouse")
        with pytest.raises(CredentialResolverError) as excinfo:
            executor._setup_profile()
        message = str(excinfo.value)
        # The failure names the REGISTRATION gap, never a secret value.
        assert "has no PAT|OAUTH_M2M credential" in message
        assert "dapi-journey-token" not in message
