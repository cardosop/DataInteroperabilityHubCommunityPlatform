"""Integration tests for credential_ref on ScheduledIngestion/ScheduledExport."""
import pytest

from hub.apps.scheduled_ingestion.models import ScheduledIngestion, SourceType

pytestmark = pytest.mark.django_db(transaction=True)


class TestCredentialRefOnIngestion:
    def test_credential_ref_is_nullable(self, scheduled_ingestion):
        """credential_ref defaults to None."""
        assert scheduled_ingestion.credential_ref is None

    def test_credential_ref_can_be_set(self, scheduled_ingestion):
        """credential_ref accepts an AWS SM ARN."""
        arn = "arn:aws:secretsmanager:us-east-1:123456:secret:my-creds"
        scheduled_ingestion.credential_ref = arn
        scheduled_ingestion.save()
        scheduled_ingestion.refresh_from_db()
        assert scheduled_ingestion.credential_ref == arn

    def test_credential_ref_accepts_prefect_block(self, scheduled_ingestion):
        """credential_ref accepts a prefect:// block reference."""
        ref = "prefect://s3-reader-block"
        scheduled_ingestion.credential_ref = ref
        scheduled_ingestion.save()
        scheduled_ingestion.refresh_from_db()
        assert scheduled_ingestion.credential_ref == ref


class TestWarehouseSourceTypes:
    def test_snowflake_source_exists(self):
        """SNOWFLAKE_SOURCE is in the SourceType enum."""
        assert hasattr(SourceType, "SNOWFLAKE_SOURCE")
        assert SourceType.SNOWFLAKE_SOURCE.value == "SNOWFLAKE_SOURCE"

    def test_bigquery_source_exists(self):
        """BIGQUERY_SOURCE is in the SourceType enum."""
        assert hasattr(SourceType, "BIGQUERY_SOURCE")

    def test_databricks_source_exists(self):
        """DATABRICKS_SOURCE is in the SourceType enum."""
        assert hasattr(SourceType, "DATABRICKS_SOURCE")

    def test_athena_source_exists(self):
        """ATHENA_SOURCE is in the SourceType enum."""
        assert hasattr(SourceType, "ATHENA_SOURCE")

    def test_all_values_in_enum(self):
        """All new values are present in SourceType.values."""
        for val in [
            "SNOWFLAKE_SOURCE",
            "BIGQUERY_SOURCE",
            "DATABRICKS_SOURCE",
            "ATHENA_SOURCE",
        ]:
            assert val in SourceType.values

    def test_new_sources_can_be_used_on_model(self, tenant):
        """ScheduledIngestion accepts warehouse source types."""
        obj = ScheduledIngestion.objects.create(
            tenant=tenant,
            name=f"wh-test-{SourceType.SNOWFLAKE_SOURCE.value}",
            source_type=SourceType.SNOWFLAKE_SOURCE.value,
            source_config={"host": "test.snowflakecomputing.com", "database": "DB", "schema": "PUBLIC"},
            schedule_type="DAILY",
            schedule_config={"time": "02:00"},
            file_pattern=".*",
            created_by=None,
        )
        assert obj.source_type == "SNOWFLAKE_SOURCE"
