"""
Phase 240.3.D.7 — per-tenant DQ threshold override tests.

Pinned spec scenarios:

* ``Tenant.dq_input_max_bytes`` and ``Tenant.dq_sampling_threshold_rows``
  validators enforce the bounds in D240.15 (10 MiB-5 GiB and
  10 000-100 000 000 respectively); values outside the bounds raise
  ``ValidationError`` from ``Tenant.full_clean()``.
* ``DQServiceClient.run_dq`` resolves a tenant's threshold values
  and forwards them to dq-service as ``X-Tenant-Threshold-Bytes`` /
  ``X-Tenant-Threshold-Rows`` headers.
* When the tenant has both fields NULL, NO threshold headers are
  forwarded — dq-service falls back to its env defaults
  (``DQ_INPUT_TOO_LARGE_BYTES`` / ``DQ_SAMPLING_THRESHOLD_ROWS``).
* When ``tenant_id`` is not passed to ``run_dq``, NO headers are
  forwarded — preserves backwards compat with all existing
  ``run_dq`` callers (lots of them — see ``orchestration``,
  ``scheduled_ingestion``, ``transformation``, ``ml`` apps).

Real Django models + a transport-boundary stub via
``unittest.mock.patch`` only on the HTTP layer — no mocks of the
threshold-resolution logic itself.
"""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError
from django.test import TransactionTestCase

pytestmark = [pytest.mark.django_db(transaction=True)]


# ---------------------------------------------------------------------------
# Tenant validation — D240.15 bounds
# ---------------------------------------------------------------------------


def _make_tenant(**kwargs):
    from hub.apps.tenants.models import Tenant

    uid = uuid.uuid4().hex[:8]
    defaults = dict(
        name=f"Threshold Tenant {uid}",
        slug=f"threshold-tenant-{uid}",
        status="ACTIVE",
        kyc_status="UNVERIFIED",
    )
    defaults.update(kwargs)
    return Tenant.objects.create(**defaults)


# ---------------------------------------------------------------------------
# Shared fake-response factory — used by header-propagation and cache-key
# tests to stub the HTTP transport boundary without duplicating the _R inner
# class six times.
# ---------------------------------------------------------------------------


def _fake_dq_response(metadata=None):
    """Return a minimal fake ``httpx.Response``-like object for /run.

    ``status_code`` is always 200, ``raise_for_status()`` is a no-op,
    and ``json()`` returns a canonical PASS result with the optional
    *metadata* dict merged in.  This allows per-test marker injection
    for cache-pollution assertions without repeating the full payload
    shape.
    """
    _metadata = metadata or {}

    class _FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {
                "overall_status": "PASS",
                "quality_score": 100.0,
                "checks": [],
                "engine_type": "GX",
                "engine_version": "0.18",
                "profile_key": "intake_basic_gx",
                "metadata": _metadata,
            }

        @staticmethod
        def raise_for_status():
            pass

    return _FakeResponse()


class TenantThresholdValidationTests(TransactionTestCase):
    def test_default_is_null_both_fields(self):
        tenant = _make_tenant()
        assert tenant.dq_input_max_bytes is None
        assert tenant.dq_sampling_threshold_rows is None

    def test_input_max_bytes_lower_bound_10_MiB(self):
        from hub.apps.tenants.models import Tenant

        t = Tenant(
            name="lo",
            slug="lo-bound",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
            dq_input_max_bytes=10 * 1024 * 1024 - 1,  # 1 byte under
        )
        with pytest.raises(ValidationError):
            t.full_clean()

    def test_input_max_bytes_upper_bound_5_GiB(self):
        from hub.apps.tenants.models import Tenant

        t = Tenant(
            name="hi",
            slug="hi-bound",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
            dq_input_max_bytes=5 * 1024 * 1024 * 1024 + 1,  # 1 byte over
        )
        with pytest.raises(ValidationError):
            t.full_clean()

    def test_input_max_bytes_inclusive_bounds_accepted(self):
        # Bound endpoints (10 MiB and 5 GiB) MUST be accepted.
        t1 = _make_tenant(dq_input_max_bytes=10 * 1024 * 1024)
        t2 = _make_tenant(dq_input_max_bytes=5 * 1024 * 1024 * 1024)
        assert t1.dq_input_max_bytes == 10 * 1024 * 1024
        assert t2.dq_input_max_bytes == 5 * 1024 * 1024 * 1024

    def test_sampling_threshold_lower_bound_10000(self):
        from hub.apps.tenants.models import Tenant

        t = Tenant(
            name="lo",
            slug="lo-sampling",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
            dq_sampling_threshold_rows=9_999,  # below 10 000
        )
        with pytest.raises(ValidationError):
            t.full_clean()

    def test_sampling_threshold_upper_bound_100_million(self):
        from hub.apps.tenants.models import Tenant

        t = Tenant(
            name="hi",
            slug="hi-sampling",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
            dq_sampling_threshold_rows=100_000_001,  # above 100M
        )
        with pytest.raises(ValidationError):
            t.full_clean()

    def test_sampling_threshold_inclusive_bounds_accepted(self):
        t1 = _make_tenant(dq_sampling_threshold_rows=10_000)
        t2 = _make_tenant(dq_sampling_threshold_rows=100_000_000)
        assert t1.dq_sampling_threshold_rows == 10_000
        assert t2.dq_sampling_threshold_rows == 100_000_000


# ---------------------------------------------------------------------------
# DQServiceClient header propagation
# ---------------------------------------------------------------------------


class DQServiceClientHeaderForwardingTests(TransactionTestCase):
    """``DQServiceClient.run_dq(file, format, tenant_id=...)`` MUST
    forward the resolved tenant thresholds as ``X-Tenant-Threshold-*``
    headers. When the tenant has NULL values OR no tenant_id is
    supplied at all, NO threshold headers are added."""

    def test_tenant_with_overrides_propagates_both_headers(self):
        from hub.apps.dq.service_client import DQServiceClient

        tenant = _make_tenant(
            dq_input_max_bytes=200 * 1024 * 1024,  # 200 MiB
            dq_sampling_threshold_rows=500_000,
        )
        client = DQServiceClient()
        captured = {}

        def _capture_request(method, endpoint, **kwargs):
            captured["headers"] = kwargs.get("headers", {})
            captured["data"] = kwargs.get("data", {})

            return _fake_dq_response()

        with patch.object(client, "_request_with_retry", _capture_request):
            client.run_dq(
                file_content=b"a,b\n1,2\n",
                file_format="csv",
                profile_key="intake_basic_gx",
                use_cache=False,
                tenant_id=str(tenant.id),
            )

        headers = captured["headers"]
        assert headers.get("X-Tenant-Threshold-Bytes") == "209715200"
        assert headers.get("X-Tenant-Threshold-Rows") == "500000"

    def test_tenant_with_null_overrides_omits_headers(self):
        from hub.apps.dq.service_client import DQServiceClient

        tenant = _make_tenant()  # both NULL
        client = DQServiceClient()
        captured = {}

        def _capture_request(method, endpoint, **kwargs):
            captured["headers"] = kwargs.get("headers", {})

            return _fake_dq_response()

        with patch.object(client, "_request_with_retry", _capture_request):
            client.run_dq(
                file_content=b"a,b\n1,2\n",
                file_format="csv",
                profile_key="intake_basic_gx",
                use_cache=False,
                tenant_id=str(tenant.id),
            )

        headers = captured["headers"]
        assert "X-Tenant-Threshold-Bytes" not in headers
        assert "X-Tenant-Threshold-Rows" not in headers

    def test_no_tenant_id_omits_headers(self):
        """Backwards-compat: legacy callers that don't pass
        ``tenant_id`` MUST NOT see threshold headers added. The
        dq-service falls through to its env defaults — same
        behaviour as before Phase 240.3.D landed."""
        from hub.apps.dq.service_client import DQServiceClient

        client = DQServiceClient()
        captured = {}

        def _capture_request(method, endpoint, **kwargs):
            captured["headers"] = kwargs.get("headers", {})

            return _fake_dq_response()

        with patch.object(client, "_request_with_retry", _capture_request):
            client.run_dq(
                file_content=b"a,b\n1,2\n",
                file_format="csv",
                profile_key="intake_basic_gx",
                use_cache=False,
                # tenant_id intentionally omitted.
            )

        headers = captured["headers"]
        assert "X-Tenant-Threshold-Bytes" not in headers
        assert "X-Tenant-Threshold-Rows" not in headers

    def test_partial_override_propagates_only_set_field(self):
        """When only ONE threshold is set on the tenant, only that
        header is forwarded — the other falls through to the
        dq-service env default."""
        from hub.apps.dq.service_client import DQServiceClient

        tenant = _make_tenant(dq_input_max_bytes=300 * 1024 * 1024)
        client = DQServiceClient()
        captured = {}

        def _capture_request(method, endpoint, **kwargs):
            captured["headers"] = kwargs.get("headers", {})

            return _fake_dq_response()

        with patch.object(client, "_request_with_retry", _capture_request):
            client.run_dq(
                file_content=b"a,b\n1,2\n",
                file_format="csv",
                profile_key="intake_basic_gx",
                use_cache=False,
                tenant_id=str(tenant.id),
            )

        headers = captured["headers"]
        assert headers.get("X-Tenant-Threshold-Bytes") == str(300 * 1024 * 1024)
        assert "X-Tenant-Threshold-Rows" not in headers

    def test_unknown_tenant_id_omits_headers_silently(self):
        """A tenant_id that doesn't resolve to any row should NOT
        crash the call — dq-service falls back to env defaults.
        This pins the behaviour for cross-tenant test fixtures
        that may pass UUIDs that aren't in the DB."""
        from hub.apps.dq.service_client import DQServiceClient

        client = DQServiceClient()
        captured = {}

        def _capture_request(method, endpoint, **kwargs):
            captured["headers"] = kwargs.get("headers", {})

            return _fake_dq_response()

        with patch.object(client, "_request_with_retry", _capture_request):
            client.run_dq(
                file_content=b"a,b\n1,2\n",
                file_format="csv",
                profile_key="intake_basic_gx",
                use_cache=False,
                tenant_id=str(uuid.uuid4()),  # not in DB
            )

        headers = captured["headers"]
        assert "X-Tenant-Threshold-Bytes" not in headers
        assert "X-Tenant-Threshold-Rows" not in headers


# ---------------------------------------------------------------------------
# Cache-key isolation across tenant overrides (audit-fix regression)
# ---------------------------------------------------------------------------


class CacheKeyIsolationByThresholdTests(TransactionTestCase):
    """Audit-fix regression: ``DQServiceClient.run_dq`` MUST NOT
    return tenant A's cached result to tenant B when the two
    tenants have different ``Tenant.dq_*`` overrides — even when
    the file/profile/contract are identical. Pre-fix the cache key
    only depended on (file_hash, profile_key, custom_checks_hash)
    and ignored thresholds, causing cross-tenant pollution."""

    def test_different_thresholds_produce_different_cache_keys(self):
        from django.core.cache import cache

        from hub.apps.dq.service_client import DQServiceClient

        # Two tenants, identical file, different sampling thresholds.
        tenant_a = _make_tenant(dq_sampling_threshold_rows=10_000)
        tenant_b = _make_tenant(dq_sampling_threshold_rows=100_000)

        client = DQServiceClient()
        cache.clear()
        seen_results = {}

        # Build a per-tenant fake response so we can detect a leak:
        # if tenant B receives ``tenant_a_marker`` it means the
        # cache key for the two collided.
        def _make_capture(marker):
            def _capture_request(method, endpoint, **kwargs):
                return _fake_dq_response(metadata={"_tenant_marker": marker})

            return _capture_request

        # Tenant A run (populates cache under tenant-A's key).
        with patch.object(
            client,
            "_request_with_retry",
            _make_capture("A"),
        ):
            seen_results["A"] = client.run_dq(
                file_content=b"a,b\n1,2\n",
                file_format="csv",
                profile_key="intake_basic_gx",
                use_cache=True,
                tenant_id=str(tenant_a.id),
            )

        # Tenant B run with the SAME file. If cache key included
        # only file/profile, this would short-circuit to tenant A's
        # cached result and the marker would be "A" — bug. With
        # the audit-fix it should miss the cache and call the (B)
        # transport stub, returning marker "B".
        with patch.object(
            client,
            "_request_with_retry",
            _make_capture("B"),
        ):
            seen_results["B"] = client.run_dq(
                file_content=b"a,b\n1,2\n",
                file_format="csv",
                profile_key="intake_basic_gx",
                use_cache=True,
                tenant_id=str(tenant_b.id),
            )

        assert seen_results["A"]["metadata"]["_tenant_marker"] == "A"
        assert seen_results["B"]["metadata"]["_tenant_marker"] == "B", (
            "Cross-tenant cache pollution: tenant B received tenant A's "
            "cached result. Cache key MUST incorporate tenant threshold "
            "values."
        )

    def test_null_override_tenants_share_cache_with_env_defaults(self):
        """Two tenants with NULL overrides must share cache entries
        — they're both running against env defaults so the result
        is genuinely interchangeable. Avoids cache-hit-rate
        regression for the common case (most tenants have NULL
        overrides)."""
        from django.core.cache import cache

        from hub.apps.dq.service_client import DQServiceClient

        tenant_a = _make_tenant()  # both NULL
        tenant_b = _make_tenant()  # both NULL
        client = DQServiceClient()
        cache.clear()

        def _make_capture(marker):
            def _capture_request(method, endpoint, **kwargs):
                return _fake_dq_response(metadata={"_tenant_marker": marker})

            return _capture_request

        with patch.object(
            client,
            "_request_with_retry",
            _make_capture("A"),
        ):
            res_a = client.run_dq(
                file_content=b"a,b\n1,2\n",
                file_format="csv",
                profile_key="intake_basic_gx",
                use_cache=True,
                tenant_id=str(tenant_a.id),
            )

        # Tenant B should hit the cache (same env-default key).
        with patch.object(
            client,
            "_request_with_retry",
            _make_capture("B"),
        ):
            res_b = client.run_dq(
                file_content=b"a,b\n1,2\n",
                file_format="csv",
                profile_key="intake_basic_gx",
                use_cache=True,
                tenant_id=str(tenant_b.id),
            )

        # Tenant B got A's result via the shared cache (no
        # override → same cache key population as the rest of the
        # NULL-override fleet).
        assert res_a["metadata"]["_tenant_marker"] == "A"
        assert res_b["metadata"]["_tenant_marker"] == "A", (
            "NULL-override tenants MUST share cache entries to "
            "preserve hit ratio for the common case. Two NULL-override "
            "tenants seeing different markers means we over-shard the "
            "cache."
        )
