"""
Phase 228 F4 (228.F4.21) — outbound adapter tests.

Pins the exponential-backoff + DLQ semantics of
``hub.apps.integrations.openlineage.adapter``. The adapter is the
ONLY HTTP boundary in the F4 surface — every other module operates
on dicts. Tests mock ONLY the outbound HTTP call (the network
boundary the spec explicitly requires fail-soft semantics for); no
internal code path is mocked.

Coverage:

* Successful POST → no DLQ row, no retry.
* Transient 5xx → retry with exponential backoff (1s/2s/4s/8s/16s).
* After 5 failed attempts → row lands in OpenLineageDeadLetter.
* DLQ payload is encrypted (event_payload_encrypted is NOT plaintext).
* Permanent 4xx (e.g., 400 Bad Request) → DLQ immediately, no retry.
* Idempotency: same event_id POSTed twice does not produce two
  DLQ rows for the same failure.
"""

from __future__ import annotations

import uuid
from unittest import mock

import pytest
import requests
from django.test import TransactionTestCase


def _create_tenant():
    from hub.apps.tenants.models import Tenant

    suffix = uuid.uuid4().hex[:8]
    return Tenant.objects.create(name=f"OL Co {suffix}", slug=f"ol-{suffix}")


def _build_event():
    from hub.apps.integrations.openlineage.translator import (
        meshant_edge_to_openlineage,
    )

    edge = {
        "id": str(uuid.uuid4()),
        "source_contract": str(uuid.uuid4()),
        "target_contract": str(uuid.uuid4()),
        "source_model": "orders",
        "source_field": "order_id",
        "target_model": "fulfillment",
        "target_field": "order_ref",
        "edge_type": "transformation",
        "transformation_ref": "dbt://orders_fulfillment.sql",
        "job_ref": "airflow://etl/orders",
        "valid_from": "2026-04-30T12:00:00+00:00",
        "valid_to": None,
    }
    return meshant_edge_to_openlineage(edge, producer="https://meshant.com/")


def _make_response(status_code: int, body: str = "") -> mock.Mock:
    """Build a ``requests.Response``-like mock."""
    resp = mock.Mock(spec=requests.Response)
    resp.status_code = status_code
    resp.text = body
    resp.content = body.encode("utf-8")
    resp.ok = 200 <= status_code < 300
    return resp


@pytest.mark.django_db(transaction=True)
class TestSuccessfulDelivery(TransactionTestCase):
    def setUp(self):
        from django.db import connection

        if not hasattr(connection.ensure_connection, "__self__"):
            from types import MethodType

            from django.db.backends.base.base import BaseDatabaseWrapper

            connection.ensure_connection = MethodType(
                BaseDatabaseWrapper.ensure_connection,
                connection,
            )
        # _fixture_teardown from a prior class (including skipped
        # integration tests) may have closed connections or left dirty
        # atomic-block state.  Reset everything and ensure a fresh one.
        connection.close()
        connection.savepoint_ids = []
        connection.needs_rollback = False
        connection.ensure_connection()

    def test_2xx_returns_delivered_with_no_dlq(self):
        from hub.apps.integrations.openlineage.adapter import (
            DeliveryOutcome,
            OpenLineageAdapter,
        )
        from hub.apps.integrations.openlineage.models import (
            OpenLineageDeadLetter,
        )

        tenant = _create_tenant()
        event = _build_event()

        before = OpenLineageDeadLetter.objects.filter(tenant=tenant).count()
        with mock.patch("requests.Session.post", return_value=_make_response(200)):
            outcome = OpenLineageAdapter().deliver(
                event=event,
                target_url="https://marquez.example.invalid/api/v1/lineage",
                tenant=tenant,
            )
        assert outcome == DeliveryOutcome.DELIVERED
        assert OpenLineageDeadLetter.objects.filter(tenant=tenant).count() == before


@pytest.mark.django_db(transaction=True)
class TestExponentialBackoffOnTransientFailures(TransactionTestCase):
    """5xx triggers retry with the canonical 1s/2s/4s/8s/16s
    backoff; the adapter performs up to 5 attempts before DLQ."""

    def setUp(self):
        from django.db import connection

        if not hasattr(connection.ensure_connection, "__self__"):
            from types import MethodType

            from django.db.backends.base.base import BaseDatabaseWrapper

            connection.ensure_connection = MethodType(
                BaseDatabaseWrapper.ensure_connection,
                connection,
            )
        # _fixture_teardown from a prior class (including skipped
        # integration tests) may have closed connections or left dirty
        # atomic-block state.  Reset everything and ensure a fresh one.
        connection.close()
        connection.savepoint_ids = []
        connection.needs_rollback = False
        connection.ensure_connection()

    def test_succeeds_on_third_attempt_no_dlq(self):
        from hub.apps.integrations.openlineage.adapter import (
            DeliveryOutcome,
            OpenLineageAdapter,
        )
        from hub.apps.integrations.openlineage.models import (
            OpenLineageDeadLetter,
        )

        tenant = _create_tenant()
        event = _build_event()

        responses = [
            _make_response(500, "boom"),
            _make_response(502, "boom"),
            _make_response(200, "ok"),
        ]

        # Patch ``time.sleep`` so the 1+2 second waits don't slow the
        # test; the adapter's backoff is the load-bearing invariant
        # we're asserting via the call_args_list of sleep, not by
        # actually waiting.
        with (
            mock.patch("requests.Session.post", side_effect=responses),
            mock.patch("hub.apps.integrations.openlineage.adapter.time.sleep") as sl,
        ):
            outcome = OpenLineageAdapter().deliver(
                event=event,
                target_url="https://marquez.example.invalid/api/v1/lineage",
                tenant=tenant,
            )
        assert outcome == DeliveryOutcome.DELIVERED
        # sleep called twice (between attempt 1→2 and 2→3) with the
        # canonical exponential schedule.
        sleep_args = [call.args[0] for call in sl.call_args_list]
        assert sleep_args == [1, 2], f"expected exp backoff [1, 2]; got {sleep_args}"
        # No DLQ row.
        assert OpenLineageDeadLetter.objects.filter(tenant=tenant).count() == 0

    def test_5_failed_attempts_lands_in_dlq(self):
        from hub.apps.integrations.openlineage.adapter import (
            DeliveryOutcome,
            OpenLineageAdapter,
        )
        from hub.apps.integrations.openlineage.models import (
            OpenLineageDeadLetter,
        )

        tenant = _create_tenant()
        event = _build_event()

        with (
            mock.patch(
                "requests.Session.post",
                side_effect=[_make_response(503, "still bad")] * 5,
            ),
            mock.patch(
                "hub.apps.integrations.openlineage.adapter.time.sleep",
            ),
        ):
            outcome = OpenLineageAdapter().deliver(
                event=event,
                target_url="https://marquez.example.invalid/api/v1/lineage",
                tenant=tenant,
            )
        assert outcome == DeliveryOutcome.DEAD_LETTERED
        rows = OpenLineageDeadLetter.objects.filter(tenant=tenant)
        assert rows.count() == 1
        row = rows.first()
        assert row.attempts == 5
        assert row.event_id == event["run"]["runId"]
        assert "503" in row.failure_reason, (
            f"failure_reason must contain the HTTP status code '503'; got {row.failure_reason!r}"
        )


@pytest.mark.django_db(transaction=True)
class TestPermanentFailureGoesToDLQImmediately(TransactionTestCase):
    """4xx (other than 408 / 429 retryable) is permanent — no
    backoff retries, immediate DLQ."""

    def setUp(self):
        from django.db import connection

        if not hasattr(connection.ensure_connection, "__self__"):
            from types import MethodType

            from django.db.backends.base.base import BaseDatabaseWrapper

            connection.ensure_connection = MethodType(
                BaseDatabaseWrapper.ensure_connection,
                connection,
            )
        # _fixture_teardown from a prior class (including skipped
        # integration tests) may have closed connections or left dirty
        # atomic-block state.  Reset everything and ensure a fresh one.
        connection.close()
        connection.savepoint_ids = []
        connection.needs_rollback = False
        connection.ensure_connection()

    def test_400_bad_request_dlqs_without_retry(self):
        from hub.apps.integrations.openlineage.adapter import (
            DeliveryOutcome,
            OpenLineageAdapter,
        )
        from hub.apps.integrations.openlineage.models import (
            OpenLineageDeadLetter,
        )

        tenant = _create_tenant()
        event = _build_event()

        with (
            mock.patch(
                "requests.Session.post",
                return_value=_make_response(400, "bad payload"),
            ) as post_mock,
            mock.patch(
                "hub.apps.integrations.openlineage.adapter.time.sleep",
            ) as sl,
        ):
            outcome = OpenLineageAdapter().deliver(
                event=event,
                target_url="https://marquez.example.invalid/api/v1/lineage",
                tenant=tenant,
            )
        assert outcome == DeliveryOutcome.DEAD_LETTERED
        # Exactly ONE POST attempt — no retry on permanent 4xx.
        assert post_mock.call_count == 1, (
            f"expected exactly 1 POST for permanent 4xx; got {post_mock.call_count}"
        )
        # No sleep calls — no retries.
        assert sl.call_count == 0
        rows = OpenLineageDeadLetter.objects.filter(tenant=tenant)
        assert rows.count() == 1
        assert rows.first().attempts == 1


@pytest.mark.django_db(transaction=True)
class TestDLQEncryptsPayload(TransactionTestCase):
    """REQ-LIN-F4-002 + 228.F4.10 — the DLQ row's
    ``event_payload_encrypted`` MUST NOT be the plaintext JSON."""

    def setUp(self):
        from django.db import connection

        if not hasattr(connection.ensure_connection, "__self__"):
            from types import MethodType

            from django.db.backends.base.base import BaseDatabaseWrapper

            connection.ensure_connection = MethodType(
                BaseDatabaseWrapper.ensure_connection,
                connection,
            )
        # _fixture_teardown from a prior class (including skipped
        # integration tests) may have closed connections or left dirty
        # atomic-block state.  Reset everything and ensure a fresh one.
        connection.close()
        connection.savepoint_ids = []
        connection.needs_rollback = False
        connection.ensure_connection()

    def test_dlq_payload_is_encrypted(self):
        from hub.apps.integrations.openlineage.adapter import (
            OpenLineageAdapter,
        )
        from hub.apps.integrations.openlineage.models import (
            OpenLineageDeadLetter,
        )

        tenant = _create_tenant()
        event = _build_event()
        plaintext_marker = event["run"]["runId"]

        with (
            mock.patch(
                "requests.Session.post",
                return_value=_make_response(400, "bad"),
            ),
            mock.patch(
                "hub.apps.integrations.openlineage.adapter.time.sleep",
            ),
        ):
            OpenLineageAdapter().deliver(
                event=event,
                target_url="https://marquez.example.invalid/api/v1/lineage",
                tenant=tenant,
            )

        row = OpenLineageDeadLetter.objects.filter(tenant=tenant).first()
        # The encrypted column MUST NOT contain the plaintext runId.
        assert plaintext_marker not in row.event_payload_encrypted, (
            f"DLQ event_payload_encrypted leaked plaintext runId "
            f"{plaintext_marker!r} — encryption helper failed or wasn't called."
        )
        # But the decryption round-trip recovers the original.
        decrypted = row.event_payload
        assert decrypted["run"]["runId"] == plaintext_marker


@pytest.mark.django_db(transaction=True)
class TestRetryableStatusCodes(TransactionTestCase):
    """408 Request Timeout and 429 Too Many Requests are retryable
    (per RFC 7231 + REST best-practice); other 4xx are not."""

    def setUp(self):
        from django.db import connection

        if not hasattr(connection.ensure_connection, "__self__"):
            from types import MethodType

            from django.db.backends.base.base import BaseDatabaseWrapper

            connection.ensure_connection = MethodType(
                BaseDatabaseWrapper.ensure_connection,
                connection,
            )
        # _fixture_teardown from a prior class (including skipped
        # integration tests) may have closed connections or left dirty
        # atomic-block state.  Reset everything and ensure a fresh one.
        connection.close()
        connection.savepoint_ids = []
        connection.needs_rollback = False
        connection.ensure_connection()

    def test_429_is_retryable(self):
        from hub.apps.integrations.openlineage.adapter import (
            DeliveryOutcome,
            OpenLineageAdapter,
        )

        tenant = _create_tenant()
        event = _build_event()

        with (
            mock.patch(
                "requests.Session.post",
                side_effect=[_make_response(429, "slow down"), _make_response(200, "ok")],
            ),
            mock.patch(
                "hub.apps.integrations.openlineage.adapter.time.sleep",
            ) as sl,
        ):
            outcome = OpenLineageAdapter().deliver(
                event=event,
                target_url="https://marquez.example.invalid/api/v1/lineage",
                tenant=tenant,
            )
        assert outcome == DeliveryOutcome.DELIVERED
        # One sleep call (between attempts 1 → 2).
        assert sl.call_count == 1


@pytest.mark.django_db(transaction=True)
class TestNetworkExceptionIsTransient(TransactionTestCase):
    """A ``requests.ConnectionError`` (DNS / refused / timeout) is
    treated as transient — retried up to the limit, then DLQ."""

    def setUp(self):
        from django.db import connection

        if not hasattr(connection.ensure_connection, "__self__"):
            from types import MethodType

            from django.db.backends.base.base import BaseDatabaseWrapper

            connection.ensure_connection = MethodType(
                BaseDatabaseWrapper.ensure_connection,
                connection,
            )
        # _fixture_teardown from a prior class (including skipped
        # integration tests) may have closed connections or left dirty
        # atomic-block state.  Reset everything and ensure a fresh one.
        connection.close()
        connection.savepoint_ids = []
        connection.needs_rollback = False
        connection.ensure_connection()

    def test_connection_error_retries_then_dlq(self):
        from hub.apps.integrations.openlineage.adapter import (
            DeliveryOutcome,
            OpenLineageAdapter,
        )
        from hub.apps.integrations.openlineage.models import (
            OpenLineageDeadLetter,
        )

        tenant = _create_tenant()
        event = _build_event()

        with (
            mock.patch(
                "requests.Session.post",
                side_effect=requests.exceptions.ConnectionError("dns refused"),
            ),
            mock.patch(
                "hub.apps.integrations.openlineage.adapter.time.sleep",
            ) as sl,
        ):
            outcome = OpenLineageAdapter().deliver(
                event=event,
                target_url="https://marquez.example.invalid/api/v1/lineage",
                tenant=tenant,
            )
        assert outcome == DeliveryOutcome.DEAD_LETTERED
        # 4 sleep calls (between 5 failed attempts).
        assert sl.call_count == 4
        # Exp schedule: [1, 2, 4, 8].
        sleep_args = [c.args[0] for c in sl.call_args_list]
        assert sleep_args == [1, 2, 4, 8]
        assert OpenLineageDeadLetter.objects.filter(tenant=tenant).count() == 1


# ---------------------------------------------------------------------------
# Phase 7 — previously uncovered adapter paths
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class TestHmacSignatureHeader(TransactionTestCase):
    """GAP — ``hmac_signature`` parameter was never exercised."""

    def test_hmac_signature_sets_header(self):
        from hub.apps.integrations.openlineage.adapter import (
            OpenLineageAdapter,
        )

        tenant = _create_tenant()
        event = _build_event()

        with mock.patch("requests.Session.post", return_value=_make_response(200)) as post_mock:
            OpenLineageAdapter().deliver(
                event=event,
                target_url="https://marquez.example/api/v1/lineage",
                tenant=tenant,
                hmac_signature="test-hmac-sig-abc123",
            )
        call_headers = post_mock.call_args.kwargs.get("headers", {})
        assert call_headers.get("X-Meshant-Signature") == "test-hmac-sig-abc123", (
            f"hmac_signature header not set; headers={call_headers}"
        )


class TestAdditionalRetryableStatusCodes:
    """GAP — status codes 408, 425, 502, 504 are declared retryable
    but only 429 and 503 were tested.

    Uses plain pytest functions (not TransactionTestCase) so that
    parametrize works correctly.
    """

    @staticmethod
    def _setup():
        import uuid

        from hub.apps.tenants.models import Tenant

        suffix = uuid.uuid4().hex[:8]
        return Tenant.objects.create(
            name=f"OL Retry Co {suffix}", slug=f"olrtry-{suffix}"
        )

    @pytest.mark.django_db(transaction=True)
    @pytest.mark.parametrize("status_code", [408, 425, 502, 504])
    def test_status_code_retries_then_succeeds(self, status_code):
        from hub.apps.integrations.openlineage.adapter import (
            DeliveryOutcome,
            OpenLineageAdapter,
        )

        tenant = self._setup()
        event = _build_event()

        with (
            mock.patch(
                "requests.Session.post",
                side_effect=[_make_response(status_code, "transient"), _make_response(200, "ok")],
            ),
            mock.patch("hub.apps.integrations.openlineage.adapter.time.sleep") as sl,
        ):
            outcome = OpenLineageAdapter().deliver(
                event=event,
                target_url="https://marquez.example/api/v1/lineage",
                tenant=tenant,
            )
        assert outcome == DeliveryOutcome.DELIVERED, (
            f"expected DELIVERED after retry on {status_code}; got {outcome}"
        )
        assert sl.call_count == 1, (
            f"expected 1 sleep call for retry on {status_code}; got {sl.call_count}"
        )


@pytest.mark.django_db(transaction=True)
class TestTimeoutIsTransient(TransactionTestCase):
    """GAP — ``requests.exceptions.Timeout`` was listed as retryable
    but never tested; only ``ConnectionError`` was."""

    def test_timeout_retries_then_dlq(self):
        from hub.apps.integrations.openlineage.adapter import (
            DeliveryOutcome,
            OpenLineageAdapter,
        )
        from hub.apps.integrations.openlineage.models import (
            OpenLineageDeadLetter,
        )

        tenant = _create_tenant()
        event = _build_event()

        with (
            mock.patch(
                "requests.Session.post",
                side_effect=requests.exceptions.Timeout("read timed out"),
            ),
            mock.patch("hub.apps.integrations.openlineage.adapter.time.sleep") as sl,
        ):
            outcome = OpenLineageAdapter().deliver(
                event=event,
                target_url="https://marquez.example/api/v1/lineage",
                tenant=tenant,
            )
        assert outcome == DeliveryOutcome.DEAD_LETTERED
        assert sl.call_count == 4  # 5 attempts → 4 sleeps
        row = OpenLineageDeadLetter.objects.filter(tenant=tenant).first()
        assert row is not None
        # The adapter classifies Timeout as "network_error" (same as
        # ConnectionError); the detail field captures the full message.
        assert row.failure_reason == "network_error"
        assert "timed out" in (row.failure_detail or "")


@pytest.mark.django_db(transaction=True)
class TestNonRetryableRequestException(TransactionTestCase):
    """GAP — ``requests.exceptions.RequestException`` subclasses that
    are NOT ConnectionError / Timeout are permanent (DLQ immediately)."""

    def test_invalid_url_dlqs_immediately(self):
        from hub.apps.integrations.openlineage.adapter import (
            DeliveryOutcome,
            OpenLineageAdapter,
        )
        from hub.apps.integrations.openlineage.models import (
            OpenLineageDeadLetter,
        )

        tenant = _create_tenant()
        event = _build_event()

        with (
            mock.patch(
                "requests.Session.post",
                side_effect=requests.exceptions.InvalidURL("bad url"),
            ),
            mock.patch("hub.apps.integrations.openlineage.adapter.time.sleep") as sl,
        ):
            outcome = OpenLineageAdapter().deliver(
                event=event,
                target_url="https://marquez.example/api/v1/lineage",
                tenant=tenant,
            )
        assert outcome == DeliveryOutcome.DEAD_LETTERED
        assert sl.call_count == 0  # No retry on permanent RequestException
        row = OpenLineageDeadLetter.objects.filter(tenant=tenant).first()
        assert row is not None
        assert row.attempts == 1


@pytest.mark.django_db(transaction=True)
class TestAdapterInitValidation(TransactionTestCase):
    """GAP — ``__init__`` validation of max_attempts vs backoff schedule."""

    def test_max_attempts_exceeds_backoff_raises_value_error(self):
        from hub.apps.integrations.openlineage.adapter import OpenLineageAdapter

        with pytest.raises(ValueError, match="max_attempts"):
            OpenLineageAdapter(backoff_schedule=(1,), max_attempts=5)

    def test_default_parameters_are_valid(self):
        from hub.apps.integrations.openlineage.adapter import OpenLineageAdapter

        # Default config must construct without error
        adapter = OpenLineageAdapter()
        assert adapter.max_attempts == 5
        assert adapter.backoff_schedule == (1, 2, 4, 8, 16)
        assert adapter.request_timeout_seconds == 10.0
