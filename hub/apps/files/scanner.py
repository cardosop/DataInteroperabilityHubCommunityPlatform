"""
ClamAV malware scanning via pyclamd (TCP clamd).

Uses ClamdNetworkSocket against CLAMAV_HOST:CLAMAV_PORT.
"""
from __future__ import annotations

import structlog
from django.conf import settings

from hub.apps.files.models import FileScanStatus

logger = structlog.get_logger(__name__)

# Standard EICAR test string (safe test pattern recognized by AV engines).
EICAR_STANDARD_TEST_BYTES = (
    b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
)


def _threat_description_from_scan_result(result: object) -> str | None:
    """Normalize pyclamd scan_stream dict values (signature names) for audits."""
    if result is None or not isinstance(result, dict):
        return None
    for _k, v in result.items():
        if v is not None and str(v).strip():
            return str(v).strip()
    return None


class ClamAVScanner:
    """Wrap pyclamd; map scan results to ``FileScanStatus`` values."""

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        timeout: float | None = None,
    ) -> None:
        self.host = (
            host if host is not None else getattr(settings, "CLAMAV_HOST", "clamav")
        )
        self.port = int(
            port if port is not None else getattr(settings, "CLAMAV_PORT", 3310)
        )
        self.timeout = timeout if timeout is not None else float(
            getattr(settings, "CLAMAV_TIMEOUT_SECONDS", 120)
        )

    def classify_bytes_with_detail(self, data: bytes) -> tuple[str, str | None]:
        """
        Scan bytes; return ``(FileScanStatus value, threat_name_or_none)``.

        Transport failures yield ``(SCAN_UNAVAILABLE, None)``.
        """
        try:
            from pyclamd.pyclamd import BufferTooLongError
            from pyclamd.pyclamd import ClamdNetworkSocket
            from pyclamd.pyclamd import ConnectionError as ClamdConnectionError
        except ImportError:
            logger.warning("pyclamd_not_installed")
            return FileScanStatus.SCAN_UNAVAILABLE, None

        try:
            client = ClamdNetworkSocket(
                self.host,
                self.port,
                timeout=self.timeout,
            )
        except ClamdConnectionError as e:
            logger.warning(
                "clamav_connect_failed",
                host=self.host,
                port=self.port,
                error=str(e),
            )
            return FileScanStatus.SCAN_UNAVAILABLE, None

        try:
            result = client.scan_stream(data)
        except ClamdConnectionError as e:
            logger.warning(
                "clamav_scan_stream_connection_failed",
                host=self.host,
                port=self.port,
                error=str(e),
            )
            return FileScanStatus.SCAN_UNAVAILABLE, None
        except BufferTooLongError as e:
            logger.warning("clamav_buffer_too_long", error=str(e))
            return FileScanStatus.SCAN_ERROR, None
        except Exception as e:
            logger.warning("clamav_scan_failed", error=str(e), exc_info=True)
            return FileScanStatus.SCAN_ERROR, None

        if result is None:
            return FileScanStatus.CLEAN, None
        return FileScanStatus.INFECTED, _threat_description_from_scan_result(result)

    def classify_bytes(self, data: bytes) -> str:
        """
        Scan bytes; return a ``FileScanStatus`` value (no threat metadata).

        Prefer :meth:`classify_bytes_with_detail` when auditing infections.
        """
        status, _detail = self.classify_bytes_with_detail(data)
        return status
