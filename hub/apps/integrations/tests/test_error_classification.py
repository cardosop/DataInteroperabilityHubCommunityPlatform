"""
Phase 77 — BR-10: Connector Error Classification

Tests covering:
1. classify_connector_error() — transient, permanent, unknown
2. MarketplaceSyncJob.add_error() stores error_type
3. tasks.py error-handling: permanent → fail immediately,
   transient → re-raise for retry, unknown → retry once then fail
"""
import uuid

import httpx
import pytest
from django.test import TestCase

from hub.apps.integrations.base import SyncStatus
from hub.apps.integrations.error_classification import (
    ConnectorErrorType,
    classify_connector_error,
)
from hub.apps.integrations.models import MarketplaceSyncJob
from hub.apps.tenants.models import Tenant, KYCStatus
from hub.apps.testing.billing_support import (
    ensure_tenant_has_active_subscription,
)

pytestmark = pytest.mark.django_db(transaction=True)


# ── helper ──────────────────────────────────────────────────────


def _make_httpx_status_error(status_code: int) -> httpx.HTTPStatusError:
    """Build a real httpx.HTTPStatusError with the given status."""
    request = httpx.Request("GET", "https://example.com/api")
    response = httpx.Response(
        status_code=status_code,
        request=request,
    )
    return httpx.HTTPStatusError(
        message=f"{status_code} error",
        request=request,
        response=response,
    )


# ── 1. classify_connector_error unit tests ──────────────────────


class ClassifyConnectorErrorTest(TestCase):
    """Unit tests for classify_connector_error()."""

    # ── Transient (by exception type — stdlib) ──

    def test_connection_error_is_transient(self):
        exc = ConnectionError("connection refused")
        self.assertEqual(
            classify_connector_error(exc),
            ConnectorErrorType.TRANSIENT,
        )

    def test_timeout_error_is_transient(self):
        exc = TimeoutError("timed out")
        self.assertEqual(
            classify_connector_error(exc),
            ConnectorErrorType.TRANSIENT,
        )

    def test_os_error_is_transient(self):
        exc = OSError("network unreachable")
        self.assertEqual(
            classify_connector_error(exc),
            ConnectorErrorType.TRANSIENT,
        )

    def test_httpx_connect_error_is_transient(self):
        request = httpx.Request("GET", "https://x.com")
        exc = httpx.ConnectError(
            "failed to connect", request=request,
        )
        self.assertEqual(
            classify_connector_error(exc),
            ConnectorErrorType.TRANSIENT,
        )

    # ── Transient (by exception type — httpx) ──

    def test_httpx_read_timeout_is_transient(self):
        request = httpx.Request("GET", "https://x.com")
        exc = httpx.ReadTimeout(
            "read timed out", request=request,
        )
        self.assertEqual(
            classify_connector_error(exc),
            ConnectorErrorType.TRANSIENT,
        )

    def test_httpx_pool_timeout_is_transient(self):
        request = httpx.Request("GET", "https://x.com")
        exc = httpx.PoolTimeout(
            "pool timed out", request=request,
        )
        self.assertEqual(
            classify_connector_error(exc),
            ConnectorErrorType.TRANSIENT,
        )

    # ── Transient (by HTTP status code) ──

    def test_429_is_transient(self):
        exc = _make_httpx_status_error(429)
        self.assertEqual(
            classify_connector_error(exc),
            ConnectorErrorType.TRANSIENT,
        )

    def test_502_is_transient(self):
        exc = _make_httpx_status_error(502)
        self.assertEqual(
            classify_connector_error(exc),
            ConnectorErrorType.TRANSIENT,
        )

    def test_503_is_transient(self):
        exc = _make_httpx_status_error(503)
        self.assertEqual(
            classify_connector_error(exc),
            ConnectorErrorType.TRANSIENT,
        )

    def test_504_is_transient(self):
        exc = _make_httpx_status_error(504)
        self.assertEqual(
            classify_connector_error(exc),
            ConnectorErrorType.TRANSIENT,
        )

    # ── Permanent (by HTTP status code) ──

    def test_400_is_permanent(self):
        exc = _make_httpx_status_error(400)
        self.assertEqual(
            classify_connector_error(exc),
            ConnectorErrorType.PERMANENT,
        )

    def test_401_is_permanent(self):
        exc = _make_httpx_status_error(401)
        self.assertEqual(
            classify_connector_error(exc),
            ConnectorErrorType.PERMANENT,
        )

    def test_403_is_permanent(self):
        exc = _make_httpx_status_error(403)
        self.assertEqual(
            classify_connector_error(exc),
            ConnectorErrorType.PERMANENT,
        )

    def test_404_is_permanent(self):
        exc = _make_httpx_status_error(404)
        self.assertEqual(
            classify_connector_error(exc),
            ConnectorErrorType.PERMANENT,
        )

    def test_422_is_permanent(self):
        exc = _make_httpx_status_error(422)
        self.assertEqual(
            classify_connector_error(exc),
            ConnectorErrorType.PERMANENT,
        )

    # ── Unknown ──

    def test_generic_runtime_error_is_unknown(self):
        exc = RuntimeError("something broke")
        self.assertEqual(
            classify_connector_error(exc),
            ConnectorErrorType.UNKNOWN,
        )

    def test_generic_exception_is_unknown(self):
        exc = Exception("mystery")
        self.assertEqual(
            classify_connector_error(exc),
            ConnectorErrorType.UNKNOWN,
        )

    def test_500_is_not_classified_as_transient(self):
        """500 Internal Server Error is NOT in the transient set
        (unlike the per-connector _is_transient_error methods);
        at the job level it signals a bug, not a retry-able hiccup.
        It falls to UNKNOWN → retry once."""
        exc = _make_httpx_status_error(500)
        self.assertEqual(
            classify_connector_error(exc),
            ConnectorErrorType.UNKNOWN,
        )


# ── 2. MarketplaceSyncJob.add_error() with error_type ──────────


class AddErrorWithTypeTest(TestCase):
    """add_error() stores error_type in the JSON entry."""

    def setUp(self):
        self.tenant = Tenant.objects.create(
            name="Err Test",
            slug="err-test",
            kyc_status=KYCStatus.VERIFIED,
        )
        ensure_tenant_has_active_subscription(self.tenant)

    def _make_sync_job(self):
        from hub.apps.integrations.models import (
            MarketplaceConnection,
        )

        conn = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type="CKAN_INSTANCE",
            name=f"conn-{uuid.uuid4().hex[:8]}",
            config={},
            is_active=True,
        )
        return MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=conn,
            direction="PULL",
            status=SyncStatus.RUNNING.value,
        )

    def test_add_error_without_error_type(self):
        """Backward-compatible: no error_type → entry has no key."""
        job = self._make_sync_job()
        job.add_error("something failed")
        entry = job.errors[-1]
        self.assertEqual(entry["message"], "something failed")
        self.assertIn("timestamp", entry)
        self.assertNotIn("error_type", entry)

    def test_add_error_with_error_type(self):
        """Phase 77: error_type is stored in the entry."""
        job = self._make_sync_job()
        job.add_error(
            "auth failed",
            error_type=ConnectorErrorType.PERMANENT.value,
        )
        entry = job.errors[-1]
        self.assertEqual(entry["message"], "auth failed")
        self.assertEqual(entry["error_type"], "permanent")

    def test_add_error_transient_type(self):
        job = self._make_sync_job()
        job.add_error(
            "503 service unavailable",
            error_type=ConnectorErrorType.TRANSIENT.value,
        )
        entry = job.errors[-1]
        self.assertEqual(entry["error_type"], "transient")

    def test_add_error_unknown_type(self):
        job = self._make_sync_job()
        job.add_error(
            "weird error",
            error_type=ConnectorErrorType.UNKNOWN.value,
        )
        entry = job.errors[-1]
        self.assertEqual(entry["error_type"], "unknown")


# ── 2b. No duplicate when add_error + mark_failed(no msg) ───────


class NoDuplicateErrorOnMarkFailedTest(TestCase):
    """Verify that the corrected pattern — add_error() first,
    then mark_failed() WITHOUT error_message — produces exactly
    one error entry (not two)."""

    def setUp(self):
        self.tenant = Tenant.objects.create(
            name="Dup Test",
            slug="dup-test",
            kyc_status=KYCStatus.VERIFIED,
        )
        ensure_tenant_has_active_subscription(self.tenant)

    def _make_sync_job(self):
        from hub.apps.integrations.models import (
            MarketplaceConnection,
        )

        conn = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type="CKAN_INSTANCE",
            name=f"conn-{uuid.uuid4().hex[:8]}",
            config={},
            is_active=True,
        )
        return MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=conn,
            direction="PULL",
            status=SyncStatus.RUNNING.value,
        )

    def test_add_error_then_mark_failed_no_msg_single_entry(self):
        """add_error(msg, error_type=X) + mark_failed() (no msg)
        should produce exactly ONE error entry with error_type."""
        job = self._make_sync_job()
        job.add_error(
            "auth failure 401",
            save=False,
            error_type=ConnectorErrorType.PERMANENT.value,
        )
        job.mark_failed()  # no error_message → no second add_error
        job.refresh_from_db()
        self.assertEqual(len(job.errors), 1)
        self.assertEqual(
            job.errors[0]["error_type"], "permanent",
        )
        self.assertEqual(job.status, SyncStatus.FAILED.value)

    def test_mark_failed_with_msg_creates_entry(self):
        """mark_failed(error_message=X) still works for callers
        that don't use add_error separately."""
        job = self._make_sync_job()
        job.mark_failed(error_message="plain fail")
        job.refresh_from_db()
        self.assertEqual(len(job.errors), 1)
        self.assertEqual(
            job.errors[0]["message"], "plain fail",
        )
        self.assertNotIn("error_type", job.errors[0])


# ── 3. Task-level retry behaviour (wiring test) ────────────────


class TaskErrorClassificationWiringTest(TestCase):
    """Verify that execute_marketplace_sync uses
    classify_connector_error and the error_class span attribute
    is present in the error-handling code path."""

    def test_tasks_imports_error_classification(self):
        """tasks.py imports classify_connector_error and
        ConnectorErrorType at module level."""
        import inspect
        import hub.apps.integrations.tasks as tasks_mod

        source = inspect.getsource(tasks_mod)
        self.assertIn(
            "classify_connector_error",
            source,
            "tasks.py must import classify_connector_error",
        )
        self.assertIn(
            "ConnectorErrorType",
            source,
            "tasks.py must import ConnectorErrorType",
        )

    def test_tasks_classifies_before_retry_decision(self):
        """The error-handling block in execute_marketplace_sync
        calls classify_connector_error and branches on the
        result."""
        import inspect
        import hub.apps.integrations.tasks as tasks_mod

        source = inspect.getsource(
            tasks_mod.execute_marketplace_sync,
        )
        # Must call the classifier
        self.assertIn("classify_connector_error(", source)
        # Must branch on PERMANENT
        self.assertIn("ConnectorErrorType.PERMANENT", source)
        # Must branch on TRANSIENT
        self.assertIn("ConnectorErrorType.TRANSIENT", source)
        # Must handle UNKNOWN with max retries
        self.assertIn("max_unknown_retries", source)

    def test_permanent_error_no_retry_in_logic(self):
        """PERMANENT branch sets error.retryable=False and
        raises ServiceError (not re-raise)."""
        import inspect
        import hub.apps.integrations.tasks as tasks_mod

        source = inspect.getsource(
            tasks_mod.execute_marketplace_sync,
        )
        # After PERMANENT, must mark retryable false
        perm_idx = source.index(
            "ConnectorErrorType.PERMANENT"
        )
        perm_block = source[perm_idx:perm_idx + 800]
        self.assertIn(
            '"error.retryable": False',
            perm_block,
        )
        self.assertIn("mark_failed", perm_block)

    def test_permanent_no_duplicate_error_entry(self):
        """PERMANENT branch calls mark_failed() WITHOUT
        error_message to avoid duplicate error entries."""
        import inspect
        import hub.apps.integrations.tasks as tasks_mod

        source = inspect.getsource(
            tasks_mod.execute_marketplace_sync,
        )
        perm_idx = source.index(
            "ConnectorErrorType.PERMANENT"
        )
        perm_block = source[perm_idx:perm_idx + 800]
        # mark_failed must be called without error_message
        self.assertIn("mark_failed()", perm_block)

    def test_transient_error_retried_in_logic(self):
        """TRANSIENT branch sets error.retryable=True and
        re-raises (bare raise, not ServiceError)."""
        import inspect
        import hub.apps.integrations.tasks as tasks_mod

        source = inspect.getsource(
            tasks_mod.execute_marketplace_sync,
        )
        trans_idx = source.index(
            "ConnectorErrorType.TRANSIENT"
        )
        trans_block = source[trans_idx:trans_idx + 600]
        self.assertIn(
            '"error.retryable": True',
            trans_block,
        )
        # Must re-raise (bare raise), NOT wrap in ServiceError
        self.assertIn("raise\n", trans_block)
