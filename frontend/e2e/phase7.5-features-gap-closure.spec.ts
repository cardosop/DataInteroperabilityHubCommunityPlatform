/**
 * @deprecated — this file has been split per Phase 226 E3.
 *
 * Each test in the original phase7.5 file was relocated verbatim into a
 * focused per-area file under `frontend/e2e/features/`:
 *
 *   integrations-developer-baas-gap.spec.ts        (A.2, A.3)
 *   auth-sessions-keys-invitations-gap.spec.ts     (B.3, B.4, B.5)
 *   search-gap.spec.ts                             (C)
 *   profile-tenant-settings-gap.spec.ts            (P, Q)
 *   dq-compliance-runs-gap.spec.ts                 (A.4)
 *   governance-access-requests-gap.spec.ts         (D)
 *   asset-health-observability-gap.spec.ts         (E, F, O.2)
 *   lineage-files-audit-gap.spec.ts                (G, H, I)
 *   scheduled-semantic-schema-webhooks-gap.spec.ts (J, K, L, M)
 *   home-admin-routes-gap.spec.ts                  (N.1, N.2, critical-routes)
 *
 * 226.E5 deletes this file once Track D's replacement specs (D1 SSO,
 * D3 billing) close. Until then the file remains on disk as a marker;
 * Playwright runs the file but finds no `test.*` callers, so it
 * registers zero tests and adds zero wall-clock time.
 */
export {};
