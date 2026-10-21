# Virus scan incident response

## Triage order

1. Inspect `clamav_*` structured logs + RQ backlog (`docs/ci/datasets-files-phase260-ci-matrix.md` gate metrics).
2. Restart unhealthy clamd pods; rotate if compromise suspected.
3. Replay infected uploads from quarantine bucket (never auto-retry silently).
4. Raise Sec incident if worm signatures repeat across tenants.

## Bypass policy

Emergency disable ONLY via `CLAMAV_ENABLED=False` OR `CLAMAV_STARTUP_VERSION_CHECK_ENABLED=False` documented in CHANGELOG.

## ClamAV outage policy — `SCAN_UNAVAILABLE_POLICY` (W1.18, decided 2026-10-08)

**Decision record.** When a file's scan never produced a verdict
(`SCAN_UNAVAILABLE` — clamd disabled or unreachable at scan time), the
dataset-source gate (`validate_file_allows_dataset_creation`) and the
download gate (`FileViewSet.download`) honour this policy:

- **`allow` (DEFAULT, decided 2026-10-08):** the file proceeds —
  availability over assurance. The outage stays observable: every
  SCAN_UNAVAILABLE verdict emits `FILE_MALWARE_SCAN_UNAVAILABLE` audit
  rows + `scan_completed{outcome="unavailable"}` metrics, which SRE
  alerts on (alert: `FileMalwareScanUnavailable`). Chosen as the default
  because a ClamAV outage must not take file upload/download offline
  platform-wide; the residual risk (an unscanned file served during the
  outage) is tracked by the audit trail for later re-scan/review.
- **`block` (fail-closed, opt-in):** SCAN_UNAVAILABLE is treated like
  PENDING_SCAN at both gates — 503 `FILE_SCAN_UNAVAILABLE` +
  `FILE_SCAN_UNAVAILABLE_BLOCKED` audit. For high-assurance tenants or
  regulated environments. Flip with `SCAN_UNAVAILABLE_POLICY=block`
  (invalid values fail boot with `ImproperlyConfigured`).

**Outage response (while ClamAV is down):**

1. Confirm the failure class from logs/metrics (clamd down vs
   `CLAMAV_ENABLED=False`).
2. Restart unhealthy clamd pods (triage order above).
3. Files sitting `PENDING_SCAN` resume on the next RQ sweep after clamd
   recovers; `SCAN_UNAVAILABLE` files are NOT auto-rescanned — re-drive
   them via `enqueue_file_malware_scan` if a re-scan is required, or
   leave the audit trail as the outage record.
4. If the outage outlasts the response window and the platform must keep
   serving uploads, the operator may run `SCAN_UNAVAILABLE_POLICY=allow`
   (default) — every such decision is recorded in the CHANGELOG per the
   bypass policy above.

## Maintenance

- **Owner**: Security Team
- **Last reviewed**: 2026-10-08 (W1.18 — SCAN_UNAVAILABLE_POLICY added)
- **Next review**: 2027-01-08
