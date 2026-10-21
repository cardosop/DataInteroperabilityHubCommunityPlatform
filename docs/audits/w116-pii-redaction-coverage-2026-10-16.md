# W11.6 — PII Data Map + Redaction Coverage

**Date:** 2026-10-16
**Scope:** `docs/PII_DATA_MAP.md` (regenerated 2026-10-16 via
`scripts/audit_pii_fields.py` — 12 apps, 25 PII fields) against the two
redaction utilities: `hub/apps/observability/logging.py` (structlog processor,
VALUE patterns) and `hub/apps/audit/utils.py::redact_pii` (KEY + VALUE patterns,
audit-event details).

## Per-type coverage

| PII type | Map fields | Log redaction (value) | Audit redaction | Verdict |
|---|---|---|---|---|
| email | 9 (LoginAttempt.email, LineageSubscription.email, DSARRequest.email_otp_*, ComplianceReport.email_*, …) | ✓ `[EMAIL_REDACTED]` | ✓ value pattern in `redact_string` | COVERED |
| phone | — (none in the current map; the field-name audit pattern covers `phone\|mobile\|cell\|fax` when they appear) | ✓ `[PHONE_REDACTED]` (10+ digits) | ✓ value pattern | COVERED |
| ssn | 1 (a `ssn`-keyed field) | ✓ `[SSN_REDACTED]` (nnn-nn-nnnn) | ✓ value pattern + `ssn`/`social_security_number` KEY redaction | COVERED |
| credit_card | — (none in the map; pattern ready) | ✓ `[CARD_REDACTED]` | ✓ value pattern | COVERED |
| ip_address | 3 (LoginAttempt.ip_address, SecurityAuditLog.ip_address, …) | ✗ no IP value pattern | ✓ `ip_address` field-name audit pattern (detection) — VALUE not redacted in audit either | **GAP — recorded** |
| name | 1 (a name-keyed field) | ✗ | ✗ (names cannot be regex-detected in values; key redaction would destroy audit forensics) | **GAP — recorded** |
| address | 11 (incl. country/street/city/postal) | ✗ | ✗ (same rationale as names) | **GAP — recorded** |

## The recorded gaps (deliberate, not omissions)

* **IP addresses in logs.** The structlog processor binds the request IP
  (`event_dict["ip"]`) unredacted. Regex-redacting 4-octet sequences would
  mangle version numbers, SQL plans and queue names in the same logs, and the
  IP itself is the abuse-throttle/forensic key. Mitigation: log-access control
  (the observability stack is the only reader) + the audit/log retention
  categories (Phase 234.5) — recorded as the accepted posture, revisit when
  log shipping leaves the tenant boundary.
* **Names / addresses.** Value-redaction cannot detect free-text names and
  addresses; key-based redaction would strip actor/resource names from the
  AUDIT table, destroying the accountability purpose of audit rows. The audit
  path protects the high-risk fields (secrets: `password`, `password_hash`,
  `api_key`, `token`, `secret`) by KEY, and structured PII (email/phone/SSN/
  card) by VALUE. Names/addresses are covered by audit access control +
  retention instead.

## Verification

* Map regeneration is part of `make quality-gates` (`audit_pii_fields.py
  --ci` exits 1 on NEW PII fields — the map is the ratchet baseline).
* The coverage table is pinned by
  `scripts/tests/test_w116_exc_str_leak_ban.py::test_pii_map_and_redaction_artifacts_exist`
  (the five covered types must be named in this doc).
* Redaction behavior itself is pinned by the existing audit-utils and
  logging suites (`hub/apps/audit/tests/`, observability logging tests).
