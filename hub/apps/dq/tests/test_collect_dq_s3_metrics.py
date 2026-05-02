"""
Phase 240.1.B.5 — TDD tests for the ``collect_dq_s3_metrics`` management
command + the ``dq_s3_payload_bytes_total`` Prometheus metric.

The collector walks the configured DQ payload S3 bucket+prefix, sums
object sizes per-tenant (the leading path segment after the prefix is
the tenant id), and updates the `dq_s3_payload_bytes_total` gauge.

We use ``moto`` (in-process AWS mock) at the boto3-API boundary so the
test exercises the *real* boto3 list_objects_v2 paginator + page
shape — no DIY mocks of S3-listing semantics that could drift from
production behaviour.
"""
from __future__ import annotations

import importlib
import io
import os
import sys
import uuid

import pytest
from django.core.management import call_command
from django.test import TransactionTestCase, override_settings

# moto is in requirements-dev.txt; skip cleanly on environments that
# don't have it (CI does).
moto = pytest.importorskip("moto")
import boto3  # noqa: E402 — after moto import per moto's docs


def _bucket_name() -> str:
    return f"dq-payloads-{uuid.uuid4().hex[:8]}"


def _put(s3, bucket: str, key: str, body: bytes) -> None:
    s3.put_object(Bucket=bucket, Key=key, Body=body)


@pytest.mark.django_db(transaction=True)
class CollectDqS3MetricsTests(TransactionTestCase):
    """Pin the contract:

    * The command walks ``s3://{DQ_S3_BUCKET}/{DQ_S3_PREFIX}`` and
      aggregates per-tenant byte totals.
    * The ``dq_s3_payload_bytes_total{tenant_id}`` gauge is set to the
      observed sum for each tenant present in the prefix.
    * The command is idempotent — re-running it returns the same
      values (no double-counting via Counter accumulation).
    * Empty / missing prefix returns success and sets no labels (the
      gauge stays at its prior value, which is 0 on a fresh process).
    """

    def setUp(self):
        from moto import mock_aws
        # Use mock_aws as a context manager that activates for the
        # whole TestCase. The boto3 client created inside the mock
        # is also seen by the command (because the command uses the
        # same default AWS region + credentials).
        os.environ["AWS_ACCESS_KEY_ID"] = "testing"
        os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
        os.environ["AWS_SESSION_TOKEN"] = "testing"
        os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
        self._mock = mock_aws()
        self._mock.start()
        self._bucket = _bucket_name()
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket=self._bucket)
        self._s3 = s3

    def tearDown(self):
        self._mock.stop()

    def _run(self):
        out = io.StringIO()
        with override_settings(
            DQ_S3_BUCKET=self._bucket,
            DQ_S3_PREFIX="dq/",
        ):
            call_command("collect_dq_s3_metrics", stdout=out)
        return out.getvalue()

    @staticmethod
    def _gauge_value(tenant_id: str) -> float:
        from services.shared.metrics import dq_s3_payload_bytes_total
        try:
            sample = (
                dq_s3_payload_bytes_total.labels(
                    service="hub", tenant_id=tenant_id,
                )
            )
            # prometheus_client Gauge stores its current value at ._value
            return float(sample._value.get())
        except Exception:
            return 0.0

    def test_per_tenant_aggregation(self):
        tenant_a = str(uuid.uuid4())
        tenant_b = str(uuid.uuid4())
        _put(self._s3, self._bucket, f"dq/{tenant_a}/run-1.json", b"x" * 100)
        _put(self._s3, self._bucket, f"dq/{tenant_a}/run-2.json", b"x" * 250)
        _put(self._s3, self._bucket, f"dq/{tenant_b}/run-1.json", b"x" * 75)

        self._run()

        self.assertEqual(self._gauge_value(tenant_a), 350.0)
        self.assertEqual(self._gauge_value(tenant_b), 75.0)

    def test_idempotent_rerun(self):
        tenant = str(uuid.uuid4())
        _put(self._s3, self._bucket, f"dq/{tenant}/run-1.json", b"x" * 500)

        self._run()
        first = self._gauge_value(tenant)
        self._run()
        second = self._gauge_value(tenant)
        self.assertEqual(first, second, msg="gauge MUST be set, not added")
        self.assertEqual(first, 500.0)

    def test_empty_prefix_does_not_error(self):
        # Bucket exists but no objects under dq/ prefix — collector
        # MUST exit cleanly (the gauge keeps prior values; on a fresh
        # process no labels are set).
        out = self._run()
        # Stdout should mention zero objects scanned for diagnostics.
        self.assertIn("0", out)

    def test_objects_outside_prefix_ignored(self):
        tenant = str(uuid.uuid4())
        # Real DQ object under the prefix.
        _put(self._s3, self._bucket, f"dq/{tenant}/run-1.json", b"x" * 200)
        # A non-DQ object outside the prefix MUST NOT contribute.
        _put(self._s3, self._bucket, "uploads/some-other-file.csv", b"x" * 9999)

        self._run()
        self.assertEqual(self._gauge_value(tenant), 200.0)

    def test_tenant_id_segment_is_first_path_component_after_prefix(self):
        """`dq/<tenant_id>/<rest>` — the segment immediately after the
        prefix is the tenant id; deeper subkeys are summed under that
        tenant."""
        tenant = str(uuid.uuid4())
        _put(self._s3, self._bucket, f"dq/{tenant}/sub/dir/run-1.json", b"x" * 300)
        _put(self._s3, self._bucket, f"dq/{tenant}/run-2.json", b"x" * 100)

        self._run()
        self.assertEqual(self._gauge_value(tenant), 400.0)
