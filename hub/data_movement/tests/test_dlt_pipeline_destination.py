"""285.6 ingestion destination binding.

The dlt filesystem destination REQUIRES ``bucket_url`` and no runtime
config source provided one (no env/TOML in the containers) — dlt raised
``ConfigFieldMissingException: Missing 1 field(s) in configuration
``FilesystemDestinationClientConfiguration``: ``bucket_url``` at
``step=sync`` and every scheduled-ingestion run FAILED
(JOURNEY-INGESTION-001 E2E). The pipeline must bind the staging bucket
from ``settings.DLT_FILESYSTEM_BUCKET_URL`` — never rely on dlt's
config discovery.
"""

import pytest
from django.test import SimpleTestCase, override_settings

from hub.data_movement.dlt_pipeline import DataMovementPipeline

pytestmark = pytest.mark.django_db(transaction=False)


class IngestionDestinationBindingTest(SimpleTestCase):
    """The ingestion pipeline's filesystem destination carries the
    settings-configured bucket_url without any external dlt config."""

    @override_settings(DLT_FILESYSTEM_BUCKET_URL="file:///app/dlt-staging")
    def test_ingestion_destination_binds_bucket_url_from_settings(self):
        pipeline = DataMovementPipeline(direction="ingestion", pipeline_name="bind-test")
        dest = pipeline._resolve_destination()
        params = getattr(dest, "config_params", {})
        self.assertEqual(params.get("bucket_url"), "file:///app/dlt-staging")

    def test_default_bucket_url_falls_back_to_worker_local_dir(self):
        pipeline = DataMovementPipeline(direction="ingestion", pipeline_name="bind-test")
        dest = pipeline._resolve_destination()
        params = getattr(dest, "config_params", {})
        self.assertTrue(params.get("bucket_url", "").startswith("file://"))


def test_explicit_dlt_config_wins_over_settings_binding(monkeypatch, tmp_path):
    """An operator/test-supplied dlt config
    (``DESTINATION__FILESYSTEM__BUCKET_URL``) must keep precedence —
    the settings binding is a last resort only, so test fixtures and
    env-overridden deployments keep their isolated buckets."""
    bucket = tmp_path / "bucket"
    monkeypatch.setenv("DESTINATION__FILESYSTEM__BUCKET_URL", f"file://{bucket}")
    with override_settings(DLT_FILESYSTEM_BUCKET_URL="file:///app/dlt-staging"):
        pipeline = DataMovementPipeline(direction="ingestion", pipeline_name="bind-test")
        dest = pipeline._resolve_destination()
    params = getattr(dest, "config_params", {})
    assert "bucket_url" not in params
