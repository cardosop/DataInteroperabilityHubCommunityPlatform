"""
Phase 77 — BR-10: Connector Error Classification

Tests covering:
1. classify_connector_error() — transient, permanent, unknown
2. MarketplaceSyncJob.add_error() stores error_type
3. tasks.py error-handling: permanent → fail immediately,
   transient → re-raise for retry, unknown → retry once then fail
"""

import contextlib
import uuid

import httpx
import pytest
from django.test import TestCase

from hub.apps.core.services.base import ServiceError
from hub.apps.integrations.base import (
    DataMarketplaceConnector,
    MarketplaceListing,
    MarketplaceType,
    SyncDirection,
    SyncResult,
    SyncStatus,
)
from hub.apps.integrations.error_classification import (
    ConnectorErrorType,
    classify_connector_error,
)
from hub.apps.integrations.factory import MarketplaceConnectorFactory
from hub.apps.integrations.models import (
    MarketplaceConnection,
    MarketplaceSyncJob,
)
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.testing.billing_support import (
    ensure_tenant_has_active_subscription,
)
from hub.apps.users.models import User, UserStatus

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
            "failed to connect",
            request=request,
        )
        self.assertEqual(
            classify_connector_error(exc),
            ConnectorErrorType.TRANSIENT,
        )

    # ── Transient (by exception type — httpx) ──

    def test_httpx_read_timeout_is_transient(self):
        request = httpx.Request("GET", "https://x.com")
        exc = httpx.ReadTimeout(
            "read timed out",
            request=request,
        )
        self.assertEqual(
            classify_connector_error(exc),
            ConnectorErrorType.TRANSIENT,
        )

    def test_httpx_pool_timeout_is_transient(self):
        request = httpx.Request("GET", "https://x.com")
        exc = httpx.PoolTimeout(
            "pool timed out",
            request=request,
        )
        self.assertEqual(
            classify_connector_error(exc),
            ConnectorErrorType.TRANSIENT,
        )

    def test_httpx_connect_timeout_is_transient(self):
        request = httpx.Request("GET", "https://x.com")
        exc = httpx.ConnectTimeout("connect timed out", request=request)
        self.assertEqual(
            classify_connector_error(exc),
            ConnectorErrorType.TRANSIENT,
        )

    def test_httpx_remote_protocol_error_is_transient(self):
        request = httpx.Request("GET", "https://x.com")
        exc = httpx.RemoteProtocolError("protocol error", request=request)
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

    def test_405_is_permanent(self):
        exc = _make_httpx_status_error(405)
        self.assertEqual(
            classify_connector_error(exc),
            ConnectorErrorType.PERMANENT,
        )

    def test_409_is_permanent(self):
        exc = _make_httpx_status_error(409)
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
            job.errors[0]["error_type"],
            "permanent",
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
            job.errors[0]["message"],
            "plain fail",
        )
        self.assertNotIn("error_type", job.errors[0])


# ── 3. Task-level retry behaviour (wiring test) ────────────────


class TaskErrorClassificationWiringTest(TestCase):
    """Verify at runtime that execute_marketplace_sync correctly wires
    classify_connector_error into the retry / abort decision logic."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"T-{uid}",
            slug=f"t-{uid}",
        )
        self.user = User.objects.create_user(
            email=f"u-{uid}@example.com",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name=f"conn-{uid}",
            config={"api_key": "test-key"},
        )

    # ── helpers ────────────────────────────────────────────────────

    class _SimpleTestConnector(DataMarketplaceConnector):
        """Minimal connector for wiring tests."""

        @property
        def marketplace_type(self) -> MarketplaceType:
            return MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE

        @property
        def supported_sync_directions(self):
            return [SyncDirection.PUSH, SyncDirection.PULL]

        def authenticate(self, credentials):
            return True

        def test_connection(self):
            return True

        def list_listings(self, filters=None, limit=None, offset=None):
            return []

        def get_listing(self, listing_id):
            return MarketplaceListing(
                marketplace_id=listing_id,
                marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE,
                title="Test",
            )

        def list_resources(self, listing_id):
            return []

        def create_listing(self, listing):
            return listing

        def update_listing(self, listing_id, listing):
            return listing

        def publish_resource(self, listing_id, resource):
            return resource

        def download_resource(self, resource_id, destination_path):
            return destination_path

        def map_to_hub_asset(self, listing, sync_job_id=None):
            from hub.apps.assets.models import AssetSourceType
            from hub.apps.integrations.base import MarketplaceAssetMapping

            return MarketplaceAssetMapping(
                asset_data={"name": listing.title},
                source_type=AssetSourceType.FEDERATED,
                source_metadata={},
            )

        def map_from_hub_asset(self, asset_data, **kwargs):
            return MarketplaceListing(
                marketplace_id=asset_data.get("id", "test"),
                marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE,
                title=asset_data.get("name", "Unknown"),
            )

        def sync_push(self, asset_ids, options=None):
            return SyncResult(
                status=SyncStatus.COMPLETED,
                total_items=len(asset_ids),
                successful_items=len(asset_ids),
            )

        def sync_pull(self, listing_ids=None, filters=None, options=None):
            return SyncResult(
                status=SyncStatus.COMPLETED,
                total_items=0,
                successful_items=0,
            )

    @staticmethod
    def _register_test_connector(connector_cls):
        MarketplaceConnectorFactory.register_connector(
            MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE,
            connector_cls,
        )

    @staticmethod
    def _unregister_test_connector():
        with contextlib.suppress(ValueError):
            MarketplaceConnectorFactory.unregister_connector(
                MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE,
            )

    # ── tests ──────────────────────────────────────────────────────

    def test_connector_connection_error_is_re_raised(self):
        """ConnectionError from connector during sync execution is
        re-raised to the caller so the task's TRANSIENT handler can
        classify it and potentially retry."""
        import hub.apps.integrations.tasks as tasks_mod

        class _TransientConnector(self._SimpleTestConnector):
            def sync_push(self, asset_ids, options=None):
                raise ConnectionError("Connection timeout")

        self._register_test_connector(_TransientConnector)
        try:
            sync_job = MarketplaceSyncJob.objects.create(
                tenant=self.tenant,
                connection=self.connection,
                direction=SyncDirection.PUSH.value,
                status=SyncStatus.PENDING.value,
                metadata={"asset_ids": ["a-1"]},
            )
            with self.assertRaises(ConnectionError):
                tasks_mod.execute_marketplace_sync(str(sync_job.id))
        finally:
            self._unregister_test_connector()

    def test_connector_returns_none_raises_service_error_and_marks_failed(self):
        """When a connector returns None, tasks.py raises ServiceError
        directly (NOT via the classification PERMANENT path). Job is
        marked FAILED."""
        import hub.apps.integrations.tasks as tasks_mod

        class _NoResultConnector(self._SimpleTestConnector):
            def sync_push(self, asset_ids, options=None):
                return None

        self._register_test_connector(_NoResultConnector)
        try:
            sync_job = MarketplaceSyncJob.objects.create(
                tenant=self.tenant,
                connection=self.connection,
                direction=SyncDirection.PUSH.value,
                status=SyncStatus.PENDING.value,
                metadata={"asset_ids": ["a-1"]},
            )
            with self.assertRaises(ServiceError) as cm:
                tasks_mod.execute_marketplace_sync(str(sync_job.id))
            self.assertIn("no result", str(cm.exception).lower())

            sync_job.refresh_from_db()
            self.assertEqual(sync_job.status, SyncStatus.FAILED.value)
        finally:
            self._unregister_test_connector()

    def test_transient_error_is_re_raised(self):
        """TRANSIENT errors are re-raised (bare raise) so the caller
        can retry — they are not wrapped in ServiceError."""
        import hub.apps.integrations.tasks as tasks_mod

        class _TransientConnector(self._SimpleTestConnector):
            def sync_push(self, asset_ids, options=None):
                raise ConnectionError("Connection timeout")

        self._register_test_connector(_TransientConnector)
        try:
            sync_job = MarketplaceSyncJob.objects.create(
                tenant=self.tenant,
                connection=self.connection,
                direction=SyncDirection.PUSH.value,
                status=SyncStatus.PENDING.value,
                metadata={"asset_ids": ["a-1"]},
            )
            with self.assertRaises(ConnectionError):
                tasks_mod.execute_marketplace_sync(str(sync_job.id))

            sync_job.refresh_from_db()
            # The job should have the error recorded
            self.assertGreater(len(sync_job.errors), 0)
        finally:
            self._unregister_test_connector()

    def test_permanent_http_error_raises_service_error(self):
        """classify_connector_error PERMANENT path (tasks.py lines 866-887):
        connector raises httpx.HTTPStatusError(401), classified as PERMANENT,
        job marked FAILED with error_type='permanent', ServiceError raised."""
        import hub.apps.integrations.tasks as tasks_mod
        import httpx

        class _AuthFailureConnector(self._SimpleTestConnector):
            def sync_push(self, asset_ids, options=None):
                request = httpx.Request("GET", "https://example.com/api")
                response = httpx.Response(status_code=401, request=request)
                raise httpx.HTTPStatusError(
                    message="401 Unauthorized",
                    request=request,
                    response=response,
                )

        self._register_test_connector(_AuthFailureConnector)
        try:
            sync_job = MarketplaceSyncJob.objects.create(
                tenant=self.tenant,
                connection=self.connection,
                direction=SyncDirection.PUSH.value,
                status=SyncStatus.PENDING.value,
                metadata={"asset_ids": ["a-1"]},
            )
            with self.assertRaises(ServiceError) as cm:
                tasks_mod.execute_marketplace_sync(str(sync_job.id))
            self.assertIn("Permanent error during sync", str(cm.exception))

            sync_job.refresh_from_db()
            self.assertEqual(sync_job.status, SyncStatus.FAILED.value)
            self.assertTrue(any(
                e.get("error_type") == "permanent"
                for e in sync_job.errors
            ))
        finally:
            self._unregister_test_connector()

    def test_unknown_error_retry_count_zero_re_raises(self):
        """UNKNOWN error with retry_count=0 re-raises the original exception
        (first retry attempt — may be retried by the caller)."""
        import hub.apps.integrations.tasks as tasks_mod

        class _RuntimeErrorConnector(self._SimpleTestConnector):
            def sync_push(self, asset_ids, options=None):
                raise RuntimeError("Unexpected connector crash")

        self._register_test_connector(_RuntimeErrorConnector)
        try:
            sync_job = MarketplaceSyncJob.objects.create(
                tenant=self.tenant,
                connection=self.connection,
                direction=SyncDirection.PUSH.value,
                status=SyncStatus.PENDING.value,
                metadata={"asset_ids": ["a-1"]},
            )
            with self.assertRaises(RuntimeError):
                tasks_mod.execute_marketplace_sync(str(sync_job.id), retry_count=0)

            sync_job.refresh_from_db()
            self.assertGreater(len(sync_job.errors), 0)
            self.assertTrue(any(
                e.get("error_type") == "unknown"
                for e in sync_job.errors
            ))
        finally:
            self._unregister_test_connector()

    def test_unknown_error_retry_count_exceeded_raises_service_error(self):
        """UNKNOWN error with retry_count >= 1 raises ServiceError
        and marks the job as FAILED (retry budget exhausted)."""
        import hub.apps.integrations.tasks as tasks_mod

        class _RuntimeErrorConnector2(self._SimpleTestConnector):
            def sync_push(self, asset_ids, options=None):
                raise RuntimeError("Unexpected connector crash")

        self._register_test_connector(_RuntimeErrorConnector2)
        try:
            sync_job = MarketplaceSyncJob.objects.create(
                tenant=self.tenant,
                connection=self.connection,
                direction=SyncDirection.PUSH.value,
                status=SyncStatus.PENDING.value,
                metadata={"asset_ids": ["a-1"]},
            )
            with self.assertRaises(ServiceError):
                tasks_mod.execute_marketplace_sync(str(sync_job.id), retry_count=1)

            sync_job.refresh_from_db()
            self.assertEqual(sync_job.status, SyncStatus.FAILED.value)
            self.assertTrue(any(
                e.get("error_type") == "unknown"
                for e in sync_job.errors
            ))
        finally:
            self._unregister_test_connector()

    def test_bidirectional_sync_executes_and_completes(self):
        """BIDIRECTIONAL sync path (tasks.py lines 491-568) executes both
        PUSH and PULL and marks the job COMPLETED."""
        import hub.apps.integrations.tasks as tasks_mod

        class _BidiConnector(self._SimpleTestConnector):
            def sync_push(self, asset_ids, options=None):
                return SyncResult(
                    status=SyncStatus.COMPLETED,
                    total_items=1,
                    successful_items=1,
                )

            def sync_pull(self, listing_ids=None, filters=None, options=None):
                return SyncResult(
                    status=SyncStatus.COMPLETED,
                    total_items=1,
                    successful_items=1,
                )

        self._register_test_connector(_BidiConnector)
        try:
            sync_job = MarketplaceSyncJob.objects.create(
                tenant=self.tenant,
                connection=self.connection,
                direction=SyncDirection.BIDIRECTIONAL.value,
                status=SyncStatus.PENDING.value,
                metadata={"asset_ids": ["a-1"], "listing_ids": ["l-1"]},
            )
            result = tasks_mod.execute_marketplace_sync(str(sync_job.id))
            self.assertEqual(result["status"], "completed")
            sync_job.refresh_from_db()
            self.assertEqual(sync_job.status, SyncStatus.COMPLETED.value)
        finally:
            self._unregister_test_connector()
