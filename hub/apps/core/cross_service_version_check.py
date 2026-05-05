"""
Phase 250.0.14 / D250.15 — cross-service version-compatibility startup check.

Hub backend at startup queries compliance-service ``/version`` and dq-service
``/version``; refuses to start if either reports a version less than the
configured minimum.

Why this exists
---------------
Phase 250.1.A introduces in-memory compliance + DQ scan endpoints
(``ComplianceService.scan_inmemory()`` / ``DQService.scan_inmemory()``)
that do NOT exist in pre-Phase-250 versions of those services. A Hub
deployment that reaches those endpoints against an older microservice
silently fails (404, or wrong response shape) instead of running the
fail-closed gates per D250.2.

By failing fast at startup — refusing to bring up the Hub api / worker
pod when an incompatible microservice is detected — we surface the
mismatch as a clear deploy-time error rather than a confusing runtime
500.

Configuration
-------------
Three env vars (or Django settings) drive the check:

* ``DQ_SERVICE_URL`` (existing) — base URL of the dq-service.
* ``COMPLIANCE_SERVICE_URL`` (existing) — base URL of the compliance-service.
* ``HUB_REQUIRED_DQ_SERVICE_VERSION`` (new) — minimum dq-service version
  the Hub requires (semver). Default ``"0.0.0"`` (no requirement).
* ``HUB_REQUIRED_COMPLIANCE_SERVICE_VERSION`` (new) — minimum
  compliance-service version. Default ``"0.0.0"``.
* ``CROSS_SERVICE_VERSION_CHECK_ENABLED`` (new) — master switch. Default
  ``True`` in production, ``False`` elsewhere.
* ``CROSS_SERVICE_VERSION_CHECK_TIMEOUT_SECONDS`` (new) — per-service
  HTTP probe timeout. Default ``5.0``.

Behaviour
---------
* Production environment + flag enabled + service unreachable → raise
  ``ImproperlyConfigured`` (Hub fails to start).
* Production + flag enabled + service version < required → raise
  ``ImproperlyConfigured``.
* Non-production OR flag disabled → log a WARNING and allow startup.
* Tests / management commands → check is skipped entirely (mirrors
  ``hub.apps.core.apps._should_run_startup_validation()`` pattern).

Failure mode
------------
Failure is fail-closed at startup: the pod refuses to come up. k8s
restart-loop kicks in; deploy fails with a clear error message; ops
sees the version mismatch in pod logs.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger(__name__)


_VERSION_PATTERN = re.compile(r"^(\d+)\.(\d+)\.(\d+)")
_DEFAULT_TIMEOUT_S = 5.0


@dataclass(frozen=True)
class _ServiceProbe:
    """Specification for one service's startup probe.

    Args:
        name: Human-friendly service name (used in error messages).
        base_url_setting: Django settings attribute holding the base URL.
        required_version_setting: Django settings attribute holding the
            minimum required semver string.
    """

    name: str
    base_url_setting: str
    required_version_setting: str


_PROBES = (
    _ServiceProbe(
        name="dq-service",
        base_url_setting="DQ_SERVICE_URL",
        required_version_setting="HUB_REQUIRED_DQ_SERVICE_VERSION",
    ),
    _ServiceProbe(
        name="compliance-service",
        base_url_setting="COMPLIANCE_SERVICE_URL",
        required_version_setting="HUB_REQUIRED_COMPLIANCE_SERVICE_VERSION",
    ),
)


def _parse_semver(version: str) -> tuple[int, int, int]:
    """Parse a semver string ``"major.minor.patch"`` into a tuple.

    Tolerates pre-release / build suffixes by capturing only the leading
    ``major.minor.patch``. Raises ``ImproperlyConfigured`` on malformed
    input — production version reporting is a contract, not a guess.
    """
    match = _VERSION_PATTERN.match(version)
    if not match:
        raise ImproperlyConfigured(
            f"Invalid semver string: {version!r}. Expected "
            f"'major.minor.patch' (suffixes after the patch are tolerated)."
        )
    return tuple(int(g) for g in match.groups())  # type: ignore[return-value]


def _compare_semver(actual: str, required: str) -> int:
    """Return -1 if actual < required, 0 if equal, 1 if greater."""
    actual_t = _parse_semver(actual)
    required_t = _parse_semver(required)
    if actual_t < required_t:
        return -1
    if actual_t > required_t:
        return 1
    return 0


def _http_get_version(
    base_url: str,
    timeout_s: float,
) -> Optional[str]:
    """Probe ``{base_url}/version`` and return the reported version string.

    Returns ``None`` if the service is unreachable or returns a
    non-success status. Raises ``ImproperlyConfigured`` only on truly
    malformed responses (e.g. body has no ``version`` field) — network
    failures are caller-handled so the caller can produce a richer error
    message.
    """
    import httpx  # imported lazily so test envs without httpx still load

    url = base_url.rstrip("/") + "/version"
    try:
        response = httpx.get(url, timeout=timeout_s)
    except httpx.RequestError as exc:
        logger.warning(
            "cross_service_version_check_unreachable",
            extra={"url": url, "error": str(exc)},
        )
        return None

    if response.status_code != 200:
        logger.warning(
            "cross_service_version_check_non_200",
            extra={"url": url, "status_code": response.status_code},
        )
        return None

    try:
        body = response.json()
    except ValueError as exc:
        raise ImproperlyConfigured(
            f"Service at {url} returned non-JSON body: {exc}. "
            "Expected JSON with a 'version' field."
        ) from exc

    version = body.get("version")
    if not version or not isinstance(version, str):
        raise ImproperlyConfigured(
            f"Service at {url} returned JSON without a 'version' string field. "
            f"Got: {body!r}"
        )
    return version


def _check_one(
    probe: _ServiceProbe,
    timeout_s: float,
    is_production: bool,
) -> None:
    """Run the version-compatibility check for one service.

    In production: raise ``ImproperlyConfigured`` on mismatch /
    unreachability. In non-production: log a warning and continue.
    """
    base_url = getattr(settings, probe.base_url_setting, None)
    if not base_url:
        if is_production:
            raise ImproperlyConfigured(
                f"{probe.name}: settings.{probe.base_url_setting} is not "
                f"configured but cross-service version check is enabled."
            )
        logger.warning(
            "cross_service_version_check_skipped_no_url",
            extra={"service": probe.name, "setting": probe.base_url_setting},
        )
        return

    required = getattr(settings, probe.required_version_setting, "0.0.0")
    if required == "0.0.0":
        # No minimum requirement configured — skip silently.
        return

    actual = _http_get_version(base_url, timeout_s=timeout_s)
    if actual is None:
        if is_production:
            raise ImproperlyConfigured(
                f"{probe.name}: unreachable at {base_url}/version. Hub "
                f"requires {probe.name} >= {required}; cannot verify "
                f"version. Refusing to start in production."
            )
        logger.warning(
            "cross_service_version_check_unreachable_nonprod",
            extra={"service": probe.name, "base_url": base_url},
        )
        return

    cmp_result = _compare_semver(actual, required)
    if cmp_result < 0:
        message = (
            f"{probe.name}: reported version {actual!r} is less than "
            f"Hub-required minimum {required!r}. Phase 250 in-memory scan "
            f"endpoints (per D250.1.A) require an updated microservice. "
            f"Refusing to start in production."
        )
        if is_production:
            raise ImproperlyConfigured(message)
        logger.warning("cross_service_version_check_too_old_nonprod", extra={
            "service": probe.name,
            "actual_version": actual,
            "required_version": required,
        })
        return

    logger.info(
        "cross_service_version_check_ok",
        extra={
            "service": probe.name,
            "actual_version": actual,
            "required_version": required,
            "comparison": "equal" if cmp_result == 0 else "greater",
        },
    )


def run_cross_service_version_check() -> None:
    """Public entry point — invoked from ``CoreConfig.ready()`` in
    production startup, or from the ``validate_cross_service_versions``
    management command.

    The function returns ``None`` on success and raises
    ``ImproperlyConfigured`` on mismatch (production only). Non-production
    failures degrade to log warnings to keep developer machines workable.
    """
    enabled = getattr(settings, "CROSS_SERVICE_VERSION_CHECK_ENABLED", None)
    env = getattr(settings, "ENVIRONMENT", "development").strip().lower()
    is_production = env == "production"

    # Default ON in production, OFF elsewhere.
    if enabled is None:
        enabled = is_production
    if not enabled:
        logger.debug(
            "cross_service_version_check_disabled",
            extra={"environment": env},
        )
        return

    timeout_s = float(
        getattr(
            settings,
            "CROSS_SERVICE_VERSION_CHECK_TIMEOUT_SECONDS",
            _DEFAULT_TIMEOUT_S,
        )
    )

    for probe in _PROBES:
        _check_one(probe, timeout_s=timeout_s, is_production=is_production)


__all__ = [
    "run_cross_service_version_check",
    "_compare_semver",  # exported for tests
    "_parse_semver",    # exported for tests
]
