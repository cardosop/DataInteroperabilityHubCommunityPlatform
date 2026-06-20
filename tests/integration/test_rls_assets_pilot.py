import uuid
from contextlib import contextmanager

import pytest
from django.db import connection, transaction

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.tenants.models import Tenant
from hub.apps.tenants.request_tenant import tenant_context

pytestmark = [
    pytest.mark.integration,
    pytest.mark.rls,
    pytest.mark.django_db(transaction=True),
]


@contextmanager
def _set_role(role_name: str):
    if role_name not in {"meshant_app", "meshant_admin"}:
        raise ValueError(f"Unsupported role_name: {role_name}")
    with connection.cursor() as cursor:
        # role_name is allowlisted above; never interpolate user input.
        cursor.execute(f"SET ROLE {role_name}")
    try:
        yield
    finally:
        with connection.cursor() as cursor:
            cursor.execute("RESET ROLE")


@pytest.fixture
def seeded_assets():
    tenant_a = Tenant.objects.create(
        name=f"RLS Asset A {uuid.uuid4().hex[:8]}",
        slug=f"rls-assets-a-{uuid.uuid4().hex[:8]}",
        status="ACTIVE",
        kyc_status="UNVERIFIED",
    )
    tenant_b = Tenant.objects.create(
        name=f"RLS Asset B {uuid.uuid4().hex[:8]}",
        slug=f"rls-assets-b-{uuid.uuid4().hex[:8]}",
        status="ACTIVE",
        kyc_status="UNVERIFIED",
    )
    asset_a = Asset.objects.create(
        tenant=tenant_a,
        key=f"a-{uuid.uuid4().hex[:8]}",
        name="Asset A",
        status=AssetStatus.ACTIVE,
    )
    asset_b = Asset.objects.create(
        tenant=tenant_b,
        key=f"b-{uuid.uuid4().hex[:8]}",
        name="Asset B",
        status=AssetStatus.ACTIVE,
    )
    return tenant_a, tenant_b, asset_a, asset_b


def _count_assets_raw() -> int:
    with connection.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM assets")
        row = cursor.fetchone()
    if row is None:
        raise AssertionError("Expected COUNT(*) row from assets query")
    return int(row[0])


def test_assets_rls_blocks_reads_without_tenant_guc(seeded_assets, pytestconfig):
    selected_role = pytestconfig.getoption("database")
    if selected_role not in {"default", "meshant_app"}:
        pytest.skip(  # noqa: skip-in-body — runtime service dependency
            f"assets pilot RLS test expects --database=meshant_app or default, got {selected_role}"
        )
    with _set_role("meshant_app"):
        assert _count_assets_raw() == 0


def test_assets_rls_scopes_orm_reads_by_tenant_context(seeded_assets, pytestconfig):
    selected_role = pytestconfig.getoption("database")
    if selected_role not in {"default", "meshant_app"}:
        pytest.skip(  # noqa: skip-in-body — runtime service dependency
            f"assets pilot RLS test expects --database=meshant_app or default, got {selected_role}"
        )
    tenant_a, _, asset_a, _ = seeded_assets
    with _set_role("meshant_app"):
        assert list(Asset.objects.values_list("id", flat=True)) == []
        with tenant_context(str(tenant_a.id)):
            visible_asset_ids = list(Asset.objects.order_by("id").values_list("id", flat=True))
        assert visible_asset_ids == [asset_a.id]


def test_assets_rls_kill_switch_guc_off_exposes_all_rows(seeded_assets, pytestconfig):
    selected_role = pytestconfig.getoption("database")
    if selected_role not in {"default", "meshant_app"}:
        pytest.skip(  # noqa: skip-in-body — runtime service dependency
            f"assets pilot RLS test expects --database=meshant_app or default, got {selected_role}"
        )
    with _set_role("meshant_app"), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL app.rls_assets_enabled = 'false'")
        assert _count_assets_raw() == 2
