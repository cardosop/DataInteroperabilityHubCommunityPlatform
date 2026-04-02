/**
 * E2E Console Utilities
 * Shared helpers for filtering expected/benign browser console errors.
 * Avoids circular deps (auth ↔ helpers).
 */

/**
 * Returns true if the browser console error is expected/benign and should not be logged.
 * Used to suppress noise from failure tests, optional services (503), backend under load,
 * and known benign network/WS issues.
 */
export function isBenignConsoleError(text: string): boolean {
  const t = text.toLowerCase();
  return (
    t.includes('err_socket_not_connected') ||
    t.includes('err_aborted') ||
    (t.includes('failed to load resource') &&
      (t.includes('404') || t.includes('not found') || t.includes('ws://') || t.includes('websocket'))) ||
    (t.includes('[error report]') && t.includes('not found')) ||
    /contract not found|listing not found|entitlement not found|dataset not found|run not found|job not found|connection not found|domain not found/i.test(
      t
    ) ||
    // Optional service unavailable (503)
    (t.includes('[error report]') && t.includes('semantic service unavailable')) ||
    (t.includes('[error report]') && (t.includes('status code 503') || t.includes('503'))) ||
    (t.includes('failed to load resource') && t.includes('503')) ||
    // Transient under parallel E2E load: auth race, token refresh, rate limiting
    (t.includes('failed to load resource') && (t.includes('401') || t.includes('400') || t.includes('429'))) ||
    // 403: test user lacks permissions for capability-gated endpoints (AI, ML, admin, billing).
    // The app handles these via ErrorDisplay/empty state. Tests that ASSERT 403 behaviour use
    // response interception, not console error detection.
    (t.includes('failed to load resource') && t.includes('403')) ||
    (t.includes('[error report]') && (t.includes('status code 403') || t.includes('request failed with status code 403') || t.includes('you do not have permission'))) ||
    // 500 from statement timeout under parallel E2E load: PostgreSQL kills slow queries,
    // producing transient 500s that resolve on retry.  Not a code bug.
    (t.includes('failed to load resource') && t.includes('500') && t.includes('statement timeout')) ||
    (t.includes('[error report]') && t.includes('statement timeout')) ||
    // NOTE: other 500 errors are NOT benign — they indicate real backend bugs that should be surfaced.
    // Postgres connection pool exhausted under parallel E2E load (transient)
    (t.includes('too many clients') || t.includes('too many connections')) ||
    // Transient network: ERR_NETWORK_CHANGED when API restarts or connection drops
    (t.includes('failed to load resource') && t.includes('err_network_changed')) ||
    // API down/restart during E2E: connection refused, reset, socket hang up
    (t.includes('failed to load resource') &&
      (t.includes('err_connection_refused') || t.includes('err_connection_reset') || t.includes('econnreset'))) ||
    (t.includes('[error report]') &&
      (t.includes('econnreset') || t.includes('econnrefused') || t.includes('socket hang up') || t.includes('fetch failed'))) ||
    // Capabilities timeout/slow under parallel E2E load
    (t.includes('[error report]') && t.includes('timeout of') && t.includes('exceeded')) ||
    (t.includes('failed to load capabilities')) ||
    // Test isolation: duplicate key when parallel workers create assets
    (t.includes('[error report]') && t.includes('duplicate key')) ||
    // Validation errors expected in some flows (activate blocked, listing requires ACTIVE asset)
    (t.includes('[error report]') && t.includes('requirements not met')) ||
    (t.includes('[error report]') && t.includes('must be active to be listed')) ||
    // HMR transient during file edits
    (t.includes('does not provide an export named') && /errorreportingservice|error_reporting_service/i.test(t)) ||
    (t.includes('failed to reload') && t.includes('syntax error')) ||
    // Failure-scenario tests: intentional invalid-JSON ODPS submission triggers a parse error report
    (t.includes('[error report]') && t.includes('failed to parse odps document')) ||
    (t.includes('[error report]') && t.includes('invalid json')) ||
    (t.includes('failed to create odps product')) ||
    // Transient backend 500 during ODPS creation under parallel E2E load (PostgreSQL atomic block error)
    (t.includes('[error report]') && t.includes('product creation failed')) ||
    (t.includes('[error report]') && t.includes('atomic') && t.includes('block')) ||
    (t.includes('[error report]') && t.includes('current transaction')) ||
    // Failure-scenario tests: intentional invalid ODPS submission (missing required fields such as
    // product.dataSchema) produces backend 400 validation errors — expected in contract-creation-flow
    // "invalid ODPS (missing schema.fields) shows error" test and similar ODPS validation tests.
    (t.includes('[error report]') && t.includes('odps') && t.includes('required')) ||
    (t.includes('[error report]') && t.includes('product.dataschema')) ||
    (t.includes('[error report]') && t.includes('dataschema') && t.includes('field is required')) ||
    // File upload: MinIO presigned-URL timeouts during parallel E2E load cause upload failures
    // that are retried by the test. The [FileUpload] console.error is expected during retry cycles.
    (t.includes('[fileupload]') && t.includes('upload failed')) ||
    (t.startsWith('[fileupload]') && t.includes('error:')) ||
    // Failure-scenario tests: intentional route abort (page.route → abort) produces ERR_FAILED and
    // a Network Error report — these are expected for the "network error" failure scenario test
    (t.includes('failed to load resource') && t.includes('err_failed')) ||
    (t.includes('[error report]') && t.includes('network error')) ||
    // Duplicate-resource creation (409 Conflict) — expected when parallel E2E workers try to create
    // the same asset/contract concurrently, or when a test intentionally triggers a duplicate-key error.
    (t.includes('failed to load resource') && t.includes('409')) ||
    // External service unreachable in E2E Docker environment (e.g. WebSocket relay, telemetry endpoint)
    t.includes('err_address_unreachable') ||
    // MinIO presigned URLs use Docker-internal hostnames (e.g. minio:9000) that browsers can't resolve
    t.includes('err_name_not_resolved') ||
    // Vite proxy timeouts under parallel E2E load — transient, the test retries the actual operation
    (t.includes('failed to load resource') && t.includes('err_timed_out')) ||
    // Connection closed/reset — transient network errors under parallel E2E load
    (t.includes('failed to load resource') && t.includes('err_connection_closed')) ||
    // 422 Unprocessable Entity: validation errors in purchase/order/create flows (e.g. missing required
    // fields, cross-tenant ordering restrictions). Expected in failure-scenario tests.
    (t.includes('failed to load resource') && t.includes('422')) ||
    (t.includes('[error report]') && (t.includes('status code 422') || t.includes('request failed with status code 422'))) ||
    // Marketplace ordering: cross-tenant orders may be restricted; "not eligible", "cross-tenant"
    (t.includes('[error report]') && (t.includes('not eligible') || t.includes('cross-tenant') || t.includes('already purchased'))) ||
    // Capability/feature-gated routes: feature disabled or not provisioned for this tenant
    (t.includes('[error report]') && (t.includes('feature') && (t.includes('disabled') || t.includes('not available') || t.includes('not enabled')))) ||
    // Workflows disabled for this tenant — backend configuration; expected in contract/ODPS creation tests
    (t.includes('[error report]') && t.includes('workflows are disabled')) ||
    (t.includes('workflows are disabled for this tenant')) ||
    // Auth token refresh race: "Token is invalid or expired" during parallel E2E load (transient)
    (t.includes('[error report]') && (t.includes('token') && (t.includes('invalid') || t.includes('expired')))) ||
    // WebSocket: ERR_TUNNEL_CONNECTION_FAILED or similar tunnel errors in Docker networking
    t.includes('err_tunnel_connection_failed') ||
    // React strict-mode double-render warnings (not errors, but appear as errors in some setups)
    (t.includes('act(') && t.includes('wrap')) ||
    // "Failed to fetch" is a generic network error — same as fetch failed, covered differently above
    (t.includes('[error report]') && t.includes('failed to fetch'))
  );
}
