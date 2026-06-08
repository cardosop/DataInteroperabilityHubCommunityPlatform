"""Phase 260.0.17 — fail-closed ClamAV daemon version gate (production startup)."""

from __future__ import annotations
import structlog
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from hub.apps.files.clamav_transport import read_clamd_version_banner, version_meets_minimum

logger = structlog.get_logger(__name__)


def run_clamav_version_compat_check() -> None:
    """
    When ``CLAMAV_ENABLED`` and checks are enabled, query clamd ``VERSION`` and
    compare with ``CLAMAV_MINIMUM_ENGINE_VERSION`` (``major.minor.patch``).
    """
    if not getattr(settings, "CLAMAV_ENABLED", False):
        return
    if not getattr(settings, "CLAMAV_STARTUP_VERSION_CHECK_ENABLED", True):
        return

    minimum = getattr(settings, "CLAMAV_MINIMUM_ENGINE_VERSION", "0.103.0")
    host = getattr(settings, "CLAMAV_HOST", "clamav")
    port = int(getattr(settings, "CLAMAV_PORT", 3310))
    timeout = float(getattr(settings, "CLAMAV_TIMEOUT_SECONDS", 120.0))

    try:
        banner = read_clamd_version_banner(
            host, port, timeout_seconds=min(timeout, 30.0)
        )
        ok, effective = version_meets_minimum(daemon_banner=banner, required_text=str(minimum))
        if ok:
            logger.info(
                "clamav_daemon_version_gate_ok",
                banner=banner,
                effective_semver=effective,
                minimum=minimum,
            )
            return
        raise ImproperlyConfigured(
            f"CLAMAV_MINIMUM_ENGINE_VERSION={minimum} not satisfied "
            f"(daemon reports {effective!r}; full banner={banner!r})."
        )
    except ImproperlyConfigured:
        raise
    except Exception as exc:
        raise ImproperlyConfigured(
            "ClamAV daemon version probe failed — fix connectivity or disable "
            "CLAMAV_STARTUP_VERSION_CHECK_ENABLED for emergency rollback only."
        ) from exc
