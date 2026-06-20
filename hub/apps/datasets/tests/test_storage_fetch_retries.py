"""Tests for tenacity-backed dataset schema fetch helpers (Phase 260.0.8).

Phase 260.5.F.R1 GAP-B added coverage for ranged reads (sample-mode
inference path) AND for storage adapters that WRAP ``ClientError``
in a generic ``Exception`` (the real ``S3StorageClient`` does this
in both ``get_file_content`` and ``download_range``). The unwrap
helper in ``storage_fetch._attempt_get_content`` is what makes
missing-file detection + tenacity retry classification work for
both the direct-ClientError and wrapped variants.
"""

from __future__ import annotations

from unittest import TestCase

import pytest
from botocore.exceptions import ClientError

from hub.apps.core.services.base import ValidationError
from hub.apps.datasets.storage_fetch import (
    fetch_file_content_for_dataset_schema_safe,
)


class SlowDownThenOkStorage:
    def __init__(self) -> None:
        self.attempts = 0

    def get_file_content(self, _path: str) -> bytes:
        self.attempts += 1
        if self.attempts < 3:
            raise ClientError(
                {"Error": {"Code": "SlowDown", "Message": "reduce rate"}},
                "GetObject",
            )
        return b"a,b\n1"


class Always404Storage:
    def get_file_content(self, _path: str) -> bytes:
        raise ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "nope"}},
            "GetObject",
        )


class AlwaysSlowDownStorage:
    """Phase 260.7.D — every attempt raises a transient error, exhausting
    the retry budget. With ``stop_after_attempt(3)`` the safe-wrapper
    sees ``RetryError`` after 3 attempts and translates to
    ``ValidationError``."""

    def __init__(self) -> None:
        self.attempts = 0

    def get_file_content(self, _path: str) -> bytes:
        self.attempts += 1
        raise ClientError(
            {"Error": {"Code": "SlowDown", "Message": "reduce rate"}},
            "GetObject",
        )


class FirstAttemptOkStorage:
    """First-call-succeeds path — no retries should fire."""

    def __init__(self) -> None:
        self.attempts = 0

    def get_file_content(self, _path: str) -> bytes:
        self.attempts += 1
        return b"id,value\n1,a\n"


class WrappedSlowDownThenOkStorage:
    """Mirrors the real :class:`S3StorageClient` pattern of catching
    ``ClientError`` and re-raising as ``Exception(...) from e``.
    The unwrap in ``_attempt_get_content`` MUST recover the
    underlying ``ClientError`` for tenacity's retry classifier."""

    def __init__(self) -> None:
        self.attempts = 0

    def get_file_content(self, _path: str) -> bytes:
        self.attempts += 1
        if self.attempts < 3:
            try:
                raise ClientError(
                    {"Error": {"Code": "SlowDown", "Message": "reduce rate"}},
                    "GetObject",
                )
            except ClientError as e:
                raise Exception(f"Failed to download file: {e!s}") from e
        return b"a,b\n1"


class WrappedAlways404Storage:
    """Wrapped 404 — the real S3StorageClient pattern."""

    def get_file_content(self, _path: str) -> bytes:
        try:
            raise ClientError(
                {"Error": {"Code": "NoSuchKey", "Message": "nope"}},
                "GetObject",
            )
        except ClientError as e:
            raise Exception(f"Failed to download file: {e!s}") from e


class RangedSlowDownThenOkStorage:
    """Sample-mode (max_bytes) path — wrapped ClientError shape."""

    def __init__(self) -> None:
        self.attempts = 0

    def download_range(self, _path: str, *, end: int) -> bytes:
        self.attempts += 1
        if self.attempts < 3:
            try:
                raise ClientError(
                    {"Error": {"Code": "SlowDown", "Message": "reduce rate"}},
                    "GetObject",
                )
            except ClientError as e:
                raise Exception(f"Failed to download object range: {e!s}") from e
        # Return only ``end`` bytes — matches real S3 ranged GET.
        return b"a,b\n1\n2,3\n"[:end]


class RangedAlways404Storage:
    def download_range(self, _path: str, *, end: int) -> bytes:
        try:
            raise ClientError(
                {"Error": {"Code": "NoSuchKey", "Message": "nope"}},
                "GetObject",
            )
        except ClientError as e:
            raise Exception(f"Failed to download object range: {e!s}") from e


class DatasetStorageFetchRetryTests(TestCase):
    @pytest.mark.integration
    def test_retries_slowdown_before_success(self) -> None:
        storage = SlowDownThenOkStorage()
        body = fetch_file_content_for_dataset_schema_safe(
            storage=storage,
            storage_path="tenant/x.csv",
        )
        self.assertEqual(body, b"a,b\n1")
        self.assertGreaterEqual(storage.attempts, 3)

    @pytest.mark.integration
    def test_missing_key_surfaces_validation_error(self) -> None:
        with self.assertRaises(ValidationError):
            fetch_file_content_for_dataset_schema_safe(
                storage=Always404Storage(),
                storage_path="missing",
            )


class WrappedClientErrorUnwrapTests(TestCase):
    """Phase 260.5.F.R1 GAP-B — adapters that wrap ``ClientError``
    as a generic ``Exception`` (the real ``S3StorageClient``
    pattern) MUST still get retry + missing-file translation.

    Without :func:`_unwrap_client_error`, ``isinstance(exc,
    ClientError)`` in tenacity's classifier and in
    ``_attempt_get_content``'s direct-ClientError branch both
    miss — every transient 5xx propagates without retry, every
    404 propagates without becoming a typed
    ``FileMissingInStorageError`` / ``ValidationError``.
    """

    @pytest.mark.integration
    def test_full_read_wrapped_slowdown_retries_and_succeeds(self) -> None:
        # Wrapped SlowDown (ClientError caught + re-raised as
        # Exception with __cause__) must still trigger tenacity's
        # retry — proving the unwrap recovers the type.
        storage = WrappedSlowDownThenOkStorage()
        body = fetch_file_content_for_dataset_schema_safe(
            storage=storage,
            storage_path="tenant/x.csv",
        )
        self.assertEqual(body, b"a,b\n1")
        self.assertGreaterEqual(
            storage.attempts,
            3,
            "Wrapped SlowDown was not retried — unwrap regressed",
        )

    @pytest.mark.integration
    def test_full_read_wrapped_404_surfaces_validation_error(self) -> None:
        # Wrapped 404 must translate to ValidationError (via
        # FileMissingInStorageError → safe wrapper) rather than
        # propagating as a generic Exception.
        with self.assertRaises(ValidationError):
            fetch_file_content_for_dataset_schema_safe(
                storage=WrappedAlways404Storage(),
                storage_path="missing",
            )

    @pytest.mark.integration
    def test_ranged_wrapped_slowdown_retries_and_succeeds(self) -> None:
        # Sample-mode path — same unwrap rule applies. Without
        # this test the ranged-read retry behaviour is silently
        # absent (the original storage_fetch tests only covered
        # the FULL_READ path).
        storage = RangedSlowDownThenOkStorage()
        body = fetch_file_content_for_dataset_schema_safe(
            storage=storage,
            storage_path="tenant/x.csv",
            max_bytes=64,
        )
        self.assertTrue(body.startswith(b"a,b"))
        self.assertGreaterEqual(
            storage.attempts,
            3,
            "Wrapped ranged-SlowDown was not retried — unwrap regressed",
        )

    @pytest.mark.integration
    def test_ranged_wrapped_404_surfaces_validation_error(self) -> None:
        with self.assertRaises(ValidationError):
            fetch_file_content_for_dataset_schema_safe(
                storage=RangedAlways404Storage(),
                storage_path="missing",
                max_bytes=64,
            )


# ---------------------------------------------------------------------------
# Phase 260.7.D — tightened retry budget + metric emission tests.
# ---------------------------------------------------------------------------


class RetryBudgetTighteningTests(TestCase):
    """260.7.D.1 — verify the retry decorator's stop/wait params match
    the spec (``stop_after_attempt(3)``, ``wait_exponential(multiplier=1,
    max=5)``).

    These assertions read the introspectable tenacity attributes on
    the wrapped function so a future drift (e.g., a refactor that
    silently changes the budget back to 5 attempts) is caught at the
    parameter level, independently of behavioural tests.
    """

    @pytest.mark.integration
    def test_retry_decorator_uses_three_attempts(self) -> None:
        from hub.apps.datasets.storage_fetch import (
            fetch_file_content_for_dataset_schema_retrying,
        )

        retry_state = fetch_file_content_for_dataset_schema_retrying.retry
        # tenacity exposes the stop policy on the wrapped callable;
        # ``max_attempt_number`` is the integer the spec pins.
        self.assertEqual(
            getattr(retry_state.stop, "max_attempt_number", None),
            3,
            "260.7.D.1 contract: stop_after_attempt(3)",
        )

    @pytest.mark.integration
    def test_retry_decorator_uses_exponential_multiplier_one_max_five(self) -> None:
        from hub.apps.datasets.storage_fetch import (
            fetch_file_content_for_dataset_schema_retrying,
        )

        wait_state = fetch_file_content_for_dataset_schema_retrying.retry.wait
        # ``wait_exponential`` exposes its multiplier + max as
        # attributes; pin both.
        self.assertEqual(
            getattr(wait_state, "multiplier", None),
            1,
            "260.7.D.1 contract: wait_exponential(multiplier=1, ...)",
        )
        self.assertEqual(
            getattr(wait_state, "max", None),
            5,
            "260.7.D.1 contract: wait_exponential(..., max=5)",
        )

    @pytest.mark.integration
    def test_exhausted_retries_raise_validation_error_with_three_attempts(self) -> None:
        """3 transient failures → 3 attempts made, then RetryError → ValidationError.

        Confirms ``reraise=False`` is in effect (pre-260.7.D was
        ``reraise=True``, which would have re-raised the underlying
        ClientError instead of letting the safe-wrapper translate to
        ValidationError).
        """
        storage = AlwaysSlowDownStorage()
        with self.assertRaises(ValidationError):
            fetch_file_content_for_dataset_schema_safe(
                storage=storage,
                storage_path="tenant/x.csv",
            )
        # stop_after_attempt(3) → exactly 3 attempts made before giving up.
        self.assertEqual(
            storage.attempts,
            3,
            f"stop_after_attempt(3) must produce 3 attempts; got {storage.attempts}",
        )


class DatasetInferenceRetriesMetricTests(TestCase):
    """260.7.D.2 — the ``dataset_inference_retries_total{result}`` Counter
    must increment at three result-points: per-retry, on success, on failure.

    Each test snapshots the labeled counters BEFORE the call and asserts
    the DELTA after — so prior tests' increments don't pollute the
    assertion. The ``_value._count`` proxy is the
    ``hub.apps.observability.otel_metrics`` test-readable accumulator.
    """

    def _counter_value(self, result: str) -> float:
        from hub.apps.observability.otel_metrics import (
            dataset_inference_retries_total,
        )

        return float(dataset_inference_retries_total.labels(result=result)._value._count)

    @pytest.mark.integration
    def test_first_attempt_success_increments_success_only(self) -> None:
        before_success = self._counter_value("success")
        before_retry = self._counter_value("retry")
        before_failure = self._counter_value("failure")

        body = fetch_file_content_for_dataset_schema_safe(
            storage=FirstAttemptOkStorage(),
            storage_path="tenant/x.csv",
        )

        self.assertEqual(body, b"id,value\n1,a\n")
        self.assertEqual(
            self._counter_value("success") - before_success,
            1.0,
            "first-attempt success must increment result=success exactly once",
        )
        self.assertEqual(
            self._counter_value("retry") - before_retry,
            0.0,
            "first-attempt success must NOT fire result=retry",
        )
        self.assertEqual(
            self._counter_value("failure") - before_failure,
            0.0,
            "first-attempt success must NOT fire result=failure",
        )

    @pytest.mark.integration
    def test_retry_then_success_increments_retry_and_success(self) -> None:
        before_success = self._counter_value("success")
        before_retry = self._counter_value("retry")
        before_failure = self._counter_value("failure")

        # SlowDownThenOkStorage: 2 transient failures, then success on
        # attempt 3 → before_sleep fires twice, then success.
        storage = SlowDownThenOkStorage()
        fetch_file_content_for_dataset_schema_safe(
            storage=storage,
            storage_path="tenant/x.csv",
        )

        self.assertEqual(storage.attempts, 3)
        self.assertEqual(
            self._counter_value("retry") - before_retry,
            2.0,
            "2 retries (between attempts 1→2 and 2→3) must increment result=retry twice",
        )
        self.assertEqual(
            self._counter_value("success") - before_success,
            1.0,
            "successful eventual return must increment result=success once",
        )
        self.assertEqual(
            self._counter_value("failure") - before_failure,
            0.0,
            "successful eventual return must NOT fire result=failure",
        )

    @pytest.mark.integration
    def test_exhausted_retries_increments_retry_and_failure(self) -> None:
        before_success = self._counter_value("success")
        before_retry = self._counter_value("retry")
        before_failure = self._counter_value("failure")

        storage = AlwaysSlowDownStorage()
        with self.assertRaises(ValidationError):
            fetch_file_content_for_dataset_schema_safe(
                storage=storage,
                storage_path="tenant/x.csv",
            )

        # 3 attempts; before_sleep fires between attempts 1→2 and 2→3
        # (twice). The third attempt's failure exhausts the budget
        # without firing before_sleep — tenacity's stop check happens
        # BEFORE before_sleep.
        self.assertEqual(
            self._counter_value("retry") - before_retry,
            2.0,
            "exhausted retries must increment result=retry twice (one per backoff sleep)",
        )
        self.assertEqual(
            self._counter_value("failure") - before_failure,
            1.0,
            "exhausted retries must increment result=failure once (RetryError → ValidationError)",
        )
        self.assertEqual(
            self._counter_value("success") - before_success,
            0.0,
            "exhausted retries must NOT fire result=success",
        )

    @pytest.mark.integration
    def test_permanent_404_increments_failure_no_retries(self) -> None:
        """NoSuchKey is permanent (not in _RETRYABLE_BOTOCODES) →
        no retries fire, but the safe-wrapper still increments
        result=failure (FileMissingInStorageError path)."""
        before_success = self._counter_value("success")
        before_retry = self._counter_value("retry")
        before_failure = self._counter_value("failure")

        with self.assertRaises(ValidationError):
            fetch_file_content_for_dataset_schema_safe(
                storage=Always404Storage(),
                storage_path="missing",
            )

        self.assertEqual(
            self._counter_value("retry") - before_retry,
            0.0,
            "permanent 404 must NOT increment result=retry",
        )
        self.assertEqual(
            self._counter_value("failure") - before_failure,
            1.0,
            "permanent 404 (FileMissingInStorageError) must increment result=failure",
        )
        self.assertEqual(
            self._counter_value("success") - before_success,
            0.0,
            "permanent 404 must NOT fire result=success",
        )

    @pytest.mark.integration
    def test_success_plus_failure_equals_total_calls_invariant(self) -> None:
        """Accounting invariant: success + failure increments equals the
        number of safe-wrapper INVOCATIONS, regardless of how many
        retries fired internally. Pins the docstring claim that the
        metric is ``accounting-clean``.
        """
        before_success = self._counter_value("success")
        before_failure = self._counter_value("failure")

        # Three calls: 1 first-attempt success + 1 retry-then-success + 1 permanent-failure.
        fetch_file_content_for_dataset_schema_safe(
            storage=FirstAttemptOkStorage(),
            storage_path="a",
        )
        fetch_file_content_for_dataset_schema_safe(
            storage=SlowDownThenOkStorage(),
            storage_path="b",
        )
        with self.assertRaises(ValidationError):
            fetch_file_content_for_dataset_schema_safe(
                storage=Always404Storage(),
                storage_path="c",
            )

        delta_success = self._counter_value("success") - before_success
        delta_failure = self._counter_value("failure") - before_failure
        self.assertEqual(
            delta_success + delta_failure,
            3.0,
            "260.7.D invariant: every safe-wrapper call increments exactly one of "
            f"{{success, failure}}; got success+failure delta = {delta_success + delta_failure}",
        )

    @pytest.mark.integration
    def test_wrapped_storage_retry_metric_fires_through_unwrap(self) -> None:
        """260.7.D R1 audit GAP-C — wrapped-ClientError adapters (the
        real ``S3StorageClient`` shape) must STILL trigger the
        ``result="retry"`` increments + ``result="success"`` outcome.

        The other metric tests use UNWRAPPED storage; this one pins
        the cross-cutting contract that ``_unwrap_client_error`` +
        tenacity classifier + before_sleep callback all fire together
        on the WRAPPED-exception path. A regression in
        ``_unwrap_client_error`` (the helper that recovers the
        underlying ``ClientError`` from the real-S3StorageClient
        ``Exception(f"Failed to ...: {e}") from e`` shape) would
        suppress retries entirely AND silently break the metric —
        the existing ``WrappedClientErrorUnwrapTests`` would catch
        the BEHAVIOUR (no retry happens) but NOT the metric drift.
        """
        before_retry = self._counter_value("retry")
        before_success = self._counter_value("success")

        # Wrapped storage that raises wrapped-SlowDown twice, then
        # succeeds on the 3rd attempt. Mirrors the production shape
        # of S3StorageClient.get_file_content (catches ClientError
        # and re-raises Exception(f"Failed to ...: {e}") from e).
        storage = WrappedSlowDownThenOkStorage()
        body = fetch_file_content_for_dataset_schema_safe(
            storage=storage,
            storage_path="tenant/wrapped.csv",
        )
        self.assertEqual(body, b"a,b\n1")
        self.assertEqual(storage.attempts, 3)

        # The metric MUST fire identically to the unwrapped path —
        # 2 retries (between attempts 1→2 and 2→3) + 1 success.
        self.assertEqual(
            self._counter_value("retry") - before_retry,
            2.0,
            "wrapped-SlowDown path must increment result=retry twice "
            "(_unwrap_client_error + tenacity classifier + before_sleep "
            "all chained correctly)",
        )
        self.assertEqual(
            self._counter_value("success") - before_success,
            1.0,
            "wrapped-SlowDown eventual success must increment result=success once",
        )
