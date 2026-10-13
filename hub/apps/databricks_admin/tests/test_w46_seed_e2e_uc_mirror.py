"""W4.6 (openspec oss-release-remediation, G1) — TDD pins for the moved
E2E UC-mirror seed command (``seed_e2e_uc_mirror``).

No mocks: the REAL command over real Postgres rows (the W4.3
offboarding-sweep convention — plain pytest functions under
``transaction=True``). The command seeds the JOURNEY-DB-005/006 chain
(workspace e2e-databricks → e2e_main.e2e_sales.e2e_orders) inside
``tenant_context`` — the RLS management-command contract the pre-move
block violated (unarmed estate writes).
"""

from __future__ import annotations

import uuid

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from hub.apps.tenants.models import Tenant

pytestmark = pytest.mark.django_db(transaction=True)


def _make_tenant() -> Tenant:
    uid = uuid.uuid4().hex[:8]
    return Tenant.objects.create(name=f"mirror-{uid}", slug=f"mirror-{uid}")


def _mirror_rows(tenant):
    from hub.apps.databricks_admin.models import (
        DatabricksWorkspace,
        UCCatalog,
        UCSchema,
        UCTable,
    )

    return (
        DatabricksWorkspace.objects.filter(tenant=tenant, name="e2e-databricks"),
        UCCatalog.objects.filter(workspace__tenant=tenant, name="e2e_main"),
        UCSchema.objects.filter(catalog__workspace__tenant=tenant, name="e2e_sales"),
        UCTable.objects.filter(
            schema__catalog__workspace__tenant=tenant, name="e2e_orders"
        ),
    )


class TestSeedE2eUcMirrorCommand:
    def test_seeds_the_full_chain_with_real_rows(self):
        tenant = _make_tenant()
        call_command("seed_e2e_uc_mirror", str(tenant.id))

        workspaces, catalogs, schemas, tables = _mirror_rows(tenant)
        assert workspaces.count() == 1
        assert catalogs.count() == 1
        assert schemas.count() == 1
        assert tables.count() == 1

        # The JOURNEY-DB-005/006 drill contract: the catalog browser
        # renders full_name || name — the seed stamps the sync-mirroring
        # full_names unconditionally.
        table = tables.get()
        assert table.full_name == "e2e_main.e2e_sales.e2e_orders"
        assert table.columns == [{"name": "id", "type_text": "BIGINT"}]

    def test_idempotent(self):
        tenant = _make_tenant()
        call_command("seed_e2e_uc_mirror", str(tenant.id))
        call_command("seed_e2e_uc_mirror", str(tenant.id))
        workspaces, catalogs, schemas, tables = _mirror_rows(tenant)
        assert workspaces.count() == 1
        assert catalogs.count() == 1
        assert schemas.count() == 1
        assert tables.count() == 1

    def test_dry_run_writes_nothing(self):
        tenant = _make_tenant()
        call_command("seed_e2e_uc_mirror", str(tenant.id), "--dry-run")
        workspaces, catalogs, schemas, tables = _mirror_rows(tenant)
        assert workspaces.count() == 0
        assert catalogs.count() == 0
        assert schemas.count() == 0
        assert tables.count() == 0

    def test_unknown_tenant_refuses(self):
        with pytest.raises(CommandError, match="not found"):
            call_command("seed_e2e_uc_mirror", str(uuid.uuid4()))
