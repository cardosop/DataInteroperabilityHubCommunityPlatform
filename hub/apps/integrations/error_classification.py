"""
Connector Error Classification (Phase 77)

Centralised classification of connector errors into transient, permanent,
or unknown categories.  Used by the sync-job executor to decide retry
strategy:

- TRANSIENT  → retry with exponential back-off
- PERMANENT  → fail immediately (no retry)
- UNKNOWN    → retry once, then fail
"""
import logging
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)

# HTTP status codes considered transient (server-side / rate-limit)
_TRANSIENT_STATUS_CODES = frozenset({429, 502, 503, 504})

# HTTP status codes considered permanent (client-side / auth)
_PERMANENT_STATUS_CODES = frozenset({400, 401, 403, 404, 405, 409, 422})


class ConnectorErrorType(str, Enum):
    """Classification of connector errors for retry decisions."""

    TRANSIENT = "transient"
    PERMANENT = "permanent"
    UNKNOWN = "unknown"


def _extract_status_code(exc: Exception) -> Optional[int]:
    """Extract an HTTP status code from common exception types.

    Supports:
    - ``httpx.HTTPStatusError``  (``exc.response.status_code``)
    - ``requests.HTTPError``     (``exc.response.status_code``)
    - Any exception with a ``status_code`` attribute
    - Any exception with a ``response.status_code`` attribute
    """
    # Direct attribute (some SDK wrappers)
    if hasattr(exc, "status_code"):
        code = exc.status_code
        if isinstance(code, int):
            return code

    # httpx / requests style
    response = getattr(exc, "response", None)
    if response is not None:
        code = getattr(response, "status_code", None)
        if isinstance(code, int):
            return code

    return None


def classify_connector_error(exc: Exception) -> ConnectorErrorType:
    """Classify an exception raised by a marketplace connector.

    Classification rules (evaluated in order):

    1. **Known transient exception types** →  ``TRANSIENT``
       ``ConnectionError``, ``TimeoutError``, ``OSError``,
       ``httpx.ConnectError``, ``httpx.ReadTimeout``,
       ``httpx.ConnectTimeout``, ``httpx.PoolTimeout``.
    2. **HTTP status code extractable from exception**
       - status in {429, 502, 503, 504}  →  ``TRANSIENT``
       - status in {400, 401, 403, 404, 405, 409, 422}  →  ``PERMANENT``
    3. **Everything else** → ``UNKNOWN``

    Args:
        exc: The exception to classify.

    Returns:
        A ``ConnectorErrorType`` member.
    """
    exc_type = type(exc).__name__

    # ── 1. Known transient base types ───────────────────────────
    if isinstance(exc, (ConnectionError, TimeoutError, OSError)):
        logger.debug(
            "error_classified",
            extra={
                "error_type": ConnectorErrorType.TRANSIENT.value,
                "exception_class": exc_type,
                "reason": "transient_base_type",
            },
        )
        return ConnectorErrorType.TRANSIENT

    # httpx-specific transient types (without hard import)
    try:
        import httpx  # noqa: F811

        if isinstance(
            exc,
            (
                httpx.ConnectError,
                httpx.ReadTimeout,
                httpx.ConnectTimeout,
                httpx.PoolTimeout,
                httpx.RemoteProtocolError,
            ),
        ):
            logger.debug(
                "error_classified",
                extra={
                    "error_type": ConnectorErrorType.TRANSIENT.value,
                    "exception_class": exc_type,
                    "reason": "httpx_transient_type",
                },
            )
            return ConnectorErrorType.TRANSIENT
    except ImportError:
        pass

    # ── 2. HTTP status code from the exception ──────────────────
    status_code = _extract_status_code(exc)
    if status_code is not None:
        if status_code in _TRANSIENT_STATUS_CODES:
            logger.debug(
                "error_classified",
                extra={
                    "error_type": ConnectorErrorType.TRANSIENT.value,
                    "exception_class": exc_type,
                    "status_code": status_code,
                    "reason": "transient_status_code",
                },
            )
            return ConnectorErrorType.TRANSIENT

        if status_code in _PERMANENT_STATUS_CODES:
            logger.debug(
                "error_classified",
                extra={
                    "error_type": ConnectorErrorType.PERMANENT.value,
                    "exception_class": exc_type,
                    "status_code": status_code,
                    "reason": "permanent_status_code",
                },
            )
            return ConnectorErrorType.PERMANENT

    # ── 3. Fallback ─────────────────────────────────────────────
    logger.debug(
        "error_classified",
        extra={
            "error_type": ConnectorErrorType.UNKNOWN.value,
            "exception_class": exc_type,
            "status_code": status_code,
            "reason": "unrecognised_error",
        },
    )
    return ConnectorErrorType.UNKNOWN
