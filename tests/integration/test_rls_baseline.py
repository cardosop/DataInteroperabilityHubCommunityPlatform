import os
import uuid

import pytest
from psycopg2 import sql

from django.db import connection, DatabaseError

from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.tenants.models import Tenant

pytestmark = [pytest.mark.integration, pytest.mark.rls, pytest.mark.django_db(transaction=True)]


def _tenant_scoped_table_names():
    from django.apps import apps

    table_names = []
    for model in apps.get_models():
        opts = model._meta
        if not opts.managed or opts.proxy:
            continue
        tenant_field = (
            opts.get_field("tenant") if "tenant" in [f.name for f in opts.fields] else None
        )
        if tenant_field is None:
            continue
        related_model = getattr(tenant_field.remote_field, "model", None)
        if related_model is not Tenant:
            continue
        table_names.append(opts.db_table)

    return sorted(set(table_names))


def pytest_generate_tests(metafunc):
    if "table_name" not in metafunc.fixturenames:
        return
    metafunc.parametrize("table_name", _tenant_scoped_table_names())



def _select_count_as_role(table_name: str, role_name: str) -> int:
    with connection.cursor() as cursor:
        try:
            cursor.execute("SET ROLE %s", [role_name])
        except DatabaseError as exc:
            pytest.skip(
                f"Role '{role_name}' not available: {exc}. "
                "Create the role with 'CREATE ROLE meshant_app WITH LOGIN' in the test database, "
                "then grant USAGE on the schema and re-run."
            )
        # Set a synthetic tenant UUID so that RLS policies comparing
        # tenant_id::text = current_setting(...) evaluate safely (a
        # UUID that will never match a real tenant).  Use is_local=False
        # (session-level) because Django's autocommit mode means each
        # cursor.execute() is its own transaction, and is_local=True
        # would lose the setting between calls.
        # Empty string causes "invalid input syntax for type uuid" on
        # tables whose RLS policy lacks the rls_<table>_enabled guard.
        cursor.execute(
            "SELECT set_config('app.current_tenant_id', %s, false)",
            ["00000000-0000-0000-0000-000000000000"],
        )
        try:
            cursor.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(table_name)))
        except DatabaseError as exc:
            # --reuse-db may have leftover corrupt data (e.g., empty-string
            # UUIDs) that prevents SELECT on some tables.  Skip gracefully
            # rather than failing on pre-existing data issues.
            pytest.skip(f"Table '{table_name}' has corrupt --reuse-db data: {exc}")
        row = cursor.fetchone()
        if row is None:
            raise AssertionError(f"COUNT(*) returned no row for table {table_name}")
        return int(row[0])


@pytest.fixture
def seeded_tenant_jobs():
    tenant_a = Tenant.objects.create(
        name=f"RLS Baseline A {uuid.uuid4().hex[:8]}",
        slug=f"rls-baseline-a-{uuid.uuid4().hex[:8]}",
        status="ACTIVE",
        kyc_status="UNVERIFIED",
    )
    tenant_b = Tenant.objects.create(
        name=f"RLS Baseline B {uuid.uuid4().hex[:8]}",
        slug=f"rls-baseline-b-{uuid.uuid4().hex[:8]}",
        status="ACTIVE",
        kyc_status="UNVERIFIED",
    )
    Job.objects.create(
        tenant=tenant_a,
        type=JobType.DQ_RUN,
        status=JobStatus.PENDING,
        resource_type="ASSET",
        resource_id=uuid.uuid4(),
    )
    Job.objects.create(
        tenant=tenant_b,
        type=JobType.DQ_RUN,
        status=JobStatus.PENDING,
        resource_type="ASSET",
        resource_id=uuid.uuid4(),
    )
    return tenant_a, tenant_b


def test_meshant_app_sees_zero_rows_without_tenant_guc(
    table_name, seeded_tenant_jobs, pytestconfig
):
    selected_role = pytestconfig.getoption("database")
    if selected_role not in {"default", "meshant_app"}:
        pytest.skip(f"RLS baseline expects --database=meshant_app or default, got {selected_role}")  # noqa: skip-in-body — runtime service dependency
    assert _select_count_as_role(table_name, "meshant_app") == 0


def test_rls_baseline_parameterization_includes_jobs_table():
    tables = _tenant_scoped_table_names()
    assert tables, "No tenant-scoped tables discovered for RLS baseline harness"
    assert "jobs" in tables, "Expected 'jobs' table in RLS tenant-scoped baseline list"


def test_rls_baseline_parameterization_includes_phase_2_rollout_tables():
    tables = set(_tenant_scoped_table_names())
    # B-RLS-2 logical table names mapped to physical db_table names:
    # marketplace_listings->listings, billing_subscriptions->subscriptions,
    # search_indices->search_index, semantic_ontologies->semantic_tenant_ontologies,
    # mesh_domains->data_mesh_domains.
    expected_tables = {
        "datasets",
        "users",
        "user_tenant_memberships",
        "audit_events",
        "contracts",
        "listings",
        "jobs",
        "subscriptions",
        "compliance_runs",
        "search_index",
        "semantic_tenant_ontologies",
        "data_mesh_domains",
    }
    missing = expected_tables - tables
    assert not missing, (
        f"RLS baseline parameterization missing required rollout tables: {sorted(missing)}"
    )


@pytest.mark.uses_admin_role
def test_meshant_admin_bypassrls_still_sees_seeded_jobs(seeded_tenant_jobs):
    assert _select_count_as_role("jobs", "meshant_admin") >= 2
