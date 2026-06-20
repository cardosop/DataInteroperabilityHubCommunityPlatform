"""Phase 260.0.17 — fail-closed ClamAV daemon version gate (production startup).

Phase 260.3 improvement: retry the VERSION probe up to 3 times with
exponential backoff (2s / 4s / 8s) before failing the startup gate.
Temporary DNS resolution delays or container scheduling races in
Kubernetes should not send the API pod into CrashLoopBackOff.
"""

from __future__ import annotations

import time as _time

import structlog
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from hub.apps.files.clamav_transport import read_clamd_version_banner, version_meets_minimum

logger = structlog.get_logger(__name__)

_RETRY_COUNT = 3
_RETRY_BACKOFF_BASE_SECONDS = 2.0  # 2s, 4s, 8s


def run_clamav_version_compat_check() -> None:
    """
    When ``CLAMAV_ENABLED`` and checks are enabled, query clamd ``VERSION`` and
    compare with ``CLAMAV_MINIMUM_ENGINE_VERSION`` (``major.minor.patch``).

    Retries up to ``_RETRY_COUNT`` times with backoff for transient
    connectivity failures (DNS, scheduling races).
    """
    if not getattr(settings, "CLAMAV_ENABLED", False):
        return
    if not getattr(settings, "CLAMAV_STARTUP_VERSION_CHECK_ENABLED", True):
        return

    minimum = getattr(settings, "CLAMAV_MINIMUM_ENGINE_VERSION", "0.103.0")
    host = getattr(settings, "CLAMAV_HOST", "clamav")
    port = int(getattr(settings, "CLAMAV_PORT", 3310))
    timeout = float(getattr(settings, "CLAMAV_TIMEOUT_SECONDS", 120.0))

    last_exc: Exception | None = None
    for attempt in range(_RETRY_COUNT + 1):
        try:
            banner = read_clamd_version_banner(host, port, timeout_seconds=min(timeout, 30.0))
            ok, effective = version_meets_minimum(
                daemon_banner=banner, required_text=str(minimum)
            )
            if ok:
                logger.info(
                    "clamav_daemon_version_gate_ok",
                    banner=banner,
                    effective_semver=effective,
                    minimum=minimum,
                    attempt=attempt,
                )
                return
            raise ImproperlyConfigured(
                f"CLAMAV_MINIMUM_ENGINE_VERSION={minimum} not satisfied "
                f"(daemon reports {effective!r}; full banner={banner!r})."
            )
        except ImproperlyConfigured:
            raise
        except Exception as exc:
            last_exc = exc
            if attempt < _RETRY_COUNT:
                wait = _RETRY_BACKOFF_BASE_SECONDS * (2**attempt)
                logger.warning(
                    "clamav_daemon_version_probe_retry",
                    attempt=attempt + 1,
                    max_attempts=_RETRY_COUNT,
                    wait_seconds=wait,
                    error=str(exc),
                )
                _time.sleep(wait)
            # else: fall through to the final raise below

    raise ImproperlyConfigured(
        "ClamAV daemon version probe failed after "
        f"{_RETRY_COUNT + 1} attempts — fix connectivity or disable "
        "CLAMAV_STARTUP_VERSION_CHECK_ENABLED for emergency rollback only."
    ) from last_exc
