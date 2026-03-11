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
    // Transient under parallel E2E load: auth race, token refresh, backend overload
    (t.includes('failed to load resource') && (t.includes('401') || t.includes('500') || t.includes('400'))) ||
    // Role/permission checks (403) expected in: accept-invitation failure tests (invalid token returns
    // 403 Forbidden), capability-gated route tests, and unauthenticated redirect tests.
    (t.includes('failed to load resource') && t.includes('403')) ||
    (t.includes('[error report]') && t.includes('status code 403')) ||
    (t.includes('[error report]') && t.includes('request failed with status code 403')) ||
    // [Error Report] 500 when API under load or proxy socket hang up
    (t.includes('[error report]') && t.includes('status code 500')) ||
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
    // Failure-scenario tests: intentional invalid ODPS submission (missing required fields such as
    // product.dataSchema) produces backend 400 validation errors — expected in contract-creation-flow
    // "invalid ODPS (missing schema.fields) shows error" test and similar ODPS validation tests.
    (t.includes('[error report]') && t.includes('odps') && t.includes('required')) ||
    (t.includes('[error report]') && t.includes('product.dataschema')) ||
    (t.includes('[error report]') && t.includes('dataschema') && t.includes('field is required')) ||
    // Failure-scenario tests: intentional route abort (page.route → abort) produces ERR_FAILED and
    // a Network Error report — these are expected for the "network error" failure scenario test
    (t.includes('failed to load resource') && t.includes('err_failed')) ||
    (t.includes('[error report]') && t.includes('network error'))
  );
}
