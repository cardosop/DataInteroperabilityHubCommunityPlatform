"""
285.10.1.1 — Tests for WarehouseQueryRunner, TableFQN, and FakeWarehouseQueryRunner.
"""
import pytest
from hub.data_movement.warehouse_query_runner import (
    TableFQN,
    ReadOnlyGuard,
    WarehouseIdempotencyKey,
    FakeWarehouseQueryRunner,
)


# ── TableFQN tests ────────────────────────────────────────────────────


class TestTableFQN:
    def test_snowflake_fqn(self):
        fqn = TableFQN("ANALYTICS.PUBLIC.CUSTOMERS", "snowflake")
        assert fqn.database == "ANALYTICS"
        assert fqn.schema_name == "PUBLIC"
        assert fqn.table_name == "CUSTOMERS"
        assert fqn.quoted() == '"ANALYTICS"."PUBLIC"."CUSTOMERS"'
        assert fqn.unqualified() == "CUSTOMERS"
        assert fqn.schema_qualified() == "PUBLIC.CUSTOMERS"

    def test_bigquery_fqn(self):
        fqn = TableFQN("my-project.analytics.customers", "bigquery")
        assert fqn.database == "my-project"
        assert fqn.schema_name == "analytics"
        assert fqn.table_name == "customers"
        assert fqn.quoted() == "`my-project`.`analytics`.`customers`"
        assert fqn.unqualified() == "customers"

    def test_databricks_fqn(self):
        fqn = TableFQN("main.dbt_schema.output_table", "databricks")
        assert fqn.database == "main"
        assert fqn.schema_name == "dbt_schema"
        assert fqn.table_name == "output_table"
        assert fqn.quoted() == "`main`.`dbt_schema`.`output_table`"
        assert fqn.schema_qualified() == "dbt_schema.output_table"

    def test_two_part_fqn(self):
        fqn = TableFQN("public.customers", "snowflake")
        assert fqn.database == ""
        assert fqn.schema_name == "public"
        assert fqn.table_name == "customers"

    def test_one_part_fqn(self):
        fqn = TableFQN("customers", "snowflake")
        assert fqn.database == ""
        assert fqn.schema_name == ""
        assert fqn.table_name == "customers"
        assert fqn.unqualified() == "customers"

    def test_unsupported_warehouse_defaults(self):
        fqn = TableFQN("a.b.c", "athena")
        # Defaults to basic split
        assert fqn.table_name == "c"


# ── ReadOnlyGuard tests ────────────────────────────────────────────────


class TestReadOnlyGuard:
    def test_select_allowed(self):
        ReadOnlyGuard.check("SELECT * FROM customers")

    def test_with_cte_allowed(self):
        ReadOnlyGuard.check("WITH cte AS (SELECT * FROM t) SELECT * FROM cte")

    def test_insert_rejected(self):
        with pytest.raises(ValueError, match="INSERT"):
            ReadOnlyGuard.check("INSERT INTO t VALUES (1)")

    def test_update_rejected(self):
        with pytest.raises(ValueError, match="UPDATE"):
            ReadOnlyGuard.check("UPDATE t SET x=1")

    def test_delete_rejected(self):
        with pytest.raises(ValueError, match="DELETE"):
            ReadOnlyGuard.check("DELETE FROM t")

    def test_drop_rejected(self):
        with pytest.raises(ValueError, match="DROP"):
            ReadOnlyGuard.check("DROP TABLE t")

    def test_alter_rejected(self):
        with pytest.raises(ValueError, match="ALTER"):
            ReadOnlyGuard.check("ALTER TABLE t ADD COLUMN x INT")

    def test_truncate_rejected(self):
        with pytest.raises(ValueError, match="TRUNCATE"):
            ReadOnlyGuard.check("TRUNCATE TABLE t")

    def test_create_rejected(self):
        with pytest.raises(ValueError, match="CREATE"):
            ReadOnlyGuard.check("CREATE TABLE t (x INT)")

    def test_grant_rejected(self):
        with pytest.raises(ValueError, match="GRANT"):
            ReadOnlyGuard.check("GRANT SELECT ON t TO user")

    def test_case_insensitive(self):
        with pytest.raises(ValueError):
            ReadOnlyGuard.check("insert into t values (1)")

    def test_null_sql_allowed(self):
        ReadOnlyGuard.check("")  # empty string allowed
        ReadOnlyGuard.check(None)  # None allowed


# ── Idempotency tests ─────────────────────────────────────────────────


class TestIdempotencyKey:
    def test_composite_key_format(self):
        key = WarehouseIdempotencyKey(
            table_fqn="analytics.public.customers",
            check_definition_hash="abc123",
            table_last_modified="2026-05-19T10:00:00Z",
        )
        assert "analytics.public.customers" in str(key)
        assert "abc123" in str(key)

    def test_equality(self):
        a = WarehouseIdempotencyKey("t", "h1", "ts1")
        b = WarehouseIdempotencyKey("t", "h1", "ts1")
        assert a == b
        assert hash(a) == hash(b)

    def test_inequality(self):
        a = WarehouseIdempotencyKey("t1", "h1", "ts")
        b = WarehouseIdempotencyKey("t2", "h1", "ts")
        assert a != b


# ── FakeWarehouseQueryRunner tests ────────────────────────────────────


class TestFakeWarehouseQueryRunner:
    def test_execute_returns_rows(self):
        fake = FakeWarehouseQueryRunner(
            rows=[{"id": 1, "name": "test"}, {"id": 2, "name": "test2"}],
        )
        result = fake.execute("SELECT * FROM t")
        assert len(result) == 2
        assert result[0]["name"] == "test"

    def test_execute_aggregate(self):
        fake = FakeWarehouseQueryRunner(
            aggregate_result={"count": 100, "avg": 3.5},
        )
        result = fake.execute_aggregate("SELECT COUNT(*), AVG(x) FROM t")
        assert result["count"] == 100

    def test_get_table_schema(self):
        fake = FakeWarehouseQueryRunner(
            schema=[
                {"name": "id", "type": "integer", "nullable": False},
                {"name": "name", "type": "varchar", "nullable": True},
            ],
        )
        schema = fake.get_table_schema("t")
        assert len(schema) == 2

    def test_read_only_guard_respected(self):
        fake = FakeWarehouseQueryRunner()
        with pytest.raises(ValueError, match="DROP"):
            fake.execute("DROP TABLE t")

    def test_write_sql_injected(self):
        fake = FakeWarehouseQueryRunner(rows=[{"x": 1}])
        with pytest.raises(ValueError, match="INSERT"):
            fake.execute("SELECT * FROM t; INSERT INTO t VALUES (1)")

    def test_cost_tracking_accumulates(self):
        fake = FakeWarehouseQueryRunner()
        fake.execute("SELECT * FROM t")
        fake.execute("SELECT * FROM u")
        assert fake.total_cost > 0
        assert fake.query_count == 2
