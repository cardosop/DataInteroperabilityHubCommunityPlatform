# ADR-DSF-004 — Minimum ClamAV engine version handshake

**Status**: Accepted (Phase 260.0)

## Decision

Production Hub calls clamd VERSION (TCP) during `CoreConfig.ready`; fails fast when below `CLAMAV_MINIMUM_ENGINE_VERSION` (`hub/apps/core/clamav_startup_check.py`).

Bypass only via explicit `CLAMAV_STARTUP_VERSION_CHECK_ENABLED=False` with Sec sign-off.

## Consequences

Deployments require clamd readiness before api `Ready`.

