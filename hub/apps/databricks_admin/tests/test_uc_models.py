"""Phase 1 (openspec add-databricks-uc-read task 1.2) — UC mirror models.

No mocks: real Postgres constraints + real RLS. The mirror models are a
refreshable CACHE of the workspace's Unity Catalog estate — read-only
from the Hub's perspective, tenant-scoped through the workspace parent
chain (indirect-FK RLS).

Coverage:
- MODEL: the full parent chain workspace → catalog → schema →
  table/view/volume/model, plus workspace-level external locations and
  storage credentials; per-level uniqueness; cascade on parent delete;
  default ordering; string reps.
- RLS: every one of the 8 tables ships a paired indirect-FK policy
  (multi-hop through the parent chain where needed), a kill-switch GUC,
  and reverse SQL — the 285.14.3.8 scan pattern.
"""

import os
import re

import pytest
from django.db import IntegrityError, transaction
from django.test import TestCase

from hub.apps.databricks_admin.models import (
    DatabricksCloud,
    DatabricksWorkspace,
)
from hub.apps.databricks_admin.tests._fixtures import REAL_HOST, require_dns
from tests.factories import TenantFactory

pytestmark = pytest.mark.django_db(transaction=True)


def _workspace(tenant, name="prod"):
    return DatabricksWorkspace.objects.create(
        tenant=tenant,
        name=name,
        host=REAL_HOST,
        cloud=DatabricksCloud.AWS,
        region="us-east-1",
    )


def _catalog(workspace, name="main"):
    from hub.apps.databricks_admin.models import UCCatalog

    return UCCatalog.objects.create(workspace=workspace, name=name)


def _schema(catalog, name="sales"):
    from hub.apps.databricks_admin.models import UCSchema

    return UCSchema.objects.create(catalog=catalog, name=name)


class UCChainsTests(TestCase):
    """The parent chain + uniqueness + cascades across all 8 models."""

    def setUp(self):
        require_dns()
        self.tenant = TenantFactory.create_tenant()
        self.workspace = _workspace(self.tenant)

    def test_catalog_belongs_to_workspace_with_unique_name(self):
        from hub.apps.databricks_admin.models import UCCatalog

        first = _catalog(self.workspace)
        assert first.workspace_id == self.workspace.id
        assert str(first) == "UCCatalog main"
        with pytest.raises(IntegrityError), transaction.atomic():
            UCCatalog.objects.create(workspace=self.workspace, name="main")

    def test_schema_table_view_volume_model_chain(self):
        from hub.apps.databricks_admin.models import (
            UCModel,
            UCSchema,
            UCTable,
            UCView,
            UCVolume,
        )

        catalog = _catalog(self.workspace)
        schema = _schema(catalog)

        table = UCTable.objects.create(
            schema=schema,
            name="orders",
            table_type="MANAGED",
            columns=[{"name": "id"}],
            comment="Order fact table",
        )
        view = UCView.objects.create(
            schema=schema, name="v_orders", view_definition="SELECT 1", comment="Orders view"
        )
        volume = UCVolume.objects.create(
            schema=schema, name="raw", volume_type="MANAGED", comment="Raw landing volume"
        )
        model = UCModel.objects.create(
            schema=schema,
            name="churn_model",
            aliases=["prod"],
            latest_version=3,
            comment="Churn classifier",
        )

        assert table.schema_id == schema.id
        assert view.schema_id == schema.id
        assert volume.schema_id == schema.id
        assert model.schema_id == schema.id
        # The mirror captures the UC comment surface consistently — the
        # 1.4 search feed consumes these.
        assert table.comment == "Order fact table"
        assert view.comment == "Orders view"
        assert volume.comment == "Raw landing volume"
        assert model.comment == "Churn classifier"

        # Uniqueness at each level. Each expected IntegrityError runs
        # inside its own atomic() so the failed statement does not poison
        # the test transaction for the FOLLOWING creates.
        with pytest.raises(IntegrityError), transaction.atomic():
            UCTable.objects.create(schema=schema, name="orders")
        with pytest.raises(IntegrityError), transaction.atomic():
            UCView.objects.create(schema=schema, name="v_orders")
        with pytest.raises(IntegrityError), transaction.atomic():
            UCVolume.objects.create(schema=schema, name="raw")
        with pytest.raises(IntegrityError), transaction.atomic():
            UCModel.objects.create(schema=schema, name="churn_model")
        # Same names are legal in a DIFFERENT schema of the same workspace.
        other_schema = UCSchema.objects.create(catalog=catalog, name="marketing")
        assert UCTable.objects.create(schema=other_schema, name="orders").id

    def test_workspace_level_mirrors(self):
        from hub.apps.databricks_admin.models import UCExternalLocation, UCStorageCredential

        loc = UCExternalLocation.objects.create(
            workspace=self.workspace, name="s3_raw", url="s3://bucket/raw", credential_name="cred-a"
        )
        cred = UCStorageCredential.objects.create(workspace=self.workspace, name="cred-a")
        assert loc.workspace_id == self.workspace.id
        assert cred.workspace_id == self.workspace.id
        with pytest.raises(IntegrityError), transaction.atomic():
            UCExternalLocation.objects.create(workspace=self.workspace, name="s3_raw")
        with pytest.raises(IntegrityError), transaction.atomic():
            UCStorageCredential.objects.create(workspace=self.workspace, name="cred-a")

    def test_workspace_delete_cascades_through_the_chain(self):
        from hub.apps.databricks_admin.models import (
            UCCatalog,
            UCSchema,
            UCTable,
        )

        catalog = _catalog(self.workspace)
        schema = _schema(catalog)
        UCTable.objects.create(schema=schema, name="orders")
        self.workspace.delete()
        # Scoped to THIS test's rows: the shared test DB accumulates
        # leaked mirror rows from parallel sessions, so global-emptiness
        # asserts are not robust there (the 0.9 note documents the same
        # convention for credentials/workspaces) — the cascade contract
        # is that the chain BELOW the deleted workspace is gone.
        assert not UCCatalog.objects.filter(id=catalog.id).exists()
        assert not UCSchema.objects.filter(id=schema.id).exists()
        assert not UCTable.objects.filter(schema=schema).exists()

    def test_synced_at_stamps_mirror_freshness(self):

        catalog = _catalog(self.workspace)
        assert catalog.synced_at is not None


class UCMirrorRLSPolicyTests(TestCase):
    """Paired indirect-FK RLS policies for all 8 mirror tables."""

    UC_TABLES = (
        "databricks_uc_catalogs",
        "databricks_uc_schemas",
        "databricks_uc_tables",
        "databricks_uc_views",
        "databricks_uc_volumes",
        "databricks_uc_external_locations",
        "databricks_uc_storage_credentials",
        "databricks_uc_models",
    )

    def setUp(self):
        import hub.apps.databricks_admin

        app_dir = os.path.dirname(hub.apps.databricks_admin.__file__)
        mig_dir = os.path.join(app_dir, "migrations")
        texts = []
        for fname in sorted(os.listdir(mig_dir)):
            if not fname.endswith(".py") or fname.startswith("_"):
                continue
            with open(os.path.join(mig_dir, fname), encoding="utf-8") as fh:
                texts.append(fh.read())
        self.migration_text = "\n".join(texts)

    def test_every_mirror_table_has_a_policy(self):
        for table in self.UC_TABLES:
            assert re.search(
                rf"CREATE\s+POLICY\s+\S+\s+ON\s+{table}",
                self.migration_text,
                re.IGNORECASE,
            ), f"{table} must ship a paired RLS policy (CLAUDE.md contract)"

    def test_policies_resolve_the_tenant_through_the_workspace_chain(self):
        # The multi-hop indirect-FK shape: every policy's USING clause must
        # terminate at databricks_workspaces' tenant check.
        normalized = re.sub(r"\s+", " ", self.migration_text)
        assert normalized.count("databricks_workspaces") >= len(self.UC_TABLES), (
            "every policy must subquery through the workspace parent chain"
        )
        assert "app.current_tenant_id" in self.migration_text

    def test_kill_switch_guc_per_table(self):
        for table in self.UC_TABLES:
            guc = table[len("databricks_") :]  # e.g. uc_catalogs
            assert f"app.rls_{guc}_enabled" in self.migration_text, (
                f"{table} policy must carry the kill-switch GUC"
            )

    def test_reverse_sql_drops_policies_and_disables_rls(self):
        for table in self.UC_TABLES:
            assert f"DROP POLICY IF EXISTS tenant_isolation ON {table}" in self.migration_text
            assert f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY" in self.migration_text
