"""Phase 260.0.8 — Retry transient S3 / transport failures when loading blobs for schema inference.

Phase 260.7.D — tightened the retry budget to ``stop_after_attempt(3)``
+ ``wait_exponential(multiplier=1, max=5)`` (was ``stop_after_attempt(5)``
+ ``wait_exponential(multiplier=0.5, max=8)``) per spec, AND wired the
``dataset_inference_retries_total{result}`` Counter so ops can see retry
volume + final-outcome ratios in dashboards. ALSO flipped ``reraise=True``
→ ``reraise=False`` so the safe-wrapper's ``except RetryError`` block
becomes reachable — pre-260.7.D it was dead code (``reraise=True`` re-raised
the underlying transient exception, which propagated past the safe-wrapper
without being translated to ``ValidationError``).
"""

from __future__ import annotations
import errno
import logging
from typing import Optional

from botocore.exceptions import ClientError
from tenacity import (
    RetryError,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from hub.apps.core.services.base import ValidationError
from hub.apps.observability.otel_metrics import dataset_inference_retries_total

logger = logging.getLogger(__name__)


def _emit_retry_metric(retry_state) -> None:
    """Tenacity ``before_sleep`` callback — increments the retry counter.

    Fires once per retry attempt (i.e., between attempt N and attempt
    N+1, AFTER attempt N raised a transient error and BEFORE the
    backoff sleep). With ``stop_after_attempt(3)`` and 3 transient
    failures, this fires twice (between 1→2 and 2→3); the 3rd
    failure exhausts the budget without firing again.

    Best-effort: a metric subsystem failure must NOT crash the
    fetch path. Wrapped in try/except per the codebase's standard
    pattern (see e.g. ``worker_run_lifecycle.py:105-107``).
    """
    try:
        dataset_inference_retries_total.labels(result="retry").inc()
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning(
            "dataset_inference_retry_metric_emit_failed",
            extra={"error": str(exc)},
        )

_RETRYABLE_BOTOCODES = frozenset(
    {
        "500",
        "InternalError",
        "InternalServerError",
        "SlowDown",
        "503",
        "ServiceUnavailable",
        "RequestTimeout",
        "RequestTimeoutException",
        "RequestTimeTooSkewed",
        "ExpiredTokenException",
        "ThrottlingException",
        "ProvisionedThroughputExceededException",
    }
)


def _is_transient_download_error(exc: BaseException) -> bool:
    if isinstance(exc, (BrokenPipeError, ConnectionResetError, TimeoutError)):
        return True
    if isinstance(exc, OSError):
        err = getattr(exc, "errno", None)
        return err in {errno.EPIPE, errno.ECONNRESET, errno.ETIMEDOUT, errno.ECONNABORTED}
    msg = str(exc).lower()
    if "slow down" in msg or "timeout" in msg or "temporarily unavailable" in msg:
        return True
    if isinstance(exc, ClientError):
        code = exc.response.get("Error", {}).get("Code", "")
        if code in _RETRYABLE_BOTOCODES:
            return True
    return False


class FileMissingInStorageError(Exception):
    """Permanent missing-object — not retried."""


def _unwrap_client_error(exc: BaseException) -> Optional[ClientError]:
    """Return the underlying ``ClientError`` if *exc* is one or
    wraps one, else ``None``.

    Phase 260.5.F.R1 GAP-B — :class:`S3StorageClient.get_file_content`
    and :meth:`download_range` both catch ``ClientError`` and
    re-raise as ``Exception(f"Failed to ...: {e}") from e``. The
    ``from e`` preserves the cause as ``exc.__cause__``. Without
    explicit unwrapping, the storage-fetch layer's missing-file
    detection (``except ClientError`` with code 404 → translate
    to :class:`FileMissingInStorageError`) and tenacity's
    ``_is_transient_download_error`` retry classifier (which
    matches ``isinstance(exc, ClientError)``) both miss the real
    cause — every transient 5xx propagates as a non-retryable
    ``Exception`` with a noisy message.

    The unwrap is defensive (handles BOTH direct ClientError AND
    wrapped variants) so test mocks that raise ClientError
    directly continue to work without modification.
    """
    if isinstance(exc, ClientError):
        return exc
    cause = getattr(exc, "__cause__", None)
    if isinstance(cause, ClientError):
        return cause
    return None


def _attempt_get_content(
    storage: object,
    storage_path: str,
    *,
    max_bytes: Optional[int] = None,
) -> bytes:
    """Fetch object bytes, optionally limited to a byte prefix.

    When ``max_bytes`` is set, uses :meth:`S3StorageClient.download_range`
    so only the first ``max_bytes`` bytes are transferred from S3.
    The caller is responsible for downstream truncation to a clean
    parser boundary (see
    :func:`hub.apps.datasets.inference_limits.truncate_to_clean_boundary`).

    Both the FULL_READ and SAMPLE paths route their failures through
    :func:`_unwrap_client_error` so missing-file translation +
    tenacity retry classification fire whether the storage adapter
    raises ``ClientError`` directly (test mocks, future backends)
    or wrapped (current ``S3StorageClient``).
    """
    if max_bytes is not None and max_bytes > 0:
        range_fn = getattr(storage, "download_range", None)
        if not callable(range_fn):
            raise TypeError("storage must expose download_range for sample-mode fetches")
        try:
            return range_fn(storage_path, end=max_bytes)
        except Exception as exc:
            client_err = _unwrap_client_error(exc)
            if client_err is not None:
                code = client_err.response.get("Error", {}).get("Code", "")
                if code in {"404", "NoSuchKey", "NotFound"}:
                    raise FileMissingInStorageError(storage_path) from exc
                # Re-raise the underlying ClientError so tenacity's
                # retry classifier sees the right type.
                raise client_err from exc
            raise

    get_fn = getattr(storage, "get_file_content", None)
    if not callable(get_fn):
        raise TypeError("storage must expose get_file_content")
    try:
        return get_fn(storage_path)
    except Exception as exc:
        client_err = _unwrap_client_error(exc)
        if client_err is not None:
            code = client_err.response.get("Error", {}).get("Code", "")
            if code in {"404", "NoSuchKey", "NotFound"}:
                raise FileMissingInStorageError(storage_path) from exc
            raise client_err from exc
        raise


@retry(
    # Phase 260.7.D — flipped from ``reraise=True`` so RetryError fires
    # when retries are exhausted; the safe-wrapper's existing
    # ``except RetryError`` handler then translates it to
    # ``ValidationError``. Pre-260.7.D the handler was dead code: with
    # ``reraise=True``, tenacity re-raised the underlying transient
    # exception which propagated past the safe-wrapper unchanged.
    reraise=False,
    retry=retry_if_exception(_is_transient_download_error),
    # Phase 260.7.D — tightened from ``stop_after_attempt(5)`` +
    # ``wait_exponential(multiplier=0.5, max=8)`` per task spec. The
    # net wall-clock is similar (3 attempts × ~3.3s avg backoff vs.
    # 5 × ~3s) but the failure shape is more predictable: max 3
    # attempts means callers know the upper-bound latency.
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, max=5),
    # Phase 260.7.D — emit ``result="retry"`` per attempt for
    # dashboard visibility on transient-error frequency.
    before_sleep=_emit_retry_metric,
)
def fetch_file_content_for_dataset_schema_retrying(
    *,
    storage: object,
    storage_path: str,
    max_bytes: Optional[int] = None,
) -> bytes:
    """GET object bytes from ``S3StorageClient`` with bounded exponential backoff.

    Phase 260.5.F: when ``max_bytes`` is provided, uses a ranged
    GET (``Range: bytes=0-N``) to fetch only the first ``max_bytes``
    bytes — the load-bearing optimisation for sample-mode
    inference on large files. The retry / backoff policy applies
    to ranged reads identically.

    Phase 260.7.D: retry budget is ``stop_after_attempt(3)`` +
    ``wait_exponential(multiplier=1, max=5)``; each retry attempt
    increments ``dataset_inference_retries_total{result="retry"}``
    via the ``before_sleep`` callback.
    """
    return _attempt_get_content(storage, storage_path, max_bytes=max_bytes)


def fetch_file_content_for_dataset_schema_safe(
    *,
    storage: object,
    storage_path: str,
    max_bytes: Optional[int] = None,
) -> bytes:
    """
    Dataset creation path helper — translates transport failures into ``ValidationError``
    shapes expected by serializers / callers.

    Phase 260.5.F: optional ``max_bytes`` enables sample-mode
    inference. Callers should obtain the value from
    :func:`hub.apps.datasets.inference_limits.plan_inference_for_file`
    rather than passing a hard-coded number, so the policy stays
    centralised.

    Phase 260.7.D: increments
    ``dataset_inference_retries_total{result=...}`` at every exit:
    ``success`` on bytes returned, ``failure`` on
    :class:`FileMissingInStorageError` (404/NoSuchKey, permanent) OR
    :class:`tenacity.RetryError` (retries exhausted). The metric is
    accounting-clean: every call increments exactly one of
    ``{success, failure}``, while ``retry`` is orthogonal (per-attempt).
    """
    try:
        result = fetch_file_content_for_dataset_schema_retrying(
            storage=storage,
            storage_path=storage_path,
            max_bytes=max_bytes,
        )
    except FileMissingInStorageError:
        # Phase 260.7.D — outcome metric: permanent missing object.
        # Wrapped best-effort so a metric failure can't mask the
        # underlying ValidationError the caller needs to see.
        try:
            dataset_inference_retries_total.labels(result="failure").inc()
        except Exception as metric_exc:  # pragma: no cover — defensive
            logger.warning(
                "dataset_inference_failure_metric_emit_failed",
                extra={"error": str(metric_exc)},
            )
        raise ValidationError(
            "File blob missing from storage; cannot infer schema.",
            details={"storage_path": storage_path},
        )
    except RetryError as exc:
        cause = exc.last_attempt.exception()
        logger.warning(
            "dataset_schema_fetch_exhausted_retries",
            extra={"storage_path": storage_path, "error": str(cause)},
        )
        # Phase 260.7.D — outcome metric: retries exhausted.
        try:
            dataset_inference_retries_total.labels(result="failure").inc()
        except Exception as metric_exc:  # pragma: no cover — defensive
            logger.warning(
                "dataset_inference_failure_metric_emit_failed",
                extra={"error": str(metric_exc)},
            )
        raise ValidationError(
            f"Storage read exhausted retries after transient errors: {cause}",
            details={"storage_path": storage_path},
        ) from cause

    # Phase 260.7.D — outcome metric: bytes returned (success path).
    # Reached only when retrying() returned without raising — which
    # means EITHER first-attempt success OR success after 1+ retries.
    # In both shapes the outcome is "success"; the per-attempt
    # ``retry`` increments emitted by ``_emit_retry_metric`` are
    # orthogonal and tell the retry-frequency story separately.
    try:
        dataset_inference_retries_total.labels(result="success").inc()
    except Exception as metric_exc:  # pragma: no cover — defensive
        logger.warning(
            "dataset_inference_success_metric_emit_failed",
            extra={"error": str(metric_exc)},
        )
    return result
