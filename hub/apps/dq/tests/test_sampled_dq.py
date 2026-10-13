"""275.E.1 — sampled DQ runs (TDD RED→GREEN).

Phase 275.E.1 requires ``DQRun.sampled`` so sampled-DQ (LIMIT-N) runs are
distinguishable from full-scan runs.  These tests pin the contract:

1. ``create_dq_run(sample_limit=N)`` persists ``sampled=True`` and records
   the limit in ``details_json``.
2. ``run_warehouse_dq`` forwards the sample limit so the executed SQL is
   capped with ``LIMIT N`` and the produced DQRun carries ``sampled=True``.
"""

from __future__ import annotations

import pytest

from hub.apps.tenants.models import Tenant


@pytest.mark.django_db
def test_create_dq_run_with_sample_limit_marks_sampled():
    """A run created with a sample limit must persist sampled=True + limit."""
    from hub.apps.dq.services import DQService

    tenant = Tenant.objects.create(
        name="sampled-dq-tenant", slug=f"sampled-dq-{pytest.importorskip('uuid').uuid4().hex[:8]}"
    )
    from hub.apps.users.models import User, UserStatus

    user = User.objects.create_user(
        email=f"sampled-dq-{__import__('uuid').uuid4().hex[:8]}@meshant.test",
        password="testpass",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )

    from hub.apps.assets.models import Asset, AssetStatus

    asset = Asset.objects.create(
        tenant=tenant,
        key=f"sampled-dq-asset-{__import__('uuid').uuid4().hex[:8]}",
        name="Sampled DQ Asset",
        status=AssetStatus.ACTIVE,
        source_type="HUB_NATIVE",
        created_by=user,
    )

    service = DQService(tenant_id=str(tenant.id), user_id=str(user.id))
    run = service.create_dq_run(
        tenant_id=str(tenant.id),
        user_id=str(user.id),
        asset_id=str(asset.id),
        profile_key="intake_basic_gx",
        sample_limit=100,
    )

    run.refresh_from_db()
    assert run.sampled is True
    assert (run.details_json or {}).get("sample_limit") == 100

    # And a run WITHOUT a sample limit stays a full scan.
    run2 = service.create_dq_run(
        tenant_id=str(tenant.id),
        user_id=str(user.id),
        asset_id=str(asset.id),
        profile_key="intake_basic_gx",
    )
    run2.refresh_from_db()
    assert run2.sampled is False


@pytest.mark.django_db
def test_scan_inmemory_warehouse_applies_sample_limit():
    """scan_inmemory_warehouse(sample_limit=...) caps SQL and marks sampled."""
    from unittest.mock import patch

    from hub.apps.dq.services import DQService

    tenant = Tenant.objects.create(
        name="sampled-scan-tenant",
        slug=f"sampled-scan-{__import__('uuid').uuid4().hex[:8]}",
        data_quality_advanced_enabled=True,
    )

    warehouse_config = {"table_fqn": "demo_db.public.customers", "warehouse_type": "SNOWFLAKE"}
    check_defs = [{"name": "not_null", "column": "id"}]

    from hub.apps.assets.models import Asset, AssetStatus
    from hub.apps.users.models import User, UserStatus

    user = User.objects.create_user(
        email=f"scan-{__import__('uuid').uuid4().hex[:8]}@meshant.test",
        password="testpass",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )
    asset = Asset.objects.create(
        tenant=tenant,
        key=f"scan-asset-{__import__('uuid').uuid4().hex[:8]}",
        name="Scan Asset",
        status=AssetStatus.ACTIVE,
        source_type="HUB_NATIVE",
        created_by=user,
    )

    captured_sql: list[str] = []

    class _FakeConnector:
        def __init__(self, *_a, **_kw):
            pass

        def connect(self) -> None:
            pass

        def close(self) -> None:
            pass

        def execute_query(self, sql: str, params=None):
            captured_sql.append(sql)
            return [], []

    with (
        patch(
            "hub.apps.dq.services._resolve_warehouse_connector",
            return_value=_FakeConnector(),
        ),
        patch(
            "hub.apps.dq.warehouse_sql_compiler.DQWarehouseSQLCompiler.compile",
            return_value=[
                __import__("types").SimpleNamespace(
                    sql="SELECT COUNT(*) FROM demo_db.public.customers",
                    check_name="not_null",
                    check_type="not_null",
                    column_name="id",
                )
            ],
        ),
    ):
        run = DQService.scan_inmemory_warehouse(
            tenant=tenant,
            asset=asset,
            check_definitions=check_defs,
            warehouse_config=warehouse_config,
            sample_limit=50,
        )

    assert run.sampled is True
    assert any("LIMIT 50" in sql.upper() for sql in captured_sql), captured_sql
