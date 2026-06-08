# Virus scan incident response

## Triage order

1. Inspect `clamav_*` structured logs + RQ backlog (`docs/ci/datasets-files-phase260-ci-matrix.md` gate metrics).
2. Restart unhealthy clamd pods; rotate if compromise suspected.
3. Replay infected uploads from quarantine bucket (never auto-retry silently).
4. Raise Sec incident if worm signatures repeat across tenants.

## Bypass policy

Emergency disable ONLY via `CLAMAV_ENABLED=False` OR `CLAMAV_STARTUP_VERSION_CHECK_ENABLED=False` documented in CHANGELOG.

## Maintenance

- **Owner**: Security Team
- **Last reviewed**: 2026-05-13
- **Next review**: 2026-08-11
