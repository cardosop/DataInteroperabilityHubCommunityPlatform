import os
import uuid

import psycopg2
import pytest
from psycopg2 import sql

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


def _db_url_for_role(role_name: str) -> str:
    # Always construct the URL from POSTGRES_* env vars — never use
    # os.environ.get("DATABASE_URL") which is set by .env.dev to a
    # Docker hostname ("postgres") that doesn't resolve outside Docker.
    postgres_db = os.environ.get("POSTGRES_DB", "hub_test_test_shared")
    test_db_suffix = os.environ.get("TEST_DB_SUFFIX", "")
    if test_db_suffix and not postgres_db.endswith(f"_test_{test_db_suffix}"):
        db_name = f"{postgres_db}_test_{test_db_suffix}"
    else:
        db_name = postgres_db

    base_url = (
        "postgresql://"
        f"{os.environ.get('POSTGRES_USER', 'hub_test')}:"
        f"{os.environ.get('POSTGRES_PASSWORD', 'hub_test')}@"
        f"{os.environ.get('POSTGRES_HOST', 'localhost')}:"
        f"{os.environ.get('POSTGRES_PORT', '5432')}/"
        f"{db_name}"
    )

    if role_name == "meshant_app":
        return os.environ.get("DATABASE_URL_APP") or base_url
    if role_name == "meshant_admin":
        return os.environ.get("DATABASE_URL_ADMIN") or base_url
    raise ValueError(f"Unsupported role name: {role_name}")


def _select_count_as_role(table_name: str, role_name: str) -> int:
    database_url = _db_url_for_role(role_name)
    with psycopg2.connect(database_url) as conn:
        conn.autocommit = True
        with conn.cursor() as cursor:
            try:
                cursor.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(role_name)))
            except psycopg2.Error as exc:
                pytest.skip(
                    f"Role '{role_name}' not available: {exc}. "
                    "Create the role with 'CREATE ROLE meshant_app WITH LOGIN' in the test database, "
                    "then grant USAGE on the schema and re-run."
                )
            # Register app.current_tenant_id as a placeholder so that RLS
            # policies referencing current_setting('app.current_tenant_id')
            # (without missing_ok=true) do not raise UndefinedObject.  The
            # test expects meshant_app to see zero rows when the GUC is
            # unset because tenant_id = NULL::uuid evaluates to NULL.
            cursor.execute(sql.SQL("SET LOCAL app.current_tenant_id = ''"))
            cursor.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(table_name)))
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
