# DSAR public surface — security review (Phase 232.2.19)

This runbook supports **OWASP ZAP** / **Burp Suite** style reviews of the anonymous DSAR ingress aligned with D232.14 privacy-counsel oversight.

## Scope

- `POST /api/v1/public/dsar-requests/` — create request (hCaptcha, throttling, optional idempotency).
- `POST /api/v1/public/dsar-requests/{uuid}/verify-otp/`
- `GET /api/v1/public/dsar-requests/status/{uuid}/` — status by reference token only (no subject PII in response body beyond what the subject already knows).

## Preconditions

1. Staging tenant has `compliance_dsar_enabled=True` and realistic mail delivery (or outbox inspection).
2. hCaptcha **siteverify** uses a real secret in the target environment; do **not** rely on `DSAR_SKIP_HCAPTCHA_VERIFICATION` outside local CI.
3. Note baseline rate limits for scope `dsar_public` (`DEFAULT_THROTTLE_RATES`).
4. Optional CI automation: `.github/workflows/phase232-public-zap-baseline.yml` (repository variable `PHASE232_ZAP_TARGET`).

## Passive scan (ZAP)

1. Point ZAP at the API base URL; exclude authenticated governance routes from the default context to avoid noise.
2. Import an OpenAPI snapshot if available; otherwise manually seed the three URLs above.
3. Run **Spider** then **Active Scan** on the public context only.
4. Expect **no authenticated session** cookies on public paths; confirm CORS and caching headers do not leak tokens.

## Manual abuse cases (Burp)

| Case | Expectation |
|------|-------------|
| Omit / forged `hcaptcha_response` | `400` captcha failure |
| Brute-force OTP | Throttle + lockout behaviour per implementation |
| Replay `Idempotency-Key` within `DSAR_PUBLIC_IDEMPOTENCY_WINDOW_HOURS` (default **24**) | Stable `200 duplicate` replay for identical payload |
| Same key **after** the configured window expires | **`201`** new DSAR permitted (distinct `id`) |
| Cross-tenant reference token | `404` (no existence oracle) |
| Oversized JSON body | `413` / validation error per DRF |

## Privacy counsel gate (232.2.20)

- Capture: sample request/response redactions, retention of audit codes (`DSAR_*`), and backup registry posture (`BackupAffectedBySubject`) for erasure.
- Sign-off recorded in the tenant’s RoPA / DPIA addendum; link this runbook and test evidence in the change record.

## Maintenance

- **Owner**: Compliance Team
- **Last reviewed**: 2026-05-13
- **Next review**: 2026-08-11
